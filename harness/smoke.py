"""Toolchain smoke tests through the real Inspect Task + docker sandbox path, with mockllm issuing
scripted tool calls that Inspect dispatches to the tools. No paid model is involved:
INSPECT_DISABLE_MODEL_API=1 is set before Inspect loads (every provider except mockllm raises), and
inherited credential-like variables are removed from the process, and dummy credentials are placed
in the harness process environment so the in-sandbox probe can show that they do not leak. The probe
reports presence and counts only; no environment value is ever printed.
Usage: .venv/bin/python -m harness.smoke [normal|pivot|resources|tool_timeout|sample_timeout|all] [--keep]
Run it through harness/tests/run_isolated.sh so that no .env can be loaded from the working directory."""
import datetime as dt
import glob
import json
import os
import re
import sys

os.environ["INSPECT_DISABLE_MODEL_API"] = "1"
CREDENTIAL_NAME_RE = re.compile(r"(_API_KEY$|_TOKEN$|SECRET|PASSWORD|^ANTHROPIC_|^OPENAI_|^HF_|^AZURE_|^GOOGLE_|^AWS_|^MISTRAL_|^TOGETHER_|^GROQ_)", re.I)


def scrub_inherited_credentials() -> int:
    """Remove any inherited credential-like variable from this process before Inspect loads.
    Only the count is reported; names and values are never printed."""
    names = [k for k in os.environ if CREDENTIAL_NAME_RE.search(k)]
    for k in names:
        del os.environ[k]
    return len(names)


SCRUBBED = scrub_inherited_credentials()
DUMMY_CREDS = {"ANTHROPIC_API_KEY": "dummy-test-key-not-real-0001", "OPENAI_API_KEY": "dummy-test-key-not-real-0002",
               "HF_TOKEN": "dummy-test-key-not-real-0003"}
os.environ.update(DUMMY_CREDS)

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ModelOutput, get_model  # noqa: E402

from .task import make_task  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIX = os.path.join(HERE, "fixtures")
LOG_DIR = os.path.join(ROOT, "logs", "stage2", "inspect")
RUN_ROOT = os.path.join(ROOT, "logs", "stage2", "runs")
M = "mockllm/model"
FIXTURE_NAMES = ["notes.txt", "sample.png", "sample_formulas.xlsx", "sample_doc.docx", "sample_deck.pptx", "sample.pdf", "pivot_src.xlsx", "pivot_uno.py"]


def fixture_files() -> dict[str, str]:
    return {f"/workspace/inputs/{n}": os.path.join(FIX, n) for n in FIXTURE_NAMES}


def tc(tool: str, **args) -> ModelOutput:
    return ModelOutput.for_tool_call(M, tool, args)


def done(msg: str = "done") -> ModelOutput:
    return ModelOutput.from_content(M, msg)


PROBE_FS = r'''
echo "== id: $(id)  cwd: $(pwd)"
for p in /Users /Users/yuning /host /mnt/host /private/gold /private/rubric /workspace/private /workspace/preregistration.md /workspace/plan /data/gdpval.parquet /workspace/gdpval.parquet /workspace/scripts /workspace/harness /root/.env /workspace/.env /run/secrets; do
  if [ -e "$p" ]; then echo "EXISTS $p"; else echo "absent $p"; fi
done
echo "== filesystem search for evaluation material:"
find / -xdev \( -name '*.parquet' -o -name 'preregistration.md' -o -name 'plan.md' -o -path '*/private/gold/*' -o -path '*/private/rubric/*' -o -name 'rubric_*.json' -o -name '.env' \) 2>/dev/null | grep -v -E '^/(proc|sys)/|site-packages' | head -20
echo "(search done)"
echo "== mounts (non-virtual):"
grep -v -E ' (proc|sysfs|tmpfs|cgroup2?|devpts|mqueue|overlay|devtmpfs|shm|fusectl|securityfs) ' /proc/mounts | awk '{print $1, $2, $3}'
echo "== credential check (presence only; no variable values are printed):"
for v in ANTHROPIC_API_KEY OPENAI_API_KEY HF_TOKEN; do if [ -n "${!v+x}" ]; then echo "$v: PRESENT"; else echo "$v: absent"; fi; done
echo "dummy sentinel occurrences in environment values: $(env | grep -c 'dummy-test-key' || true)"
echo "environment values matching known key prefixes: $(env | cut -d= -f2- | grep -c -E '^(sk-|sk-ant-|hf_|AKIA|AIza|ghp_|gho_|xox[baprs]-)' || true)"
echo "== capabilities:"; grep -E 'Cap(Eff|Bnd)' /proc/self/status
echo "== workspace and output trees:"; find /workspace /output -maxdepth 3 | sort
echo "== staged file content:"; cat /workspace/inputs/notes.txt
'''
PROBE_NET = r'''
python3 - <<'PY'
import socket
for host, port in [("1.1.1.1", 53), ("8.8.8.8", 443)]:
    s = socket.socket(); s.settimeout(3)
    try:
        s.connect((host, port)); print("NET OPEN", host, port)
    except Exception as e:
        print("NET BLOCKED", host, port, type(e).__name__)
try:
    print("DNS RESOLVED", socket.gethostbyname("huggingface.co"))
except Exception as e:
    print("DNS BLOCKED", type(e).__name__)
PY
echo "== interfaces:"; tail -n +3 /proc/net/dev | awk '{print $1}'
'''
PY_WRITE = r'''
import os, openpyxl
from docx import Document
os.makedirs("/output/final", exist_ok=True)
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "out"
ws.append(["a", "b", "sum"]); ws.append([2, 3, "=A2+B2"]); wb.save("/output/final/smoke_out.xlsx")
d = Document(); d.add_heading("Smoke output", 1); d.add_paragraph("written inside the sandbox"); d.save("/output/final/smoke_out.docx")
f = openpyxl.load_workbook("/workspace/inputs/sample_formulas.xlsx").active
v = openpyxl.load_workbook("/workspace/inputs/sample_formulas.xlsx", data_only=True).active
print("staged xlsx: C5 formula =", f["C5"].value, "| C5 cached value =", v["C5"].value, "| E2 literal =", v["E2"].value)
print("output files:", sorted(os.listdir("/output/final")))
'''
SOFFICE_PDF = r'''
timeout 170 soffice --headless --norestore --convert-to pdf --outdir /output/final /output/final/smoke_out.docx 2>&1 | tail -1
ls -la /output/final
python3 -c "import pymupdf; d=pymupdf.open('/output/final/smoke_out.pdf'); print('pdf pages', d.page_count, '| text:', d[0].get_text().strip()[:60])"
'''
SOFFICE_RECALC = r'''
mkdir -p /tmp/recalc && cp /workspace/inputs/sample_formulas.xlsx /tmp/recalc/in.xlsx
timeout 170 soffice --headless --norestore --convert-to 'xlsx:Calc MS Excel 2007 XML' --outdir /tmp/recalc/out /tmp/recalc/in.xlsx 2>&1 | tail -1
python3 -c "
import openpyxl
f = openpyxl.load_workbook('/tmp/recalc/out/in.xlsx').active
v = openpyxl.load_workbook('/tmp/recalc/out/in.xlsx', data_only=True).active
print('after LibreOffice recalculation: C5 formula =', f['C5'].value, '| C5 cached =', v['C5'].value, '| C2 cached =', v['C2'].value, '| E2 =', v['E2'].value)"
'''


def scenario_normal():
    return [
        tc("bash", command=PROBE_FS),
        tc("bash", command=PROBE_NET),
        tc("python", code=PY_WRITE),
        tc("bash", command=SOFFICE_PDF),
        tc("bash", command=SOFFICE_RECALC),
        tc("view_image", path="/workspace/inputs/sample.png"),
        tc("render_document", path="/workspace/inputs/sample_deck.pptx", page=1),
        tc("render_document", path="/output/final/smoke_out.docx", page=1),
        tc("render_document", path="inputs/sample.pdf", page=2),
        tc("render_document", path="/workspace/inputs/sample_formulas.xlsx", page=1),
        tc("view_image", path="/workspace/private/secret.png"),
        tc("view_image", path="/Users/yuning/turing-th/harness/fixtures/sample.png"),
        tc("render_document", path="/Users/yuning/turing-th/README.md", page=1),
        done("Smoke run complete."),
    ]


def scenario_tool_timeout():
    return [
        tc("bash", command="echo start; sleep 20; echo late"),
        tc("bash", command="echo still-alive-after-tool-timeout; ls /output/final"),
        done("Tool timeout scenario complete."),
    ]


def scenario_sample_timeout():
    return [
        tc("bash", command="mkdir -p /output/final && echo early-file > /output/final/early.txt && sleep 120 && echo late"),
        tc("bash", command="echo should-not-run"),
        done("should not be reached"),
    ]


PROBE_RESOURCES = r'''
echo "== staged tree:"; find /workspace -type f | sort | sed 's#^/workspace/##' | head -40
echo "== counts: inputs=$(ls /workspace/inputs | wc -l) pages=$(ls /workspace/resources/pages | wc -l) icons=$(ls /workspace/resources/icons | wc -l)"
echo "== zip hashes:"; sha256sum /workspace/resources/icons/*.zip
echo "== unzip category pack:"; mkdir -p /tmp/icons && unzip -q -o /workspace/resources/icons/category-icons.zip -d /tmp/icons && echo "svg=$(find /tmp/icons -name '*.svg' | wc -l) png=$(find /tmp/icons -name '*.png' | wc -l)"
echo "== page text head:"; head -c 300 /workspace/resources/pages/06_cloud_google_com_cdn.txt; echo
echo "== html size:"; stat -c '%s %n' /workspace/resources/pages/06_cloud_google_com_cdn.html
echo "== pdf input readable:"; python3 -c "import pymupdf; d=pymupdf.open('/workspace/inputs/Current_Architecture.pdf'); print('pages', d.page_count, 'chars', len(d[0].get_text()))"
echo "== docx input readable:"; python3 -c "import docx; d=docx.Document('/workspace/inputs/Current_Architecture_Summary.docx'); print('paragraphs', len(d.paragraphs))"
'''


PIVOT_CMD = ("/usr/bin/python3 /workspace/inputs/pivot_uno.py /workspace/inputs/pivot_src.xlsx /output/final/pivot_out.xlsx 2>&1 | grep -v javaldx | head -8; "
             "python3 -c \"import openpyxl; wb=openpyxl.load_workbook('/output/final/pivot_out.xlsx'); ws=wb['Pivot']; pt=ws._pivots[0]; "
             "print('pivot', pt.name, 'source', pt.cache.cacheSource.worksheetSource.sheet, pt.cache.cacheSource.worksheetSource.ref, 'dataFields', [(d.name, d.subtotal) for d in pt.dataFields])\"")


def scenario_pivot():
    return [tc("bash", command=PIVOT_CMD), done("Pivot scenario complete.")]


def scenario_resources():
    return [tc("bash", command=PROBE_RESOURCES), done("Resources scenario complete.")]


def _result_text(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts = []
        for c in result:
            t = getattr(c, "type", None)
            if t == "text":
                parts.append(c.text)
            elif t == "image":
                parts.append(f"<image {len(c.image)} chars base64>")
            else:
                parts.append(f"<{t}>")
        return "\n".join(parts)
    return str(result)


def run(name: str, outputs, tool_timeout: int = 600, time_limit: int | None = None, keep: bool = False,
        samples: list[Sample] | None = None) -> dict:
    runs_root = os.path.join(RUN_ROOT, name)
    samples = samples or [Sample(id=f"smoke-{name}", input="Run the scripted smoke test.", files=fixture_files())]
    task, run_dir = make_task(samples, runs_root, tool_timeout=tool_timeout, time_limit=time_limit, name=f"smoke_{name}")
    model = get_model(M, custom_outputs=outputs)
    logs = inspect_eval(task, model=model, log_dir=LOG_DIR, display="plain", log_level="warning",
                        sandbox_cleanup=not keep, log_images=True, sandbox_prebuilt=True, task_retry_attempts=0)
    log = logs[0]
    s = log.samples[0] if log.samples else None
    run_dir = os.path.join(run_dir, s.uuid) if s else run_dir
    summary = {"scenario": name, "status": log.status, "eval_model": log.eval.model, "log_file": log.location, "run_dir": run_dir,
               "scrubbed_inherited_credential_vars": SCRUBBED,
               "eval_error": log.error.message[:300] if log.error else None, "tool_timeout": tool_timeout, "time_limit": time_limit}
    print(f"\n######## scenario {name}: status={log.status} model={log.eval.model} log={log.location}")
    if s:
        tool_events = [e for e in s.events if e.event == "tool"]
        model_events = [e for e in s.events if e.event == "model"]
        summary.update({"sample_limit": s.limit.type if s.limit else None, "sample_error": s.error.message[:300] if s.error else None,
                        "model_events": len(model_events), "tool_events": [],
                        "scores": {k: {"unscored": True, "provisional": True, "answer": v.answer} for k, v in (s.scores or {}).items()}})
        print(f"sample limit={summary['sample_limit']} error={summary['sample_error']} model_events={len(model_events)} tool_events={len(tool_events)}")
        for e in tool_events:
            err = e.error.message if e.error else None
            text = _result_text(e.result)
            summary["tool_events"].append({"function": e.function,
                                           "arguments": {k: (v if len(str(v)) < 120 else str(v)[:120] + "…") for k, v in (e.arguments or {}).items()},
                                           "error": err, "result_excerpt": text[:3000]})
            print(f"\n--- tool event: {e.function}  error={err!r}")
            print(text[:3000])
        print("scores:", summary["scores"])
    cjs = glob.glob(os.path.join(run_dir, "**", "collection.json"), recursive=True)
    summary["collection_files"] = []
    for cj in cjs:
        with open(cj, encoding="utf-8") as f:
            info = json.load(f)
        summary["collection_files"].append({"path": cj, "status": info["status"], "harness_error": info["harness_error"],
                                            "file_count": info["file_count"], "passes": [p["note"] for p in info["passes"]],
                                            "files": [(f["sandbox_path"], f.get("size"), f["status"], f.get("reason")) for f in info["files"]],
                                            "skipped": info["skipped"], "rejected": info["rejected"]})
    print("collection:", json.dumps(summary["collection_files"], indent=1))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(os.path.join(run_dir, f"summary_{stamp}.json"), "x", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keep = "--keep" in sys.argv
    if which in ("normal", "all"):
        run("normal", scenario_normal(), keep=keep)
    if which in ("pivot", "all"):
        run("pivot", scenario_pivot(), tool_timeout=300)
    if which in ("resources", "all"):
        from .samples import build_samples
        run("resources", scenario_resources(), samples=build_samples(["a45bc83b-22f9-4def-8d89-9c5661b2b86f"]))
    if which in ("tool_timeout", "all"):
        run("tool_timeout", scenario_tool_timeout(), tool_timeout=5)
    if which in ("sample_timeout", "all"):
        run("sample_timeout", scenario_sample_timeout(), tool_timeout=600, time_limit=25)


if __name__ == "__main__":
    main()
