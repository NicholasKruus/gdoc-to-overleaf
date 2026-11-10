# Putting the project in Overleaf (Claude in Chrome)

Everything here goes through the user's own signed-in Overleaf tab, in the same
way a person would do it. Overleaf's free plan is enough. Tested against
overleaf.com in November 2026. If a step stops matching the page, look at a
screenshot and adapt; tell the user what changed.

Ground rules:

- **Uploads come from the work folder.** Chrome's `file_upload` accepts only files
  the session can read, which is why `WORK` lives under the session's scratchpad
  or working directory. Each upload call is capped at 10 MB.
- **Never click a dialog that deletes, shares or publishes.** Overwriting the
  files this skill manages is fine once the edit guard has passed.
- **Do not use `credentials: 'include'`** when fetching compile output; the log
  host rejects it. The scripts below already handle this.
- If Overleaf shows a cookie banner, choose the essential-only option.
- If the tab lands on a login page, stop. The user signs in; never type their
  credentials.

## New project

1. Open `https://www.overleaf.com/project`.
2. Click **New project**, then **Existing project (.zip)** (labelled "Upload
   project" in some versions).
3. Find the dialog's file input (`find`: "file input in the upload dialog") and
   `file_upload` `WORK/upload.zip`. Do not click "Select a .zip file", which
   opens a native picker you cannot use.
4. Overleaf creates the project, names it after `\title`, opens it and compiles
   it. The URL is `https://www.overleaf.com/project/<id>`. Give that to the user.

Overleaf drops dotfiles from an imported zip, which is why the sync manifest is
`gdoc/gdoc-to-overleaf.json`, not a hidden file.

## Update an existing project

### 1. Run the edit guard

Open the project tab and run `scripts/overleaf_guard.js` with `javascript_tool`
(paste the file's contents; it ends in an awaited expression). It downloads the
project from the same origin, hashes the files the last sync wrote, and returns:

| Field | Meaning |
|---|---|
| `manifest: true`, `edited: []`, `missing: []` | Safe: nothing this skill manages was changed in Overleaf. Go ahead. |
| `edited: [...]` | Someone changed these managed files in Overleaf since `lastSync`. **Stop.** Tell the user which files, and offer: (a) they move those edits into the Google Doc and you sync again, (b) overwrite anyway, (c) stop. Default to (a). |
| `missing: [...]` | Managed files were deleted or renamed in Overleaf. Ask before recreating them. |
| `added: [...]` | Files in `gdoc/` that the last sync did not write. They are left alone; mention them. |
| `manifest: false` with `managedLooking` files | `gdoc/` exists but has no manifest, so you cannot tell what was edited. Ask before overwriting. |
| `manifest: false`, no `gdoc/` | First sync into this project (for example, a co-author's template). See "First sync into an existing project". |
| `mainFile`, `mainInputs` | The project's main file (the top-level `.tex` with `\documentclass`; templates often call it something other than `main.tex`) and its `\input` lines. The body is only used if `\input{gdoc/body}` (and `\input{gdoc/support}` in the preamble) are there. |

Also read the manifest's `decisions` and `style` (returned as fields) and apply
them in step 4 of the skill.

### 2. Upload the managed files

Upload folder by folder. Upload `gdoc/gdoc-to-overleaf.json` last, so an
interrupted sync is caught by the next guard run.

1. Click a file that is not being replaced (usually `main.tex`), so the editor
   does not have a replaced file open. If a replaced file is open, Overleaf shows
   "Document Updated Externally"; click **OK**.
2. In the file tree, click the target folder (`gdoc`, or `gdoc/figures`). Uploads
   go into the selected folder.
3. Click **Upload** in the file-tree toolbar. In the "Add files" dialog, use
   `find` for the *files* input (not the folder input) and `file_upload` that
   folder's files.
4. If Overleaf asks "The following files already exist ... Do you want to
   overwrite them?", click **Overwrite**. The guard has already established that
   these are this skill's files.
5. Repeat for each folder that has new or changed files.

To create a missing folder: select its parent, click **New folder** in the
file-tree toolbar, type the name, and press Enter. Check where it landed: a new
folder can end up in the project root even with its parent selected. If so, drag
it onto the parent folder in the file tree.

A file the new sync no longer produces (an image removed from the doc) stays in
Overleaf. List it for the user; do not delete it.

### First sync into an existing project

The usual case is a co-author's project already set up with a venue template.

1. Create `gdoc/` and `gdoc/figures/` with **New folder**, and upload the files.
2. The main file (`mainFile` from the guard) needs `\input{gdoc/support}` in the preamble and `\input{gdoc/body}`
   where the content goes, plus the doc's title, authors and abstract in the
   template's macros. **Ask before changing their `main.tex`**, and show the exact
   lines. With a yes, fetch the current main file's text (adapt the guard script
   to return it), build the new version in `WORK/run/project/` under the same
   name, run the check with `--main <that name>` and `--skip-input` for
   template-owned inputs such as a checklist, then upload it to the project root
   (open another root file first so the root folder is selected) and confirm
   **Overwrite**.

## Compile and verify

1. Click **Recompile** and wait for the PDF (about 5–10 seconds).
2. Run `scripts/overleaf_log.js` with `javascript_tool`. It reads the latest
   compile log the page fetched and returns `pages`, `errors` (with line
   numbers), undefined references and citations, multiply-defined labels,
   overfull boxes, and missing characters.
3. Fix any errors in the LaTeX in `WORK`, re-run the check, re-package and
   re-upload. Common ones:
   - `\citet` undefined: natbib is not loaded.
   - "Unicode character ... not set up": put the character in maths, or switch the
     project to LuaLaTeX or XeLaTeX (Menu > Compiler).
   - Option clash: a line in `gdoc/support.tex` conflicts with the template.
4. `find` can confirm specific text in the PDF preview, since Overleaf renders a
   text layer. Use it to spot-check a few changed passages.
5. Compare `pages` with the style guide's limit.

## Without Claude in Chrome

Tell the user:

1. Go to overleaf.com and sign in.
2. Click **New project** > **Upload project**, and choose `<path to upload.zip>`.

For an update, they upload the files in `gdoc/` through **Upload** in the file
tree, into the `gdoc` folder. Ask them first whether anyone has edited those
files in Overleaf.
