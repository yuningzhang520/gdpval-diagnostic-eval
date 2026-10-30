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

from .budget import BudgetExhausted, BudgetLedger, usage_from_eval_sample

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
    return v if isinstance(v, int) else None


def eval_kwargs(cfg: dict, *, log_dir: str, token_limit: int | None = None) -> dict:
    """The fixed execution and retry settings for inspect_ai.eval(); nothing here touches
    credentials. Four retry layers: Inspect request retries (max_retries), SDK retries
    (model_args max_retries=0), sample reruns (retry_on_error=0, fail_on_error=False), task
    retries (task_retry_attempts=0; eval_set is not used)."""
    g, r, c = cfg["generation"], cfg["retries"], cfg["concurrency"]["pilot"]
    l1, l2 = r["layer_1_inspect_model_request"], r["layer_2_provider_sdk"]
    kw = {
        "log_dir": log_dir, "epochs": g["epochs"], "sandbox_prebuilt": True, "log_images": True,
        "time_limit": g["time_limit_s"], "working_limit": g["working_limit_s"], "message_limit": g["message_limit"],
        "token_limit": token_limit if token_limit is not None else _int_or_none(g.get("token_limit")),
        "max_retries": l1["max_retries"], "timeout": l1["timeout_s"],
        "model_args": {"max_retries": l2["max_retries"]},
        "retry_on_error": 0, "fail_on_error": False, "task_retry_attempts": 0,
        "max_samples": c["max_samples"], "max_tasks": c["max_tasks"], "max_sandboxes": c["max_sandboxes"], "max_connections": c["max_connections"],
    }
    if g["attempts"] != 1 or g["epochs"] != 1:
        raise LauncherError("attempts and epochs must both be 1")
    return kw


def prices_from_config(cfg: dict) -> dict:
    """Ledger prices keyed by Inspect model name (provider/model) from the candidate facts."""
    out = {}
    facts = cfg["models"].get("candidate_facts_queried_2026_10_30", {})
    for model, f in facts.items():
        provider = "anthropic" if model.startswith("claude") else "openai" if model.startswith("gpt") else "google"
        price = {"input": f.get("input_per_mtok_usd"), "output": f.get("output_per_mtok_usd"),
                 "cache_read": f.get("cache_read_per_mtok_usd", f.get("cached_input_per_mtok_usd")),
                 "cache_write": f.get("cache_write_5m_per_mtok_usd", f.get("input_per_mtok_usd"))}
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
        self.engineering_failures: dict[str, int] = {}

    def record(self, name: str, payload: dict) -> str:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = os.path.join(self.record_dir, f"{stamp}_{name}_{os.urandom(3).hex()}.json")
        with open(path, "x", encoding="utf-8") as f:
            json.dump(payload, f, indent=1, default=str)
        return path

    def run_sample(self, *, task, model: str, unit_id: str, estimate_usd, token_limit: int | None = None, dry_run: bool = False) -> dict:
        """One sample unit. Refuses to start when the budget cannot cover the estimate or a stop
        condition applies; settles from the eval log afterwards; on failure settles conservatively
        at the reserved amount (estimated) so nothing is released without a record."""
        reasons = self.ledger.stop_reasons(next_estimate_usd=estimate_usd, engineering_failures=self.engineering_failures)
        if reasons:
            self.record("refused", {"unit_id": unit_id, "model": model, "reasons": reasons, "ledger": self.ledger.snapshot()})
            raise BudgetExhausted("; ".join(reasons))
        try:
            reservation = self.ledger.reserve(unit_id, "sample", estimate_usd, {"model": model, "task": getattr(task, "name", str(task))})
        except BudgetExhausted as ex:
            self.record("refused", {"unit_id": unit_id, "model": model, "reasons": [str(ex)], "ledger": self.ledger.snapshot()})
            raise
        kw = eval_kwargs(self.cfg, log_dir=self.log_dir, token_limit=token_limit)
        meta = {"unit_id": unit_id, "model": model, "entry_point": "inspect_ai.eval", "eval_kwargs": kw, "reservation": reservation,
                "config_status": self.cfg["_status"][:5], "started_at": _now()}
        if dry_run:
            meta["dry_run"] = True
            self.ledger.void(unit_id, "dry run: eval() not called")
            meta["ledger_after"] = self.ledger.snapshot()
            self.record("dry_run", meta)
            return meta
        try:
            logs = self.eval_fn(task, model=model, **kw)
            log = logs[0]
            sample = log.samples[0] if log.samples else None
            usage, retries = usage_from_eval_sample(sample) if sample else ({}, {})
            settlement = self.ledger.settle(unit_id, usage, retries_by_model=retries, note=f"inspect status {log.status}",
                                            fallback_to_reservation=not usage)
            meta.update({"inspect_status": log.status, "log_file": getattr(log, "location", None), "usage": usage, "retries": retries,
                         "settlement": settlement, "ledger_after": self.ledger.snapshot(), "finished_at": _now()})
            self.record("sample", meta)
            return meta
        except Exception as ex:
            cls = type(ex).__name__
            self.engineering_failures[cls] = self.engineering_failures.get(cls, 0) + 1
            settlement = self.ledger.settle(unit_id, {}, note=f"eval failed: {cls}", estimated=True, fallback_to_reservation=True)
            meta.update({"error": f"{cls}: {str(ex)[:300]}", "settlement": settlement, "ledger_after": self.ledger.snapshot(), "finished_at": _now()})
            self.record("sample_error", meta)
            raise

    def run_judge_batch(self, *, unit_id: str, estimate_usd, batch_fn, dry_run: bool = False) -> dict:
        """One independent judge batch: same reserve → run → settle contract. ``batch_fn`` returns
        ({model: usage}, {model: retries}); the judge implementation itself is Stage 3b work."""
        reasons = self.ledger.stop_reasons(next_estimate_usd=estimate_usd, engineering_failures=self.engineering_failures)
        if reasons:
            self.record("refused", {"unit_id": unit_id, "kind": "judge", "reasons": reasons, "ledger": self.ledger.snapshot()})
            raise BudgetExhausted("; ".join(reasons))
        reservation = self.ledger.reserve(unit_id, "judge", estimate_usd, {"kind": "judge"})
        if dry_run:
            self.ledger.void(unit_id, "dry run: judge batch not called")
            return {"unit_id": unit_id, "dry_run": True, "reservation": reservation}
        try:
            usage, retries = batch_fn()
            settlement = self.ledger.settle(unit_id, usage, retries_by_model=retries, note="judge batch", fallback_to_reservation=not usage)
            return {"unit_id": unit_id, "settlement": settlement, "ledger_after": self.ledger.snapshot()}
        except Exception as ex:
            cls = type(ex).__name__
            self.engineering_failures[cls] = self.engineering_failures.get(cls, 0) + 1
            self.ledger.settle(unit_id, {}, note=f"judge batch failed: {cls}", estimated=True, fallback_to_reservation=True)
            raise

    def open_reservations_after_restart(self) -> list[str]:
        """Units reserved by an earlier process that never settled. They stay reserved (budget is
        not released) until a human settles them from the eval log or voids them explicitly."""
        return self.ledger.snapshot()["open_reservations"]


# ----------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="GDPval pilot launcher (trusted host process)")
    p.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    p.add_argument("--runs-root", required=True, help="absolute real path for collected outputs and records")
    p.add_argument("--ledger", required=True, help="path of the persistent budget ledger (JSON)")
    p.add_argument("--task-id", required=True)
    p.add_argument("--model", required=True, help="Inspect model name, e.g. anthropic/claude-opus-5-5")
    p.add_argument("--estimate-usd", required=True, type=Decimal, help="pre-run cost estimate for this unit (no estimate, no start)")
    p.add_argument("--token-limit", type=int, default=None)
    p.add_argument("--env-file", default=os.path.join(ROOT, ".env"))
    p.add_argument("--dry-run", action="store_true", help="run every check and the reservation logic; do not call eval()")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    if not args.dry_run:
        refuse_disabled_model_api()
    runs_root = resolve_runs_root(args.runs_root)
    provider = args.model.split("/", 1)[0]
    loaded = load_env_file(args.env_file)
    missing = missing_keys([provider])
    if missing and not args.dry_run:
        raise LauncherError(f"missing credential variable(s): {missing} (names only; nothing printed)")
    image = preflight_image(cfg["sandbox"]["image"])
    ledger = BudgetLedger(args.ledger, cfg["pilot"]["budget_ceiling_usd"], prices_from_config(cfg))
    print(json.dumps({"config_sha256": config_sha256(args.config), "config_status": cfg["_status"][:5], "runs_root": runs_root,
                      "env_names_loaded": loaded, "missing_key_names": missing, "image_id": image.get("image_id"),
                      "image_attempts": len(image["attempts"]), "ledger": ledger.snapshot(), "dry_run": args.dry_run}, indent=1))
    if args.dry_run:
        from .samples import build_samples
        from .task import make_task
        samples = build_samples([args.task_id], verify_config=args.config)  # I1: fail closed on any staged-file mismatch
        if not samples:
            raise LauncherError(f"task {args.task_id} is not in data/selected_tasks.json")
        print(json.dumps({"staging_verified": samples[0].metadata["staging_verified"]}))
        task, _ = make_task(samples, runs_root, name=f"pilot_{args.task_id[:8]}")
        launcher = PilotLauncher(cfg, runs_root=runs_root, ledger=ledger, eval_fn=None)
        unit_id = f"{args.task_id}:{args.model}:{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        launcher.run_sample(task=task, model=args.model, unit_id=unit_id, estimate_usd=args.estimate_usd, token_limit=args.token_limit, dry_run=True)
        return 0
    raise LauncherError("real mode is not enabled in this stage: paid calls require separate authorization")


if __name__ == "__main__":
    sys.exit(main())
