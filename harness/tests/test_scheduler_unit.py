"""Scheduler and unit-gate policy (approved 2026-11-01) with fake batch processes: real subprocesses that write the
records a unit leaves behind (inventory line, run_outcome.json, collected files, artifact manifest) and a shared
timeline. No model, provider, Inspect or Docker call; the resource sampler and run metadata are injected."""
import json
import os
import sys
import tempfile
import textwrap
import time
import unittest

from harness import launcher as L
from harness import scheduler as S
from harness import unit_gate as G

CONFIG = os.path.join(L.ROOT, "config.json")
GEM, OPUS, GPT = "google/gemini-3.8-flash", "anthropic/claude-opus-5-5", "openai/gpt-6.1-sol"
B5 = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"

FAKE = textwrap.dedent(r'''
    import datetime as dt, hashlib, json, os, sys, time
    spec = json.loads(sys.argv[1]); o = spec["outcome"]
    def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with open(spec["timeline"], "a") as f: f.write(json.dumps({"ev": "start", "label": spec["label"], "model": spec["model"], "task": spec["task"], "t": time.time()}) + "\n")
    time.sleep(o.get("sleep", 0.25))
    uuid = "U" + os.urandom(6).hex(); d = os.path.join(spec["runs_root"], uuid); fin = os.path.join(d, "final"); os.makedirs(fin)
    files = []
    for i, ext in enumerate(o.get("files", [".xlsx"])):
        p = os.path.join(fin, f"f{i}{ext}")
        if ext == ".xlsx":
            import openpyxl; wb = openpyxl.Workbook(); wb.active["A1"] = 1; wb.save(p)
        else:
            open(p, "wb").write(o.get("bytes", b"x").encode() if isinstance(o.get("bytes"), str) else b"x")
        files.append({"path": f"f{i}{ext}", "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "bytes": os.path.getsize(p)})
    status = o.get("collection", "complete" if files else "no_files_confirmed")
    json.dump({"execution": {"status": o.get("status", "completed"), "limit_types": o.get("limits", []), "solver_finished": o.get("status", "completed") == "completed"},
               "collection": {"status": status, "file_count": len(files)}, "grading_eligible": o.get("eligible", True), "harness_error": False, "outcome_class": "collected"},
              open(os.path.join(d, "run_outcome.json"), "w"))
    json.dump({"files": files, "file_count": len(files), "collector_cross_check": {"consistent": o.get("manifest_ok", True)}}, open(os.path.join(d, "artifact_manifest.json"), "w"))
    with open(os.path.join(spec["runs_root"], "run_inventory.jsonl"), "a") as f:
        f.write(json.dumps({"recorded_at": now(), "kind": o.get("kind", "sample"), "run_label": spec["label"], "task_id": spec["task"], "model": spec["model"], "run_uuid": uuid,
                            "log_file": "fake.eval", "settlement_cost_usd": "1.00", "estimated": o.get("estimated", False), "manual_review_required": False, "stop_recorded": None,
                            "engineering_failure": o.get("engineering_failure"), "config_sha256": spec["config_sha"], "dry_run": False}) + "\n")
    os.makedirs(os.path.join(spec["runs_root"], "batch_records"), exist_ok=True)
    json.dump({"model": spec["model"], "started_at": spec["started_at"], "plan": [{"task_id": spec["task"], "action": "run"}], "status": "completed" if o.get("rc", 0) == 0 else "stopped"},
              open(os.path.join(spec["runs_root"], "batch_records", f"batch_{spec['label']}_{uuid}.json"), "w"))
    with open(spec["timeline"], "a") as f: f.write(json.dumps({"ev": "end", "label": spec["label"], "model": spec["model"], "task": spec["task"], "t": time.time(), "uuid": uuid}) + "\n")
    sys.exit(o.get("rc", 0))
''')


def plan_jobs(rep=True, dev=True, val=True, compat=True):
    jobs = []
    if rep:
        jobs.append({"name": "dev_replacement", "label": "dev", "model": GEM, "tasks": [B5], "estimate": "5.00", "gemini": True, "replacement": True, "expected_exts": [".xlsx"]})
    if compat:
        jobs.append({"name": "compat_opus", "label": "compat", "model": OPUS, "tasks": "all", "estimate": "8.00"})
    if dev:
        jobs.append({"name": "dev_rest", "label": "dev", "model": GEM, "tasks": "all", "estimate": "5.00", "gemini": True, "requires": ["dev_replacement:accepted"] if rep else []})
    if compat:
        jobs.append({"name": "compat_gpt", "label": "compat", "model": GPT, "tasks": "all", "estimate": "5.00", "requires": ["compat_opus:done_ok"]})
    if val:
        jobs.append({"name": "validation", "label": "validation", "model": GEM, "tasks": "all", "estimate": "5.00", "gemini": True, "requires": ["dev_replacement:accepted"] if rep else []})
    return jobs


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.path.realpath(tempfile.gettempdir()))
        self.base = os.path.join(self.tmp.name, "runsbase")
        for lbl in ("dev", "validation", "compat"):
            os.makedirs(os.path.join(self.base, lbl, "runs"))
        self.timeline = os.path.join(self.tmp.name, "timeline.jsonl")
        self.script = os.path.join(self.tmp.name, "fake_unit.py")
        with open(self.script, "w") as f:
            f.write(FAKE)
        self.outcomes = {}  # (label, model, task) -> outcome dict; default completed .xlsx
        self.loops = set()  # tasks whose metadata reports a suspected tool-error loop

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, jobs, cap=2, sample=None):
        plan = {"name": "test", "base": self.base, "config": CONFIG, "authorized_by": "test", "authorization_ref": "test", "jobs": jobs, "poll_s": 0.05, "sample_s": 3600}
        sha = L.config_sha256(CONFIG)

        def argv(j, task):
            runs_root, _ = sch.roots(j["label"])
            spec = {"runs_root": runs_root, "task": task, "model": j["model"], "label": j["label"], "timeline": self.timeline, "config_sha": sha, "started_at": S.now_iso(),
                    "outcome": self.outcomes.get((j["label"], j["model"], task), {})}
            return [sys.executable, self.script, json.dumps(spec)]

        sch = S.Scheduler(plan, batch_argv=argv, sampler=sample or (lambda since: {"containers": [], "docker_mem_used": 0, "docker_vm_mem_total": 8 << 30, "swap_used": 0, "pressure_level": 1, "oom_events": 0}),
                          metadata_fn=lambda log: {"suspected_tool_error_loop": False, "messages": {"total": 10}}, sleep=time.sleep)
        sch.tracker.cap = cap
        orig = sch.after_unit

        def after(j, inv):  # inject the loop flag per task through the metadata function
            sch.metadata_fn = (lambda log, t=inv["task_id"]: {"suspected_tool_error_loop": t in self.loops})
            return orig(j, inv)
        sch.after_unit = after
        return sch

    def events(self):
        out = []
        if os.path.exists(self.timeline):
            out = [json.loads(l) for l in open(self.timeline)]
        return out

    def max_concurrency(self):
        live, peak, per_label_peak = set(), 0, 0
        for e in sorted(self.events(), key=lambda e: (e["t"], e["ev"] == "start")):
            key = (e["label"], e["model"], e["task"])
            if e["ev"] == "start":
                live.add(key)
            else:
                live.discard(key)
            peak = max(peak, len(live))
            labels = [k[0] for k in live]
            per_label_peak = max([per_label_peak] + [labels.count(l) for l in set(labels)])
        return peak, per_label_peak


class SchedulingTests(_Base):
    def test_happy_path_cap_two_one_per_class_order_and_designations(self):
        sch = self.make(plan_jobs())
        self.assertEqual(sch.loop(), 0)
        ev = self.events()
        starts = [e for e in ev if e["ev"] == "start"]
        peak, per_label = self.max_concurrency()
        self.assertLessEqual(peak, 2); self.assertEqual(per_label, 1)
        first_two = {(e["label"], e["model"]) for e in sorted(starts, key=lambda e: e["t"])[:2]}
        self.assertEqual(first_two, {("dev", GEM), ("compat", OPUS)})  # replacement and compat start together
        dev = [e for e in starts if e["label"] == "dev"]; val = [e for e in starts if e["label"] == "validation"]
        self.assertEqual((len(dev), len(val)), (10, 10))  # replacement + nine remaining dev tasks; ten validation tasks
        t_opus_end = next(e["t"] for e in ev if e["ev"] == "end" and e["model"] == OPUS)
        t_gpt_start = next(e["t"] for e in starts if e["model"] == GPT)
        self.assertGreater(t_gpt_start, t_opus_end)
        t_rep_end = next(e["t"] for e in ev if e["ev"] == "end" and e["task"] == B5)
        self.assertTrue(all(e["t"] > t_rep_end for e in dev if e["task"] != B5) and all(e["t"] > t_rep_end for e in val))
        self.assertEqual(len([d for d in G.designations(os.path.join(self.base, "dev", "runs")) if d["designation"] == "canonical"]), 10)
        self.assertEqual(len(G.designations(os.path.join(self.base, "validation", "runs"))), 10)
        st = json.load(open(sch.state_path))
        self.assertEqual({n: s["status"] for n, s in st["jobs"].items()}, {"dev_replacement": "done", "compat_opus": "done", "dev_rest": "done", "compat_gpt": "done", "validation": "done"})
        self.assertIsNone(st["gemini_stop"])

    def test_rejected_replacement_blocks_gemini_but_not_compat(self):
        self.outcomes[("dev", GEM, B5)] = {"status": "limited", "limits": ["message"]}
        sch = self.make(plan_jobs())
        sch.loop()
        starts = [e for e in self.events() if e["ev"] == "start"]
        self.assertEqual([(e["label"], e["model"]) for e in starts if e["label"] != "compat"], [("dev", GEM)])  # only the replacement
        self.assertEqual(sorted(e["model"] for e in starts if e["label"] == "compat"), sorted([OPUS, GPT]))
        st = json.load(open(sch.state_path))
        self.assertIn("not an accepted limit type", json.dumps(st["gemini_stop"]))
        self.assertEqual((st["jobs"]["dev_rest"]["status"], st["jobs"]["validation"]["status"]), ("blocked", "blocked"))

    def test_replacement_needs_the_expected_file_type(self):
        self.outcomes[("dev", GEM, B5)] = {"files": [".txt"]}
        sch = self.make(plan_jobs(compat=False))
        sch.loop()
        st = json.load(open(sch.state_path))
        self.assertIn("expected file type", json.dumps(st["gemini_stop"]))

    def test_accepted_limits_continue_and_the_two_limit_rule_stops_gemini(self):
        tasks = S.Scheduler.class_tasks(self.make(plan_jobs()), "dev")
        self.outcomes[("dev", GEM, B5)] = {"status": "limited", "limits": ["token"]}  # accepted, not counted
        self.outcomes[("dev", GEM, tasks[1])] = {"status": "limited", "limits": ["time", "working"]}  # counted once (one unit)
        self.outcomes[("dev", GEM, tasks[3])] = {"status": "limited", "limits": ["cost"]}  # second counted unit
        sch = self.make(plan_jobs(compat=False, val=False))
        sch.loop()
        st = json.load(open(sch.state_path))
        self.assertIn("two-limit rule", json.dumps(st["gemini_stop"]))
        self.assertEqual(len(st["gemini_stop"]["units"]), 2)
        dev_tasks = [e["task"] for e in self.events() if e["ev"] == "start" and e["label"] == "dev"]
        self.assertEqual(dev_tasks, [B5] + tasks[1:4])  # nothing launched after the second counted unit
        self.assertEqual(st["jobs"]["dev_rest"]["status"], "blocked")

    def test_diagnostic_attempts_are_not_counted_and_a_single_hit_continues(self):
        dev_root = os.path.join(self.base, "dev", "runs")
        tasks = S.Scheduler.class_tasks(self.make(plan_jobs()), "dev")
        # an earlier time-limited attempt designated diagnostic must not count
        uuid = "Udiag"; os.makedirs(os.path.join(dev_root, uuid))
        json.dump({"execution": {"status": "limited", "limit_types": ["time"]}}, open(os.path.join(dev_root, uuid, "run_outcome.json"), "w"))
        with open(os.path.join(dev_root, "run_inventory.jsonl"), "a") as f:
            f.write(json.dumps({"recorded_at": "2026-11-01T00:00:00+00:00", "kind": "sample", "task_id": B5, "model": GEM, "run_uuid": uuid, "config_sha256": "old"}) + "\n")
        G.designate(dev_root, run_uuid=uuid, task_id=B5, model=GEM, designation="diagnostic", reason="test", by="test", ref="test")
        self.outcomes[("dev", GEM, tasks[2])] = {"status": "limited", "limits": ["time"]}
        sch = self.make(plan_jobs(compat=False, val=False))
        sch.loop()
        st = json.load(open(sch.state_path))
        self.assertIsNone(st["gemini_stop"])
        self.assertEqual(st["jobs"]["dev_rest"]["status"], "done")
        self.assertEqual(len([e for e in self.events() if e["ev"] == "start"]), 10)  # the replacement ran despite the earlier attempt (other config sha)

    def test_tool_error_loop_and_integrity_failures_stop_gemini(self):
        tasks = S.Scheduler.class_tasks(self.make(plan_jobs()), "dev")
        self.loops.add(tasks[2])
        sch = self.make(plan_jobs(compat=False, val=False))
        sch.loop()
        st = json.load(open(sch.state_path))
        self.assertIn("tool-error loop", json.dumps(st["gemini_stop"]))
        self.loops.clear()
        self.tearDown(); self.setUp()
        self.outcomes[("dev", GEM, tasks[1])] = {"manifest_ok": False}
        sch = self.make(plan_jobs(compat=False, val=False))
        sch.loop()
        self.assertIn("manifest", json.dumps(json.load(open(sch.state_path))["gemini_stop"]))

    def test_candidate_policy_unchanged_message_limit_is_an_observation_rc_decides(self):
        self.outcomes[("compat", OPUS, "87da214f-fd92-4c58-9854-f4d0d10adce0")] = {"status": "limited", "limits": ["message"]}
        sch = self.make(plan_jobs(rep=False, dev=False, val=False))
        sch.loop()
        self.assertEqual(sorted(e["model"] for e in self.events() if e["ev"] == "start"), sorted([OPUS, GPT]))
        self.tearDown(); self.setUp()
        self.outcomes[("compat", OPUS, "87da214f-fd92-4c58-9854-f4d0d10adce0")] = {"rc": 3}
        sch = self.make(plan_jobs(rep=False, dev=False, val=False))
        sch.loop()
        st = json.load(open(sch.state_path))
        self.assertEqual([e["model"] for e in self.events() if e["ev"] == "start"], [OPUS])
        self.assertEqual(st["jobs"]["compat_gpt"]["status"], "blocked")

    def test_replacement_runs_at_most_once_per_config_and_stop_new_blocks_launches(self):
        sch = self.make(plan_jobs(compat=False, dev=False, val=False))
        sch.loop()
        self.assertEqual(len([e for e in self.events() if e["ev"] == "start"]), 1)
        os.remove(sch.state_path)  # even without the scheduler state, the inventory line under this config sha blocks a second run
        sch2 = self.make(plan_jobs(compat=False, dev=False, val=False))
        self.assertEqual(sch2.remaining_tasks(sch2.job("dev_replacement")), [])
        sch2.loop()
        self.assertEqual(len([e for e in self.events() if e["ev"] == "start"]), 1)
        self.tearDown(); self.setUp()
        sch3 = self.make(plan_jobs())
        open(os.path.join(sch3.dir, "stop_new"), "w").close()
        sch3.loop()
        self.assertEqual(self.events(), [])

    def test_restarted_scheduler_adopts_in_flight_units_without_relaunching(self):
        self.outcomes[("dev", GEM, B5)] = {"sleep": 2.0}
        self.outcomes[("compat", OPUS, "87da214f-fd92-4c58-9854-f4d0d10adce0")] = {"sleep": 2.0}
        a = self.make(plan_jobs())
        a.step()  # launches the replacement and compat Opus, then "crashes" (never polled again)
        self.assertEqual(sorted(a.running()), ["compat_opus", "dev_replacement"])
        import threading  # in production the dead scheduler's children are reparented to launchd, which reaps them
        for p in a.children.values():
            threading.Thread(target=p.wait, daemon=True).start()
        b = self.make(plan_jobs())  # new process view: same state directory, no child handles
        self.assertEqual(sorted(b.running()), ["compat_opus", "dev_replacement"])
        self.assertEqual(b.loop(), 0)
        starts = [(e["label"], e["model"], e["task"]) for e in self.events() if e["ev"] == "start"]
        self.assertEqual(len(starts), len(set(starts)))  # nothing launched twice
        self.assertEqual(starts.count(("dev", GEM, B5)), 1)
        st = json.load(open(b.state_path))
        self.assertTrue(st["jobs"]["dev_replacement"]["accepted"])
        self.assertEqual({n: s["status"] for n, s in st["jobs"].items()}, {"dev_replacement": "done", "compat_opus": "done", "dev_rest": "done", "compat_gpt": "done", "validation": "done"})
        self.assertEqual(st["jobs"]["dev_replacement"]["invocations"][0]["rc"], 0)  # read from the batch record

    def test_cap_one_override_serialises_all_classes(self):
        sch = self.make(plan_jobs(dev=False))
        open(os.path.join(sch.dir, "cap_override"), "w").write("1")
        sch.loop()
        self.assertEqual(self.max_concurrency()[0], 1)


class ResourceTrackerTests(unittest.TestCase):
    TOTAL = 8 << 30

    def s(self, mem, n=2, pressure=1, swap=0, oom=0):
        return {"containers": ["inspect-a", "inspect-b"][:n], "docker_mem_used": mem, "docker_vm_mem_total": self.TOTAL, "swap_used": swap, "pressure_level": pressure, "oom_events": oom}

    def run_overlap(self, tr, mem, seconds=1860, step=60, **kw):
        out, t = [], 1000.0
        for _ in range(int(seconds / step) + 1):
            out += tr.update(self.s(mem, **kw), active_units=2, t=t); t += step
        return out

    def test_raise_to_three_after_thirty_minutes_below_half(self):
        tr = S.ResourceTracker(cap=2)
        ev = self.run_overlap(tr, int(0.3 * self.TOTAL))
        self.assertEqual(tr.cap, 3); self.assertEqual(len(ev), 1); self.assertIn("raise to 3", ev[0]["decision"])

    def test_no_raise_before_thirty_minutes_or_without_overlap(self):
        tr = S.ResourceTracker(cap=2)
        self.run_overlap(tr, int(0.3 * self.TOTAL), seconds=1700)
        self.assertEqual(tr.cap, 2)
        tr = S.ResourceTracker(cap=2)
        self.run_overlap(tr, int(0.3 * self.TOTAL), n=1)  # one container: no actual overlap
        self.assertEqual((tr.cap, tr.overlap_s), (2, 0.0))

    def test_keep_two_on_high_peak_swap_growth_or_integrity(self):
        tr = S.ResourceTracker(cap=2)
        ev = self.run_overlap(tr, int(0.55 * self.TOTAL))
        self.assertEqual(tr.cap, 2); self.assertIn("keep 2", ev[-1]["decision"])
        tr = S.ResourceTracker(cap=2)
        t = 0.0
        for i in range(32):
            tr.update(self.s(int(0.3 * self.TOTAL), swap=i * 25 * S.MIB), active_units=2, t=t); t += 60  # 775 MiB: above the 512 MiB raise limit, below 1 GiB contention
        self.assertEqual((tr.cap, tr.contention, tr.evaluated), (2, False, True))
        tr = S.ResourceTracker(cap=2); tr.integrity_failures = 1
        self.run_overlap(tr, int(0.3 * self.TOTAL))
        self.assertEqual(tr.cap, 2)

    def test_contention_lowers_the_cap_once_per_episode_and_ends_raising(self):
        tr = S.ResourceTracker(cap=2)
        ev = tr.update(self.s(int(0.85 * self.TOTAL)), active_units=2, t=0)
        ev += tr.update(self.s(int(0.86 * self.TOTAL)), active_units=2, t=60)
        self.assertEqual((tr.cap, len(ev)), (1, 1))
        self.run_overlap(tr, int(0.3 * self.TOTAL))
        self.assertEqual(tr.cap, 1)  # no raise after contention
        tr = S.ResourceTracker(cap=3)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=1), active_units=2, t=0)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2), active_units=2, t=60)  # worsened from a normal baseline
        self.assertEqual(tr.cap, 2)
        tr = S.ResourceTracker(cap=2)
        tr.update(self.s(int(0.3 * self.TOTAL), oom=1), active_units=2, t=0)
        self.assertEqual(tr.cap, 1)

    def test_contention_is_relative_to_the_baseline(self):
        tr = S.ResourceTracker(cap=2)  # the host is already at warn before any unit: not contention; no raise either
        ev = self.run_overlap(tr, int(0.3 * self.TOTAL), pressure=2)
        self.assertEqual(tr.cap, 2); self.assertEqual(len(ev), 1); self.assertTrue(ev[0]["decision"].startswith("adaptive evaluation after 30 min of overlap"))
        self.assertIn("keep 2", ev[0]["decision"])
        tr = S.ResourceTracker(cap=2)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2), active_units=2, t=0)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=4), active_units=2, t=60)  # critical
        self.assertEqual(tr.cap, 1)
        tr = S.ResourceTracker(cap=2)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2, swap=8 << 30), active_units=2, t=0)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2, swap=(8 << 30) + 1100 * S.MIB), active_units=2, t=60)  # swap grew by more than 1 GiB
        self.assertEqual(tr.cap, 1)

    def test_operator_reset_restores_the_initial_cap_and_rebaselines(self):
        tr = S.ResourceTracker(cap=2)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=1), active_units=2, t=0)
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2), active_units=2, t=60)
        self.assertEqual((tr.cap, tr.contention), (1, True))
        d = tr.reset(2, "test")
        self.assertEqual((tr.cap, tr.contention, tr.pressure_baseline, d["cap_after"]), (2, False, None, 2))
        tr.update(self.s(int(0.3 * self.TOTAL), pressure=2), active_units=2, t=120)  # new baseline warn
        self.assertEqual(tr.cap, 2)

    def test_parse_size(self):
        self.assertEqual(S.parse_size("512MiB / 3GiB"), 512 * S.MIB)
        self.assertEqual(S.parse_size("1.5GiB"), int(1.5 * (1 << 30)))
        self.assertIsNone(S.parse_size("--"))


class GateTests(unittest.TestCase):
    def test_structural_check_on_good_and_bad_files(self):
        with tempfile.TemporaryDirectory() as d:
            import openpyxl
            good = os.path.join(d, "a.xlsx"); wb = openpyxl.Workbook(); wb.save(good)
            bad = os.path.join(d, "b.xlsx"); open(bad, "wb").write(b"not a zip")
            pdf = os.path.join(d, "c.pdf"); open(pdf, "wb").write(b"%PDF-1.4\n...\n%%EOF\n")
            badpdf = os.path.join(d, "d.pdf"); open(badpdf, "wb").write(b"hello")
            empty = os.path.join(d, "e.docx"); open(empty, "wb").close()
            self.assertTrue(G.structural_check(good)["ok"]); self.assertFalse(G.structural_check(bad)["ok"])
            self.assertTrue(G.structural_check(pdf)["ok"]); self.assertFalse(G.structural_check(badpdf)["ok"])
            self.assertFalse(G.structural_check(empty)["ok"])
            self.assertNotIn("a.xlsx", json.dumps(G.structural_check(good)))  # no file name in the verdict

    def test_unit_without_record_or_outcome_is_a_stop(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(G.evaluate_unit(d, None, gemini=True)["decision"], "stop")
            r = G.evaluate_unit(d, {"kind": "sample", "run_uuid": "X"}, gemini=True)
            self.assertEqual(r["decision"], "stop"); self.assertIn("outcome unknown", " ".join(r["reasons"]))
            self.assertEqual(G.evaluate_unit(d, {"kind": "sample_error", "engineering_failure": "RetryError", "run_uuid": "X"}, gemini=True)["decision"], "stop")


if __name__ == "__main__":
    unittest.main()


class RealBatchArgvTests(_Base):
    """The scheduler's real launch line: caffeinate -i, the project interpreter, harness.batch with one task, the batch
    restatement the batch runner accepts, --allow-repeat only on the replacement; run as a batch dry run on the real
    config (paths, label, model and task-set checks) with a fake docker runner."""

    def test_argv_is_accepted_by_the_batch_runner(self):
        from decimal import Decimal
        from types import SimpleNamespace
        from harness import batch as B
        plan = {"name": "argv", "base": self.base, "config": CONFIG, "authorized_by": "test", "authorization_ref": "test", "jobs": plan_jobs(), "env_file": os.path.join(self.tmp.name, "env.test")}
        with open(plan["env_file"], "w") as f:
            f.write("GOOGLE_API_KEY=dummy-test-key-not-real-0009\nANTHROPIC_API_KEY=dummy-test-key-not-real-0010\nOPENAI_API_KEY=dummy-test-key-not-real-0011\n")
        sch = S.Scheduler(plan)
        cfg = L.load_config(CONFIG); image_id = cfg["sandbox"]["image_id"]
        docker = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=f"{image_id}|arm64|linux|[]\n", stderr="")
        for name, task in (("dev_replacement", B5), ("compat_opus", "87da214f-fd92-4c58-9854-f4d0d10adce0"), ("compat_gpt", "87da214f-fd92-4c58-9854-f4d0d10adce0"),
                           ("dev_rest", sch.class_tasks("dev")[1]), ("validation", B5)):
            j = sch.job(name)
            argv = sch._batch_argv(j, task)
            self.assertEqual(argv[:2], ["caffeinate", "-i"])
            self.assertTrue(argv[2].endswith(os.path.join(".venv", "bin", "python")))
            mod = argv[argv.index("harness.batch") + 1:]
            val = lambda flag: mod[mod.index(flag) + 1]
            self.assertEqual((val("--run-label"), val("--model"), val("--tasks"), val("--config")), (j["label"], j["model"], task, CONFIG))
            self.assertEqual("--allow-repeat" in mod, bool(j.get("replacement")))
            B.parse_confirm_batch(val("--confirm-batch"), run_label=j["label"], model=j["model"], units=1, estimate_usd=Decimal(j["estimate"]))
            self.assertEqual(Decimal(j["estimate"]), Decimal(str(cfg["batches"][j["label"]]["reservation_usd_by_model"][j["model"]])))
            dry = [a for a in mod if a not in ("--real-run",)]
            for flag in ("--confirm-batch", "--authorized-by", "--authorization-ref"):
                i = dry.index(flag); del dry[i:i + 2]
            self.assertEqual(B.main(dry + ["--dry-run"], docker_runner=docker), 0, name)
        self.assertTrue(os.path.exists(os.path.join(self.base, "dev", "runs", "run_inventory.jsonl")))
