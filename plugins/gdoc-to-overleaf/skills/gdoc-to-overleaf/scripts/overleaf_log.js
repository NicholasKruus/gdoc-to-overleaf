// Run in an Overleaf project tab (javascript_tool) after a compile finishes.
// Reads the latest compile log the page itself fetched, and summarises it:
// page count, errors with their line, and the warnings that matter.
await (async () => {
  const logs = performance.getEntriesByType('resource')
    .map((e) => e.name).filter((u) => u.includes('/output/output.log'));
  if (!logs.length) return {error: 'No compile log yet. Click Recompile, wait for the PDF, then run this again.'};
  const res = await fetch(logs[logs.length - 1]);  // the log host rejects credentialed requests
  if (!res.ok) return {error: `Could not read the log: HTTP ${res.status}`};
  const log = await res.text();
  const lines = log.split('\n');
  const errors = [];
  lines.forEach((l, i) => {
    if (l.startsWith('! ')) {
      const where = lines.slice(i + 1, i + 8).find((x) => /^l\.\d+/.test(x)) || '';
      errors.push((l + ' ' + where).slice(0, 240));
    }
  });
  const count = (re) => (log.match(re) || []).length;
  const pages = log.match(/Output written on \S+ \((\d+) pages?/);
  const missingChars = [...new Set((log.match(/Missing character: There is no (.) /g) || [])
    .map((m) => m.slice(-2, -1)))];
  return {
    pages: pages ? Number(pages[1]) : null,
    errors: errors.slice(0, 15),
    undefinedReferences: count(/LaTeX Warning: Reference `[^']*' on page/g),
    undefinedCitations: count(/(?:LaTeX|Package natbib) Warning: Citation `[^']*' on page/g),
    multiplyDefinedLabels: count(/LaTeX Warning: Label `[^']*' multiply defined/g),
    overfullBoxes: count(/^Overfull \\hbox/gm),
    rerunNeeded: /Rerun to get|Label\(s\) may have changed/.test(log),
    missingChars,
    unicodeErrors: count(/Unicode character .* not set up for use with LaTeX/g),
  };
})()
