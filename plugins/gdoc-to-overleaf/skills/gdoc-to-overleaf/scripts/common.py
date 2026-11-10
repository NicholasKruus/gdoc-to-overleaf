"""Shared helpers: word normalisation, math normalisation and hashing.

Both sides of the check (the doc and the LaTeX) go through the same functions,
so a word only counts as changed if its letters or digits changed.
"""

import hashlib
import re
import sys
import unicodedata

QUOTES = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
    "\u00ab": '"', "\u00bb": '"', "\u00a0": " ", "\u2009": " ", "\u202f": " ",
    "\u2011": "-", "\u2010": "-",
})
# Characters stripped from both ends of a word. Inner punctuation stays, so
# "self-improvement" and "U.S." keep their shape.
EDGE = "\"'`.,;:!?()[]{}<>*_~|/\\\u2013\u2014\u2026\u00b7\u2022#\u220e\u25a1\u25a0\u2610"
NUMBERISH = re.compile(r"^\(?\[?(?:[0-9]+(?:[.\-][0-9]+)*[a-z]?|[ivxlcdm]+|[a-z])\]?\)?$")
YEAR = re.compile(r"(?:19|20)[0-9]{2}[a-z]?")

LABEL_WORDS = {
    "abstract", "acknowledgement", "acknowledgements", "acknowledgment",
    "acknowledgments", "algorithm", "appendix", "assumption", "axiom", "bibliography",
    "case", "chapter", "claim", "conjecture", "contents", "corollary", "definition",
    "eq", "equation", "example", "exercise", "fact", "fig", "figure", "hypothesis",
    "keywords", "lemma", "listing", "notation", "note", "observation", "part",
    "problem", "proof", "proposition", "question", "references", "remark",
    "section", "solution", "table", "theorem",
}


def utf8_stdout():
    """Windows consoles default to a legacy code page; doc text is Unicode."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def norm_word(word):
    w = unicodedata.normalize("NFKC", word).translate(QUOTES).lower()
    return w.strip(EDGE)


def words(text):
    """Split text into normalised words, dropping pure punctuation."""
    out = []
    for raw in text.translate(QUOTES).split():
        w = norm_word(raw)
        if w:
            out.append(w)
    return out


MATH_DROP = [
    r"\\label\{[^}]*\}", r"\\(?:nonumber|notag|displaystyle|textstyle|scriptstyle)\b",
    r"\\(?:left|right|big|Big|bigg|Bigg)[lr]?\b", r"\\[,;:! ]", r"\\q?quad\b", r"~", r"&",
    r"\\\\", r"\\(?:mathrm|operatorname|text|mathit|mathnormal)\b",
]
MATH_SYNONYMS = [
    (r"\\to\b", r"\\rightarrow"), (r"\\le\b", r"\\leq"), (r"\\ge\b", r"\\geq"),
    (r"\\ne\b", r"\\neq"), (r"\\gets\b", r"\\leftarrow"), (r"\\lbrace\b", "{"),
    (r"\\rbrace\b", "}"), (r"\\vert\b", "|"), (r"\\land\b", r"\\wedge"),
    (r"\\lor\b", r"\\vee"), (r"\\lnot\b", r"\\neg"), (r"\\dots[bcmoi]?\b", r"\\ldots"),
    (r"\\cdots\b", r"\\ldots"), ("\u2026", r"\\ldots"), (r"\\varepsilon\b", r"\\epsilon"),
    (r"\\ast\b", "*"), (r"\\prime\b", "'"),
]


def norm_math(tex):
    t = unicodedata.normalize("NFKC", tex)
    for pat in MATH_DROP:
        t = re.sub(pat, "", t)
    for pat, rep in MATH_SYNONYMS:
        t = re.sub(pat, rep, t)
    t = re.sub(r"[\s{}]", "", t)
    return t.rstrip(".,;")


def is_numberish(w):
    return bool(NUMBERISH.match(w))


def looks_like_citation(tokens):
    text = " ".join(tokens)
    return bool(YEAR.search(text)) or bool(re.fullmatch(r"[0-9,\s\-–]+", text))


TEXT_EXT = {".tex", ".bib", ".bst", ".cls", ".sty", ".json", ".md", ".txt", ".bbl"}


def file_hash(path):
    """sha256 of a file, with text normalised the same way the browser side does.

    Overleaf stores text files as lines, so a trailing newline or CRLF can change
    on the round trip. Text is hashed as LF lines without trailing whitespace.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if any(str(path).lower().endswith(ext) for ext in TEXT_EXT):
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        text = "\n".join(line.rstrip(" \t") for line in text.split("\n")).strip("\n")
        data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
