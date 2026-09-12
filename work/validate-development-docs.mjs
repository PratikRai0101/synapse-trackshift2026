import fs from 'node:fs';
import path from 'node:path';

// Documentation QA only: this does not validate physics, software or research claims.
const root = process.cwd();
const base = path.join(root, 'docs/development');
const errors = [];
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
  const name = path.join(dir, entry.name);
  return entry.isDirectory() ? walk(name) : [name];
});
const files = walk(base);
const markdown = files.filter(file => file.endsWith('.md'));
let localLinks = 0;
let tableRows = 0;
const refs = fs.readFileSync(path.join(base, '10-references.md'), 'utf8');
const knownRefs = new Set([...refs.matchAll(/\*\*([PDS]\d{2}) —/g)].map(match => match[1]));

for (const file of markdown) {
  const source = fs.readFileSync(file, 'utf8');
  const relative = path.relative(root, file);
  for (const match of source.matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)) {
    let target = match[1].trim();
    if (/^(https?:|mailto:|#)/.test(target)) continue;
    target = decodeURIComponent(target.split('#')[0]);
    if (target.startsWith('<') && target.endsWith('>')) target = target.slice(1, -1);
    const full = path.resolve(path.dirname(file), target);
    localLinks += 1;
    if (!fs.existsSync(full)) errors.push(`${relative}: missing link ${target}`);
  }
  for (const match of source.matchAll(/\b([PDS]\d{2})\b/g)) {
    if (!knownRefs.has(match[1])) errors.push(`${relative}: undefined reference ${match[1]}`);
  }
  let fence = false;
  let columns = null;
  const lines = source.split('\n');
  lines.forEach((line, index) => {
    if (line.startsWith('```')) { fence = !fence; columns = null; return; }
    if (fence) return;
    if (line.startsWith('|') && line.endsWith('|')) {
      const count = line.split(/(?<!\\)\|/).length - 2;
      if (columns === null) columns = count;
      if (count !== columns) errors.push(`${relative}:${index + 1}: table has ${count} columns, expected ${columns}`);
      tableRows += 1;
    } else columns = null;
    if (/^#{1,6} /.test(line) && index + 1 < lines.length && lines[index + 1].trim()) {
      errors.push(`${relative}:${index + 1}: heading needs blank following line`);
    }
  });
  if (fence) errors.push(`${relative}: unclosed code fence`);
}

for (const file of files.filter(file => file.endsWith('.json'))) {
  try {
    const record = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (record.execution_ready !== false) errors.push(`${file}: example must not be execution-ready`);
    if (!record.schema_version) errors.push(`${file}: missing schema_version`);
  } catch (error) { errors.push(`${file}: ${error.message}`); }
}

const backlog = fs.readFileSync(path.join(base, '07-engineering-backlog.md'), 'utf8');
const ticketBlocks = [...backlog.matchAll(/^## (T\d{2}) — ([^\n]+)\n([\s\S]*?)(?=^## T\d{2}|$(?![\s\S]))/gm)];
const tickets = new Map(ticketBlocks.map(match => [match[1], { title: match[2], body: match[3] }]));
if (tickets.size !== 14) errors.push(`Expected 14 backlog tickets, found ${tickets.size}`);
for (const [id, ticket] of tickets) {
  if (!ticket.body.includes('**Blocked by:**')) errors.push(`${id}: missing blockers`);
  if (!ticket.body.includes('- [ ]')) errors.push(`${id}: missing acceptance checks`);
  const blockers = ticket.body.match(/\*\*Blocked by:\*\*([^\n]*)/)?.[1] ?? '';
  for (const match of blockers.matchAll(/\bT\d{2}\b/g)) {
    if (!tickets.has(match[0])) errors.push(`${id}: unknown blocker ${match[0]}`);
    if (Number(match[0].slice(1)) >= Number(id.slice(1))) errors.push(`${id}: nonpreceding blocker ${match[0]}`);
  }
}

const reqs = Array.from({ length: 18 }, (_, index) => `R${String(index + 1).padStart(2, '0')}`);
for (const req of reqs) if (!backlog.includes(req)) errors.push(`Requirement not mapped in backlog: ${req}`);

const report = {
  markdownFiles: markdown.length,
  localLinksChecked: localLinks,
  tableRowsChecked: tableRows,
  referenceIds: knownRefs.size,
  jsonExamples: files.filter(file => file.endsWith('.json')).length,
  tickets: tickets.size,
  requirementsMapped: reqs.length,
  errors
};
console.log(JSON.stringify(report, null, 2));
process.exitCode = errors.length ? 1 : 0;
