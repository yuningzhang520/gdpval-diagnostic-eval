"""List the models visible to each provider key (no generation, no paid call).

Loads credentials from the project .env into this trusted process only (variable names are
recorded, values never printed), queries the models-list endpoint of Anthropic, OpenAI and
Google with full pagination, and writes data/provider_model_lists/<UTC stamp>.json with the exact
ids, SDK versions, request and page counts, completeness, errors (a provider with an auth,
rate-limit or pagination error is recorded as partial, never as a complete list) and the
visibility of the candidate ids. A model's presence in the list proves visibility for this key
only, not generation, tool use, image input or reasoning-parameter availability.
Usage: .venv/bin/python scripts/list_provider_models.py [--env .env] [--out data/provider_model_lists]
"""
import argparse
import datetime as dt
import importlib.metadata as md
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
CANDIDATES = {"anthropic": ["claude-opus-5-5", "claude-sonnet-5-5"], "openai": ["gpt-6.1-sol"], "google": ["gemini-3.1-pro-preview"]}
KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}


def load_env(path: str) -> list[str]:
    names = []
    if not os.path.isfile(path):
        return names
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = ENV_LINE.match(line)
            if not m or line.lstrip().startswith("#"):
                continue
            k, v = m.group(1), m.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            os.environ.setdefault(k, v)
            names.append(k)
    return names


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


sys.path.insert(0, ROOT)
from harness.redact import redact  # noqa: E402  (one redaction rule for every persisted error text)


def list_anthropic(record: dict) -> None:
    import anthropic
    record["sdk"] = f"anthropic {anthropic.__version__}"
    client = anthropic.Anthropic(max_retries=0)
    ids, pages, requests = [], 0, 0
    page = client.models.list(limit=100)
    requests += 1
    while True:
        pages += 1
        ids.extend(m.id for m in page.data)
        if not page.has_next_page():
            break
        page = page.get_next_page()
        requests += 1
    record.update({"ids": ids, "pages": pages, "requests": requests, "complete": True, "pagination": "cursor (after_id), page size 100"})


def list_openai(record: dict) -> None:
    import openai
    record["sdk"] = f"openai {openai.__version__}"
    client = openai.OpenAI(max_retries=0)
    ids, pages, requests = [], 0, 0
    page = client.models.list()
    requests += 1
    while True:
        pages += 1
        ids.extend(m.id for m in page.data)
        if not getattr(page, "has_next_page", lambda: False)():
            break
        page = page.get_next_page()
        requests += 1
    record.update({"ids": ids, "pages": pages, "requests": requests, "complete": True,
                   "pagination": "list endpoint returns one page; SDK reported no further page"})


def list_google(record: dict) -> None:
    from google import genai
    record["sdk"] = f"google-genai {md.version('google-genai')}"
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    ids, pages, requests = [], 0, 0
    pager = client.models.list(config={"page_size": 100})
    requests += 1
    while True:
        pages += 1
        ids.extend(m.name for m in pager.page)
        try:
            pager.next_page()
            requests += 1
        except IndexError:  # google-genai raises IndexError when no further page exists
            break
    record.update({"ids": ids, "pages": pages, "requests": requests, "complete": True, "pagination": "page token, page size 100; ids carry the 'models/' prefix"})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, ".env"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "provider_model_lists"))
    args = ap.parse_args()
    names = load_env(args.env)
    result = {"queried_at_utc": now(), "env_file_present": os.path.isfile(args.env), "env_variable_names": names,
              "note": "models-list only; no generation; presence proves visibility for this key only", "providers": {}}
    for provider, fn in (("anthropic", list_anthropic), ("openai", list_openai), ("google", list_google)):
        rec = {"key_variable": KEYS[provider], "key_present": bool(os.environ.get(KEYS[provider])), "started_at": now(),
               "ids": [], "pages": 0, "requests": 0, "complete": False, "error": None}
        if not rec["key_present"]:
            rec["error"] = "skipped: key variable absent"
        else:
            t0 = time.monotonic()
            try:
                fn(rec)
            except Exception as ex:  # auth, rate limit, pagination: partial, never complete
                rec["error"] = f"{type(ex).__name__}: {redact(str(ex))}"
                rec["complete"] = False
            rec["elapsed_s"] = round(time.monotonic() - t0, 2)
        rec["finished_at"] = now()
        rec["count"] = len(rec["ids"])
        rec["candidates"] = {c: any(i == c or i == f"models/{c}" or i.startswith(c + "-") for i in rec["ids"]) for c in CANDIDATES[provider]}
        result["providers"][provider] = rec
    os.makedirs(args.out, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(args.out, f"{stamp}.json")
    with open(path, "x", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    for p, rec in result["providers"].items():
        print(f"{p}: key_present={rec['key_present']} count={rec['count']} pages={rec['pages']} requests={rec['requests']} complete={rec['complete']} error={rec['error']} candidates={rec['candidates']}")
    print("written:", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
