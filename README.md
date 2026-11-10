# Google Doc to Overleaf

A [Claude Code](https://claude.com/claude-code) skill that turns a Google Doc into a
LaTeX project and puts it in Overleaf. It can create a new project or update an
existing one, and can format the paper to a style guide, such as a NeurIPS,
ICML, ICLR, ACL, IEEE or ACM template.

Ask Claude something like:

> Put https://docs.google.com/document/d/... in Overleaf, formatted for ICML 2026.

> Sync my paper doc into https://www.overleaf.com/project/...

## What it does

1. **Exports** the doc as .docx through your own signed-in Chrome, using
   [Claude in Chrome](https://claude.com/chrome). No Google Cloud setup and no
   sharing settings are needed. Without Chrome, you download the .docx yourself.
2. **Converts** the export with [pandoc](https://pandoc.org). This keeps headings,
   lists, footnotes, tables, images, links and Google Docs equations, which become
   LaTeX maths.
3. **Infers what your formatting means.** It finds what pandoc drops and maps it
   to LaTeX:
   - a bold "Theorem 1." becomes a `theorem` environment;
   - a centred italic "Figure 2: ..." under an image becomes its caption, and
     "Figure 2" in the text becomes `\ref`;
   - a centred equation becomes display maths, and Courier lines become `verbatim`;
   - `$x^2$` typed into the doc becomes real maths, and "(Author, 2020)" becomes
     `\citet`.
4. **Applies a style guide** if you name one. It uses the venue's official
   template, submission or camera-ready mode, anonymisation, required sections,
   caption placement, citation style and page limit. It never writes content for
   you; it lists what only you can supply.
5. **Checks every word.** A deterministic check compares what the LaTeX prints
   with the doc, word by word and formula by formula. Claude may change structure
   but not your words. The check accepts only:
   - text LaTeX now generates, such as theorem labels, section and reference
     numbers, and citations;
   - text that moved as a block, such as a caption placed above its table;
   - changes Claude declares, such as anonymising authors. These are shown to you.
6. **Puts it in Overleaf** by uploading a new project, or by updating only the
   files it manages in an existing one (`gdoc/`). Before an update, it checks
   whether anyone edited those files in Overleaf since the last sync, and stops
   if they did. Then it compiles and reports errors and page count.

## Install

In Claude Code:

```
/plugin marketplace add NicholasKruus/gdoc-to-overleaf
/plugin install gdoc-to-overleaf@gdoc-to-overleaf
```

Or copy `plugins/gdoc-to-overleaf/skills/gdoc-to-overleaf/` to
`~/.claude/skills/gdoc-to-overleaf/`. On Windows that is
`%USERPROFILE%\.claude\skills\gdoc-to-overleaf\`.

### Requirements

- Claude Code on macOS, Windows or Linux.
- Python 3.9 or later. The scripts use only the standard library.
- pandoc 3.1 or later:
  - macOS: `brew install pandoc`
  - Windows: `winget install --id JohnMacFarlane.Pandoc -e`
  - Linux: see [pandoc.org/installing](https://pandoc.org/installing.html); distro packages are often too old.

  The skill checks this on first use and offers to install it.
- Optional: [Claude in Chrome](https://claude.com/chrome), signed in to Google and
  Overleaf, for the hands-free export and upload. Without it, the skill asks you to
  download the .docx and upload the zip.

Overleaf's free plan is enough. The skill uses Overleaf's web interface, not its
Git integration.

## Privacy

Your doc goes from your browser to a temporary folder on your computer, and from
there to your own Overleaf account. The scripts make no network requests. Claude
reads the doc's text to do the conversion. The temporary folder is deleted at the
end.

## Limits

- Drawings and some embedded objects do not survive the .docx export; the skill
  tells you when that happens.
- Zotero citations in Google Docs become plain text, not `\cite` keys.
- Comments and pending suggestions are listed, not converted. Suggestions are left
  out unless you ask for them to be applied.
- The check sees words, maths and counts. It does not see emphasis or layout, so
  look over the PDF.
- It runs when you ask. It does not sync on a schedule.
- It is for Claude Code. In claude.ai chat, the sandbox cannot reach Google
  or Overleaf.

## Development

```
python -m unittest -v tests/test_g2o.py
```

CI runs the tests on Linux, macOS and Windows. `tests/fixtures/test-paper.docx`
is a Google Docs export with a title, footnote, table, image, equations, a
comment and a pending suggestion. `tests/fixtures/inferred-body.tex` is the LaTeX
a correct run should produce from it.

## Licence

MIT. See [LICENSE](LICENSE).
