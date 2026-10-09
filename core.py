"""Core logic shared by the command-line steps.

normalize()  bring a transcription or an OCR reading to a comparable form
compare()    character-level differences between the transcription and one reader
lint()       house-style checks that need no reader (spaces, dash-as-minus, half-width marks)
unread()     transcription text that no reader produced (usually text inside pictures)
vote()       does a reading support the transcription, the alternative, both or neither
verdict()    turn the votes for one spot into auto-ok / likely-wrong / human
"""
import re
from difflib import SequenceMatcher

MAX_SPAN = 4      # only short differences are reported; longer ones are layout noise
CONTEXT = 8       # characters of context kept on each side of a difference
MIN_CONTEXT = 2   # a shorter context is accepted only when the neighbouring difference is that close

# Transcription markup that page readers never produce. These are our conventions; adjust to yours.
MARKUP_LINE = re.compile(r"^\[(页眉|页码|教材缩略图[^\]]*|插图[^\]]*|接上页|接下页|栏目|待核说明)\][^\n]*", re.M)
TITLE_MARK = re.compile(r"^\[标题\] ?", re.M)
HANDWRITING_PREFIX = "手写："

HALF_TO_FULL = str.maketrans({",": "，", ":": "：", ";": "；", "(": "（", ")": "）", "?": "？", "!": "！"})
LATEX = [
    (re.compile(r"\\frac\{([^{}]*)\}\{([^{}]*)\}"), r"\1/\2"),
    (re.compile(r"\\(?:pi|uppi)"), "π"),
    (re.compile(r"\\approx"), "≈"),
    (re.compile(r"\\times"), "×"),
    (re.compile(r"\\div"), "÷"),
    (re.compile(r"\\(?:leq|le)"), "≤"),
    (re.compile(r"\\(?:geq|ge)"), "≥"),
    (re.compile(r"\^\{?2\}?"), "²"),
    (re.compile(r"\^\{?3\}?"), "³"),
    (re.compile(r"\\circ"), "°"),
    (re.compile(r"\\[a-zA-Z]+"), ""),
]
DASH = re.compile(r"[-－−–—]")
DASH_RULE = re.compile(r"[-－−–—]{3,}")   # table rules such as |---|


def normalize(text: str, is_final: bool) -> str:
    """Remove what readers format differently (spaces, table pipes, LaTeX, quote style, half/full-width
    commas and brackets) but keep what matters: ～ versus ~, and minus signs (every dash becomes "-")."""
    text = DASH_RULE.sub("", text)
    if not is_final:   # readers often output the half-width ~ for a printed ～; only the transcription's width matters
        text = text.replace("~", "～")
    text = text.replace("~", "\ue000").replace("～", "\ue001")
    text = DASH.sub("\ue002", text)
    if is_final:
        text = TITLE_MARK.sub("", MARKUP_LINE.sub("", text))
    text = re.sub(r"<[^>]+>", "", text)
    for pat, rep in LATEX:
        text = pat.sub(rep, text)
    text = re.sub(r"^#+", "", text, flags=re.M)
    for s in ("$", "{", "}", "[Non-Text]", "●", "|", "｜", "\\，", "\\,", "\u0307", "\\"):
        text = text.replace(s, "")
    text = text.replace("∶", "：").translate(HALF_TO_FULL)
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace(HANDWRITING_PREFIX, "")
    text = re.sub(r"\s+", "", text)
    return text.replace("\ue000", "~").replace("\ue001", "～").replace("\ue002", "-")


def compare(final: str, reader: str, witness: str) -> list[dict]:
    """Short differences between the normalized transcription and one reader.

    Context stops at the neighbouring difference, so errors close together do not hide each other.
    `witness` is a second reading used only to label the difference:
      final-differs-from-both  the witness also reads the alternative  (strongest signal)
      possible-joint-omission  the reader has extra text the witness lacks too
      reader-only              the witness agrees with the transcription
      unresolved               the witness supports neither or both
    """
    out = []
    ops = [op for op in SequenceMatcher(None, final, reader, autojunk=False).get_opcodes() if op[0] != "equal"]
    for k, (_, i1, i2, j1, j2) in enumerate(ops):
        fin, alt = final[i1:i2], reader[j1:j2]
        if max(len(fin), len(alt)) > MAX_SPAN:
            continue
        if {fin, alt} == {"-", "一"}:   # readers read a printed dash — as the character 一; lint checks real misuse
            continue
        prev_i, prev_j = (ops[k - 1][2], ops[k - 1][4]) if k else (0, 0)
        next_i, next_j = (ops[k + 1][1], ops[k + 1][3]) if k + 1 < len(ops) else (len(final), len(reader))
        nl, nr = min(CONTEXT, i1 - prev_i, j1 - prev_j), min(CONTEXT, next_i - i2, next_j - j2)
        if (nl < MIN_CONTEXT and i1 > 0) or (nr < MIN_CONTEXT and i2 < len(final)):
            continue
        left, right = final[i1 - nl:i1], final[i2:i2 + nr]
        w_final, w_alt = (left + fin + right) in witness, (left + alt + right) in witness
        if w_alt and not w_final:
            kind = "final-differs-from-both"
        elif w_final and not w_alt and len(alt) > len(fin):
            kind = "possible-joint-omission"
        elif w_final and not w_alt:
            kind = "reader-only"
        else:
            kind = "unresolved"
        out.append({"kind": kind, "final": fin, "alt": alt, "left": left, "right": right})
    return out


# House-style rules for Chinese text that need no reader. Each one caught real errors in our test.
LINT = re.compile(
    r"[“‘（][ 　]+[A-Za-z0-9(]|[A-Za-z0-9)][ 　]+[”’）]|[，。；：、][ 　]+[A-Za-z0-9]"  # space between CJK mark and letter/digit
    r"|[A-Za-z0-9)）][ 　]+[，。；：、]"                                              # space before a CJK mark (表3-2 ，)
    r"|[\u4e00-\u9fff][ 　]+[0-9]"                                                  # CJK, space, digit (大约 120)
    r"|…[ 　]+\S"                                                                    # space after an ellipsis
    r"|[0-9][—－–−][0-9]"                                                            # minus typed as a dash (8—3=5)
    r"|[0-9]一[0-9]"                                                                 # the character 一 used as a minus
    r"|[\u4e00-\u9fff]-[\u4e00-\u9fff]"                                             # hyphen between words; print uses —
    r"|~"                                                                            # half-width tilde; print uses ～
    r"|(?<![0-9])[,;:?!]|[,;:?!](?![0-9])"                                           # half-width marks outside numbers
)


def lint(raw: str) -> list[dict]:
    """Rule hits on prose lines; markup and handwriting lines keep their own spacing."""
    out = []
    for line in raw.splitlines():
        if line.startswith(("[", HANDWRITING_PREFIX[:2])):
            continue
        line = line.replace("[?]", "\ue003")                                         # unreadable mark, not a "?"
        line = re.sub(r"(\d:\d\d)[—－–−](\d)", lambda m: m.group(1) + "\ue004" + m.group(2), line)  # 11:30—12:00
        for m in LINT.finditer(line):
            out.append({"final": m.group(0), "alt": "", "left": line[max(0, m.start() - 6):m.start()],
                        "right": line[m.end():m.end() + 6]})
    return out


def unread(final: str, readers: list[str], min_len: int = 3) -> list[dict]:
    """Runs of transcription text (>= min_len chars) that no reader produced in a 3+ character match."""
    covered = [False] * len(final)
    for r in readers:
        for a, _, n in SequenceMatcher(None, final, r, autojunk=False).get_matching_blocks():
            if n >= 3:
                covered[a:a + n] = [True] * n
    out, i = [], 0
    while i < len(final):
        if covered[i]:
            i += 1
            continue
        j = i
        while j < len(final) and not covered[j]:
            j += 1
        if j - i >= min_len:
            out.append({"final": final[i:j], "alt": "", "left": final[max(0, i - 6):i], "right": final[j:j + 6]})
        i = j
    return out


def vote(text: str, spot: dict) -> tuple[bool, bool]:
    """(supports transcription, supports an alternative) for one normalized reading of the spot.
    Context may be anchored on one side only, because spots often sit at a table-cell or line edge."""
    left, right = spot["left"][-3:], spot["right"][:3]

    def sup(x: str) -> bool:
        if left + x + right in text:
            return True
        return bool(x) and ((len(x + right) >= 4 and x + right in text) or (len(left + x) >= 4 and left + x in text))
    return sup(spot["final"]), any(sup(a) for a in spot["alts"])


def verdict(votes: dict[str, tuple[bool, bool]], judge: str = "vlm") -> str:
    """auto-ok only if the blind model read supports the transcription, at least one other reader does too,
    and at most one reader backs the alternative. The model backing the alternative = likely-wrong."""
    others = {k: v for k, v in votes.items() if k != judge}
    pro = [k for k, v in others.items() if v == (True, False)]
    contra = [k for k, v in others.items() if v == (False, True)]
    if votes[judge] == (True, False) and pro and len(contra) <= 1:
        return "auto-ok"
    if votes[judge] == (False, True):
        return "likely-wrong"
    return "human"
