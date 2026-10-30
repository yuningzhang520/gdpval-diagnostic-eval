"""I2 regression through the real Inspect Task + docker sandbox chain with mockllm: images are
created inside the sandbox (valid copy, random bytes named .png, JPEG bytes named .png, a
9000x9000 1-bit PNG, a file over the byte limit) and `view_image` must return an image only for
the valid one and a specific ToolError otherwise. Usage (isolated launcher):
  harness/tests/run_isolated.sh <root> harness.tests.regress_tools --output-root <new dir>"""
import argparse
import json
import os
from pathlib import Path

assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1", "use run_isolated.sh"
from harness.smoke import M, done, fixture_files, tc  # noqa: E402

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402

from harness.task import make_task  # noqa: E402

MAKE_IMAGES = r'''
set -e
mkdir -p /tmp/img
cp /workspace/inputs/sample.png /tmp/img/good.png
head -c 4000 /dev/urandom > /tmp/img/random.png
python3 - <<'PY'
from PIL import Image
Image.new("RGB", (20, 10), (10, 200, 10)).save("/tmp/img/jpeg_named_png.png", format="JPEG")
Image.new("1", (9000, 9000), 1).save("/tmp/img/huge.png", format="PNG")
with open("/tmp/img/good.png", "rb") as f: data = f.read()
open("/tmp/img/truncated.png", "wb").write(data[: len(data) // 2])
PY
head -c 8500000 /dev/zero > /tmp/img/big.png
ls -la /tmp/img
'''


def has_image(result) -> bool:
    return isinstance(result, list) and any(getattr(c, "type", None) == "image" for c in result)


def main():
    p = argparse.ArgumentParser(); p.add_argument("--output-root", required=True); args = p.parse_args()
    root = Path(args.output_root); root.mkdir(parents=True, exist_ok=False)
    outputs = [tc("bash", command=MAKE_IMAGES),
               tc("view_image", path="/tmp/img/good.png"), tc("view_image", path="/tmp/img/random.png"),
               tc("view_image", path="/tmp/img/jpeg_named_png.png"), tc("view_image", path="/tmp/img/huge.png"),
               tc("view_image", path="/tmp/img/truncated.png"), tc("view_image", path="/tmp/img/big.png"),
               tc("render_document", path="/workspace/inputs/sample.pdf", page=1), done()]
    task, runs = make_task([Sample(id="regress-tools", input="Run the image tool regression.", files=fixture_files())], str(root / "runs"), name="regress_tools")
    log = inspect_eval(task, model=get_model(M, custom_outputs=outputs), log_dir=str(root / "inspect"), sandbox_prebuilt=True, sandbox_cleanup=True,
                       display="plain", log_level="warning", max_samples=1, max_tasks=1, task_retry_attempts=0)[0]
    ev = [e for e in log.samples[0].events if e.event == "tool"]
    checks = []
    def check(name, ok, detail=None):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:300] if detail is not None else None})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:160]}" if detail is not None and not ok else ""))
    check("8 tool events (1 bash, 6 view_image, 1 render_document), image setup succeeded", len(ev) == 8 and ev[0].error is None, (len(ev), ev[0].error and ev[0].error.message))
    check("valid PNG returns an image with decoded dimensions", ev[1].error is None and has_image(ev[1].result) and "PNG" in str(ev[1].result[0].text), ev[1].error and ev[1].error.message)
    expect = {2: "could not be decoded", 3: "does not match", 4: "pixels", 5: "could not be decoded", 6: "limit is"}
    for i, needle in expect.items():
        e = ev[i]
        check(f"{e.arguments.get('path')} refused with '{needle}' and no image", e.error is not None and needle in e.error.message and not has_image(e.result), e.error and e.error.message)
    check("render_document still returns a validated PNG", ev[7].error is None and has_image(ev[7].result), ev[7].error and ev[7].error.message)
    (root / "results.json").write_text(json.dumps({"log": log.location, "checks": checks}, indent=1))
    failed = [c for c in checks if c["result"] != "PASS"]
    print(f"==== TOOLS {len(checks) - len(failed)} PASS, {len(failed)} FAIL; results {root / 'results.json'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
