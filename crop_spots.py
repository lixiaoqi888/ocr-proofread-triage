"""Step 3 — cut each reader spot out of the page image.

The line whose text best matches the spot's context is found among the line boxes from read_pages.py;
vertically adjacent lines that overlap it horizontally are added (a spot often sits at a line break),
10 px padding is added and the crop is upscaled 2x — small print is read much better when enlarged.

Usage: python crop_spots.py spots.json BOXES_DIR IMAGES_DIR OUT_DIR
Images are found as IMAGES_DIR/<page>.jpg|.jpeg|.png, boxes as BOXES_DIR/<page>.json.
Writes OUT_DIR/NNNN.png and OUT_DIR/manifest.json (spot index, png, page, the crop's own line texts).
"""
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

from PIL import Image


def squash(t: str) -> str:
    return re.sub(r"\s+", "", t)


def main() -> None:
    spots_file, boxes_dir, images_dir, out = (Path(x) for x in sys.argv[1:5])
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(spots_file.read_text(encoding="utf-8"))
    readers = {n for s in data["spots"] for n in s["src"].split("+")} - {"lint", "handwriting", "unread"}
    cache, manifest = {}, []
    for i, s in enumerate(data["spots"]):
        if s["src"].split("+")[0] not in readers:
            continue
        if s["page"] not in cache:
            img = next((images_dir / f"{s['page']}{ext}" for ext in (".jpg", ".jpeg", ".png")
                        if (images_dir / f"{s['page']}{ext}").exists()), None)
            bf = boxes_dir / f"{s['page']}.json"
            bx = json.loads(bf.read_text()) if bf.exists() else {"boxes": [], "txts": []}
            cache[s["page"]] = (Image.open(img).convert("RGB") if img and bx["boxes"] else None,
                                [(b, squash(t)) for b, t in zip(bx["boxes"], bx["txts"])])
        im, lines = cache[s["page"]]
        if im is None:
            continue
        ctxs = [s["left"] + x + s["right"] for x in [s["final"]] + s["alts"]]

        def score(t: str) -> float:
            return max(sum(n for *_, n in SequenceMatcher(None, c, t, autojunk=False).get_matching_blocks())
                       / max(1, len(c)) for c in ctxs)
        k = max(range(len(lines)), key=lambda j: score(lines[j][1]))
        box = lines[k][0]
        x0, x1 = min(p[0] for p in box), max(p[0] for p in box)
        y0, y1 = min(p[1] for p in box), max(p[1] for p in box)
        h, picked = y1 - y0, []
        for b, t in lines:
            bx0, bx1 = min(p[0] for p in b), max(p[0] for p in b)
            by0, by1 = min(p[1] for p in b), max(p[1] for p in b)
            if abs((by0 + by1) / 2 - (y0 + y1) / 2) <= 1.6 * h and \
                    min(bx1, x1) - max(bx0, x0) > 0.3 * min(bx1 - bx0, x1 - x0):
                picked.append((b, t))
        X0 = min(min(p[0] for p in b) for b, _ in picked) - 10
        X1 = max(max(p[0] for p in b) for b, _ in picked) + 10
        Y0 = min(min(p[1] for p in b) for b, _ in picked) - 10
        Y1 = max(max(p[1] for p in b) for b, _ in picked) + 10
        crop = im.crop((max(0, X0), max(0, Y0), min(im.width, X1), min(im.height, Y1)))
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        name = f"{i:04d}.png"
        crop.save(out / name)
        manifest.append({"i": i, "png": name, "page": s["page"], "match": round(score(lines[k][1]), 2),
                         "crop_lines": "".join(t for _, t in sorted(picked, key=lambda bt: min(p[1] for p in bt[0])))})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(manifest), "crops")


if __name__ == "__main__":
    main()
