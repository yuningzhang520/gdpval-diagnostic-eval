"""Redaction of persisted error text (launcher records, ledger failure details, grading results,
provider model-list errors). Keeps only what a record needs: credential-like strings, key=value
secrets, any long token that carries a digit (opaque identifiers and key fragments) and the user
name in host paths are replaced; the result is truncated. The full message stays only in the
Inspect log / process output, never in harness or grading records."""
import re

KEY_PATTERNS = [re.compile(p) for p in (r"sk-ant-[A-Za-z0-9_-]{8,}", r"sk-[A-Za-z0-9_-]{16,}", r"AIza[0-9A-Za-z_-]{20,}", r"hf_[A-Za-z0-9]{16,}",
                                         r"AKIA[0-9A-Z]{12,}", r"ghp_[A-Za-z0-9]{16,}", r"xox[baprs]-[A-Za-z0-9-]{10,}", r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}",
                                         r"(?i)\b(api[_-]?key|token|secret|password|authorization)\b\s*[=:]\s*\S+", r"\b[A-Za-z0-9+/_-]{40,}\b",
                                         r"(?=[^\s'\"]*\d)[^\s'\"]{20,}")]
PATH_USER = re.compile(r"(/(?:Users|home)/)[^/\s'\"]+")


def redact(text, limit: int = 300) -> str:
    s = str(text)
    for p in KEY_PATTERNS:
        s = p.sub("<redacted>", s)
    s = PATH_USER.sub(r"\1<user>", s)
    return s[:limit]


def redact_path(path, limit: int = 300) -> str | None:
    """A host path with the user name removed (file names stay identifiable); None stays None."""
    if path is None:
        return None
    return PATH_USER.sub(r"\1<user>", str(path))[:limit]
