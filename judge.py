"""Step 4 — a vision model reads every crop blind, then the program votes.

The model is never shown the transcription or the candidate readings, and the prompt contains no example
words: candidates bias it toward the text it is shown, and example words leak answers. It only copies what
it sees. Reads are cached by the crop's content hash, so re-runs cost nothing.

Votes per spot: the model's read, the crop's own lines (from the line-box reader), and every page-level
reading (witness and readers, except the line-box reader, whose page text would vote twice).
Verdicts (core.verdict): auto-ok / likely-wrong / human.

Any OpenAI-compatible chat endpoint with image input works. Configuration by environment variables:
  VLM_API_KEY    required
  VLM_BASE_URL   default https://open.bigmodel.cn/api/paas/v4   (Zhipu)
  VLM_MODEL      default glm-5.3-flash
  VLM_EXTRA      JSON merged into the request; default enables GLM thinking with reasoning_effort "high"

Usage: python judge.py spots.json CROPS_DIR --witness DIR --reader NAME=DIR [...] --boxes-reader NAME
                       --out verdicts.json [--workers 4]
"""
import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import core

PROMPT = "请把图中的文字逐字照抄出来，包括所有标点符号。严格照原样：不要改正、不要补全、不要改写，也不要加任何解释。看不清的字写□。只输出抄写结果。"
DEFAULT_EXTRA = {"thinking": {"type": "enabled"}, "reasoning_effort": "high", "temperature": 1, "top_p": 0.95,
                 "max_tokens": 32768}


def ask(png: Path) -> str:
    base = os.environ.get("VLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    extra = json.loads(os.environ["VLM_EXTRA"]) if os.environ.get("VLM_EXTRA") else DEFAULT_EXTRA
    body = {"model": os.environ.get("VLM_MODEL", "glm-5.3-flash"), **extra, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode()}},
                {"type": "text", "text": PROMPT}]}]}
    req_body = json.dumps(body).encode()
    for attempt in range(5):
        req = urllib.request.Request(base + "/chat/completions", data=req_body, headers={
            "Authorization": "Bearer " + os.environ["VLM_API_KEY"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spots", type=Path)
    ap.add_argument("crops", type=Path)
    ap.add_argument("--witness", required=True, type=Path)
    ap.add_argument("--reader", action="append", required=True, help="NAME=DIR")
    ap.add_argument("--boxes-reader", default="", help="reader whose line boxes made the crops")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    spots = json.loads(a.spots.read_text(encoding="utf-8"))["spots"]
    manifest = json.loads((a.crops / "manifest.json").read_text(encoding="utf-8"))
    cache = a.crops / "reads"
    cache.mkdir(exist_ok=True)

    def read(e: dict) -> str:
        png = a.crops / e["png"]
        c = cache / (hashlib.sha1(png.read_bytes()).hexdigest()[:16] + ".txt")
        if not c.exists():
            c.write_text(ask(png), encoding="utf-8")
        return c.read_text(encoding="utf-8")

    with ThreadPoolExecutor(a.workers) as pool:
        reads = list(pool.map(read, manifest))
    page_dirs = {"witness": a.witness, **{n: Path(d) for n, d in (r.split("=", 1) for r in a.reader)}}
    page_dirs.pop(a.boxes_reader, None)
    texts: dict = {}
    out = []
    for e, text in zip(manifest, reads):
        s = spots[e["i"]]
        src_file = next(p for p in Path(s["source"]).iterdir() if p.stem == s["page"])
        votes = {"vlm": core.vote(core.normalize(text, False), s),
                 "crop_lines": core.vote(core.normalize(e["crop_lines"], False), s)}
        for n, d in page_dirs.items():
            key = (n, src_file.name)
            if key not in texts:
                p = d / src_file.name
                texts[key] = core.normalize(p.read_text(encoding="utf-8"), False) if p.exists() else ""
            votes[n] = core.vote(texts[key], s)
        out.append({**e, "spot": s["left"][-3:] + "[" + s["final"] + "→" + "/".join(dict.fromkeys(s["alts"])) + "]"
                    + s["right"][:3], "vlm_read": text.strip()[:300], "votes": votes, "verdict": core.verdict(votes)})
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict = {}
    for r in out:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(counts)


if __name__ == "__main__":
    main()
