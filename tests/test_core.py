"""Self-check of the core rules on made-up text. Run: python tests/test_core.py (or pytest)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core  # noqa: E402


def test_normalize_keeps_what_matters():
    assert core.normalize("第2～4题", True) != core.normalize("第2~4题", True)        # tilde width stays visible
    assert core.normalize("850-300", False) == core.normalize("850—300", False)      # all dashes are one minus
    assert core.normalize("1~10", False) == core.normalize("1～10", True)           # a reader's ~ matches a printed ～
    assert core.normalize("1~10", True) != core.normalize("1～10", True)            # but the transcription's width counts
    assert core.normalize("例如, (1)", False) == core.normalize("例如，（1）", False)   # comma/bracket width ignored
    assert core.normalize("[页眉] 第三单元\n正文", True) == "正文"                    # markup dropped from transcription


def test_compare_close_errors_do_not_hide_each_other():
    reading = "比赛时间是10：05到10：20，下一节课再说。"
    bad = "比赛时间是10.05到10.20，一下节课再说。"
    diffs = [(d["final"], d["alt"], d["kind"]) for d in core.compare(bad, reading, reading)]
    assert diffs == [(".", "：", "final-differs-from-both"), (".", "：", "final-differs-from-both")], diffs
    assert core.compare(reading, reading, reading) == []


def test_compare_ignores_dash_read_as_yi():
    assert core.compare("保定-石家庄的路程", "保定一石家庄的路程", "保定一石家庄的路程") == []


def test_compare_finds_a_dropped_character():
    diffs = core.compare("这是长方形的特点", "这是长方形边的特点", "这是长方形边的特点")
    assert [(d["final"], d["alt"]) for d in diffs] == [("", "边")]


def test_lint_rules():
    hits = lambda s: [h["final"] for h in core.lint(s)]  # noqa: E731
    assert hits("式子写成“ x+2x=90 ”") == ["“ x", "0 ”"]
    assert hits("参见表3-2 ，然后") == ["2 ，"]
    assert hits("大约 120天") == ["约 1"]
    assert hits("写成“8—3=5”") == ["8—3"]
    assert hits("写成8一3=5") == ["8一3"]                       # the character 一 used as a minus
    assert hits("路线是甲地-乙地") == ["地-乙"]                 # hyphen between words; print uses —
    assert hits("路线是甲地—乙地") == []
    assert hits("一共有12个，[?]看不清") == []                  # unreadable mark is not a half-width "?"
    assert hits("11:30—12:00 午饭") == []                       # time range, not a minus
    assert hits("手写：1000-92 ≈ 900") == []                    # handwriting keeps its own spacing


def test_unread_lists_text_no_reader_produced():
    out = core.unread("前面一致的文字图中独有标签后面一致的文字", ["前面一致的文字后面一致的文字"])
    assert [u["final"] for u in out] == ["图中独有标签"]


def test_vote_and_verdict():
    spot = {"left": "逐步理", "final": "清", "alts": ["顺"], "right": "思路后"}
    assert core.vote("我们逐步理顺思路后再写", spot) == (False, True)
    assert core.vote("我们逐步理清思路后再写", spot) == (True, False)
    ok, alt = (True, False), (False, True)
    assert core.verdict({"vlm": ok, "crop_lines": alt, "witness": ok}) == "auto-ok"
    assert core.verdict({"vlm": ok, "crop_lines": alt, "witness": ok, "mineru": alt}) == "human"   # two readers against
    assert core.verdict({"vlm": alt, "crop_lines": alt, "witness": ok}) == "likely-wrong"
    assert core.verdict({"vlm": (False, False), "crop_lines": alt, "witness": ok}) == "human"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all checks passed")
