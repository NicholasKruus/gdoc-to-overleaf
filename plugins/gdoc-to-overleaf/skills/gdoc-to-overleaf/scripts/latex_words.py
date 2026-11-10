"""Turn a LaTeX project into the words and maths a reader would see.

This is deliberately not a TeX engine. It reads the source the way a careful
proofreader would: text inside braces is text, unless the command is known to
take a label, key, path, length or colour. Unknown commands keep their text, so
a venue macro such as \\icmltitle{...} still counts.

Some LaTeX constructs print words the source does not contain ("Theorem 1",
"Figure 2", reference numbers, citations). Those places emit marker tokens, and
the checker accepts a doc phrase replaced at a marker only if it looks like what
LaTeX prints there.
"""

import os
import re
import unicodedata

from common import norm_math, words

# Arguments: o = optional, skipped; O = optional, text; s = mandatory, skipped;
# t = mandatory, text. A leading "*" in the name is consumed automatically.
ARGS = {
    "label": "s", "ref": "s", "eqref": "s", "cref": "s", "Cref": "s", "autoref": "s",
    "pageref": "s", "nameref": "s", "vref": "s", "hyperref": "ot",
    "cite": "oos", "citep": "oos", "citet": "oos", "citealp": "oos", "citealt": "oos",
    "citeauthor": "oos", "citeyear": "oos", "citeyearpar": "oos", "parencite": "oos",
    "textcite": "oos", "autocite": "oos", "footcite": "oos", "nocite": "s", "citenum": "s",
    "includegraphics": "os", "input": "s", "include": "s", "bibliography": "s",
    "bibliographystyle": "s", "usepackage": "os", "documentclass": "os",
    "href": "st", "hypersetup": "s", "setlength": "ss", "addtolength": "ss",
    "setcounter": "ss", "addtocounter": "ss", "vspace": "s", "hspace": "s", "vskip": "",
    "pagestyle": "s", "thispagestyle": "s", "pagenumbering": "s", "color": "s",
    "textcolor": "st", "colorbox": "st", "fcolorbox": "sst", "definecolor": "sss",
    "caption": "ot", "captionof": "sot", "footnote": "Ot", "footnotetext": "Ot",
    "multicolumn": "sst", "multirow": "osot", "cline": "s", "cmidrule": "os",
    "newcommand": "", "renewcommand": "", "providecommand": "", "newenvironment": "",
    "newtheorem": "", "theoremstyle": "s", "declaretheorem": "", "graphicspath": "s",
    "rule": "oss", "raisebox": "soot", "resizebox": "sst", "scalebox": "sot",
    "makebox": "oot", "framebox": "oot", "parbox": "ooost", "item": "O", "bibitem": "os",
    "linenumbers": "", "todo": "ot", "url": "t", "path": "t", "texttt": "t",
    "affil": "Ot", "address": "t", "email": "t", "thanks": "t", "keywords": "t",
    "icmlauthor": "ts", "icmlaffiliation": "st", "icmlcorrespondingauthor": "ts",
    "icmlkeywords": "s", "icmlsetsymbol": "ss", "printAffiliationsAndNotice": "s",
    "crefname": "sss", "Crefname": "sss", "numberwithin": "ss", "lstset": "s",
    "subfloat": "Ot", "sisetup": "s", "SI": "ost", "si": "os", "num": "ot", "qty": "ost",
    "phantom": "s", "hphantom": "s", "vphantom": "s", "special": "s", "ifthenelse": "stt",
    "appendix": "", "maketitle": "", "tableofcontents": "", "listoffigures": "",
    "listoftables": "", "clearpage": "", "newpage": "", "centering": "",
}
REF_COMMANDS = {"ref", "eqref", "cref", "Cref", "autoref", "pageref", "nameref", "vref"}
CITE_COMMANDS = {"cite", "citep", "citet", "citealp", "citealt", "citeauthor", "citeyear",
                 "citeyearpar", "parencite", "textcite", "autocite", "footcite", "citenum"}
LABEL_COMMANDS = {"caption", "captionof", "part", "chapter", "section", "subsection",
                  "subsubsection", "paragraph", "subparagraph", "item", "subfloat", "bibitem"}
SECTIONING = {"part", "chapter", "section", "subsection", "subsubsection", "paragraph",
              "subparagraph"}
for _name in SECTIONING:
    ARGS.setdefault(_name, "ot")
MATH_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline",
             "multline*", "eqnarray", "eqnarray*", "displaymath", "math", "alignat",
             "alignat*", "flalign", "flalign*", "split", "aligned", "gathered", "dmath",
             "dmath*", "subequations"}
VERBATIM_ENVS = {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "alltt",
                 "comment", "filecontents", "filecontents*"}
LABEL_ENVS = {"abstract", "thebibliography", "theorem", "lemma", "proposition", "corollary",
              "definition", "remark", "example", "proof", "claim", "conjecture", "assumption",
              "fact", "observation", "notation", "problem", "question", "exercise", "solution",
              "hypothesis", "axiom", "algorithm", "keywords", "acknowledgments", "acknowledgements", "appendices"}
ENV_ARGS = {
    "tabular": "os", "tabular*": "sos", "tabularx": "sos", "tabulary": "sos", "longtable": "os",
    "array": "os", "tblr": "os", "longtblr": "oos", "minipage": "ooos", "multicols": "s",
    "multicols*": "s", "figure": "o", "figure*": "o", "table": "o", "table*": "o",
    "wrapfigure": "osos", "wraptable": "osos", "subfigure": "os", "subtable": "os",
    "thebibliography": "s", "itemize": "o", "enumerate": "o", "description": "o",
    "adjustbox": "s", "tcolorbox": "o", "algorithm": "o", "algorithmic": "o",
    "theorem": "O", "lemma": "O", "proposition": "O", "corollary": "O", "definition": "O",
    "remark": "O", "example": "O", "proof": "O", "claim": "O", "conjecture": "O",
    "minted": "os", "lstlisting": "o", "Verbatim": "o", "center": "", "flushleft": "",
    "flushright": "", "quote": "", "quotation": "",
}
ESCAPES = {"&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}", " ": " ",
           ",": " ", ";": " ", ":": " ", "!": "", "/": "", "-": "", "\\": " ", "@": ""}
SYMBOLS = {
    "textquotesingle": "'", "textquotedbl": '"', "textbackslash": "\\", "textasciitilde": "~",
    "textasciicircum": "^", "textunderscore": "_", "textbar": "|", "textless": "<",
    "textgreater": ">", "ldots": "\u2026", "dots": "\u2026", "textellipsis": "\u2026",
    "textendash": "\u2013", "textemdash": "\u2014", "textbullet": "\u2022", "S": "\u00a7",
    "P": "\u00b6", "copyright": "\u00a9", "textregistered": "\u00ae", "texttrademark": "\u2122",
    "pounds": "\u00a3", "euro": "\u20ac", "textdegree": "\u00b0", "LaTeX": "LaTeX",
    "TeX": "TeX", "ss": "\u00df", "ae": "\u00e6", "AE": "\u00c6", "oe": "\u0153",
    "OE": "\u0152", "o": "\u00f8", "O": "\u00d8", "aa": "\u00e5", "AA": "\u00c5", "l": "\u0142",
    "L": "\u0141", "i": "i", "j": "j", "newline": " ", "linebreak": " ", "par": " ",
    "quad": " ", "qquad": " ", "enspace": " ", "thinspace": " ", "noindent": "",
    "hline": " ", "toprule": " ", "midrule": " ", "bottomrule": " ", "and": " ", "AND": " ",
    "And": " ", "tabularnewline": " ", "endhead": " ", "endfirsthead": " ", "endfoot": " ",
    "endlastfoot": " ", "today": "", "xspace": "",
}
ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
           "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
           "c": "\u0327", "k": "\u0328", "r": "\u030a", "b": "\u0331", "d": "\u0323"}


class Tokens:
    def __init__(self):
        self.items = []  # ("w", word) | ("m", math) | ("k", marker)
        self.buf = []

    def text(self, s):
        self.buf.append(s)

    def flush(self):
        if self.buf:
            for w in words("".join(self.buf)):
                self.items.append(("w", w))
            self.buf = []

    def math(self, tex):
        self.flush()
        n = norm_math(tex)
        if n:
            self.items.append(("m", n))

    def marker(self, kind):
        self.flush()
        self.items.append(("k", kind))


class Parser:
    def __init__(self, root, label_envs):
        self.root = root
        self.label_envs = label_envs
        self.seen_files = set()
        self.missing_files = []

    # ---- low-level scanning ----------------------------------------------

    @staticmethod
    def skip_space(s, i):
        while i < len(s) and s[i] in " \t\n\r":
            i += 1
        return i

    @staticmethod
    def group(s, i, open_="{", close="}"):
        """Return (content, index after) for a balanced group starting at s[i]."""
        depth, j = 0, i
        while j < len(s):
            c = s[j]
            if c == "\\":
                j += 2
                continue
            if c == open_:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)

    def arg(self, s, i, kind):
        """Read one argument. Returns (content or None, new index)."""
        j = self.skip_space(s, i)
        if kind in "oO":
            if j < len(s) and s[j] == "[":
                return self.group(s, j, "[", "]")
            return None, i
        if j < len(s) and s[j] == "{":
            return self.group(s, j)
        if j < len(s) and s[j] == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[j:])
            return m.group(0), j + len(m.group(0))
        if j < len(s):
            return s[j], j + 1
        return None, i

    # ---- files --------------------------------------------------------------

    def read_file(self, name):
        for cand in (name, name + ".tex"):
            path = os.path.normpath(os.path.join(self.root, cand))
            if os.path.isfile(path):
                if path in self.seen_files:
                    return ""
                self.seen_files.add(path)
                with open(path, encoding="utf-8", errors="replace") as fh:
                    return strip_comments(fh.read())
        self.missing_files.append(name)
        return ""

    # ---- main walk ------------------------------------------------------------

    def run(self, s, out):
        i, n = 0, len(s)
        while i < n:
            c = s[i]
            if c == "\\":
                i = self.command(s, i, out)
            elif c == "{" or c == "}":
                i += 1
            elif c == "$":
                if s.startswith("$$", i):
                    end = s.find("$$", i + 2)
                    end = n if end < 0 else end
                    out.math(s[i + 2:end])
                    i = end + 2
                else:
                    j = i + 1
                    while j < n and not (s[j] == "$" and s[j - 1] != "\\"):
                        j += 1
                    out.math(s[i + 1:j])
                    i = j + 1
            elif c == "~":
                out.text(" ")
                i += 1
            elif c == "&":
                out.text(" ")
                i += 1
            elif s.startswith("---", i):
                out.text("\u2014")
                i += 3
            elif s.startswith("--", i):
                out.text("\u2013")
                i += 2
            elif s.startswith("``", i) or s.startswith("''", i):
                out.text('"')
                i += 2
            else:
                out.text(c)
                i += 1
        out.flush()

    def command(self, s, i, out):
        m = re.match(r"\\([A-Za-z@]+)(\*?)|\\(.)", s[i:])
        if not m:
            return i + 1
        if m.group(3) is not None:
            ch = m.group(3)
            j = i + 2
            if ch == "(":
                end = s.find("\\)", j)
                end = len(s) if end < 0 else end
                out.math(s[j:end])
                return end + 2
            if ch == "[":
                end = s.find("\\]", j)
                end = len(s) if end < 0 else end
                out.math(s[j:end])
                return end + 2
            if ch == "\\":
                out.text(" ")
                k = self.skip_space(s, j)
                if k < len(s) and s[k] == "[":
                    _, j = self.group(s, k, "[", "]")
                return j
            if ch in ACCENTS:
                arg, j = self.arg(s, j, "t")
                base = (arg or "").strip()
                if not base:
                    out.text(ch)  # \^{} and \~{} print the bare character
                else:
                    out.text(unicodedata.normalize("NFC", base[:1] + ACCENTS[ch]) + base[1:])
                return j
            out.text(ESCAPES.get(ch, ch))
            return j
        name, star = m.group(1), m.group(2)
        j = i + len(m.group(0))
        if not star:
            # TeX swallows the spaces after a control word.
            while j < len(s) and s[j] in " \t":
                j += 1
        if name in ACCENTS and len(name) == 1 and name in "uvHckrbd":
            arg, j = self.arg(s, j, "t")
            base = arg or ""
            out.text(unicodedata.normalize("NFC", base[:1] + ACCENTS[name]) + base[1:])
            return j
        if name == "begin":
            return self.begin(s, j, out)
        if name == "end":
            env, j = self.arg(s, j, "s")
            if env in self.label_envs:
                out.text(" ")
            return j
        if name in ("newcommand", "renewcommand", "providecommand", "DeclareMathOperator",
                    "newenvironment", "renewenvironment", "def", "let", "newtheorem",
                    "declaretheorem", "newcounter", "makeatletter", "makeatother"):
            return self.skip_definition(s, j, name)
        if name in ("input", "include", "subfile"):
            arg, j = self.arg(s, j, "s")
            if arg:
                self.run(self.read_file(arg.strip()), out)
            return j
        if name in REF_COMMANDS:
            for kind in ARGS[name]:
                _, j = self.arg(s, j, kind)
            out.marker("ref")
            return j
        if name in CITE_COMMANDS:
            for kind in ARGS[name]:
                _, j = self.arg(s, j, kind)
            out.marker("cite")
            return j
        if name in SYMBOLS:
            out.text(SYMBOLS[name])
            return j
        if name in LABEL_COMMANDS:
            out.marker("item" if name == "item" else "label")
        spec = ARGS.get(name)
        if spec is None:
            # Unknown command: its brace groups are text.
            return j
        for kind in spec:
            content, j = self.arg(s, j, kind)
            if content is not None and kind in "Ot":
                out.text(" ")
                self.run(content, out)
                out.text(" ")
        return j

    def skip_definition(self, s, j, name):
        """Skip a macro or theorem definition entirely; it prints nothing here."""
        if name in ("makeatletter", "makeatother"):
            return j
        if name in ("newtheorem", "declaretheorem"):
            env, j = self.arg(s, j, "o" if name == "declaretheorem" else "s")
            if name == "declaretheorem":
                env, j = self.arg(s, j, "s")
            if env:
                self.label_envs.add(env.strip())
            for kind in "oso":
                _, j = self.arg(s, j, kind)
            return j
        if name in ("def", "let"):
            j = self.skip_space(s, j)
            m = re.match(r"\\[A-Za-z@]+|\\.", s[j:])
            if m:
                j += len(m.group(0))
            while j < len(s) and s[j] not in "{\n":
                j += 1
            if j < len(s) and s[j] == "{":
                _, j = self.group(s, j)
            return j
        _, j = self.arg(s, j, "s")
        while True:
            k = self.skip_space(s, j)
            if k < len(s) and s[k] == "[":
                _, j = self.group(s, k, "[", "]")
            else:
                break
        _, j = self.arg(s, j, "s")
        if name in ("newenvironment", "renewenvironment"):
            _, j = self.arg(s, j, "s")
        return j

    def begin(self, s, j, out):
        env, j = self.arg(s, j, "s")
        env = (env or "").strip()
        if env in MATH_ENVS:
            end = s.find("\\end{%s}" % env, j)
            end = len(s) if end < 0 else end
            out.math(s[j:end])
            return end + len("\\end{%s}" % env)
        if env in VERBATIM_ENVS:
            for kind in ENV_ARGS.get(env, ""):
                _, j = self.arg(s, j, kind)
            end = s.find("\\end{%s}" % env, j)
            end = len(s) if end < 0 else end
            out.text(" " + s[j:end] + " ")
            return end + len("\\end{%s}" % env)
        if env in self.label_envs:
            out.marker("label")
        for kind in ENV_ARGS.get(env, "O" if env in self.label_envs else ""):
            content, j = self.arg(s, j, kind)
            if content is not None and kind in "Ot":
                self.run(content, out)
        return j


def strip_comments(text):
    out = []
    for line in text.split("\n"):
        k = 0
        while True:
            k = line.find("%", k)
            if k < 0:
                break
            backslashes = 0
            b = k - 1
            while b >= 0 and line[b] == "\\":
                backslashes += 1
                b -= 1
            if backslashes % 2 == 0:
                line = line[:k]
                break
            k += 1
        out.append(line)
    return "\n".join(out)


def project_tokens(root, main="main.tex"):
    """Tokens for what the project prints, starting from its main file."""
    parser = Parser(root, set(LABEL_ENVS))
    path = os.path.join(root, main)
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = strip_comments(fh.read())
    parser.seen_files.add(os.path.normpath(path))
    out = Tokens()
    start = text.find("\\begin{document}")
    preamble, body = (text[:start], text[start + len("\\begin{document}"):]) if start >= 0 else ("", text)
    end = body.find("\\end{document}")
    if end >= 0:
        body = body[:end]
    # Theorem definitions can live in the preamble or an input file.
    for m in re.finditer(r"\\(?:newtheorem\*?|declaretheorem(?:\[[^\]]*\])?)\{([^}]+)\}", preamble):
        parser.label_envs.add(m.group(1).strip())
    for name in ("title", "subtitle", "author"):
        for m in re.finditer(r"\\%s\s*(\[[^\]]*\])?\s*\{" % name, preamble):
            content, _ = Parser.group(preamble, m.end() - 1)
            parser.run(content, out)
            out.text(" ")
    parser.run(body, out)
    out.flush()
    return out.items, parser


def _pdflatex_safe(ch):
    """Characters LaTeX's default UTF-8 setup with T1 fonts can typeset in text."""
    o = ord(ch)
    return (0xA0 <= o <= 0x17F or 0x2010 <= o <= 0x2027 or o in (
        0x2030, 0x2032, 0x2033, 0x2039, 0x203A, 0x20AC, 0x2122, 0x2190, 0x2192, 0x02C6, 0x02DC,
        0x2212))


def lint(root, main="main.tex"):
    """Cheap structural checks that do not need a TeX installation."""
    problems, warnings = [], []
    texts = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".tex"):
                p = os.path.join(dirpath, f)
                with open(p, encoding="utf-8", errors="replace") as fh:
                    texts[os.path.relpath(p, root).replace(os.sep, "/")] = strip_comments(fh.read())
    labels, refs, cites, bibkeys = set(), set(), set(), set()
    for name, t in texts.items():
        clean = re.sub(r"\\\\", "  ", t)
        clean = re.sub(r"\\[{}]", "  ", clean)
        if clean.count("{") != clean.count("}"):
            problems.append("%s: %d '{' but %d '}'" % (name, clean.count("{"), clean.count("}")))
        stack = []
        for m in re.finditer(r"\\(begin|end)\{([^}]+)\}", t):
            if m.group(1) == "begin":
                stack.append(m.group(2))
            elif stack and stack[-1] == m.group(2):
                stack.pop()
            else:
                problems.append("%s: \\end{%s} does not match %s" % (
                    name, m.group(2), "\\begin{%s}" % stack[-1] if stack else "any \\begin"))
                break
        else:
            if stack:
                problems.append("%s: \\begin{%s} is never closed" % (name, stack[-1]))
        labels.update(re.findall(r"\\label\{([^}]+)\}", t))
        for m in re.finditer(r"\\(?:ref|eqref|cref|Cref|autoref|pageref|vref|nameref)\{([^}]+)\}", t):
            refs.update(x.strip() for x in m.group(1).split(","))
        for m in re.finditer(r"\\(?:%s)\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}" % "|".join(CITE_COMMANDS | {"nocite"}), t):
            cites.update(x.strip() for x in m.group(1).split(","))
        for m in re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", t):
            bibkeys.add(m.group(1).strip())
        for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t):
            target = m.group(1).strip()
            base = os.path.join(root, target)
            if not any(os.path.isfile(base + ext) for ext in ("", ".png", ".jpg", ".jpeg", ".pdf", ".eps")):
                problems.append("%s: image %s is missing" % (name, target))
        if re.search(r"\\\$\\textbackslash", t):
            warnings.append("%s: typed LaTeX from the doc is still escaped as text" % name)
        if "\\textquotesingle" in t:
            warnings.append("%s: contains \\textquotesingle; use a plain apostrophe" % name)
        prose = re.sub(r"\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", " ", t, flags=re.S)
        risky = sorted({ch for ch in prose if ord(ch) > 127 and not _pdflatex_safe(ch)})
        if risky:
            warnings.append("%s: characters pdflatex may not typeset outside maths: %s. Put them "
                            "in maths (\\(\\times\\)), or compile with LuaLaTeX or XeLaTeX."
                            % (name, " ".join(risky[:20])))
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".bib"):
                with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as fh:
                    bibkeys.update(k.strip() for k in re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", fh.read()))
    for r in sorted(refs - labels):
        problems.append("\\ref{%s} has no matching \\label" % r)
    for c in sorted(cites - bibkeys - {"*"}):
        problems.append("\\cite{%s} has no bibliography entry" % c)
    if main not in texts:
        problems.append("%s is missing" % main)
    return problems, warnings
