"""Pilot launcher (trusted host process). Implements the pre-flight checks, the fixed retry
layers, the budget reservation / settlement around each unit, and the approved stop conditions.

Entry point: ``inspect_ai.eval()`` (not ``eval_set()``), with ``task_retry_attempts=0``,
``retry_on_error=0`` and ``fail_on_error=False``; provider SDK retries are turned off through
``model_args={"max_retries": 0}`` and Inspect's own request retries are bounded by
``max_retries`` from ``config.json``. Credentials are loaded from ``.env`` into this process only
and never printed; the sandbox compose file passes no environment through, so they do not reach
the model sandbox. ``INSPECT_DISABLE_MODEL_API`` is refused in real mode so that a mock run is
never mistaken for a formal one. ``runs_root`` must be a real path. The Docker image pre-flight
retries the transient "No such image" answer a bounded number of times.

No per-request budget interception happens inside the agent loop: the ledger bounds what may
start, token/working limits bound a running sample, and settlement uses the usage Inspect
recorded. ``--dry-run`` performs every check and the reservation logic without calling eval().
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from decimal import Decimal

from .budget import BudgetExhausted, BudgetLedger, LedgerConflict, model_events_usage, usage_from_eval_sample

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_ENV_BY_PROVIDER = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class LauncherError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- environment
def load_env_file(path: str, environ: dict | None = None) -> list[str]:
    """Load KEY=VALUE lines into the (trusted) process environment. Returns the names only.
    Values are never logged. Existing variables are not overwritten."""
    environ = os.environ if environ is None else environ
    names = []
    if not os.path.isfile(path):
        return names
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = ENV_LINE.match(line)
            if not m:
                continue
            k, v = m.group(1), m.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            if k not in environ:
                environ[k] = v
            names.append(k)
    return names


def missing_keys(providers: list[str], environ: dict | None = None) -> list[str]:
    """Names of required provider keys that are absent or empty (names only, never values)."""
    environ = os.environ if environ is None else environ
    return [KEY_ENV_BY_PROVIDER[p] for p in providers if not environ.get(KEY_ENV_BY_PROVIDER[p])]


def refuse_disabled_model_api(environ: dict | None = None) -> None:
    environ = os.environ if environ is None else environ
    if environ.get("INSPECT_DISABLE_MODEL_API") is not None:
        raise LauncherError("INSPECT_DISABLE_MODEL_API is set: this process is in mock mode and must not be used for a real run")


# ----------------------------------------------------------------------------- paths
def resolve_runs_root(path: str, create: bool = True) -> str:
    """Require an absolute path whose every component is real (no symlink anywhere, including
    macOS /tmp -> /private/tmp and /var -> /private/var). Returns the path unchanged."""
    if not os.path.isabs(path):
        raise LauncherError(f"runs_root must be absolute: {path!r}")
    norm = os.path.normpath(path)
    if norm != path.rstrip("/") or any(p in ("", ".", "..") for p in norm.split("/")[1:]):
        raise LauncherError(f"runs_root must be normalised: {path!r}")
    existing = norm
    while not os.path.exists(existing) and existing != "/":
        existing = os.path.dirname(existing)
    real = os.path.realpath(existing)
    if real != existing:
        raise LauncherError(f"runs_root is not a real path: {existing!r} resolves to {real!r}; use the real path (e.g. /private/tmp instead of /tmp)")
    if create:
        os.makedirs(norm, exist_ok=True)
    if os.path.realpath(norm) != norm:
        raise LauncherError(f"runs_root is not a real path after creation: {norm!r}")
    return norm


# ----------------------------------------------------------------------------- docker pre-flight
def preflight_image(image: str, attempts: int = 3, delay_s: float = 2.0, runner=subprocess.run, sleeper=time.sleep) -> dict:
    """`docker image inspect` with a bounded number of attempts (the daemon has answered
    'No such image' transiently while the image was present). Never unbounded."""
    if attempts < 1 or attempts > 10:
        raise LauncherError("attempts must be between 1 and 10")
    record = {"image": image, "attempts": []}
    for i in range(1, attempts + 1):
        try:
            res = runner(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, text=True, timeout=60)
            ok, out, err = res.returncode == 0, (res.stdout or "").strip(), (res.stderr or "").strip()[-300:]
        except Exception as ex:  # timeout or missing docker
            ok, out, err = False, "", f"{type(ex).__name__}: {str(ex)[:200]}"
        record["attempts"].append({"n": i, "ok": ok, "image_id": out if ok else None, "error": None if ok else err, "at": _now()})
        if ok:
            record["image_id"] = out
            return record
        if i < attempts:
            sleeper(delay_s)
    raise LauncherError(f"image {image!r} not confirmed after {attempts} attempts: {record['attempts'][-1]['error']}")


def preflight_sandbox(cfg: dict, compose_path: str | None = None, *, attempts: int = 3, delay_s: float = 2.0, runner=subprocess.run, sleeper=time.sleep) -> dict:
    """Pin check for the sandbox image: the compose file must name exactly the full image ID recorded
    in config.json (sandbox.image_id); the daemon must know that ID (bounded retry, by ID — never by
    tag); its platform must match config (sandbox.platform). The tag listed on the image is recorded
    for information only. Fails closed on any mismatch."""
    from .image import IMAGE_ID_RE, ImageRefError, compose_image, COMPOSE as DEFAULT_COMPOSE
    compose_path = compose_path or DEFAULT_COMPOSE
    want = cfg["sandbox"].get("image_id")
    if not isinstance(want, str) or not IMAGE_ID_RE.match(want):
        raise LauncherError("config.json sandbox.image_id must be a full local image ID (sha256:<64 hex>); refusing to start")
    alias = cfg["sandbox"].get("image")
    if alias != want:
        raise LauncherError(f"config.json sandbox.image {alias!r} differs from sandbox.image_id {want!r}; refusing to start")
    platform = cfg["sandbox"].get("platform")
    if not isinstance(platform, dict) or any(not isinstance(platform.get(k), str) or not platform.get(k).strip() for k in ("os", "architecture")):
        raise LauncherError("config.json sandbox.platform must carry non-empty 'os' and 'architecture' strings; refusing to start")
    try:
        have = compose_image(compose_path)  # parsed from the YAML structure (quoted values accepted)
    except ImageRefError as ex:
        raise LauncherError(str(ex)) from ex
    if have != want:
        raise LauncherError(f"compose image {have!r} differs from config.json sandbox.image_id {want!r}; refusing to start")
    record = {"image_id": want, "compose": compose_path, "attempts": []}
    for i in range(1, attempts + 1):
        try:
            res = runner(["docker", "image", "inspect", want, "--format", "{{.Id}}|{{.Architecture}}|{{.Os}}|{{.RepoTags}}"], capture_output=True, text=True, timeout=60)
            ok, out, err = res.returncode == 0, (res.stdout or "").strip(), (res.stderr or "").strip()[-300:]
        except Exception as ex:
            ok, out, err = False, "", f"{type(ex).__name__}: {str(ex)[:200]}"
        record["attempts"].append({"n": i, "ok": ok, "error": None if ok else err, "at": _now()})
        if ok:
            parts = out.split("|")
            record.update({"daemon_id": parts[0], "architecture": parts[1] if len(parts) > 1 else None, "os": parts[2] if len(parts) > 2 else None, "repo_tags": parts[3] if len(parts) > 3 else None})
            break
        if i < attempts:
            sleeper(delay_s)
    if "daemon_id" not in record:
        raise LauncherError(f"image {want!r} not present in the local Docker image store after {attempts} attempts: {record['attempts'][-1]['error']}")
    if record["daemon_id"] != want:
        raise LauncherError(f"daemon returned image id {record['daemon_id']!r} for {want!r}; refusing to start")
    for key in ("os", "architecture"):
        if record.get(key) != platform[key]:
            raise LauncherError(f"image {key} {record.get(key)!r} differs from config.json sandbox.platform {platform[key]!r}; refusing to start")
    return record


# ----------------------------------------------------------------------------- config and kwargs
def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if not str(cfg.get("_status", "")).startswith("DRAFT") and not str(cfg.get("_status", "")).startswith("FROZEN"):
        raise LauncherError("config.json has no recognised _status")
    return cfg


def config_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _int_or_none(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


from .redact import redact  # noqa: E402  (shared with grading and the model-list script)


def classify_eval_log(log) -> dict | None:
    """Engineering failure recorded in a *returned* Inspect log (fail_on_error=false returns rather
    than raises). Returns {"failure_class", "detail"} or None when the log shows no error."""
    err = getattr(log, "error", None)
    status = getattr(log, "status", None)
    samples = getattr(log, "samples", None) or []
    sample_errors = [getattr(s, "error", None) for s in samples if getattr(s, "error", None) is not None]
    if err is None and status != "error" and not sample_errors:
        return None
    msg = getattr(err, "message", None) or (getattr(sample_errors[0], "message", None) if sample_errors else None) or f"eval status {status}"
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.]*)(?:\(|:)", str(msg))
    cls = m.group(1) if m else ("eval_error" if err is not None else "sample_error")
    return {"failure_class": cls, "detail": redact(msg), "log_status": status, "eval_error": err is not None, "sample_errors": len(sample_errors)}


def model_cost_config(cfg: dict) -> dict:
    """Inspect ModelCost objects (USD per million tokens) for every candidate with complete prices,
    keyed by Inspect model name; used for eval(model_cost_config=...) and the cost safety net.
    Inspect 0.3.286 prices a call as input*input + output*output + cache_write*input_cache_write
    (x 1.6 when the Anthropic provider reports a 1h TTL; no multiplier for other providers) +
    cache_read*input_cache_read, with no long-context tier; therefore ``input_cache_write`` carries
    the default-TTL rate, and long-context calls are under-priced by the safety net (the ledger,
    which prices per call and per tier, is the primary control)."""
    from inspect_ai.model import ModelCost
    out = {}
    for name, p in prices_from_config(cfg).items():
        if all(isinstance(p.get(k), (int, float)) for k in ("input", "output", "cache_read", "cache_write_inspect")):
            out[name] = ModelCost(input=float(p["input"]), output=float(p["output"]), input_cache_write=float(p["cache_write_inspect"]), input_cache_read=float(p["cache_read"]))
    return out


def verify_cost_data(model: str, cfg: dict) -> dict:
    """Fail closed: when a numeric cost limit is configured, the model must have complete price
    data (from the config's candidate facts, registered with Inspect). Returns the ModelCost used."""
    from inspect_ai.model import get_model_info, set_model_cost, set_model_info, ModelInfo
    costs = model_cost_config(cfg)
    if model not in costs:
        raise LauncherError(f"cost limit configured but no complete price data for {model!r} in config.json; refusing to start")
    try:
        set_model_cost(model, costs[model])  # model known to Inspect's database
    except ValueError:
        set_model_info(model, ModelInfo(cost=costs[model]))  # model unknown to the database: register it with its cost
    info = get_model_info(model)
    if info is None or info.cost is None:
        raise LauncherError(f"cost data for {model!r} could not be registered with Inspect; refusing to start")
    return costs[model].model_dump()


def eval_kwargs(cfg: dict, *, log_dir: str, token_limit: int | None = None, model: str | None = None) -> dict:
    """The fixed execution and retry settings for inspect_ai.eval(); nothing here touches
    credentials. Four retry layers: Inspect request retries (max_retries), SDK retries
    (model_args max_retries=0), sample reruns (retry_on_error=0, fail_on_error=False), task
    retries (task_retry_attempts=0; eval_set is not used). A numeric ``cost_limit_usd`` in the
    config adds Inspect's per-sample cost limit (safety net behind the ledger) and requires price
    data for the model (fail closed)."""
    g, r, c = cfg["generation"], cfg["retries"], cfg["concurrency"]["pilot"]
    l1, l2 = r["layer_1_inspect_model_request"], r["layer_2_provider_sdk"]
    cost_limit = g.get("cost_limit_usd")
    cost_kw = {}
    if isinstance(cost_limit, (int, float)) and not isinstance(cost_limit, bool):
        if model is None:
            raise LauncherError("cost_limit_usd is set; the model name is required to verify its price data")
        verify_cost_data(model, cfg)
        cost_kw = {"cost_limit": float(cost_limit), "model_cost_config": model_cost_config(cfg)}
    max_tokens = _int_or_none(g.get("max_tokens_per_request"))
    if max_tokens is None or max_tokens <= 0:
        raise LauncherError("generation.max_tokens_per_request must be a positive integer (approved per-request output cap); refusing to start")
    attempt_timeout = _int_or_none(l1.get("attempt_timeout_s"))
    if attempt_timeout is None or attempt_timeout <= 0:
        raise LauncherError("retries.layer_1_inspect_model_request.attempt_timeout_s must be a positive integer; refusing to start")
    effective_token_limit = token_limit if token_limit is not None else _int_or_none(g.get("token_limit"))
    if effective_token_limit is None or effective_token_limit <= 0:
        raise LauncherError("generation.token_limit must be a positive integer (approved per-sample token cap); refusing to start")
    kw = {
        "log_dir": log_dir, "epochs": g["epochs"], "sandbox_prebuilt": True, "log_images": True,
        "time_limit": g["time_limit_s"], "working_limit": g["working_limit_s"], "message_limit": g["message_limit"],
        "token_limit": effective_token_limit, "max_tokens": max_tokens,
        "max_retries": l1["max_retries"], "timeout": l1["timeout_s"], "attempt_timeout": attempt_timeout,
        "model_args": {"max_retries": l2["max_retries"]},
        "retry_on_error": 0, "fail_on_error": False, "task_retry_attempts": 0,
        "max_samples": c["max_samples"], "max_tasks": c["max_tasks"], "max_sandboxes": c["max_sandboxes"], "max_connections": c["max_connections"],
        **cost_kw,
    }
    if g["attempts"] != 1 or g["epochs"] != 1:
        raise LauncherError("attempts and epochs must both be 1")
    return kw


def prices_from_config(cfg: dict) -> dict:
    """Ledger prices keyed by Inspect model name (provider/model) from the candidate facts,
    including the documented tiers: ``cache_write`` (default retention; the conservative rate the
    facts name as ``cache_write_conservative_per_mtok_usd`` when present), ``cache_write_extended``
    and ``long_context`` (threshold and rates)."""
    out = {}
    facts = cfg["models"].get("candidate_facts_queried_2026_10_30", {})
    for model, f in facts.items():
        provider = "anthropic" if model.startswith("claude") else "openai" if model.startswith("gpt") else "google"
        default_rate = f.get("cache_write_default_per_mtok_usd", f.get("cache_write_5m_per_mtok_usd"))
        ledger_rate = f.get("cache_write_ledger_per_mtok_usd", f.get("cache_write_conservative_per_mtok_usd", default_rate if default_rate is not None else f.get("input_per_mtok_usd")))
        price = {"input": f.get("input_per_mtok_usd"), "output": f.get("output_per_mtok_usd"),
                 "cache_read": f.get("cache_read_per_mtok_usd", f.get("cached_input_per_mtok_usd")),
                 "cache_write": ledger_rate,
                 # Inspect's ModelCost.input_cache_write must be the provider's default-TTL rate: Inspect applies the
                 # Anthropic 1h multiplier itself when its provider reports ttl "1h" (compute_model_cost); a pre-baked
                 # longer-TTL rate would be applied twice.
                 "cache_write_inspect": default_rate if default_rate is not None else f.get("input_per_mtok_usd")}
        price["cache_write_basis"] = f.get("cache_write_basis_short") or ("ledger rate from candidate facts" if f.get("cache_write_ledger_per_mtok_usd") is not None else
                                                                         "conservative longest-retention" if f.get("cache_write_conservative_per_mtok_usd") is not None else
                                                                         "default-retention" if default_rate is not None else "input-price stand-in")
        if f.get("cache_write_extended_per_mtok_usd") is not None:
            price["cache_write_extended"] = f["cache_write_extended_per_mtok_usd"]
        lc = f.get("long_context")
        if isinstance(lc, dict) and isinstance(lc.get("threshold_input_tokens"), int):
            price["long_context"] = {"threshold_input_tokens": lc["threshold_input_tokens"], "input": lc.get("input_per_mtok_usd"), "output": lc.get("output_per_mtok_usd"),
                                     "cache_read": lc.get("cache_read_per_mtok_usd"), "cache_write": lc.get("cache_write_per_mtok_usd")}
        if isinstance(price["input"], (int, float)) and isinstance(price["output"], (int, float)):
            out[f"{provider}/{model}"] = price
    return out


# ----------------------------------------------------------------------------- units
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _runs_root_from_config(cfg: dict) -> str:
    # The policy text lives in config; the actual root is a CLI argument so that it is never a repository path by accident.
    return cfg["collection"]["runs_root_policy"]


class PilotLauncher:
    """Orchestrates one unit at a time: check → reserve → run → settle → stop check."""

    def __init__(self, cfg: dict, *, runs_root: str, ledger: BudgetLedger, eval_fn, log_dir: str | None = None, record_dir: str | None = None):
        self.cfg = cfg
        self.runs_root = runs_root
        self.ledger = ledger
        self.eval_fn = eval_fn  # inspect_ai.eval in real mode; a fake in tests
        self.log_dir = log_dir or os.path.join(runs_root, "inspect_logs")
        self.record_dir = record_dir or os.path.join(runs_root, "launcher_records")
        os.makedirs(self.record_dir, exist_ok=True)

    @property
    def engineering_failures(self) -> dict:
        """Persisted failure counts (ledger events), not an in-memory counter."""
        return self.ledger.snapshot()["engineering_failures"]

    def _refuse_if_stopped(self, *, unit_id: str, model: str | None, estimate_usd, kind: str) -> None:
        """Approved stop conditions plus (B2-1) any open reservation of another unit: a reservation that was never
        settled, voided or manually resolved means a unit of unknown outcome and cost; no new paid unit starts until a
        human reconciles it (ledger_admin resolve / void). The unit's own idempotent re-reservation is not a reason."""
        reasons = self.ledger.stop_reasons(next_estimate_usd=estimate_usd)
        open_units = self.ledger.snapshot()["open_reservations"]
        if open_units:  # including this unit: an open reservation of the same unit means an earlier claim of unknown outcome
            reasons.append(f"open reservation(s) of unknown outcome must be reconciled before a new paid unit starts: {open_units}")
        if reasons:
            self.record("refused", {"unit_id": unit_id, "kind": kind, "model": model, "reasons": reasons, "ledger": self.ledger.snapshot()})
            raise BudgetExhausted("; ".join(reasons))

    def _after_unit(self, *, unit_id: str, settlement: dict, estimate_usd, log=None) -> dict:
        """Post-run bookkeeping (never touches the unit's run directory or outcome): record an
        engineering failure found in the returned log, record a stop when the unit cost more than
        twice its estimate, and return the persisted stop state for the next start."""
        post = {"engineering_failure": None, "stop_recorded": None}
        if log is not None:
            failure = classify_eval_log(log)
            if failure:
                self.ledger.record_engineering_failure(failure["failure_class"], unit_id, failure["detail"])
                post["engineering_failure"] = failure
        est = Decimal(str(estimate_usd))
        if est > 0 and Decimal(settlement["cost_usd"]) > 2 * est:
            reasons = [f"unit {unit_id} actual cost {settlement['cost_usd']} USD exceeds 2x its estimate {est} USD"]
            self.ledger.record_stop(reasons)
            post["stop_recorded"] = reasons
        post["stop_reasons_now"] = self.ledger.stop_reasons()
        return post

    def record(self, name: str, payload: dict) -> str:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = os.path.join(self.record_dir, f"{stamp}_{name}_{os.urandom(3).hex()}.json")
        with open(path, "x", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, default=str)
        return path

    def run_sample(self, *, task, model: str, unit_id: str, estimate_usd, token_limit: int | None = None, dry_run: bool = False) -> dict:
        """One sample unit = one Task, one returned EvalLog, one sample. Refuses to start when the
        budget cannot cover the estimate or a stop condition applies; settles from the eval log
        afterwards only when the single-log / single-sample contract holds; on failure settles
        conservatively at the reserved amount (estimated) so nothing is released without a record."""
        # Fail closed on the execution settings before the ledger is touched: a configuration
        # defect must not create a reservation or a conservative settlement.
        unit_log_dir = os.path.join(self.log_dir, unit_id.replace("/", "_").replace(":", "_"))  # this execution's own log directory: the binding usage recovery relies on
        kw = eval_kwargs(self.cfg, log_dir=unit_log_dir, token_limit=token_limit, model=model)
        # Single-task contract, before any call: the unit is one Task object. A list, tuple or set of
        # tasks (even of length 1) is refused here, before the stop check and the reservation.
        if task is None or isinstance(task, (list, tuple, set, frozenset, dict, str, bytes)):
            self.record("refused", {"unit_id": unit_id, "kind": "sample", "model": model, "reasons": [f"single-task contract: run_sample takes exactly one Task object, got {type(task).__name__}"
                                                                                                   + (f" of length {len(task)}" if hasattr(task, "__len__") else "")]})
            raise LauncherError(f"single-task contract: run_sample takes exactly one Task object, got {type(task).__name__}; refusing before any call")
        self._refuse_if_stopped(unit_id=unit_id, model=model, estimate_usd=estimate_usd, kind="sample")  # pre-check for a friendly record only
        try:
            # The atomic claim (inside the ledger lock): no other open reservation, this unit not already claimed, stop conditions.
            reservation = self.ledger.reserve(unit_id, "sample", estimate_usd, {"model": model, "task": getattr(task, "name", str(task))}, claim=True)
        except (BudgetExhausted, LedgerConflict) as ex:
            self.record("refused", {"unit_id": unit_id, "model": model, "reasons": [redact(ex)], "ledger": self.ledger.snapshot()})
            raise
        os.makedirs(unit_log_dir, exist_ok=True)
        meta = {"unit_id": unit_id, "model": model, "entry_point": "inspect_ai.eval", "eval_kwargs": kw, "reservation": reservation, "log_dir": unit_log_dir,
                "ledger": self.ledger.identity(), "config_status": self.cfg["_status"][:5], "started_at": _now()}
        if dry_run:
            meta["dry_run"] = True
            self.ledger.void(unit_id, "dry run: eval() not called")
            meta["ledger_after"] = self.ledger.snapshot()
            self.record("dry_run", meta)
            return meta
        try:
            returned = self.eval_fn(task, model=model, **kw)
            logs = list(returned) if isinstance(returned, (list, tuple)) else [returned]
            per_log = [{"index": i, "status": getattr(l, "status", None), "log_file": getattr(l, "location", None), "task": getattr(getattr(l, "eval", None), "task", None),
                        "samples": [str(getattr(s, "uuid", j)) for j, s in enumerate(list(getattr(l, "samples", None) or []))]} for i, l in enumerate(logs)]
            samples = [s for l in logs for s in list(getattr(l, "samples", None) or [])]
            if len(logs) != 1 or len(samples) != 1:
                # Single-EvalLog / single-sample contract: a unit is exactly one returned log holding exactly one
                # sample. Anything else is never settled from logs[0] / samples[0]; the reservation stays open
                # (budget not released), every log and every sample's usage is recorded, the unit is marked for
                # manual review, an engineering stop is recorded and further paid starts are refused (also
                # after a restart, because the stop is a ledger event).
                all_usage = {str(getattr(s, "uuid", i)): usage_from_eval_sample(s)[0] for i, s in enumerate(samples)}
                reasons = [f"unit {unit_id}: eval returned {len(logs)} EvalLog(s) with {len(samples)} sample(s) in total, expected exactly 1 and 1; "
                           "no settlement, reservation kept open, manual review required"]
                self.ledger.record_stop(reasons)
                meta.update({"inspect_status": [p["status"] for p in per_log], "log_file": [p["log_file"] for p in per_log], "returned_logs": per_log, "log_count": len(logs),
                             "sample_count": len(samples), "all_sample_usage": all_usage, "settlement": None, "manual_review_required": True, "stop_recorded": reasons,
                             "ledger_after": self.ledger.snapshot(), "finished_at": _now()})
                self.record("sample_cardinality", meta)
                return meta
            log = logs[0]
            sample = samples[0]
            usage, retries = usage_from_eval_sample(sample) if sample else ({}, {})
            events = model_events_usage(sample) if sample else {"calls": {}, "unknown_calls": 0, "total_calls": 0}
            incomplete = (not usage) or events["unknown_calls"] > 0  # any model call whose usage is unknown makes the unit's cost incomplete
            scope = {"same_sample": True, "sample_uuid": getattr(sample, "uuid", None), "samples_in_log": 1, "model_calls": events["total_calls"], "calls_without_usage": events["unknown_calls"],
                     "aggregate_source": "EvalSample.model_usage", "calls_source": "EvalSample.events[model].output.usage"}
            note = f"inspect status {log.status}" + (f"; {events['unknown_calls']} of {events['total_calls']} model call(s) reported no usage (cost unknown)" if events["unknown_calls"] else "")
            settlement = self.ledger.settle(unit_id, usage, retries_by_model=retries, calls_by_model=events["calls"], scope=scope, note=note,
                                            fallback_to_reservation=not usage, incomplete=incomplete)  # approved 2026-10-31: missing/incomplete usage -> conservative estimate + persistent hold
            post = self._after_unit(unit_id=unit_id, settlement=settlement, estimate_usd=estimate_usd, log=log)
            binding = self.write_ledger_binding(sample, unit_id=unit_id, model=model, task=task)
            meta.update({"inspect_status": log.status, "log_file": getattr(log, "location", None), "usage": usage, "retries": retries,
                         "settlement": settlement, "post_run": post, "ledger_binding": binding, "ledger_after": self.ledger.snapshot(), "finished_at": _now()})
            self.record("sample", meta)
            return meta
        except Exception as ex:
            cls = type(ex).__name__
            self.ledger.record_engineering_failure(cls, unit_id, redact(ex))
            # Correction A: recover whatever usage Inspect persisted before the exception (an .eval written under the unit's
            # log_dir for this task since the start) and keep it; everything else is unknown. One conservative settlement:
            # max(priced recovered part, reservation), estimated, persistent hold. The recovery limit is recorded, not hidden.
            recovery = self.recover_usage_from_logs(unit_log_dir, unit_id=unit_id, task_name=getattr(task, "name", None), model=model)
            settlement = self.ledger.settle(unit_id, recovery["usage"], note=f"eval failed: {cls}; usage recovery: {recovery['summary']}", estimated=True,
                                            fallback_to_reservation=not recovery["usage"], incomplete=True)
            post = self._after_unit(unit_id=unit_id, settlement=settlement, estimate_usd=estimate_usd)
            meta.update({"error": f"{cls}: {redact(ex)}", "settlement": settlement, "usage_recovery": recovery, "post_run": post, "ledger_after": self.ledger.snapshot(), "finished_at": _now()})
            self.record("sample_error", meta)
            raise

    def recover_usage_from_logs(self, unit_log_dir: str, *, unit_id: str, task_name: str | None, model: str | None, read_log=None) -> dict:
        """Execution-bound recovery of usage after an eval exception. Invariant: only usage that verifiably belongs to THIS
        execution contributes, and every billable event counts once. Binding: ``unit_log_dir`` is the directory this
        launcher created for this unit alone and handed to eval(log_dir=...); nothing outside it is read, and no mtime or
        name heuristics are used. Cross-checks inside: the log's eval.task and eval.model must equal the unit's; a log
        that fails them is excluded and marked ``attribution_uncertain`` (never counted). Dedup: a billable event is one
        (eval_id, sample uuid, epoch); a second representation of the same event (e.g. .eval and .json copies) is
        skipped. The aggregate EvalSample.model_usage is used, per-call events are not added on top. The limit stays
        recorded: Inspect writes the log at the end of eval, so an exception raised earlier leaves nothing to recover."""
        out = {"unit_id": unit_id, "log_dir": unit_log_dir, "usage": {}, "logs": [], "recovered": False, "counted_events": 0, "duplicate_events_skipped": 0,
               "attribution_uncertain": False, "summary": ""}
        try:
            if read_log is None:
                from inspect_ai.log import read_eval_log as read_log
            names = sorted(f for f in os.listdir(unit_log_dir) if f.endswith((".eval", ".json"))) if os.path.isdir(unit_log_dir) else []
            seen_events = set()
            for name in names:
                path = os.path.join(unit_log_dir, name)
                try:
                    log = read_log(path)
                except Exception as ex:  # unreadable or partial log: recorded, never counted
                    out["logs"].append({"log": name, "readable": False, "error": type(ex).__name__, "excluded": True, "reason": "unreadable"})
                    out["attribution_uncertain"] = True
                    continue
                ev = getattr(log, "eval", None)
                log_task, log_model, eval_id = getattr(ev, "task", None), getattr(ev, "model", None), getattr(ev, "eval_id", None)
                mismatch = [k for k, want, got in (("task", task_name, log_task), ("model", model, log_model)) if want is not None and got != want]
                if mismatch or not eval_id:
                    out["logs"].append({"log": name, "readable": True, "excluded": True, "reason": f"identity mismatch on {mismatch}" if mismatch else "no eval_id", "eval_id": eval_id, "task": log_task, "model": log_model})
                    out["attribution_uncertain"] = True
                    continue
                found, counted, dup = {}, 0, 0
                for s_ in list(getattr(log, "samples", None) or []):
                    key = (eval_id, str(getattr(s_, "uuid", None)), getattr(s_, "epoch", None))
                    if key in seen_events:
                        dup += 1
                        continue
                    seen_events.add(key)
                    counted += 1
                    u, _ = usage_from_eval_sample(s_)
                    for m, v in u.items():
                        acc = found.setdefault(m, {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0})
                        for k in acc:
                            acc[k] += int(v.get(k, 0) or 0)
                out["logs"].append({"log": name, "readable": True, "excluded": False, "eval_id": eval_id, "status": getattr(log, "status", None), "events_counted": counted, "duplicates_skipped": dup, "usage": found})
                out["counted_events"] += counted
                out["duplicate_events_skipped"] += dup
                for m, v in found.items():
                    acc = out["usage"].setdefault(m, {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0})
                    for k in acc:
                        acc[k] += v[k]
            out["recovered"] = bool(out["usage"])
            out["summary"] = ((f"recovered aggregate usage of {out['counted_events']} event(s) from this execution's log directory ({out['duplicate_events_skipped']} duplicate representation(s) skipped): {json.dumps(out['usage'], sort_keys=True)}"
                               if out["recovered"] else "no attributable Inspect log with usage in this execution's log directory (Inspect writes the .eval at the end of eval); nothing recovered, settled at the reservation")
                              + ("; some log(s) could not be attributed to this execution and were excluded (attribution uncertain)" if out["attribution_uncertain"] else ""))
        except Exception as ex:
            out["attribution_uncertain"] = True
            out["summary"] = f"usage recovery itself failed ({type(ex).__name__}); nothing recovered, settled at the reservation"
        return out

    def write_ledger_binding(self, sample, *, unit_id: str, model: str, task) -> dict:
        """Persist the run <-> ledger binding next to the collected run (runs_root/<uuid>/ledger_binding.json): run uuid,
        generation unit id, ledger real path and ledger id, task and model. Written once (never overwritten); a later
        grading or judge pass must present this ledger, so a second cost history for the same run cannot be created by
        pointing at another ledger. The run uuid is only known after the sample ran, so the pre-call record carries
        the ledger identity and the unit id, and this file links the uuid to them."""
        uuid = getattr(sample, "uuid", None)
        if not uuid:
            return {"written": False, "reason": "sample has no uuid"}
        host_dir = os.path.join(self.runs_root, str(uuid))
        os.makedirs(host_dir, exist_ok=True)
        path = os.path.join(host_dir, "ledger_binding.json")
        binding = {"record_version": 1, "run_uuid": str(uuid), "generation_unit_id": unit_id, **self.ledger.identity(), "task": getattr(task, "name", str(task)),
                   "model": model, "sample_id": getattr(sample, "id", None), "written_at": _now()}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
            same = all(existing.get(k) == binding[k] for k in ("run_uuid", "generation_unit_id", "ledger_path", "ledger_id"))
            return {"written": False, "path": path, "conflict": not same, "existing": existing}
        tmp = f"{path}.{os.urandom(4).hex()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(binding, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return {"written": True, "path": path, **binding}

    def run_judge_batch(self, *, unit_id: str, estimate_usd, batch_fn, dry_run: bool = False, recover_usage=None) -> dict:
        """One independent judge batch (the judge calls of one grading pass): atomic claim → run → settle. ``batch_fn``
        returns ({model: usage}, {model: retries}) or a dict from ProviderJudge.batch_result() carrying
        ``usage_incomplete``. ``recover_usage`` (correction B) is called when batch_fn raises: it must return the
        usage recoverable from DURABLE evidence (the write-ahead judge call log: finished events with usage; started
        events without a terminal event stay UNKNOWN) as {"usage", "unknown_calls", "source", ...}; the unit is then
        settled once at max(priced known part, reservation), estimated, held, and the 2x stop rule applies."""
        self._refuse_if_stopped(unit_id=unit_id, model=None, estimate_usd=estimate_usd, kind="judge")  # pre-check for a friendly record only
        reservation = self.ledger.reserve(unit_id, "judge", estimate_usd, {"kind": "judge"}, claim=True)
        if dry_run:
            self.ledger.void(unit_id, "dry run: judge batch not called")
            return {"unit_id": unit_id, "dry_run": True, "reservation": reservation}
        try:
            result = batch_fn()
        except Exception as ex:
            cls = type(ex).__name__
            self.ledger.record_engineering_failure(cls, unit_id, redact(ex))
            recovered = {}
            try:
                recovered = recover_usage() if recover_usage is not None else {}
            except Exception as rex:  # recovery must never hide the original failure or create a second settlement
                recovered = {"usage": {}, "error": f"recovery failed: {type(rex).__name__}"}
            known = recovered.get("usage") or {}
            note = (f"judge batch failed: {cls}; known usage recovered from {recovered.get('source', 'nothing')}: {json.dumps(known, sort_keys=True)}; "
                    f"{recovered.get('unknown_calls', 'n/a')} call(s) without a reliable terminal state stay UNKNOWN" + (f"; {recovered['error']}" if recovered.get("error") else ""))
            settlement = self.ledger.settle(unit_id, known, note=note, estimated=True, fallback_to_reservation=not known, incomplete=True)
            self._after_unit(unit_id=unit_id, settlement=settlement, estimate_usd=estimate_usd)
            raise
        if isinstance(result, dict):  # ProviderJudge.batch_result(): usage, retries, usage_incomplete, note
            usage, retries, incomplete, note = result.get("usage") or {}, result.get("retries") or {}, bool(result.get("usage_incomplete")), str(result.get("note") or "")
        else:
            usage, retries = result
            incomplete, note = False, ""
        # Approved policy (2026-10-31): incomplete usage -> the ledger settles at max(priced known part, reservation), estimated,
        # with a persistent hold (one rule, in BudgetLedger.settle); the known usage stays in the settlement and the call log.
        settlement = self.ledger.settle(unit_id, usage, retries_by_model=retries, note=f"judge batch {note}".strip() + ("; usage incomplete" if incomplete else ""),
                                        fallback_to_reservation=not usage, incomplete=incomplete)
        post = self._after_unit(unit_id=unit_id, settlement=settlement, estimate_usd=estimate_usd)
        return {"unit_id": unit_id, "settlement": settlement, "post_run": post, "ledger_after": self.ledger.snapshot(), "usage_incomplete": incomplete, "batch_note": note}

    def open_reservations_after_restart(self) -> list[str]:
        """Units reserved by an earlier process that never settled. They stay reserved (budget is
        not released) until a human settles them from the eval log or voids them explicitly."""
        return self.ledger.snapshot()["open_reservations"]


# ----------------------------------------------------------------------------- CLI
def git_provenance(root: str = ROOT) -> dict:
    """Commit and working-tree state of the code that runs (read-only git calls; never fails the run)."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10)
        porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=10)
        changed = [l for l in porcelain.stdout.splitlines() if l.strip()]
        return {"commit": head.stdout.strip() or None, "dirty": bool(changed), "changed_paths": len(changed)}
    except Exception as ex:  # git absent or not a repository: recorded, not fatal
        return {"commit": None, "dirty": None, "changed_paths": None, "error": type(ex).__name__}


def verify_system_prompt(cfg: dict, root: str = ROOT) -> dict:
    """The system prompt file actually used by make_task must hash to the value recorded in the
    config (the file bytes, or the stripped text that make_task sends; the matching form is recorded).
    A mismatch refuses the run: the prompt is frozen and identical for both models."""
    g = cfg["generation"]
    path = os.path.join(root, g["system_prompt_file"])
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8").strip()
    forms = {"file_bytes": hashlib.sha256(raw).hexdigest(), "stripped_text": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    expected = g["system_prompt_sha256"]
    matched = next((k for k, v in forms.items() if v == expected), None)
    if matched is None:
        raise LauncherError(f"system prompt file {g['system_prompt_file']} does not match generation.system_prompt_sha256 in the config (file {forms['file_bytes'][:12]}..., stripped {forms['stripped_text'][:12]}..., config {expected[:12]}...); refusing to start")
    return {"file": g["system_prompt_file"], "sha256": expected, "matched_form": matched, "text": text}


def build_unit(cfg: dict, *, task_id: str, model: str, runs_root: str, config_path: str) -> dict:
    """Samples, Task and unit id shared by --dry-run and --real-run: staged-file allowlist and hashes
    verified against the config (I1), the system prompt verified against its recorded hash, the
    tool timeout taken from the config. Nothing here calls a model."""
    from .samples import build_samples
    from .task import make_task
    prompt = verify_system_prompt(cfg)
    samples = build_samples([task_id], verify_config=config_path)  # fail closed on any staged-file mismatch
    if not samples:
        raise LauncherError(f"task {task_id} is not in data/selected_tasks.json")
    if len(samples) != 1:
        raise LauncherError(f"task {task_id} built {len(samples)} samples; a pilot unit is exactly one sample")
    task, _ = make_task(samples, runs_root, name=f"pilot_{task_id[:8]}", tool_timeout=cfg["generation"]["tool_timeout_s"], system_prompt=prompt["text"])
    unit_id = f"{task_id}:{model}:{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    return {"task": task, "unit_id": unit_id, "sample_ids": [s.id for s in samples], "staging_verified": samples[0].metadata.get("staging_verified"),
            "prompt": {k: prompt[k] for k in ("file", "sha256", "matched_form")}, "tool_timeout_s": cfg["generation"]["tool_timeout_s"]}


def confirm_scope(confirm: str | None, *, task_id: str, model: str, estimate_usd) -> None:
    """--real-run needs an explicit restatement of the paid scope: '<task_id>|<model>|<estimate_usd>'."""
    parts = (confirm or "").split("|")
    if len(parts) != 3:
        raise LauncherError("--real-run requires --confirm '<task_id>|<model>|<estimate_usd>' restating the paid scope")
    try:
        same_estimate = Decimal(parts[2].strip()) == Decimal(str(estimate_usd))
    except Exception:
        same_estimate = False
    if parts[0].strip() != task_id or parts[1].strip() != model or not same_estimate:
        raise LauncherError("--confirm does not restate the requested task, model and estimate; refusing to start")


def main(argv=None, *, eval_fn=None, environ: dict | None = None, docker_runner=subprocess.run) -> int:
    """Trusted host entry point. ``--dry-run`` runs every check and the reservation logic without
    calling eval(). ``--real-run`` is the only path that calls a provider: it needs the explicit scope
    restatement (--confirm), operator audit metadata (--authorized-by, --authorization-ref; recorded,
    not verified by the launcher), an environment that is not in mock mode, the provider credential
    name present, the image pre-flight and the prompt hash check. ``eval_fn``, ``environ`` and
    ``docker_runner`` are injection points for tests; the defaults are inspect_ai.eval, os.environ
    and subprocess.run. Importing this module or running tests never contacts a provider."""
    p = argparse.ArgumentParser(description="GDPval pilot launcher (trusted host process)")
    p.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    p.add_argument("--runs-root", required=True, help="absolute real path for collected outputs and records")
    p.add_argument("--ledger", required=True, help="path of the persistent budget ledger (JSON)")
    p.add_argument("--task-id", required=True)
    p.add_argument("--model", required=True, help="Inspect model name, e.g. anthropic/claude-opus-5-5")
    p.add_argument("--estimate-usd", required=True, type=Decimal, help="pre-run cost estimate for this unit (no estimate, no start)")
    p.add_argument("--token-limit", type=int, default=None)
    p.add_argument("--env-file", default=os.path.join(ROOT, ".env"))
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="run every check and the reservation logic; do not call eval()")
    mode.add_argument("--real-run", action="store_true", help="call the provider for exactly one sample (paid); requires --confirm, --authorized-by, --authorization-ref")
    p.add_argument("--confirm", default=None, help="restate the paid scope as '<task_id>|<model>|<estimate_usd>' (required with --real-run)")
    p.add_argument("--authorized-by", default=None, help="who approved this paid run (audit metadata, recorded verbatim)")
    p.add_argument("--authorization-ref", default=None, help="where the approval is recorded, e.g. a docs/status.md decision entry (audit metadata)")
    args = p.parse_args(argv)
    env = os.environ if environ is None else environ

    cfg = load_config(args.config)
    provider = args.model.split("/", 1)[0]
    if args.real_run:
        refuse_disabled_model_api(env)
        confirm_scope(args.confirm, task_id=args.task_id, model=args.model, estimate_usd=args.estimate_usd)
        if not (args.authorized_by and args.authorization_ref):
            raise LauncherError("--real-run requires --authorized-by and --authorization-ref (audit metadata for the run record)")
        if provider not in KEY_ENV_BY_PROVIDER and provider != "mockllm":
            raise LauncherError(f"unknown provider {provider!r}: no credential requirement is defined for it; refusing to start")
    runs_root = resolve_runs_root(args.runs_root)
    loaded = load_env_file(args.env_file, env)
    missing = missing_keys([provider], env) if provider in KEY_ENV_BY_PROVIDER else []
    if missing and args.real_run:
        raise LauncherError(f"missing credential variable(s): {missing} (names only; nothing printed)")
    image = preflight_sandbox(cfg, runner=docker_runner)  # by full image ID; compose and config must agree
    ledger = BudgetLedger(args.ledger, cfg["pilot"]["budget_ceiling_usd"], prices_from_config(cfg))
    unit = build_unit(cfg, task_id=args.task_id, model=args.model, runs_root=runs_root, config_path=args.config)
    provenance = {"code": git_provenance(), "config_path": args.config, "config_sha256": config_sha256(args.config), "config_status": cfg["_status"][:5], "ledger": ledger.identity(),
                  "prompt": unit["prompt"], "image_id": image.get("daemon_id"), "image_platform": (image.get("os"), image.get("architecture")),
                  "image_tags_informational": image.get("repo_tags"), "runs_root": runs_root, "task_id": args.task_id, "model": args.model,
                  "sample_ids": unit["sample_ids"], "staging_verified": unit["staging_verified"], "tool_timeout_s": unit["tool_timeout_s"],
                  "env_names_loaded": loaded, "missing_key_names": missing, "credential_required": provider in KEY_ENV_BY_PROVIDER}
    print(json.dumps({**provenance, "image_attempts": len(image["attempts"]), "ledger": ledger.snapshot(), "mode": "real-run" if args.real_run else "dry-run"}, indent=1, default=str))
    if args.dry_run:
        launcher = PilotLauncher(cfg, runs_root=runs_root, ledger=ledger, eval_fn=None)
        launcher.run_sample(task=unit["task"], model=args.model, unit_id=unit["unit_id"], estimate_usd=args.estimate_usd, token_limit=args.token_limit, dry_run=True)
        return 0
    # --real-run: the only paid path; inspect_ai.eval is imported here and nowhere else in this module
    if eval_fn is None:
        from inspect_ai import eval as inspect_eval
        eval_fn = inspect_eval
    launcher = PilotLauncher(cfg, runs_root=runs_root, ledger=ledger, eval_fn=eval_fn)
    authorization = {"by": args.authorized_by, "ref": args.authorization_ref, "confirm": args.confirm, "estimate_usd": str(args.estimate_usd),
                     "note": "operator-supplied audit metadata recorded verbatim; the launcher does not verify an approval"}
    launcher.record("real_run_provenance", {**provenance, "unit_id": unit["unit_id"], "authorization": authorization, "started_at": _now()})
    meta = launcher.run_sample(task=unit["task"], model=args.model, unit_id=unit["unit_id"], estimate_usd=args.estimate_usd, token_limit=args.token_limit)
    settlement = meta.get("settlement") or {}
    print(json.dumps({"unit_id": unit["unit_id"], "inspect_status": meta.get("inspect_status"), "log_file": meta.get("log_file"),
                      "settlement": {k: settlement.get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags")} if settlement else None,
                      "manual_review_required": bool(meta.get("manual_review_required") or settlement.get("manual_review_required")),
                      "stop_recorded": meta.get("stop_recorded") or (meta.get("post_run") or {}).get("stop_recorded"), "record_dir": launcher.record_dir}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
