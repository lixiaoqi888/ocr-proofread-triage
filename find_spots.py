"""Step 2 — find every spot in the transcription that needs a look.

Sources of spots (the "src" field):
  <reader name>  short character differences between the transcription and that reader
  lint           house-style rules that need no reader (core.LINT)
  unread         transcription text no reader produced (usually text inside pictures)
  handwriting    every line starting with the handwriting prefix: readers misread handwriting
                 the same way the transcription did, so a diff cannot be trusted there
Regions matching --always-human (e.g. tables of scanned student work) are listed separately.

Noise removed:
  reading order   a moved string of 4+ characters that appears elsewhere on the page
  page number     the reader inserted the printed page number
  confusions      for --filter-reader readers only: a lone disagreement whose (transcription, reader)
                  pair that reader produces 3+ times across the run (e.g. 己/已), while every other
                  reading supports the transcription. Rare lone disagreements are kept: the literal
                  reader is often the only one that reads a misprint as printed.

Usage:
  python find_spots.py --final PAGES_DIR [--final ...] --witness DIR --reader NAME=DIR [--reader ...]
                       [--filter-reader NAME] [--always-human REGEX] --out spots.json
Every directory holds one text file per page with the same file name as the transcription page.
--witness is a reading used only to label differences (we used the OCR draft the transcription
was made from); readers are compared with the transcription.
"""
import argparse
import json
import re
from pathlib import Path

import core


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def regions(raw: str, patterns: list[re.Pattern]) -> list[str]:
    """Text from each line matching a pattern up to the next blank line."""
    out, lines = [], raw.splitlines()
    for i, line in enumerate(lines):
        if any(p.search(line) for p in patterns):
            j = i
            while j < len(lines) and lines[j].strip():
                j += 1
            out.append("\n".join(lines[i:j]))
    return out


def page_spots(raw, f, witness, readers, filter_readers, confusions, learn, page_no_re):
    spots, dropped = [], {}
    m = page_no_re.search(raw)
    page_no = m.group(1) if m else ""

    def noise(x):
        fin, alt = x["final"], x["alt"]
        moved = fin or alt
        if (not fin or not alt) and len(moved) >= 4 and f.count(moved) >= (1 if not fin else 2):
            return "reading-order"
        if not fin and alt.isdigit() and alt == page_no:
            return "page-number"
        return None

    for name, text in readers.items():
        others = [witness] + [t for n, t in readers.items() if n != name]
        for x in core.compare(f, text, witness):
            if name in filter_readers:
                ctx = x["left"] + x["final"] + x["right"]
                if all(ctx in o for o in others):
                    pair = (name, x["final"], x["alt"])
                    learn[pair] = learn.get(pair, 0) + 1
                    if pair in confusions:
                        dropped["confusion"] = dropped.get("confusion", 0) + 1
                        continue
            why = noise(x)
            if why:
                dropped[why] = dropped.get(why, 0) + 1
                continue
            spots.append({"src": name, **x})
    spots += [{"src": "lint", "kind": "", **x} for x in core.lint(raw)]
    spots += [{"src": "handwriting", "kind": "", "final": line[:40], "alt": "", "left": "", "right": ""}
              for line in raw.splitlines() if line.startswith(core.HANDWRITING_PREFIX[:2])]
    spots += [{"src": "unread", "kind": "", **x} for x in core.unread(f, [witness] + list(readers.values()))]
    merged, seen = [], {}
    for s in spots:   # one spot reported by several readers is looked at once
        s["alts"] = [s["alt"]] if s["src"] in readers else []
        key = (s["left"][-3:], s["final"], s["right"][:3])
        if s["src"] in readers and key in seen:
            seen[key]["src"] += "+" + s["src"]
            seen[key]["alts"].append(s["alt"])
            continue
        if s["src"] in readers:
            seen[key] = s
        merged.append(s)
    return merged, dropped


def run(finals, witness_dir, reader_dirs, filter_readers, confusions, learn, page_no_re, human_res):
    spots, human, dropped = [], [], {}
    for fd in finals:
        for page in sorted(p for p in fd.iterdir() if p.is_file() and not p.name.startswith(".")):
            raw = load(page)
            readers = {n: core.normalize(load(d / page.name), False) for n, d in reader_dirs.items()}
            witness = core.normalize(load(witness_dir / page.name), False)
            sp, dr = page_spots(raw, core.normalize(raw, True), witness, readers, filter_readers, confusions, learn,
                                page_no_re)
            spots += [{"source": str(fd), "page": page.stem, **s} for s in sp]
            human += [{"source": str(fd), "page": page.stem, "text": t} for t in regions(raw, human_res)]
            for k, v in dr.items():
                dropped[k] = dropped.get(k, 0) + v
    return spots, human, dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="append", required=True, type=Path)
    ap.add_argument("--witness", required=True, type=Path)
    ap.add_argument("--reader", action="append", required=True, help="NAME=DIR")
    ap.add_argument("--filter-reader", action="append", default=[])
    ap.add_argument("--confusion-min", type=int, default=3)
    ap.add_argument("--always-human", action="append", default=[])
    ap.add_argument("--page-number", default=r"^\[页码\]\s*(\d+)")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    reader_dirs = {n: Path(d) for n, d in (r.split("=", 1) for r in a.reader)}
    page_no_re, human_res = re.compile(a.page_number, re.M), [re.compile(p) for p in a.always_human]
    learn: dict = {}
    run(a.final, a.witness, reader_dirs, set(a.filter_reader), set(), learn, page_no_re, [])   # pass 1: learn
    confusions = {k for k, n in learn.items() if n >= a.confusion_min}
    spots, human, dropped = run(a.final, a.witness, reader_dirs, set(a.filter_reader), confusions, {}, page_no_re,
                                human_res)
    a.out.write_text(json.dumps({"spots": spots, "always_human": human, "dropped": dropped,
                                 "confusions": sorted([[*k, learn[k]] for k in confusions], key=lambda x: -x[3])},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    by = {}
    for s in spots:
        by[s["src"].split("+")[0]] = by.get(s["src"].split("+")[0], 0) + 1
    print(f"{len(spots)} spots {by}; always-human regions {len(human)}; dropped {dropped}")


if __name__ == "__main__":
    main()
