# Inferring intent from Google Docs formatting

Google Docs has no theorem, caption, display-equation or code-block element, so
authors signal these with formatting. pandoc keeps only what Word styles
declare. `report.md` shows the rest. Use both to decide what each paragraph is.

Work paragraph by paragraph, comparing `report.md` with `gdoc/body.tex`. Change
markup and structure; never the words. When a reading is uncertain, keep the
text as it is (with its bold or italic) and tell the user.

## Signals and what they usually mean

| In the doc (report line) | Usually means | LaTeX |
|---|---|---|
| `[Title]` paragraph | Paper title | `\title{...}` in `main.tex`; delete it from the body |
| `[Subtitle]`, or a line of names and affiliations under the title | Authors | `\author{...}`, one author per `\and`, affiliation after `\\` |
| Heading or bold line "Abstract", then a paragraph | Abstract | `\begin{abstract}...\end{abstract}` (or the template's macro) |
| Heading carries its own number ("2.1 Method") | Numbered section | `\subsection{Method}`; LaTeX numbers it |
| Heading levels 1/2/3 | Section depth | `\section`, `\subsection`, `\subsubsection`; a bold run-in label that ends with a full stop is `\paragraph{...}` |
| `**Theorem 1.**` / `**Lemma 2 (Name).**` at a paragraph start | Theorem-like statement | `\begin{theorem}[Name] ... \end{theorem}` with `\label{thm:...}`; drop the typed label and number. Same for lemma, proposition, corollary, definition, remark, example, assumption, claim, conjecture. Declare any missing environment in `main.tex` |
| `_Proof._` at a paragraph start, ending with ∎ or □ | Proof | `\begin{proof} ... \end{proof}`; drop "Proof." and the end mark |
| `[center, equation only]` | Display equation | `\[ ... \]`, or `equation` with `\label` if the text refers to it by number "(3)", which then becomes `\eqref{...}` |
| Consecutive display equations aligned at `=` | Aligned derivation | `align` (or `align*`) with `&=` |
| Text typed as `$...$` or `\command{...}` (hint: contains typed LaTeX) | Maths or LaTeX the author typed by hand | Real maths `\( ... \)`; real commands. pandoc escaped them as text |
| `[all monospace]` run of paragraphs | Code or pseudocode | `verbatim` (or `lstlisting`). Inline monospace is `\texttt{}` |
| Centred italic "Figure N: ..." next to an `[image]` | Figure caption | `figure` with `\includegraphics`, `\caption{...}`, `\label{fig:...}`; drop "Figure N:" |
| Centred italic "Table N: ..." next to a table | Table caption | `table` with `\caption` above the `tabular` (the usual convention) and `\label{tab:...}` |
| "Figure 2", "Table 1", "Section 3", "Theorem 1", "Eq. (4)" in the text | Cross-reference | `Figure~\ref{fig:...}` etc. Only when the target exists in the doc |
| `(Author, Year)`, `Author (Year)`, `[12]` and a reference list at the end | Citations | `thebibliography` with one `\bibitem[Author(Year)]{key}` per entry, in the doc's wording, and `\citet`/`\citep` (the default template loads natbib; with a venue template, use its citation commands). Keep the entry text exactly as typed. A `.bib` file only if the style guide demands BibTeX |
| A link whose text is a citation | Citation that also links | Prefer the citation; keep `\href` only if there is no reference list |
| `==TODO ...==` highlight, or coloured notes to self | Author's note | Keep the words. Ask the user whether to keep, hide (`%` comment, which the check will flag for a declared allowance) or drop them |
| Indented paragraph, not in a list | Block quotation | `quote` (or `quotation` for several paragraphs) |
| Bold header row of a table | Table head | `\toprule` / `\midrule` / `\bottomrule` (booktabs); left-align text columns, right-align numbers |
| Merged table cells | Spanning headers | `\multicolumn` / `\multirow` |
| Footnote | Footnote | `\footnote{...}` (pandoc already does this) |
| Internal link to a heading or bookmark | Cross-reference | `\ref` to a `\label` you place on the target |
| "Appendix" heading near the end | Appendix | `\appendix` before it, then `\section`s |
| Text in a smaller or larger size, or a colour, with no other pattern | Usually nothing | Leave it plain and mention it if it looks deliberate |

## Things to tidy from pandoc

- `longtable` with `p{...}` columns → a `table` float with a simple `tabular`
  unless the table is longer than a page.
- `\def\labelenumi{...}` lines and `\tightlist` → delete; LaTeX's defaults are fine.
- `\hl{...}` and `\ul{...}` come from highlights and underlines (soul package).
  Keep `\hl` only for a TODO the user wants visible.
- Image sizes: pandoc sets `width` and `height` from the doc. Use
  `width=\linewidth` (or a fraction of it) and drop the height so the aspect ratio
  holds. Keep the `alt` text.
- `\href{url}{\ul{text}}` → `\href{url}{text}`.

## Doc comments and suggestions

Comments are listed in the report, not converted. Ask the user if any should
become a `\todo` or `%` comment. Pending suggestions are left out unless the user
asked to apply them.

## Write down what you decided

Add one short line per pattern to `decisions` in `WORK/notes.json`, such as
`"bold 'Theorem N.' paragraphs -> theorem environments"` or `"centred italic
'Figure N:' lines -> captions of the image above"`. The next sync reads them
back, so the same doc produces the same LaTeX.
