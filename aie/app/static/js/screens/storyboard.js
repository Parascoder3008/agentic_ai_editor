// Storyboard review: every beat with its words, layout, a framed still with each planned box, and the SFX in it.
// Approve the whole board, or leave a note on a beat ("Beat 4: full screen"): it routes to the agent that owns it.
import { useState } from "preact/hooks";
import { get, media, post } from "../api.js";
import { html, Btn, Chip, Empty, toast, usePoll } from "../ui.js";
import { runStage, setGate } from "./project.js";

export function Storyboard({ p, reload }) {
  const sb = p.storyboard;
  const approved = p.job && p.job.gates && p.job.gates.storyboard_approved;
  const [notes, reloadNotes] = usePoll(() => get(`/api/projects/${p.id}/notes`), 0, [p.id]);
  const byBeat = {};
  (notes || []).forEach((n) => n.beat != null && (byBeat[n.beat] = [...(byBeat[n.beat] || []), n]));
  if (!p.has_job) return html`<div class="panel"><${Empty} title="No storyboard yet">The storyboard is built from job.json, which this project doesn't have yet.<//></div>`;
  return html`
    <div class="row between">
      <div class="row">${approved ? html`<${Chip} tone="ok">Approved: pictures can render<//>` : html`<${Chip} tone="warn">Waiting for your approval<//>`}
        ${sb && html`<span class="small muted">${sb.length} beats · ${sb[sb.length - 1].t[1].toFixed(2)} s · red lines are Instagram's UI, yellow effects, blue the graphics stage, white captions</span>`}</div>
      <div class="row"><${Btn} size="sm" icon="refresh" onClick=${() => runStage(p.id, "storyboard", true)}>Rebuild<//>
        ${sb && html`<a class="btn sm" href=${media(p.id, "build/storyboard.html")} target="_blank" rel="noopener">Open as a page</a>`}
        ${approved ? html`<${Btn} size="sm" onClick=${async () => { await setGate(p.id, "storyboard_approved", false); reload(); }}>Withdraw approval<//>`
          : html`<${Btn} kind="primary" size="sm" icon="check" disabled=${!sb} onClick=${async () => { if (await setGate(p.id, "storyboard_approved", true)) reload(); }}>Approve storyboard<//>`}</div>
    </div>
    ${!sb ? html`<div class="panel"><${Empty} title="Not built yet">
        <p style="margin-bottom:12px">The storyboard shows every beat before anything renders: words, layout, a framed still and every planned box.</p>
        <${Btn} kind="primary" onClick=${() => runStage(p.id, "storyboard")}>Build the storyboard<//><//></div>`
      : html`<div class="beats">${sb.map((b) => html`<${Beat} p=${p} b=${b} notes=${byBeat[b.n] || []} onNote=${reloadNotes} />`)}</div>`}`;
}

function Beat({ p, b, notes, onNote }) {
  const [text, setText] = useState("");
  const add = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try { const n = await post(`/api/projects/${p.id}/notes`, { beat: b.n, t: b.t[0], text: `Beat ${b.n}: ${text}` }); setText(""); onNote(); toast(`Noted → ${n.owner}`, "ok"); }
    catch (err) { toast(err.message, "err"); }
  };
  return html`<article class="panel beat">
    <img src=${media(p.id, "build/" + b.still)} alt=${`beat ${b.n} still`} loading="lazy" />
    <div class="stack" style="gap:8px">
      <div class="row between"><h3><span class="n">${String(b.n).padStart(2, "0")}</span> ${b.t[0].toFixed(2)}–${b.t[1].toFixed(2)} s
        <span class="muted small" style="font-weight:600"> ${(b.t[1] - b.t[0]).toFixed(2)} s</span></h3><${Chip}>${b.layout}<//></div>
      <p class="words">${b.words || html`<i class="muted">no words</i>`}</p>
      <dl class="kv">
        <dt>Source</dt><dd>${b.src} from ${Number(b.in).toFixed(2)} s</dd>
        <dt>On screen</dt><dd>${b.on_screen.length ? html`<ul>${b.on_screen.map((x) => html`<li>${x}</li>`)}</ul>` : html`<span class="muted">nothing planned</span>`}</dd>
        <dt>SFX</dt><dd>${b.sfx.length ? b.sfx.map((c) => `${c.kind} @${c.t.toFixed(2)}`).join(", ") : html`<span class="muted">none</span>`}</dd>
        <dt>Why</dt><dd>${b.note || html`<span class="muted">–</span>`}</dd>
      </dl>
      ${notes.map((n) => html`<div class="note"><span class="tiny muted">${n.owner} · ${n.status}</span><span class="small">${n.text}</span></div>`)}
      <form class="row" onSubmit=${add}><input type="text" placeholder=${`Note on beat ${b.n}, e.g. "full screen here"`} value=${text}
        onInput=${(e) => setText(e.target.value)} aria-label=${`note on beat ${b.n}`} style="flex:1;min-width:200px" /><${Btn} size="sm" type="submit">Add note<//></form>
    </div>
  </article>`;
}
