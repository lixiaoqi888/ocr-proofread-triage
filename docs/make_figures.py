"""Draw the README figures in English and Chinese: pipeline.svg, results.svg, example.png.

All text in the figures is made up; no page from any real book is used.
The example's "scan" is rendered with a Song typeface, slightly blurred and noised.
Usage: python docs/make_figures.py   (macOS fonts; set SONG_FONT / SANS_FONT to other .ttc/.ttf paths elsewhere)
"""
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "images"
SONG = os.environ.get("SONG_FONT", "/System/Library/Fonts/Supplemental/Songti.ttc")
SANS = os.environ.get("SANS_FONT", "/System/Library/Fonts/Hiragino Sans GB.ttc")
FONT_CSS = "font-family:'PingFang SC','Hiragino Sans GB','Noto Sans CJK SC','Microsoft YaHei','Helvetica Neue',Arial,sans-serif"
INK, MUTED, LINE = "#1f2937", "#6b7280", "#d1d5db"
GREEN, RED, AMBER, BLUE = "#15803d", "#b91c1c", "#b45309", "#1d4ed8"

T = {
    "en": {
        "inputs": "Inputs", "page": "Scanned page", "trans": "Transcription",
        "readers": "① Three readers", "witness": "Draft OCR (witness)", "w_note": "labels differences",
        "mineru": "Independent OCR", "m_note": "e.g. MinerU", "rapid": "Literal OCR", "r_note": "RapidOCR, no language model",
        "find": "② Program finds every spot", "f1": "Character diff vs each reader", "f2": "House-style lint",
        "f3": "Text no reader produced", "f4": "Handwriting & must-see regions → human",
        "noise": "Noise removed: reading order, page numbers, frequent confusions",
        "judge": "③ Judge only the spots", "crop": "Crop the line, ×2", "blind": "Vision model copies it blind",
        "blind_note": "no candidates, no example words", "vote": "Program votes",
        "ok": "Auto-OK", "ok_note": "model + 1 reader agree", "wrong": "Likely wrong",
        "wrong_note": "shown first", "human": "Human", "human_note": "everything else",
        "r_title": "Known errors routed for review", "r_sub": "984 pages, 118 errors found earlier by a page-by-page AI review",
        "r1": "Whole-page check by a vision model*", "r2": "Round 1 (this method)", "r3": "Round 2 / this repo",
        "r_foot": "* small test: 3 segments, 83 pages, 16 errors. Round 2 rules were tuned on round-1 misses, so 97% is optimistic.",
        "s_title": "Where the 118 errors ended up (this repo)", "s1": "Likely wrong", "s2": "Human", "s3": "Auto-OK (missed)",
        "s4": "Not found", "per_page": "spots to look at per page",
        "ex_title": "One spot, judged", "ex_crop": "Crop from the page (enlarged)", "ex_trans": "Transcription",
        "ex_readers": "Readings of this spot", "ex_w": "Draft OCR", "ex_m": "Independent OCR", "ex_r": "Literal OCR (crop lines)",
        "ex_v": "Vision model, blind copy", "ex_sup_f": "supports transcription", "ex_sup_a": "supports 清",
        "ex_verdict": "Verdict: likely wrong — 理顺 should be 理清", "ex_note": "A fluent rewrite: both words fit the sentence; only the image decides.",
    },
    "zh": {
        "inputs": "输入", "page": "扫描书页", "trans": "转写稿",
        "readers": "① 三个读者", "witness": "识别初稿（见证）", "w_note": "给差异贴标签",
        "mineru": "独立识别", "m_note": "如 MinerU", "rapid": "老实识别", "r_note": "RapidOCR，不带语言模型",
        "find": "② 程序把可疑处找全", "f1": "和每个读者逐字比对", "f2": "格式规则检查",
        "f3": "没有读者读到的文字", "f4": "手写和必看区域 → 交给人",
        "noise": "去掉噪声：读序挪位、页码、高频认错字对",
        "judge": "③ 只判断可疑处", "crop": "裁出那一行，放大2倍", "blind": "视觉模型盲抄",
        "blind_note": "不给候选，不举例子", "vote": "程序投票",
        "ok": "自动放行", "ok_note": "模型和另一读者都同意", "wrong": "很可能有错",
        "wrong_note": "排在最前面看", "human": "交给人看", "human_note": "其余情况",
        "r_title": "已知错误被送去复核的比例", "r_sub": "984 页，118 处错误（来自 AI 模型逐页对图审核）",
        "r1": "视觉大模型整页挑错*", "r2": "第一轮（本方法）", "r3": "第二轮 / 本仓库代码",
        "r_foot": "* 小测试：3 段、83 页、16 处错误。第二轮规则是看着第一轮漏网补的，97% 偏乐观。",
        "s_title": "118 处错误的去向（本仓库代码）", "s1": "很可能有错", "s2": "交给人看", "s3": "误放行",
        "s4": "没找到", "per_page": "每页要看的处数",
        "ex_title": "一处可疑的判断过程", "ex_crop": "从原图裁出（已放大）", "ex_trans": "转写稿",
        "ex_readers": "这一处的各家读法", "ex_w": "识别初稿", "ex_m": "独立识别", "ex_r": "老实识别（小图内的行）",
        "ex_v": "视觉模型盲抄", "ex_sup_f": "支持转写稿", "ex_sup_a": "支持“清”",
        "ex_verdict": "结论：很可能有错——“理顺”应为“理清”", "ex_note": "典型的“改顺”：两个词放进句子都通，只能看图定。",
    },
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def box(x, y, w, h, fill="#fff", stroke=LINE, r=10, sw=1.5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def text(x, y, s, size=15, color=INK, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>'


def arrow(x1, y1, x2, y2, color=MUTED):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" marker-end="url(#a)"/>'


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="{FONT_CSS}">'
            '<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">'
            f'<path d="M0,0 L8,3 L0,6 z" fill="{MUTED}"/></marker></defs>'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>{"".join(body)}</svg>')


def pipeline(t):
    b = []
    # row 1: inputs -> readers -> find spots
    b += [box(20, 20, 170, 200, "#f9fafb"), text(105, 48, t["inputs"], 16, INK, 700, "middle")]
    b += [box(40, 66, 130, 62, "#fff"), text(105, 103, t["page"], 14, INK, 400, "middle")]
    b += [box(40, 140, 130, 62, "#fff"), text(105, 177, t["trans"], 14, INK, 400, "middle")]
    b += [arrow(190, 97, 232, 97)]
    b += [box(236, 20, 250, 200, "#eff6ff", "#bfdbfe"), text(361, 48, t["readers"], 16, BLUE, 700, "middle")]
    for i, (k, n) in enumerate([("witness", "w_note"), ("mineru", "m_note"), ("rapid", "r_note")]):
        y = 64 + i * 50
        b += [box(252, y, 218, 42, "#fff", "#bfdbfe", 8), text(264, y + 18, t[k], 14, INK, 600), text(264, y + 35, t[n], 12, MUTED)]
    b += [arrow(486, 120, 528, 120),   # the transcription goes around the readers box, into the bottom of step 2
          f'<path d="M170,171 H206 V242 H600 V226" fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#a)"/>']
    b += [box(532, 20, 408, 200, "#fefce8", "#fde68a"), text(736, 48, t["find"], 16, AMBER, 700, "middle")]
    for i, k in enumerate(["f1", "f2", "f3", "f4"]):
        b += [text(552, 80 + i * 30, "• " + t[k], 14)]
    b += [text(552, 205, t["noise"], 12, MUTED)]
    # row 2: crop -> blind read -> vote -> outcomes
    b += [arrow(736, 220, 736, 262)]
    b += [box(20, 266, 920, 170, "#f0fdf4", "#bbf7d0"), text(40, 294, t["judge"], 16, GREEN, 700)]
    b += [box(40, 312, 170, 56, "#fff", "#bbf7d0", 8), text(125, 345, t["crop"], 14, INK, 400, "middle")]
    b += [arrow(210, 340, 246, 340)]
    b += [box(250, 312, 210, 56, "#fff", "#bbf7d0", 8), text(355, 335, t["blind"], 14, INK, 600, "middle"),
          text(355, 355, t["blind_note"], 12, MUTED, 400, "middle")]
    b += [arrow(460, 340, 496, 340)]
    b += [box(500, 312, 120, 56, "#fff", "#bbf7d0", 8), text(560, 345, t["vote"], 14, INK, 400, "middle")]
    for i, (k, n, c) in enumerate([("wrong", "wrong_note", RED), ("human", "human_note", AMBER), ("ok", "ok_note", GREEN)]):
        y = 300 + i * 44
        b += [arrow(620, 340, 676, y + 18)]
        b += [box(680, y, 240, 38, "#fff", c, 8, 2), text(694, y + 24, t[k], 14, c, 700), text(906, y + 24, t[n], 12, MUTED, 400, "end")]
    return svg(960, 456, b)


def results(t):
    b = [text(20, 34, t["r_title"], 18, INK, 700), text(20, 58, t["r_sub"], 13, MUTED)]
    rows = [(t["r1"], 4 / 16, "4 / 16", RED), (t["r2"], 102 / 118, "102 / 118", AMBER), (t["r3"], 115 / 118, "115 / 118", GREEN)]
    x0, W = 300, 520
    for i, (lab, v, n, c) in enumerate(rows):
        y = 84 + i * 46
        b += [text(x0 - 12, y + 21, lab, 14, INK, 400, "end"), box(x0, y, W, 30, "#f3f4f6", "#f3f4f6", 6, 0),
              box(x0, y, W * v, 30, c, c, 6, 0), text(x0 + W * v + 8 if v < 0.85 else x0 + W * v - 8, y + 21,
                                                     f"{v:.0%}  ({n})", 13, INK if v < 0.85 else "#fff", 700,
                                                     "start" if v < 0.85 else "end")]
    b += [text(20, 238, t["r_foot"], 12, MUTED)]
    # stacked bar: where the 118 errors went
    b += [text(20, 284, t["s_title"], 16, INK, 700)]
    parts = [(t["s1"], 68, RED), (t["s2"], 47, AMBER), (t["s3"], 2, "#6b7280"), (t["s4"], 1, "#111827")]
    x = 20
    for lab, n, c in parts:
        w = 920 * n / 118
        b += [box(x, 298, w, 34, c, c, 0, 0)]
        x += w
    lx = 20
    for lab, n, c in parts:
        b += [box(lx, 348, 14, 14, c, c, 3, 0), text(lx + 20, 360, f"{lab}  {n}", 13)]
        lx += 210
    b += [text(20, 400, f"{t['per_page']}:  round 1 → 1.24   |   round 2 → 1.77   |   this repo → 1.86" if t is T["en"]
               else f"{t['per_page']}：第一轮 1.24  ｜  第二轮 1.77  ｜  本仓库代码 1.86", 13, MUTED)]
    return svg(960, 420, b)


def scan_crop() -> Image.Image:
    """A made-up line set in Song type, made to look like a 150-dpi scan, then enlarged 2x."""
    font = ImageFont.truetype(SONG, 26)
    lines = ["交流时，教师要引导学生逐步理清解决", "问题的思路，再尝试独立列式计算。"]
    im = Image.new("L", (520, 92), 247)
    d = ImageDraw.Draw(im)
    for i, s in enumerate(lines):
        d.text((14, 10 + i * 40), s, font=font, fill=30)
    rnd = random.Random(7)
    px = im.load()
    for _ in range(4000):
        x, y = rnd.randrange(im.width), rnd.randrange(im.height)
        px[x, y] = max(0, min(255, px[x, y] + rnd.randint(-40, 40)))
    im = im.filter(ImageFilter.GaussianBlur(0.6)).resize((260, 46), Image.BILINEAR).resize((520, 92), Image.BICUBIC)
    return im.resize((1040, 184), Image.LANCZOS).convert("RGB")


def example(t, lang):
    W, H = 1100, 700
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    f = lambda s: ImageFont.truetype(SANS, s)  # noqa: E731
    song = ImageFont.truetype(SONG, 30)
    song_s = ImageFont.truetype(SONG, 24)
    d.text((30, 22), t["ex_title"], font=f(28), fill=INK)
    d.text((30, 70), t["ex_crop"], font=f(18), fill=MUTED)
    crop = scan_crop()
    im.paste(crop, (30, 100))
    d.rectangle((30, 100, 30 + crop.width, 100 + crop.height), outline=LINE, width=2)
    d.text((30, 304), t["ex_trans"] + ":", font=f(18), fill=MUTED)
    d.text((30, 334), "…引导学生逐步", font=song, fill=INK)
    x = 30 + d.textlength("…引导学生逐步", font=song)
    d.rectangle((x - 2, 332, x + 62, 370), fill="#fee2e2")
    d.text((x, 334), "理顺", font=song, fill=RED)
    d.text((x + 62, 334), "解决问题的思路…", font=song, fill=INK)
    d.text((30, 400), t["ex_readers"] + ":", font=f(18), fill=MUTED)
    rows = [(t["ex_w"], "理顺", "f"), (t["ex_m"], "理清", "a"), (t["ex_r"], "理清", "a"), (t["ex_v"], "理清", "a")]
    for i, (who, read, side) in enumerate(rows):
        y = 436 + i * 38
        d.text((30, y), who, font=f(18), fill=INK)
        d.text((430, y - 3), read, font=song_s, fill=INK)
        tag, c = (t["ex_sup_f"], MUTED) if side == "f" else (t["ex_sup_a"], RED)
        d.text((540, y), "→ " + tag, font=f(18), fill=c)
    d.rounded_rectangle((30, 600, 1070, 646), radius=8, outline=RED, width=2)
    d.text((44, 610), t["ex_verdict"], font=f(20), fill=RED)
    d.text((30, 662), t["ex_note"], font=f(16), fill=MUTED)
    return im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, t in T.items():
        (OUT / f"pipeline-{lang}.svg").write_text(pipeline(t), encoding="utf-8")
        (OUT / f"results-{lang}.svg").write_text(results(t), encoding="utf-8")
        example(t, lang).save(OUT / f"example-{lang}.png", optimize=True)
    print("written to", OUT)


if __name__ == "__main__":
    main()
