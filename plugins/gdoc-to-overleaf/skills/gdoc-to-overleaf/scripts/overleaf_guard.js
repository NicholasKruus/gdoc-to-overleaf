// Run in an Overleaf project tab (javascript_tool). Downloads the project as a
// zip from the same origin, hashes the files the last sync wrote, and reports
// which ones changed in Overleaf since then. Returns names and hashes only,
// never file contents, except main.tex's \input lines.
//
// Text files are hashed exactly as common.file_hash does: LF line endings,
// trailing spaces and tabs removed from each line, blank lines trimmed at both ends.
await (async () => {
  const MANIFEST = 'gdoc/gdoc-to-overleaf.json';
  const TEXT = ['.tex', '.bib', '.bst', '.cls', '.sty', '.json', '.md', '.txt', '.bbl'];
  const id = location.pathname.match(/\/project\/([0-9a-f]{24})/)?.[1];
  if (!id) return {error: 'Not an Overleaf project page.'};
  const res = await fetch(`/project/${id}/download/zip`, {credentials: 'same-origin'});
  if (!res.ok) return {error: `Project download failed: HTTP ${res.status}`};
  const buf = await res.arrayBuffer();
  const dv = new DataView(buf), u8 = new Uint8Array(buf);
  let eocd = -1;
  for (let i = u8.length - 22; i >= 0; i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) return {error: 'The download was not a zip.'};
  const files = {};
  let p = dv.getUint32(eocd + 16, true);
  for (let k = 0, n = dv.getUint16(eocd + 10, true); k < n; k++) {
    const method = dv.getUint16(p + 10, true), size = dv.getUint32(p + 20, true);
    const nl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true);
    const off = dv.getUint32(p + 42, true);
    const name = new TextDecoder().decode(u8.slice(p + 46, p + 46 + nl));
    const start = off + 30 + dv.getUint16(off + 26, true) + dv.getUint16(off + 28, true);
    files[name] = {method, data: u8.slice(start, start + size)};
    p += 46 + nl + el + cl;
  }
  const bytes = async (f) => f.method === 0 ? f.data
    : new Uint8Array(await new Response(new Blob([f.data]).stream()
        .pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
  const hash = async (name, data) => {
    if (TEXT.some((e) => name.toLowerCase().endsWith(e))) {
      let t = new TextDecoder().decode(data).replace(/\r\n?/g, '\n');
      t = t.split('\n').map((l) => l.replace(/[ \t]+$/, '')).join('\n').replace(/^\n+|\n+$/g, '');
      data = new TextEncoder().encode(t);
    }
    const d = await crypto.subtle.digest('SHA-256', data);
    return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('');
  };
  const out = {files: Object.keys(files).length};
  if (files['main.tex']) {
    const main = new TextDecoder().decode(await bytes(files['main.tex']));
    out.mainInputs = (main.match(/\\(?:input|include)\{[^}]*\}/g) || []).slice(0, 20);
  }
  if (!files[MANIFEST]) {
    out.manifest = false;
    out.managedLooking = Object.keys(files).filter((n) => n.startsWith('gdoc/'));
    return out;
  }
  const manifest = JSON.parse(new TextDecoder().decode(await bytes(files[MANIFEST])));
  out.manifest = true;
  out.lastSync = manifest.synced;
  out.doc = manifest.doc;
  out.style = manifest.style;
  out.decisions = manifest.decisions;
  out.edited = []; out.missing = []; out.unchanged = 0;
  for (const [name, want] of Object.entries(manifest.managed || {})) {
    if (!files[name]) { out.missing.push(name); continue; }
    (await hash(name, await bytes(files[name]))) === want ? out.unchanged++ : out.edited.push(name);
  }
  out.added = Object.keys(files).filter((n) => n.startsWith('gdoc/') && n !== MANIFEST && !(n in (manifest.managed || {})));
  return out;
})()
