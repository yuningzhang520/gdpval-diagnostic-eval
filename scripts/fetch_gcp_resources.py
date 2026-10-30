#!/usr/bin/env python
"""Fetch the official Google Cloud pages and icon pack listed in one task's prompt,
so they can be pre-staged offline for both models. Records URL, fetch time, final
URL after redirects, HTTP status, content type, size and sha256 for every item,
and performs readability checks (real article text, not a login/error shell).

Nothing is summarised or rewritten: raw bodies are kept verbatim; the .txt files
are derived text extractions for local inspection only.

Usage:
    python scripts/fetch_gcp_resources.py --parquet data/gdpval.parquet \
        --task-id a45bc83b-22f9-4def-8d89-9c5661b2b86f --out-dir data/resources
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import zipfile
from collections import Counter
from urllib.parse import urljoin, urlparse

import pyarrow.parquet as pq
import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+")
BAD_TITLE = re.compile(r"sign in|log in|404|not found|error|access denied", re.I)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def slug(url: str) -> str:
    p = urlparse(url)
    s = (p.netloc + p.path).strip("/").replace("/", "_").replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_-]+", "-", s)[:80] or "root"


def extract_text(html: bytes):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--out-dir", default="data/resources")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    rows = [r for r in pq.read_table(args.parquet, columns=["task_id", "prompt"]).to_pylist()
            if r["task_id"] == args.task_id]
    if len(rows) != 1:
        print("ERROR: task id not found exactly once", file=sys.stderr)
        return 2
    prompt = rows[0]["prompt"]
    urls = []
    for u in URL_RE.findall(prompt):
        u = u.rstrip(".,;:")
        if u not in urls:
            urls.append(u)
    print(f"{len(urls)} URLs listed in the prompt")

    base = os.path.join(args.out_dir, args.task_id)
    pages_dir = os.path.join(base, "pages")
    icons_dir = os.path.join(base, "icons")
    os.makedirs(pages_dir, exist_ok=True)
    os.makedirs(icons_dir, exist_ok=True)
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    items = []

    def fetch(url):
        try:
            resp = sess.get(url, timeout=args.timeout, allow_redirects=True)
            return resp, None
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"[:200]

    icon_page_html = None
    for i, url in enumerate(urls, 1):
        kind = "icons_page" if urlparse(url).path.rstrip("/") == "/icons" else "page"
        resp, err = fetch(url)
        rec = {"kind": kind, "listed_url": url, "fetched_at_utc": fetched_at, "ok": False, "notes": []}
        if resp is None:
            rec["notes"].append(err)
            items.append(rec)
            print(f"  FAIL {url} {err}")
            continue
        body = resp.content
        ctype = resp.headers.get("Content-Type", "")
        ext = ".html" if "html" in ctype else ".bin"
        local = os.path.join(pages_dir, f"{i:02d}_{slug(url)}{ext}")
        with open(local, "wb") as f:
            f.write(body)
        title, text = extract_text(body) if "html" in ctype else ("", "")
        text_path = local[:-len(ext)] + ".txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)
        words = len(text.split())
        rec.update({"final_url": resp.url, "status": resp.status_code, "content_type": ctype,
                    "local_path": local, "text_path": text_path, "size": len(body),
                    "sha256": sha256_bytes(body), "title": title, "word_count": words})
        host_ok = urlparse(resp.url).netloc.endswith("cloud.google.com")
        if resp.status_code != 200:
            rec["notes"].append(f"HTTP {resp.status_code}")
        if not host_ok:
            rec["notes"].append(f"redirected off cloud.google.com: {resp.url}")
        if BAD_TITLE.search(title or ""):
            rec["notes"].append(f"suspicious title: {title!r}")
        if words < 150:
            rec["notes"].append(f"thin text: {words} words")
        if resp.url.rstrip("/") != url.rstrip("/"):
            rec["notes"].append(f"redirected to {resp.url}")
        rec["ok"] = resp.status_code == 200 and host_ok and words >= 150 and not BAD_TITLE.search(title or "")
        items.append(rec)
        print(f"  {'OK ' if rec['ok'] else 'CHK'} {resp.status_code} {url} -> {resp.url} | {title[:50]!r} | {words} words")
        if kind == "icons_page" and "html" in ctype:
            icon_page_html = body

    # Icon pack: discover zip links on the icons page.
    if icon_page_html is not None:
        soup = BeautifulSoup(icon_page_html, "html.parser")
        cands = []
        for a in soup.find_all("a", href=True):
            if ".zip" in a["href"].lower():
                cands.append(urljoin("https://cloud.google.com/icons", a["href"]))
        for m in re.findall(r"https?://[^\s\"']+\.zip", icon_page_html.decode("utf-8", "ignore")):
            cands.append(m)
        cands = list(dict.fromkeys(cands))
        print(f"icon pack candidates on the icons page: {cands}")
        for zurl in cands:
            resp, err = fetch(zurl)
            rec = {"kind": "icon_pack", "listed_url": "https://cloud.google.com/icons (linked zip)",
                   "zip_url": zurl, "fetched_at_utc": fetched_at, "ok": False, "notes": []}
            if resp is None or resp.status_code != 200:
                rec["notes"].append(err or f"HTTP {resp.status_code}")
                items.append(rec)
                continue
            body = resp.content
            local = os.path.join(icons_dir, os.path.basename(urlparse(zurl).path))
            with open(local, "wb") as f:
                f.write(body)
            rec.update({"final_url": resp.url, "status": resp.status_code,
                        "content_type": resp.headers.get("Content-Type", ""), "local_path": local,
                        "size": len(body), "sha256": sha256_bytes(body)})
            try:
                with zipfile.ZipFile(local) as z:
                    bad = z.testzip()
                    names = z.namelist()
                    exts = Counter(os.path.splitext(n)[1].lower() for n in names if not n.endswith("/"))
                    extract_dir = os.path.join(icons_dir, "extracted")
                    z.extractall(extract_dir)
                rec.update({"zip_entries": len(names), "zip_ext_counts": dict(exts.most_common()),
                            "extracted_to": extract_dir, "zip_testzip_first_bad": bad})
                rec["ok"] = bad is None and (exts.get(".svg", 0) + exts.get(".png", 0)) > 0
            except zipfile.BadZipFile as exc:
                rec["notes"].append(f"bad zip: {exc}")
            items.append(rec)
            print(f"  {'OK ' if rec['ok'] else 'CHK'} icon pack {zurl} size={rec.get('size')} entries={rec.get('zip_entries')} exts={rec.get('zip_ext_counts')}")
        if not cands:
            items.append({"kind": "icon_pack", "listed_url": "https://cloud.google.com/icons (linked zip)",
                          "fetched_at_utc": fetched_at, "ok": False, "notes": ["no .zip link found on icons page"]})

    out = {"task_id": args.task_id, "fetched_at_utc": fetched_at, "listed_urls": urls, "items": items,
           "ok_count": sum(1 for it in items if it["ok"]), "gap_count": sum(1 for it in items if not it["ok"])}
    with open(os.path.join(base, "resources.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"ok={out['ok_count']} gaps={out['gap_count']} -> {os.path.join(base, 'resources.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
