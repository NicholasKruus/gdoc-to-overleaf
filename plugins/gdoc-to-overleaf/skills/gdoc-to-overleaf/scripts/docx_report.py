"""Describe a .docx export's formatting, paragraph by paragraph.

pandoc keeps the structure Word styles declare (headings, lists, footnotes,
tables, maths) and drops the rest: fonts, colours, highlights, alignment,
indentation, comments. Authors often signal meaning with exactly those, such
as a centred italic "Figure 2: ..." line or a bold "Theorem 1." label. This
report puts them in front of Claude, which decides what each one means.

Only the standard library is used, so it runs anywhere Python 3.9+ does.
"""

import re
import zipfile
import xml.etree.ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}
W = "{%s}" % NS["w"]
M = "{%s}" % NS["m"]
MONO = {
    "courier new", "courier", "consolas", "roboto mono", "source code pro", "inconsolata",
    "menlo", "monaco", "fira code", "fira mono", "ibm plex mono", "ubuntu mono",
    "jetbrains mono", "space mono", "cousine", "pt mono", "dejavu sans mono", "lucida console",
    "noto sans mono", "cascadia code", "sf mono",
}
LABEL_START = re.compile(
    r"^(Theorem|Lemma|Proposition|Corollary|Definition|Remark|Example|Claim|Conjecture|"
    r"Assumption|Proof|Fact|Observation|Notation|Problem|Question|Exercise|Solution|Hypothesis|"
    r"Axiom|Algorithm)(?:\s+[0-9A-Z][0-9.]*|\s*\([^)]{1,60}\))+\s*[.:]|^Proof\s*[.:]")
CAPTION_START = re.compile(r"^(Figure|Fig\.|Table|Algorithm|Listing|Exhibit)\s*[0-9A-Z][0-9.]*\s*[.:\u2013\u2014-]", re.I)
TYPED_LATEX = re.compile(r"(\$[^$\s][^$]*\$|\\[a-zA-Z]{2,}\{|\\(?:begin|end|cite|ref|label)\b)")
NUMBERED_HEADING = re.compile(r"^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[A-Z]\.|[IVX]+\.)\s+\S")
PREVIEW = 200


def _attr(el, name):
    return None if el is None else el.get(W + name)


def _read(z, name):
    try:
        return ET.fromstring(z.read(name))
    except KeyError:
        return None


class Report:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.doc = _read(self.z, "word/document.xml")
        if self.doc is None:
            raise ValueError("Not a Word document: word/document.xml is missing.")
        self.styles = self._styles()
        self.numbering = self._numbering()
        self.links = self._links()
        self.comments = self._comments()
        self.lines = []
        self.counts = {"paragraphs": 0, "tables": 0, "images": 0, "footnotes": 0,
                       "equations": 0, "display_equations": 0, "comments": len(self.comments),
                       "suggested_insertions": 0, "suggested_deletions": 0}
        self.comment_anchor = {}
        self.suggestions = []
        self.base_size = self._base_size()
        self.in_footnote = False

    # ---- package parts ----------------------------------------------------

    def _styles(self):
        root = _read(self.z, "word/styles.xml")
        out = {}
        if root is None:
            return out
        for st in root.iter(W + "style"):
            sid = st.get(W + "styleId")
            name = st.find(W + "name")
            out[sid] = _attr(name, "val") or sid
        return out

    def _base_size(self):
        root = _read(self.z, "word/styles.xml")
        if root is None:
            return None
        for st in root.iter(W + "style"):
            if st.get(W + "styleId") == "Normal":
                sz = st.find(".//" + W + "sz")
                if sz is not None:
                    return int(_attr(sz, "val")) / 2
        sz = root.find(".//" + W + "docDefaults//" + W + "sz")
        return int(_attr(sz, "val")) / 2 if sz is not None else None

    def _numbering(self):
        root = _read(self.z, "word/numbering.xml")
        out = {}
        if root is None:
            return out
        abstract = {}
        for ab in root.iter(W + "abstractNum"):
            lv = {}
            for lvl in ab.iter(W + "lvl"):
                fmt = lvl.find(W + "numFmt")
                lv[lvl.get(W + "ilvl")] = _attr(fmt, "val") or "?"
            abstract[ab.get(W + "abstractNumId")] = lv
        for num in root.iter(W + "num"):
            ab = num.find(W + "abstractNumId")
            out[num.get(W + "numId")] = abstract.get(_attr(ab, "val"), {})
        return out

    def _links(self):
        root = _read(self.z, "word/_rels/document.xml.rels")
        out = {}
        if root is None:
            return out
        for rel in root:
            out[rel.get("Id")] = rel.get("Target")
        return out

    def _comments(self):
        root = _read(self.z, "word/comments.xml")
        out = {}
        if root is None:
            return out
        for c in root.iter(W + "comment"):
            text = " ".join("".join(t.text or "" for t in p.iter(W + "t"))
                            for p in c.iter(W + "p")).strip()
            out[c.get(W + "id")] = text
        return out

    # ---- runs -------------------------------------------------------------

    def _run_style(self, rpr):
        s = {}
        if rpr is None:
            return s
        for flag in ("b", "i", "strike", "smallCaps", "caps"):
            el = rpr.find(W + flag)
            if el is not None and _attr(el, "val") not in ("0", "false"):
                s[flag] = True
        u = rpr.find(W + "u")
        if u is not None and _attr(u, "val") not in ("none", None):
            s["u"] = True
        va = rpr.find(W + "vertAlign")
        if va is not None and _attr(va, "val") in ("superscript", "subscript"):
            s["va"] = _attr(va, "val")
        fonts = rpr.find(W + "rFonts")
        if fonts is not None:
            face = _attr(fonts, "ascii") or _attr(fonts, "hAnsi") or ""
            if face:
                s["font"] = face
        col = rpr.find(W + "color")
        if col is not None and _attr(col, "val") not in (None, "auto", "000000"):
            s["color"] = "#" + _attr(col, "val")
        hl = rpr.find(W + "highlight")
        if hl is not None and _attr(hl, "val") not in (None, "none"):
            s["hl"] = _attr(hl, "val")
        shd = rpr.find(W + "shd")
        if shd is not None and _attr(shd, "fill") not in (None, "auto", "FFFFFF", "ffffff"):
            s["hl"] = "#" + _attr(shd, "fill")
        sz = rpr.find(W + "sz")
        if sz is not None and self.base_size and abs(int(_attr(sz, "val")) / 2 - self.base_size) >= 1:
            s["size"] = int(_attr(sz, "val")) / 2
        return s

    def _mark(self, text, s, in_link):
        if not text:
            return text
        if s.get("va") == "superscript":
            text = "^{" + text + "}"
        elif s.get("va") == "subscript":
            text = "_{" + text + "}"
        if s.get("font", "").lower() in MONO:
            text = "`" + text + "`"
        if s.get("b"):
            text = "**" + text + "**"
        if s.get("i"):
            text = "_" + text + "_"
        if s.get("strike"):
            text = "~~" + text + "~~"
        if s.get("u") and not in_link:
            text = "__" + text + "__"
        if s.get("hl"):
            text = "==" + text + "==(" + s["hl"] + ")"
        if s.get("color") and not in_link:
            text = "{" + s["color"] + ":" + text + "}"
        if s.get("size") and not self.in_footnote:
            text = "{" + ("%g" % s["size"]) + "pt:" + text + "}"
        if s.get("smallCaps") or s.get("caps"):
            text = "{caps:" + text + "}"
        return text

    def _walk_inline(self, el, acc, in_link=False, change=None):
        """Collect marked-up text and facts from a paragraph's children."""
        for child in el:
            tag = child.tag
            if tag == W + "r":
                s = self._run_style(child.find(W + "rPr"))
                acc["styles"].append(s)
                parts = []
                for item in child:
                    if item.tag == W + "t":
                        parts.append(item.text or "")
                    elif item.tag == W + "delText":
                        parts.append(item.text or "")
                    elif item.tag == W + "tab":
                        parts.append("\t")
                    elif item.tag == W + "br":
                        parts.append("[page break]" if _attr(item, "type") == "page" else "↵")
                    elif item.tag == W + "footnoteReference":
                        acc["footnotes"] += 1
                        parts.append("[^fn]")
                    elif item.tag == W + "drawing":
                        acc["images"].append(self._image(item))
                        parts.append("[image]")
                text = "".join(parts)
                plain = text
                if text == "[^fn]":
                    acc["text"].append(text)
                    acc["plain"].append("")
                    continue
                if change:
                    text = "{%s:%s}" % (change, text)
                    self.suggestions.append((change, plain))
                acc["text"].append(self._mark(text, s, in_link))
                acc["plain"].append("" if change == "suggest-insert" else plain)
            elif tag == W + "hyperlink":
                target = self.links.get(child.get("{%s}id" % NS["r"])) or ("#" + (_attr(child, "anchor") or ""))
                sub = {"text": [], "plain": [], "styles": [], "footnotes": 0, "images": [], "math": 0}
                self._walk_inline(child, sub, True, change)
                label = "".join(sub["text"])
                acc["text"].append("[" + label + "](" + (target or "") + ")")
                acc["plain"].extend(sub["plain"])
                acc["styles"].extend(sub["styles"])
                acc["footnotes"] += sub["footnotes"]
                acc["images"].extend(sub["images"])
                acc["math"] += sub["math"]
                if target and target.startswith("#"):
                    acc["internal_links"] += 1
            elif tag in (W + "ins", W + "del", W + "moveTo", W + "moveFrom"):
                kind = "suggest-insert" if tag in (W + "ins", W + "moveTo") else "suggest-delete"
                key = "suggested_insertions" if kind == "suggest-insert" else "suggested_deletions"
                self.counts[key] += 1
                self._walk_inline(child, acc, in_link, kind)
            elif tag in (M + "oMath", M + "oMathPara"):
                n = len(list(child.iter(M + "oMath"))) or 1
                acc["math"] += n
                if tag == M + "oMathPara":
                    acc["display_math"] += n
                acc["text"].append("$math$")
            elif tag == W + "commentRangeStart":
                acc["comments"].append(child.get(W + "id"))
            elif tag in (W + "smartTag", W + "sdt", W + "sdtContent", W + "customXml", W + "fldSimple"):
                self._walk_inline(child, acc, in_link, change)
            elif tag == W + "bookmarkStart":
                name = _attr(child, "name") or ""
                if name and not name.startswith("_"):
                    acc["bookmarks"].append(name)

    def _image(self, drawing):
        ext = drawing.find(".//" + "{%s}" % NS["wp"] + "extent")
        doc_pr = drawing.find(".//" + "{%s}" % NS["wp"] + "docPr")
        size = ""
        if ext is not None:
            size = "%.1fx%.1fin" % (int(ext.get("cx", 0)) / 914400, int(ext.get("cy", 0)) / 914400)
        alt = (doc_pr.get("descr") or doc_pr.get("title") or "") if doc_pr is not None else ""
        floating = drawing.find("{%s}anchor" % NS["wp"]) is not None
        return {"size": size, "alt": alt[:80], "floating": floating}

    # ---- paragraphs ---------------------------------------------------------

    def paragraph(self, p, where="body"):
        ppr = p.find(W + "pPr")
        style_id = _attr(ppr.find(W + "pStyle") if ppr is not None else None, "val") or "Normal"
        style = self.styles.get(style_id, style_id)
        flags = []
        if ppr is not None:
            jc = _attr(ppr.find(W + "jc"), "val")
            if jc in ("center", "right", "both", "end"):
                flags.append({"both": "justified", "end": "right"}.get(jc, jc))
            ind = ppr.find(W + "ind")
            if ind is not None:
                left = int(_attr(ind, "left") or _attr(ind, "start") or 0)
                first = int(_attr(ind, "firstLine") or 0)
                if left >= 200 and ppr.find(W + "numPr") is None:
                    flags.append("indent %dpt" % round(left / 20))
                if first >= 200:
                    flags.append("first-line indent")
            num = ppr.find(W + "numPr")
            if num is not None:
                nid = _attr(num.find(W + "numId"), "val")
                lvl = _attr(num.find(W + "ilvl"), "val") or "0"
                fmt = self.numbering.get(nid, {}).get(lvl, "?")
                if nid and nid != "0":
                    flags.append("list %s L%s #%s" % (fmt, lvl, nid))
            if ppr.find(W + "pageBreakBefore") is not None and _attr(ppr.find(W + "pageBreakBefore"), "val") not in ("0", "false"):
                flags.append("page break before")
        acc = {"text": [], "plain": [], "styles": [], "footnotes": 0, "images": [], "math": 0,
               "display_math": 0, "comments": [], "bookmarks": [], "internal_links": 0}
        self._walk_inline(p, acc)
        text = "".join(acc["text"]).strip()
        plain = "".join(acc["plain"]).strip()
        visible = [s for s, t in zip(acc["styles"], acc["plain"]) if t.strip()]

        self.counts["paragraphs"] += 1
        self.counts["footnotes"] += acc["footnotes"] if where != "footnote" else 0
        self.counts["images"] += len(acc["images"])
        self.counts["equations"] += acc["math"]
        self.counts["display_equations"] += acc["display_math"]

        if visible and all(s.get("font", "").lower() in MONO for s in visible):
            flags.append("all monospace")
        if visible and all(s.get("b") for s in visible) and not style.lower().startswith(("heading", "title")):
            flags.append("all bold")
        if visible and all(s.get("i") for s in visible):
            flags.append("all italic")
        sizes = {s.get("size") for s in visible if s.get("size")}
        if sizes and len(visible) == len([s for s in visible if s.get("size")]):
            flags.append("text %spt" % "/".join("%g" % x for x in sorted(sizes)))
        if acc["math"] and not plain.replace("↵", "").strip():
            flags.append("equation only")
        for img in acc["images"]:
            flags.append("image %s%s%s" % (img["size"], " floating" if img["floating"] else "",
                                           ", alt: " + repr(img["alt"]) if img["alt"] else ", no alt"))
        if acc["internal_links"]:
            flags.append("%d internal link(s)" % acc["internal_links"])
        if acc["bookmarks"]:
            flags.append("bookmark " + ",".join(acc["bookmarks"][:3]))
        hints = []
        if LABEL_START.match(plain):
            hints.append("starts with a theorem-like label")
        if CAPTION_START.match(plain) and len(plain) < 400:
            hints.append("looks like a caption")
        if TYPED_LATEX.search(plain):
            hints.append("contains typed LaTeX")
        if style.lower().startswith("heading") and NUMBERED_HEADING.match(plain):
            hints.append("heading carries its own number")
        if not style.lower().startswith(("heading", "title", "subtitle")) and visible and \
                "all bold" in flags and len(plain) < 90 and not plain.endswith("."):
            hints.append("could be an unstyled heading")
        for cid in acc["comments"]:
            self.comment_anchor[cid] = self.counts["paragraphs"]
        return {"n": self.counts["paragraphs"], "style": style, "flags": flags, "hints": hints,
                "text": text, "plain": plain, "comments": acc["comments"]}

    def _is_plain(self, info):
        return (info["style"] in ("Normal", "normal", "Body Text") and not info["flags"]
                and not info["hints"] and not info["comments"]
                and not re.search(r"\*\*|`|==|~~|__|\{#|\{caps|\{[0-9.]+pt|\^\{|_\{|\{suggest", info["text"]))

    def table(self, tbl, depth=0):
        self.counts["tables"] += 1
        rows = tbl.findall(W + "tr")
        cols = max((len(r.findall(W + "tc")) for r in rows), default=0)
        merged = any(tc.find(".//" + W + "gridSpan") is not None or tc.find(".//" + W + "vMerge") is not None
                     for r in rows for tc in r.findall(W + "tc"))
        header = rows[0].find(".//" + W + "tblHeader") is not None if rows else False
        cells, notes = [], []
        for ri, row in enumerate(rows):
            for tc in row.findall(W + "tc"):
                for p in tc.findall(".//" + W + "p"):
                    info = self.paragraph(p, "table")
                    if ri == 0:
                        cells.append(info["text"])
                    hints = [h for h in info["hints"] if h != "could be an unstyled heading"]
                    if info["flags"] or hints:
                        notes.append("r%d: %s" % (ri + 1, "; ".join(info["flags"] + hints)))
        first = " | ".join(c for c in cells if c)[:PREVIEW]
        line = "T%d  %dx%d table%s%s. Row 1: %s" % (
            self.counts["tables"], len(rows), cols, ", merged cells" if merged else "",
            ", header row marked" if header else "", first)
        if notes:
            line += "  [cells: " + "; ".join(sorted(set(notes))[:6]) + "]"
        return line

    def build(self):
        body = self.doc.find(W + "body")
        out, plain_run = [], []

        def flush_plain():
            if plain_run:
                if len(plain_run) == 1:
                    out.append("P%d  plain paragraph" % plain_run[0])
                else:
                    out.append("P%d-P%d  %d plain paragraphs" % (plain_run[0], plain_run[-1], len(plain_run)))
                plain_run.clear()

        def visit(container):
            for el in container:
                if el.tag == W + "p":
                    info = self.paragraph(el)
                    if not info["plain"] and not info["flags"]:
                        continue
                    if self._is_plain(info):
                        plain_run.append(info["n"])
                        continue
                    flush_plain()
                    text = info["text"]
                    if len(text) > PREVIEW:
                        text = text[:PREVIEW] + "...(+%d chars)" % (len(text) - PREVIEW)
                    meta = [info["style"]] + info["flags"]
                    line = "P%d  [%s] %s" % (info["n"], ", ".join(meta), text)
                    if info["hints"]:
                        line += "   <- " + "; ".join(info["hints"])
                    if info["comments"]:
                        line += "   (comment %s)" % ",".join("C" + c for c in info["comments"])
                    out.append(line)
                elif el.tag == W + "tbl":
                    flush_plain()
                    out.append(self.table(el))
                elif el.tag == W + "sdt":
                    content = el.find(W + "sdtContent")
                    if content is not None:
                        visit(content)
        visit(body)
        flush_plain()

        notes = _read(self.z, "word/footnotes.xml")
        fn_lines = []
        self.in_footnote = True
        if notes is not None:
            for fn in notes.iter(W + "footnote"):
                if fn.get(W + "type") in ("separator", "continuationSeparator"):
                    continue
                texts = [self.paragraph(p, "footnote")["text"] for p in fn.iter(W + "p")]
                self.counts["paragraphs"] -= len(texts)
                joined = " ".join(t for t in texts if t)
                if joined:
                    fn_lines.append("FN%s  %s" % (fn.get(W + "id"), joined[:PREVIEW]))
        return out, fn_lines

    def render(self, title_hint=""):
        body, fns = self.build()
        lines = ["# Formatting report", ""]
        if title_hint:
            lines += ["Doc: " + title_hint, ""]
        lines += [
            "One line per paragraph that carries formatting pandoc does not keep. Runs of",
            "ordinary paragraphs are collapsed. Inline marks: **bold** _italic_ `monospace`",
            "==highlight==(colour) ~~strike~~ __underline__ ^{sup} _{sub} {#colour:text}",
            "{Npt:text} [text](link) $math$ [^fn] [image] {suggest-insert:...} {suggest-delete:...}.",
            "Text after <- is a hint from simple patterns, not a conclusion.",
            "",
            "Counts: " + ", ".join("%s %d" % (k.replace("_", " "), v) for k, v in self.counts.items()),
            "",
            "## Body",
            "",
        ] + body
        if fns:
            lines += ["", "## Footnotes", ""] + fns
        if self.comments:
            lines += ["", "## Comments (not carried into the LaTeX unless you choose to)", ""]
            for cid, text in self.comments.items():
                where = self.comment_anchor.get(cid)
                lines.append("C%s  %s%s" % (cid, "on P%d: " % where if where else "", text))
        if self.suggestions:
            lines += ["", "## Pending suggestions (left out of the draft by default)", ""]
            for kind, text in self.suggestions:
                lines.append("%s: %r" % (kind, text[:120]))
        return "\n".join(lines) + "\n"


def report(path, title_hint=""):
    r = Report(path)
    text = r.render(title_hint)
    return text, r.counts
