// Connections: every key, MCP server, app and tool, each "not set", "set", "tested OK" or "failed". Without them the
// app runs in placeholder mode: the pipeline works; the agents, avatar renders, generation and style learning wait.
import { useState } from "preact/hooks";
import { get, post, put } from "../api.js";
import { html, Btn, Chip, Icon, toast, usePoll } from "../ui.js";

const GROUPS = [["api", "API keys", "Services the agents and stages call."],
  ["mcp", "MCP servers", "Tool servers the agent team connects to (Claude Agent SDK)."],
  ["app", "Apps and folders on this PC", "Where Resolve, Premiere, After Effects and the Drive folder are."],
  ["tool", "Found on this PC", "Detected; install what's missing (python -m aie doctor has the details)."]];
const TONE = { "not set": "", set: "blue", "tested OK": "ok", failed: "err", found: "ok", missing: "warn" };

export function Connections() {
  const [data, reload] = usePoll(() => get("/api/connections"), 0);
  if (!data) return html`<div class="page"><div class="row muted"><span class="spin" /> Loading…</div></div>`;
  const s = data.summary;
  return html`<div class="page">
    <div class="page-head"><div><h1>Connections</h1><p>Keys stay on this PC in <span class="mono">secrets.local.json</span> (git-ignored) and are never shown again in full. A test makes one free, read-only call.</p></div>
      <${Chip} tone=${s.set === s.total ? "ok" : "warn"}>${s.set} of ${s.total} set<//></div>
    ${s.set < s.total && html`<div class="banner info"><div><b>Placeholder mode.</b> The pipeline renders, QA and reviews work now. Waiting for keys:
      ${!s.agents && " the agent team (Claude API),"} avatar renders (HeyGen), generated shots (Higgsfield, Flow), style learning (Apify), delivery (Drive, Composio).</div></div>`}
    ${GROUPS.map(([kind, title, help]) => html`<section class="panel">
      <div class="panel-head"><div><h2>${title}</h2><p class="small muted" style="margin-top:4px">${help}</p></div></div>
      ${data.items.filter((c) => c.kind === kind).map((c) => html`<${Row} c=${c} reload=${reload} />`)}
    </section>`)}
  </div>`;
}

function Row({ c, reload }) {
  const [vals, setVals] = useState({});
  const [busy, setBusy] = useState(false);
  const dirty = Object.values(vals).some((v) => v !== undefined);
  const save = async () => {
    setBusy(true);
    try { await put(`/api/connections/${c.id}`, { values: vals }); setVals({}); toast(`${c.name} saved`, "ok"); reload(); }
    catch (e) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true);
    try { const r = await post(`/api/connections/${c.id}/test`); toast(`${c.name}: ${r.message}`, r.ok ? "ok" : "err"); reload(); }
    catch (e) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const clear = async () => { await put(`/api/connections/${c.id}`, { values: Object.fromEntries(c.fields.map((f) => [f.key, ""])) }); reload(); };
  return html`<div class="conn">
    <div class="stack" style="gap:6px"><div class="row"><b>${c.name}</b><${Chip} tone=${TONE[c.status]}>${c.status}<//></div>
      <span class="small muted">${c.for}</span>
      ${c.test && html`<span class=${`tiny ${c.test.ok ? "" : "soft"}`}>${c.test.ok ? "✓ " : "✗ "}${c.test.message}</span>`}
      ${c.where && html`<span class="tiny mono muted">${c.where}</span>`}</div>
    <div class="fields">${c.fields.map((f) => html`<label class="field"><span>${f.label}${f.from_env ? html` <span class="hint">(from the environment)</span>` : ""}</span>
      <input type=${f.secret ? "password" : "text"} autocomplete="off" spellcheck="false"
        placeholder=${f.set ? (f.secret ? f.value : f.value) : f.hint || (f.secret ? "paste the key" : "")}
        value=${vals[f.key] === undefined ? (f.secret ? "" : f.value) : vals[f.key]} onInput=${(e) => setVals({ ...vals, [f.key]: e.target.value })} /></label>`)}</div>
    <div class="acts">${c.kind !== "tool" && html`
      <${Btn} size="sm" kind=${dirty ? "primary" : ""} disabled=${!dirty || busy} onClick=${save}>Save<//>
      <${Btn} size="sm" disabled=${busy || c.status === "not set"} onClick=${test}>Test<//>
      ${c.status !== "not set" && html`<${Btn} size="sm" kind="ghost" icon="x" aria-label=${`clear ${c.name}`} title="Clear" onClick=${clear} />`}
      ${c.docs && html`<a class="btn sm ghost" href=${c.docs} target="_blank" rel="noopener" title="Where to get it"><${Icon} name="key" /></a>`}`}</div>
  </div>`;
}
