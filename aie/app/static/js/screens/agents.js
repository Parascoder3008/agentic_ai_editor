// The agent team on a project: what it was sent, what each agent did and spent, and what it handed back to Paras.
import { useState } from "preact/hooks";
import { get, patch, post } from "../api.js";
import { html, Btn, Chip, ago, toast, usePoll } from "../ui.js";

const TONE = { done: "ok", running: "blue", paused: "warn", stopped: "warn", failed: "err", refused: "err", error: "err",
  "over budget": "warn", "turn cap": "warn", "cut off": "warn" };
const money = (x) => `$${Number(x || 0).toFixed(x >= 1 ? 2 : 3)}`;

export function AgentTeam({ p, reload }) {
  const [a, reloadAgents] = usePoll(() => get(`/api/projects/${p.id}/agents`), 2500, [p.id]);
  const [notes, reloadNotes] = usePoll(() => get(`/api/projects/${p.id}/notes`), 5000, [p.id]);
  const [open, setOpen] = useState(null);
  if (!a) return html`<section class="panel"><div class="panel-head"><h2>Agent team</h2></div><p class="muted small">Loading…</p></section>`;
  const forParas = (notes || []).filter((n) => n.owner === "Paras" && n.status === "open");
  const latest = a.dispatches[0];
  const plan = async () => {
    try { const r = await post(`/api/projects/${p.id}/agents/plan`); toast(r.message, r.busy ? "" : "ok"); reloadAgents(); }
    catch (e) { toast(e.message, e.status === 409 ? "" : "err"); }
  };
  const done = async (n) => { try { await patch(`/api/notes/${n.id}`, { status: "fixed" }); reloadNotes(); reload && reload(); } catch (e) { toast(e.message, "err"); } };
  return html`<section class="panel stack">
    <div class="panel-head"><h2>Agent team</h2>
      ${a.ready ? html`<${Chip} tone="ok">Claude API set<//>` : html`<a href="#/connections"><${Chip} tone="warn">Placeholder · needs the Claude API key<//></a>`}</div>
    ${!a.ready && html`<p class="small soft">Notes you write in Review wait here, already routed to their owner. Add the Claude API key in
      Connections and they go to the agents; the pipeline runs without them.</p>`}
    <div class="row between">
      <span class="tiny muted">Up to ${money(a.budget)} per dispatch; past it the agents stop and ask.</span>
      <${Btn} size="sm" icon="spark" disabled=${!a.ready || a.running || !p.has_job}
        title=${!a.ready ? "Needs the Claude API key (Connections)" : "The Story Editor plans the cut, effects and SFX from the transcript; the storyboard follows"}
        onClick=${plan}>Plan with agents<//></div>
    ${forParas.length > 0 && html`<div class="banner warn"><div class="stack" style="gap:8px"><b>${forParas.length} for you</b>
      ${forParas.map((n) => html`<div class="row between" style="gap:10px;align-items:start"><span class="small">${n.text}</span>
        <${Btn} size="sm" kind="ghost" icon="check" onClick=${() => done(n)}>Done<//></div>`)}</div></div>`}
    ${a.dispatches.length === 0 ? html`<p class="muted small">Nothing sent yet. In Review, pause on a moment, write a note, and press "Send to agents".</p>`
      : html`<div class="stack" style="gap:10px">${a.dispatches.map((d) => html`<div class="dispatch">
        <button class="dispatch-head" onClick=${() => setOpen(open === d.id ? null : d.id)} aria-expanded=${open === d.id || (open == null && d === latest)}>
          <span class="row" style="gap:8px"><b class="small">${d.kind === "plan" ? "Plan" : "Notes"} #${d.id}</b>
            <${Chip} tone=${TONE[d.status] || ""} live=${d.status === "running"}>${d.status}<//></span>
          <span class="tiny muted">${money(d.spent)} of ${money(d.budget)} · ${ago(d.started)}</span></button>
        ${d.message && html`<p class="small soft" style="margin:6px 0 0">${d.message}</p>`}
        ${(open === d.id || (open == null && d === latest)) && html`<div class="stack" style="gap:8px;margin-top:10px">${d.runs.map((r) => html`<div class="agent-run">
          <div class="row between"><span class="row" style="gap:6px"><${Chip} tone="blue">${r.role}<//>${r.round > 1 && html`<span class="tiny muted">QA round ${r.round - 1}</span>`}</span>
            <span class="row" style="gap:6px"><span class="tiny muted">${r.changes} change${r.changes === 1 ? "" : "s"} · ${money(r.cost)}</span>
              <${Chip} tone=${TONE[r.status] || ""} live=${r.status === "running"}>${r.status}<//></span></div>
          ${r.reply && html`<span class="small">${r.reply}</span>`}
          ${r.log && html`<details><summary class="tiny muted">What it did</summary><div class="log" style="margin-top:6px">${r.log.trim().split("\n").map((l) => html`<div>${l}</div>`)}</div></details>`}
        </div>`)}</div>`}
      </div>`)}</div>`}
  </section>`;
}
