"""Step 5 (optional) — score the triage against errors you already know about.

truth.json: a list of known errors, one object each:
  {"source": "<a --final dir as given to find_spots>", "page": "<page file stem>",
   "current": "<the wrong text as it is in the transcription>", "key": "<2-8 chars of it, near the error>",
   "type": "<free label, e.g. 漏字/标点/手写>"}

An error counts as routed when a spot on its page contains its key (or shares 4+ characters with
"current"), or when it lies inside an always-human region. Outcome per error:
  likely-wrong  a covering spot was judged likely-wrong (best case: it is at the top of the queue)
  human         routed to a human (undecided spot, lint/unread/handwriting spot, always-human region)
  AUTO-OK       every covering spot was auto-released: a miss caused by the vote
  MISS          no spot covers it

Usage: python score.py spots.json verdicts.json truth.json
"""
import json
import sys
from collections import Counter
from difflib import SequenceMatcher

import core


def lcs(a: str, b: str) -> int:
    return SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b)).size


def main() -> None:
    data = json.loads(open(sys.argv[1], encoding="utf-8").read())
    verdicts = {r["i"]: r["verdict"] for r in json.loads(open(sys.argv[2], encoding="utf-8").read())}
    truth = json.loads(open(sys.argv[3], encoding="utf-8").read())
    counts, rows = Counter(), []
    for t in truth:
        key, cur = core.normalize(t["key"], True), core.normalize(t["current"], True)
        hits = []
        for i, s in enumerate(data["spots"]):
            if s["source"] != t["source"] or s["page"] != t["page"]:
                continue
            ctx = [s["left"] + x + s["right"] for x in [s["final"]] + s["alts"]]
            if (key and any(key in c for c in ctx)) or lcs(cur, ctx[0]) >= min(4, len(cur)):
                hits.append(verdicts.get(i, "human"))
        in_region = any(r["source"] == t["source"] and r["page"] == t["page"] and t["current"] in r["text"]
                        for r in data["always_human"])
        if not hits and not in_region:
            res = "MISS"
        elif "likely-wrong" in hits:
            res = "likely-wrong"
        elif in_region or "human" in hits:
            res = "human"
        else:
            res = "AUTO-OK"
        counts[res] += 1
        rows.append((res, t["source"], t["page"], t.get("type", ""), t["current"]))
    print(dict(counts), "of", len(truth))
    for r in rows:
        if r[0] in ("MISS", "AUTO-OK"):
            print(" ", r)


if __name__ == "__main__":
    main()
