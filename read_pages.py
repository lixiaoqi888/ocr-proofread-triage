"""Step 1 — read page images with RapidOCR (PP-OCRv5 server models, local, no language model).

Writes OUT/<stem>.md (one text line per detected line) and OUT/<stem>.json (line boxes, texts, scores).
RapidOCR is the "literal" reader: it has no language model, so it does not rewrite misprints into
common words. The line boxes are also what crop_spots.py uses to cut a spot out of the page.

Usage: python read_pages.py IMAGE_DIR OUT_DIR [--threads 4]
Skips pages whose OUT/<stem>.json already exists.
"""
import argparse
import json
from pathlib import Path

from rapidocr import ModelType, OCRVersion, RapidOCR


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--threads", type=int, default=4, help="onnxruntime threads per process")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    eng = RapidOCR(params={"Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.SERVER,
                           "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.SERVER,
                           "Global.log_level": "warning", "EngineConfig.onnxruntime.intra_op_num_threads": a.threads})
    for img in sorted(p for p in a.images.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png")):
        box_file = a.out / f"{img.stem}.json"
        if box_file.exists():
            continue
        r = eng(str(img))
        txts = list(r.txts or ())
        boxes = [[list(map(float, p)) for p in b] for b in (r.boxes if r.boxes is not None else [])]
        (a.out / f"{img.stem}.md").write_text("\n".join(txts) + "\n", encoding="utf-8")
        box_file.write_text(json.dumps({"txts": txts, "boxes": boxes, "scores": [float(s) for s in (r.scores or ())]},
                                       ensure_ascii=False), encoding="utf-8")
        print(img.stem, len(txts), flush=True)


if __name__ == "__main__":
    main()
