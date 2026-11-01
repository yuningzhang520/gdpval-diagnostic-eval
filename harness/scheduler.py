"""Paid-unit scheduler across run classes (approved by the human 2026-11-01, chat: controlled parallel execution).

One scheduler process owns every paid launch of a plan. Each launch is one unit: ``harness.batch --tasks <one task>
--real-run`` under ``caffeinate -i`` in its own session (a scheduler crash or a closed terminal never terminates an
in-flight unit), with its own console log. Every unit still passes all launcher gates (staging, prompt hash, image,
atomic ledger claim, settlement, binding, manifest, inventory). Rules enforced here:

  * at most ``cap`` paid units at once across classes (initial 2, adaptive up to 3, see ResourceTracker), and at most
    one unit per run class (one ledger is never driven by two processes);
  * job prerequisites (e.g. compat GPT after compat Opus; the remaining Gemini dev units and Gemini validation only
    after the Gemini replacement unit is accepted);
  * after each unit, harness.unit_gate decides: an accepted Gemini unit is designated canonical; any stop reason stops
    every further Gemini launch; the two-limit rule (time / working / cost) across dev and validation stops Gemini
    launches at the threshold; a candidate unit that does not pass stops its class;
  * no rerun: a task with any earlier attempt is never launched again (the batch runner's own skip rule), except the
    one explicitly authorized replacement job, which runs at most once per config snapshot.

State, events and resource samples: <base>/scheduler/<plan name>/ (state.json, events.jsonl, resources.jsonl).
Controls: a file ``stop_new`` there stops new launches (the scheduler exits once nothing runs); ``cap_override``
(an integer 1-3) replaces the adaptive cap. Nothing here reads model-generated content.

Usage: python -m harness.scheduler --plan <plan.json> [--dry-plan]"""
import argparse
import datetime as dt
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time

from . import batch as B
from . import launcher as L
from . import unit_gate as G
from .budget import BudgetLedger
from .samples import TASK_SETS, load_json, task_set_for_manifest

MIB = 1 << 20


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _write_json_atomic(path: str, obj) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ----------------------------------------------------------------------------- resources
_SIZE = re.compile(r"([\d.]+)\s*([KMGT]?i?B)", re.I)
_UNITS = {"b": 1, "kb": 1000, "kib": 1 << 10, "mb": 1000 ** 2, "mib": 1 << 20, "gb": 1000 ** 3, "gib": 1 << 30, "tb": 1000 ** 4, "tib": 1 << 40}


def parse_size(text: str) -> int | None:
    m = _SIZE.search(text or "")
    if not m:
        return None
    return int(float(m.group(1)) * _UNITS.get(m.group(2).lower(), 1))


def sample_resources(run=subprocess.run, since_epoch: int | None = None) -> dict:
    """One sample of Docker and host resource use: sandbox containers (name prefix inspect-) and their memory, Docker VM
    memory, swap used, macOS memory-pressure level (1 normal, 2 warn, 4 critical), OOM events since ``since_epoch``."""
    def out(cmd, timeout=30):
        try:
            r = run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.stdout if r.returncode == 0 else None
        except Exception:
            return None
    s = {"at": now_iso()}
    names = out(["docker", "ps", "--filter", "name=inspect-", "--format", "{{.Names}}"])
    s["containers"] = [n for n in (names or "").splitlines() if n.strip()] if names is not None else None
    mem = 0
    if s["containers"]:
        st = out(["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}", *s["containers"]], timeout=60)
        for line in (st or "").splitlines():
            parts = line.split("\t")
            if len(parts) == 2:
                mem += parse_size(parts[1].split("/")[0]) or 0
    s["docker_mem_used"] = mem
    total = out(["docker", "info", "--format", "{{.MemTotal}}"])
    s["docker_vm_mem_total"] = int(total.strip()) if total and total.strip().isdigit() else None
    swap = out(["sysctl", "-n", "vm.swapusage"])
    m = re.search(r"used = ([\d.]+)M", swap or "")
    s["swap_used"] = int(float(m.group(1)) * MIB) if m else None
    lvl = out(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"])
    s["pressure_level"] = int(lvl.strip()) if lvl and lvl.strip().isdigit() else None
    if since_epoch is not None:
        ev = out(["docker", "events", "--since", str(since_epoch), "--until", str(int(time.time())), "--filter", "event=oom", "--format", "{{.Actor.Attributes.name}}"], timeout=30)
        s["oom_events"] = len([l for l in (ev or "").splitlines() if l.strip()]) if ev is not None else None
    return s


class ResourceTracker:
    """Overlap accounting and the adaptive cap rule (config.concurrency.cross_class): after OVERLAP_S of actual overlap
    of two paid sandbox units, raise 2 -> 3 when peak Docker memory during the overlap stayed below RAISE_SHARE of the
    Docker VM memory, the pressure level stayed normal, swap grew by at most SWAP_GROWTH and no OOM event occurred;
    otherwise keep 2. Contention (Docker memory above CONTENTION_SHARE, pressure warn or critical, an OOM event) lowers
    the cap by one per episode and ends adaptive raising. Never terminates anything."""
    OVERLAP_S, RAISE_SHARE, CONTENTION_SHARE, SWAP_GROWTH = 1800, 0.5, 0.8, 512 * MIB

    def __init__(self, cap: int = 2, cap_max: int = 3, state: dict | None = None):
        st = state or {}
        self.cap, self.cap_max = st.get("cap", cap), cap_max
        self.overlap_s = st.get("overlap_s", 0.0)
        self.peak_overlap_mem = st.get("peak_overlap_mem", 0)
        self.max_overlap_pressure = st.get("max_overlap_pressure", 1)
        self.swap_baseline = st.get("swap_baseline")
        self.swap_max = st.get("swap_max")
        self.oom_total = st.get("oom_total", 0)
        self.evaluated = st.get("evaluated", False)
        self.contention = st.get("contention", False)
        self.in_episode = st.get("in_episode", False)
        self.integrity_failures = st.get("integrity_failures", 0)
        self.last_at = st.get("last_at")
        self.decisions = st.get("decisions", [])

    def to_state(self) -> dict:
        return {k: getattr(self, k) for k in ("cap", "overlap_s", "peak_overlap_mem", "max_overlap_pressure", "swap_baseline", "swap_max", "oom_total", "evaluated",
                                              "contention", "in_episode", "integrity_failures", "last_at", "decisions")}

    def update(self, s: dict, *, active_units: int, t: float) -> list[dict]:
        events = []
        dt_s = 0.0 if self.last_at is None else max(0.0, min(t - self.last_at, 300.0))
        self.last_at = t
        if s.get("swap_used") is not None:
            self.swap_baseline = s["swap_used"] if self.swap_baseline is None else self.swap_baseline
            self.swap_max = max(self.swap_max or 0, s["swap_used"])
        self.oom_total += s.get("oom_events") or 0
        overlapping = active_units >= 2 and len(s.get("containers") or []) >= 2
        if overlapping:
            self.overlap_s += dt_s
            self.peak_overlap_mem = max(self.peak_overlap_mem, s.get("docker_mem_used") or 0)
            self.max_overlap_pressure = max(self.max_overlap_pressure, s.get("pressure_level") or 1)
        total = s.get("docker_vm_mem_total")
        hot = (total and (s.get("docker_mem_used") or 0) > self.CONTENTION_SHARE * total) or (s.get("pressure_level") or 1) >= 2 or (s.get("oom_events") or 0) > 0
        if hot and not self.in_episode:
            old = self.cap
            self.cap, self.contention, self.in_episode = max(1, self.cap - 1), True, True
            events.append(self._decide("contention: cap lowered; in-flight units continue", old, s))
        elif not hot:
            self.in_episode = False
        if not self.evaluated and not self.contention and self.cap == 2 and self.overlap_s >= self.OVERLAP_S:
            self.evaluated = True
            swap_growth = (self.swap_max or 0) - (self.swap_baseline or 0)
            ok = (total is not None and self.peak_overlap_mem < self.RAISE_SHARE * total and self.max_overlap_pressure == 1 and swap_growth <= self.SWAP_GROWTH
                  and self.oom_total == 0 and self.integrity_failures == 0)
            old = self.cap
            if ok:
                self.cap = min(self.cap_max, 3)
            events.append(self._decide("adaptive evaluation after 30 min of overlap: " + ("raise to 3" if ok else "keep 2"), old, s,
                                       extra={"peak_overlap_mem": self.peak_overlap_mem, "docker_vm_mem_total": total, "peak_share": round(self.peak_overlap_mem / total, 4) if total else None,
                                              "max_overlap_pressure": self.max_overlap_pressure, "swap_growth": swap_growth, "oom_total": self.oom_total,
                                              "integrity_failures": self.integrity_failures, "overlap_s": round(self.overlap_s, 1)}))
        return events

    def _decide(self, what, old, s, extra=None) -> dict:
        d = {"at": now_iso(), "event": "cap_decision", "decision": what, "cap_before": old, "cap_after": self.cap, "sample": s, **(extra or {})}
        self.decisions.append({k: v for k, v in d.items() if k != "sample"})
        return d


# ----------------------------------------------------------------------------- scheduler
class Scheduler:
    def __init__(self, plan: dict, *, run=subprocess.run, popen=subprocess.Popen, sampler=None, clock=time.time, sleep=time.sleep, metadata_fn=None, batch_argv=None):
        self.plan = plan
        self.base = plan["base"]
        self.dir = os.path.join(self.base, "scheduler", plan["name"])
        os.makedirs(self.dir, exist_ok=True)
        self.state_path = os.path.join(self.dir, "state.json")
        self.run, self.popen, self.clock, self.sleep = run, popen, clock, sleep
        self.sampler = sampler or (lambda since: sample_resources(run=self.run, since_epoch=since))
        self.metadata_fn = metadata_fn
        self.batch_argv = batch_argv or self._batch_argv
        self.cfg = L.load_config(plan["config"])
        self.config_sha = L.config_sha256(plan["config"])
        self.children = {}  # job name -> Popen (launched by this process)
        st = {}
        if os.path.isfile(self.state_path):
            with open(self.state_path, encoding="utf-8") as f:
                st = json.load(f)
        self.jobs = st.get("jobs") or {j["name"]: {"status": "pending", "invocations": [], "accepted": False} for j in plan["jobs"]}
        self.gemini_stop = st.get("gemini_stop")
        self.class_stop = st.get("class_stop") or {}
        self.started_epoch = st.get("started_epoch") or int(self.clock())
        cc = self.cfg["concurrency"]["cross_class"]
        self.tracker = ResourceTracker(cap=cc["global_paid_units_cap_initial"], cap_max=cc["global_paid_units_cap_max"], state=st.get("tracker"))
        self.last_sample = 0.0

    # -- persistence
    def event(self, name: str, **kw) -> None:
        with open(os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": now_iso(), "event": name, **kw}, default=str) + "\n")

    def save(self) -> None:
        _write_json_atomic(self.state_path, {"plan": self.plan["name"], "config": self.plan["config"], "config_sha256": self.config_sha, "jobs": self.jobs, "gemini_stop": self.gemini_stop,
                                             "class_stop": self.class_stop, "tracker": self.tracker.to_state(), "started_epoch": self.started_epoch, "saved_at": now_iso()})

    # -- helpers
    def job(self, name: str) -> dict:
        return next(j for j in self.plan["jobs"] if j["name"] == name)

    def roots(self, label: str) -> tuple[str, str]:
        return os.path.join(self.base, label, "runs"), os.path.join(self.base, label, "ledger.json")

    def class_tasks(self, label: str) -> list[str]:
        b = L.batch_controls(self.cfg, label)
        return [t["task_id"] for t in load_json(TASK_SETS[task_set_for_manifest(b["task_manifest"])]["selected"])["tasks"]]

    def remaining_tasks(self, j: dict) -> list[str]:
        runs_root, _ = self.roots(j["label"])
        if j.get("replacement"):
            done_here = [r for r in G.inventory(runs_root) if r.get("task_id") == j["tasks"][0] and r.get("model") == j["model"] and r.get("kind") != "dry_run"
                         and not r.get("dry_run") and r.get("config_sha256") == self.config_sha]
            return [] if done_here or self.jobs[j["name"]]["invocations"] else list(j["tasks"])
        attempts = B.prior_attempts(runs_root) if os.path.isdir(runs_root) else {}
        tasks = self.class_tasks(j["label"]) if j["tasks"] == "all" else list(j["tasks"])
        return [t for t in tasks if (t, j["model"]) not in attempts]

    def running(self) -> list[str]:
        return [n for n, s in self.jobs.items() if s["status"] == "running"]

    def requirements_met(self, j: dict) -> bool | None:
        """True met, False not yet, None never (a prerequisite failed)."""
        for req in j.get("requires", []):
            name, cond = req.split(":")
            s = self.jobs[name]
            if cond == "accepted":
                if s["accepted"]:
                    continue
                return None if s["status"] in ("failed", "blocked", "done") else False
            if cond == "done_ok":
                if s["status"] == "done" and not s.get("failed_units"):
                    continue
                return None if s["status"] in ("failed", "blocked") else False
        return True

    def ledger_blocks(self, label: str) -> list[str]:
        _, ledger = self.roots(label)
        if not os.path.exists(ledger):
            return []
        return B.ledger_blocks(BudgetLedger.open_existing(ledger, L.prices_from_config(self.cfg)))

    def gemini_roots(self) -> dict:
        return {lbl: self.roots(lbl)[0] for lbl in self.plan.get("gemini_scope", ["dev", "validation"])}

    def two_limit_reached(self, model: str) -> list[dict] | None:
        rule = self.cfg["batches"]["dev"]["gemini_unit_policy"]["two_limit_rule"]
        hits = G.counted_limit_units(self.gemini_roots(), model=model, counted_types=tuple(rule["counted_limit_types"]))
        return hits if len(hits) >= rule["threshold_units"] else None

    def expected_exts(self, task_id: str) -> list[str]:
        d = os.path.join(L.ROOT, "private", "gold", task_id)
        return sorted({os.path.splitext(f)[1].lower() for f in os.listdir(d)}) if os.path.isdir(d) else []

    def _batch_argv(self, j: dict, task: str) -> list[str]:
        runs_root, ledger = self.roots(j["label"])
        argv = ["caffeinate", "-i", self.plan.get("python", os.path.join(L.ROOT, ".venv", "bin", "python")), "-m", "harness.batch", "--config", self.plan["config"], "--run-label", j["label"],
                "--model", j["model"], "--runs-root", runs_root, "--ledger", ledger, "--tasks", task, "--env-file", self.plan.get("env_file", os.path.join(L.ROOT, ".env")),
                "--real-run", "--confirm-batch", f"{j['label']}|{j['model']}|1|{j['estimate']}", "--authorized-by", self.plan["authorized_by"], "--authorization-ref", self.plan["authorization_ref"]]
        if j.get("replacement"):
            argv.insert(argv.index("--real-run"), "--allow-repeat")
        return argv

    # -- launching
    def launchable(self) -> list[tuple[dict, str]]:
        out = []
        busy_labels = {self.job(n)["label"] for n in self.running()}
        for j in self.plan["jobs"]:
            s = self.jobs[j["name"]]
            if s["status"] not in ("pending", "waiting", "idle"):
                continue
            if self.class_stop.get(j["label"]):
                s["status"] = "blocked"; s["blocked_reason"] = f"run class {j['label']} stopped: {self.class_stop[j['label']].get('reason')}"
                continue
            if j["label"] in busy_labels:
                continue
            if j.get("gemini") and self.gemini_stop:
                s["status"] = "blocked"; s["blocked_reason"] = f"Gemini launches stopped: {self.gemini_stop}"
                continue
            met = self.requirements_met(j)
            if met is None:
                s["status"] = "blocked"; s["blocked_reason"] = "a prerequisite failed or was not accepted"
                continue
            if not met:
                s["status"] = "waiting"
                continue
            left = self.remaining_tasks(j)
            if not left:
                s["status"] = "done"
                self.event("job_done", job=j["name"])
                continue
            if j.get("gemini"):
                hits = self.two_limit_reached(j["model"])
                if hits:
                    self.gemini_stop = {"reason": "two-limit rule: two distinct canonical Gemini units hit a time or cost limit", "units": hits}
                    s["status"] = "blocked"; s["blocked_reason"] = "two-limit rule"
                    self.event("gemini_stop", **self.gemini_stop)
                    continue
            blocks = self.ledger_blocks(j["label"])
            if blocks:
                self.class_stop[j["label"]] = {"reason": "ledger blocks the next start", "blocks": blocks}
                self.event("class_stop", label=j["label"], blocks=blocks)
                if j.get("gemini"):
                    self.gemini_stop = {"reason": f"ledger of {j['label']} blocks", "blocks": blocks}
                continue
            out.append((j, left[0]))
            busy_labels.add(j["label"])
        return out

    def launch(self, j: dict, task: str) -> None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log = os.path.join(self.base, "batch_console", f"{j['label']}_{j['model'].replace('/', '_')}_{task[:8]}_{stamp}.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        since = now_iso()
        env = {**os.environ, "INSPECT_DISPLAY": "plain", "PYTHONUNBUFFERED": "1"}
        fh = open(log, "a", encoding="utf-8")
        p = self.popen(self.batch_argv(j, task), cwd=L.ROOT, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        fh.close()
        self.children[j["name"]] = p
        inv = {"task_id": task, "pid": p.pid, "since": since, "console_log": log, "rc": None}
        self.jobs[j["name"]]["invocations"].append(inv)
        self.jobs[j["name"]]["status"] = "running"
        self.event("launch", job=j["name"], label=j["label"], model=j["model"], task_id=task, pid=p.pid, console_log=log, cap=self.tracker.cap, running=self.running())
        self.save()

    # -- completion
    def poll_children(self) -> None:
        for name in self.running():
            inv = self.jobs[name]["invocations"][-1]
            p = self.children.get(name)
            if p is not None:
                rc = p.poll()
                if rc is None:
                    continue
            else:  # adopted after a restart: not our child; wait until the pid is gone, then read the batch record
                if _pid_alive(inv["pid"]):
                    continue
                rc = self._rc_from_batch_record(self.job(name), inv)
            inv["rc"], inv["finished_at"] = rc, now_iso()
            self.children.pop(name, None)
            self.after_unit(self.job(name), inv)
            self.save()

    def _rc_from_batch_record(self, j: dict, inv: dict):
        runs_root, _ = self.roots(j["label"])
        d = os.path.join(runs_root, "batch_records")
        recs = []
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    r = json.load(fh)
            except Exception:
                continue
            if r.get("model") == j["model"] and (r.get("started_at") or "") >= inv["since"] and any(x.get("task_id") == inv["task_id"] for x in r.get("plan", [])):
                recs.append(r)
        if not recs:
            return None
        return 0 if recs[-1].get("status") in ("completed", "paused") else 1

    def after_unit(self, j: dict, inv: dict) -> None:
        runs_root, _ = self.roots(j["label"])
        rec = G.unit_record(runs_root, task_id=inv["task_id"], model=j["model"], since=inv["since"])
        gate = G.evaluate_unit(runs_root, rec, gemini=bool(j.get("gemini")), expected_exts=self.expected_exts(inv["task_id"]) if not j.get("expected_exts") else j["expected_exts"],
                               require_files=bool(j.get("replacement")), metadata_fn=self.metadata_fn)
        if inv["rc"] != 0:
            gate["decision"] = "stop"; gate["reasons"] = [f"batch exited with {inv['rc']}"] + gate.get("reasons", [])
        blocks = self.ledger_blocks(j["label"])
        if blocks:
            gate["decision"] = "stop"; gate["reasons"] = gate.get("reasons", []) + [f"ledger blocks: {blocks}"]
        inv["gate"] = gate
        integrity = [r for r in gate.get("reasons", []) + gate.get("observations", []) if "structural" in r or "manifest" in r or "collection status" in r]
        self.tracker.integrity_failures += 1 if integrity else 0
        s = self.jobs[j["name"]]
        self.event("unit_finished", job=j["name"], task_id=inv["task_id"], rc=inv["rc"], decision=gate["decision"], reasons=gate.get("reasons"),
                   execution_status=gate.get("execution_status"), limit_types=gate.get("limit_types"), run_uuid=gate.get("run_uuid"), cost=gate.get("settlement_cost_usd"),
                   metadata={k: (gate.get("metadata") or {}).get(k) for k in ("messages", "model_calls", "tool_calls", "tool_errors", "tool_calls_per_turn", "longest_error_streak", "limit")})
        if gate["decision"] == "accept":
            if j.get("gemini") and rec and rec.get("run_uuid"):
                G.designate(runs_root, run_uuid=rec["run_uuid"], task_id=inv["task_id"], model=j["model"], designation="canonical",
                            reason=f"accepted by the unit gate (scheduler plan {self.plan['name']})", by="harness.scheduler", ref=self.plan["authorization_ref"])
            if j.get("replacement"):
                s["accepted"] = True
            s["status"] = "done" if j.get("replacement") or not self.remaining_tasks(j) else "idle"
            if j.get("gemini"):
                hits = self.two_limit_reached(j["model"])
                if hits:
                    self.gemini_stop = {"reason": "two-limit rule: two distinct canonical Gemini units hit a time or cost limit", "units": hits}
                    self.event("gemini_stop", **self.gemini_stop)
        else:
            s["status"] = "failed"
            s["failed_units"] = s.get("failed_units", 0) + 1
            if j.get("gemini"):
                self.gemini_stop = {"reason": f"unit gate stop on {j['name']} {inv['task_id']}", "reasons": gate.get("reasons")}
                self.event("gemini_stop", **self.gemini_stop)
            else:
                self.class_stop[j["label"]] = {"reason": f"unit gate stop on {j['name']}", "reasons": gate.get("reasons")}
                self.event("class_stop", label=j["label"], reasons=gate.get("reasons"))

    # -- main loop
    def effective_cap(self) -> int:
        p = os.path.join(self.dir, "cap_override")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return max(1, min(3, int(f.read().strip())))
            except ValueError:
                pass
        return self.tracker.cap

    def step(self) -> bool:
        """One scheduling step; returns False when the plan is finished (nothing running, nothing launchable)."""
        self.poll_children()
        t = self.clock()
        if t - self.last_sample >= self.plan.get("sample_s", 60):
            self.last_sample = t
            s = self.sampler(self.started_epoch)
            s["active_units"] = len(self.running())
            with open(os.path.join(self.dir, "resources.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps(s) + "\n")
            for ev in self.tracker.update(s, active_units=len(self.running()), t=t):
                self.event(ev.pop("event"), **ev)
        stop_new = os.path.exists(os.path.join(self.dir, "stop_new"))
        if not stop_new:
            for j, task in self.launchable():
                if len(self.running()) >= self.effective_cap():
                    break
                self.launch(j, task)
        self.save()
        if self.running():
            return True
        if stop_new:
            return False
        pending = [n for n, s in self.jobs.items() if s["status"] in ("pending", "waiting", "idle")]
        return bool(pending) and bool(self.launchable_any())

    def launchable_any(self) -> bool:
        return any(True for _ in self.launchable())

    def loop(self) -> int:
        self.event("scheduler_start", pid=os.getpid(), plan=self.plan["name"], config=self.plan["config"], config_sha256=self.config_sha, cap=self.tracker.cap)
        while self.step():
            self.sleep(self.plan.get("poll_s", 20))
        self.event("scheduler_end", jobs={n: s["status"] for n, s in self.jobs.items()}, gemini_stop=self.gemini_stop, class_stop=self.class_stop)
        self.save()
        return 0


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="paid-unit scheduler across run classes (one owner of all paid launches of a plan)")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--dry-plan", action="store_true", help="print what would launch first and exit (no launch)")
    args = ap.parse_args(argv)
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    sch = Scheduler(plan)
    lock = open(os.path.join(sch.dir, "scheduler.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another scheduler holds this plan's lock; refusing to start", file=sys.stderr)
        return 2
    if args.dry_plan:
        print(json.dumps({"would_launch": [(j["name"], t) for j, t in sch.launchable()][: sch.effective_cap()], "cap": sch.effective_cap(), "config_sha256": sch.config_sha}, indent=1))
        return 0
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    stop = {"flag": False}

    def _term(*_):  # stop launching; in-flight units are in their own sessions and keep running
        open(os.path.join(sch.dir, "stop_new"), "a").close()
        stop["flag"] = True
    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    return sch.loop()


if __name__ == "__main__":
    sys.exit(main())
