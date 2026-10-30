"""Model-callable tools. Every file access goes through the current sample's sandbox
(sandbox().exec / sandbox().read_file); nothing here opens a host path."""
import base64
import json
import posixpath
import shlex

from inspect_ai.model import ContentImage, ContentText
from inspect_ai.tool import ToolError, tool
from inspect_ai.util import sandbox

MAX_IMAGE_BYTES = 8_000_000
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RENDER_TMP_PREFIX = "/tmp/render_"

# Runs inside the sandbox. Each call converts into its own fresh temporary directory, checks the
# converter's exit status, requires a new non-empty PDF that opens and has at least one page, and
# removes the directory itself on every failure. On success the directory is left for the host to
# read the PNG from; the host removes it afterwards. There is no earlier PDF or image to fall back on.
RENDER_SCRIPT = r'''
import json, os, shutil, subprocess, sys, tempfile
path, page = sys.argv[1], int(sys.argv[2])
def fail(msg, **kw):
    print(json.dumps({"error": msg, **kw})); sys.exit(0)
if not os.path.isfile(path):
    fail(f"not a file: {path}")
if os.path.getsize(path) == 0:
    fail(f"file is empty: {path}")
ext = os.path.splitext(path)[1].lower()
work = tempfile.mkdtemp(prefix="render_", dir="/tmp")
ok = False
try:
    if ext == ".pdf":
        pdf = path
    else:
        expected = os.path.join(work, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        try:
            r = subprocess.run(["soffice", "--headless", "--norestore", "--convert-to", "pdf", "--outdir", work, path],
                               capture_output=True, text=True, timeout=170)
        except subprocess.TimeoutExpired:
            fail("conversion timed out after 170 s")
        if r.returncode != 0:
            fail(f"conversion command exited with status {r.returncode}", stderr=r.stderr[-500:])
        if not os.path.isfile(expected):
            fail("conversion produced no PDF", stdout=r.stdout[-300:], stderr=r.stderr[-500:])
        if os.path.getsize(expected) == 0:
            fail("conversion produced an empty PDF")
        pdf = expected
    import pymupdf
    try:
        doc = pymupdf.open(pdf)
        n = doc.page_count
    except Exception as ex:
        fail(f"PDF could not be opened: {type(ex).__name__}: {str(ex)[:200]}")
    if n < 1:
        fail("PDF has no pages")
    if page < 1 or page > n:
        fail(f"page {page} out of range 1..{n}", pages=n)
    out = os.path.join(work, f"page{page}.png")
    try:
        doc[page - 1].get_pixmap(dpi=110).save(out)
    except Exception as ex:
        fail(f"page could not be rendered: {type(ex).__name__}: {str(ex)[:200]}")
    if not os.path.isfile(out) or os.path.getsize(out) == 0:
        fail("rendering produced no image")
    ok = True
    print(json.dumps({"png": out, "pages": n, "work": work}))
finally:
    if not ok:
        shutil.rmtree(work, ignore_errors=True)
'''


def _norm(path: str) -> str:
    if not path.startswith("/"):
        path = posixpath.join("/workspace", path)
    return posixpath.normpath(path)


@tool
def view_image():
    async def execute(path: str):
        """View an image file (PNG, JPEG, GIF or WEBP) that exists inside your sandbox.

        Args:
            path: Path of the image inside the sandbox, absolute or relative to /workspace.
        """
        p = _norm(path)
        ext = posixpath.splitext(p)[1].lower()
        if ext not in MIME:
            raise ToolError(f"unsupported image type {ext!r}; use png, jpg, gif or webp")
        res = await sandbox().exec(["bash", "-c", f"test -f {shlex.quote(p)} && stat -c %s {shlex.quote(p)}"], timeout=30)
        if not res.success:
            raise ToolError(f"no such file in the sandbox: {p}")
        size = int(res.stdout.strip() or 0)
        if size > MAX_IMAGE_BYTES:
            raise ToolError(f"image is {size} bytes; limit is {MAX_IMAGE_BYTES}")
        data = await sandbox().read_file(p, text=False)
        b64 = base64.b64encode(data).decode("ascii")
        return [ContentText(text=f"{p} ({len(data)} bytes)"), ContentImage(image=f"data:{MIME[ext]};base64,{b64}")]
    return execute


async def _remove_render_dir(work: str) -> None:
    if isinstance(work, str) and work.startswith(RENDER_TMP_PREFIX) and "/" not in work[len(RENDER_TMP_PREFIX):]:
        try:
            await sandbox().exec(["rm", "-rf", work], timeout=30)
        except Exception:
            pass


@tool
def render_document():
    async def execute(path: str, page: int = 1):
        """Render one page of a PDF, DOCX, PPTX or XLSX file inside your sandbox to an image so you can check how it looks. Office files are converted to PDF with LibreOffice inside the sandbox first.

        Args:
            path: Path of the document inside the sandbox, absolute or relative to /workspace.
            page: 1-based page (or slide) number to render.
        """
        p = _norm(path)
        res = await sandbox().exec(["python3", "-c", RENDER_SCRIPT, p, str(page)], timeout=180)
        if not res.success:
            raise ToolError(f"render failed: {res.stderr[-800:]}")
        try:
            info = json.loads(res.stdout.strip().splitlines()[-1])
        except Exception:
            raise ToolError(f"render produced no result: {res.stdout[-800:]}")
        if "error" in info:
            detail = " ".join(str(info[k])[-500:] for k in ("stdout", "stderr") if info.get(k))
            raise ToolError(f"render failed: {info['error']}" + (f" ({detail})" if detail else ""))
        work = info.get("work")
        try:
            png = info.get("png")
            if not (isinstance(png, str) and isinstance(work, str) and png.startswith(work + "/")):
                raise ToolError("render failed: converter returned an unexpected output location")
            try:
                data = await sandbox().read_file(png, text=False)
            except Exception as ex:
                raise ToolError(f"render failed: rendered image could not be read ({type(ex).__name__})")
            if not data or not data.startswith(PNG_SIGNATURE):
                raise ToolError("render failed: rendered image is empty or not a PNG")
            if len(data) > MAX_IMAGE_BYTES:
                raise ToolError(f"render failed: rendered image is {len(data)} bytes; limit is {MAX_IMAGE_BYTES}")
            b64 = base64.b64encode(data).decode("ascii")
            return [ContentText(text=f"{p}: page {page} of {info['pages']}"), ContentImage(image=f"data:image/png;base64,{b64}")]
        finally:
            await _remove_render_dir(work)
    return execute
