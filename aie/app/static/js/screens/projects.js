// Projects: every job with its mode, where it is in the pipeline, its QA score and what it waits on.
import { useState } from "preact/hooks";
import { get, post } from "../api.js";
import { html, Btn, Chip, Empty, NextChip, Pipe, Score, ago, toast, usePoll } from "../ui.js";

const MODE = { footage: "Footage", avatar: "Avatar", client: "Client", longform: "Long-form" };

export function Projects() {
  const [list, reload, err] = usePoll(() => get("/api/projects"), 5000);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");
  const demo = async () => {
    setBusy(true);
    try { const r = await post("/api/demo"); toast("Demo project made: generated footage, real effects, no keys needed", "ok"); location.hash = `#/p/${r.id}`; }
    catch (e) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const shown = (list || []).filter((p) => filter === "all" || (filter === "waiting" ? /approve|fix|script|brief/.test(p.next) : p.mode === filter));
  return html`<div class="page">
    <div class="page-head">
      <div><h1>Projects</h1><p>Every edit, where it is in the pipeline and what it is waiting on. Approvals are yours; renders run one at a time on this PC.</p></div>
      <div class="row"><${Btn} onClick=${demo} disabled=${busy} icon="spark">${busy ? "Making demo…" : "Demo project"}<//>
        <a class="btn primary" href="#/new">New brief</a></div>
    </div>
    <div class="row">${["all", "waiting", "footage", "avatar", "client", "longform"].map((f) =>
      html`<button class=${`btn sm ${filter === f ? "primary" : "ghost"}`} onClick=${() => setFilter(f)}>${f === "all" ? "All" : f === "waiting" ? "Waiting on you" : MODE[f]}</button>`)}</div>
    ${err && html`<div class="banner err"><b>The app's API isn't answering.</b> ${err.message}</div>`}
    ${!list ? html`<div class="row muted"><span class="spin" /> Loading projects…</div>` : shown.length === 0 ? html`<div class="panel"><${Empty} title="No projects here yet">
        Start with <a href="#/new">a brief</a>, or make the demo project to see the whole flow with no footage and no keys.<//></div>` :
      html`<div class="cards">${shown.map((p) => html`<a class="panel pcard" href=${`#/p/${p.id}`}>
        <div class="row between" style="align-items:flex-start">
          <div class="stack" style="gap:6px;min-width:0"><h3>${p.title}</h3><span class="path">${p.path}</span></div>
          <${Score} qa=${p.qa} />
        </div>
        <div class="row"><${Chip}>${MODE[p.mode] || p.mode}<//><${NextChip} next=${p.next} />
          ${p.open_notes > 0 && html`<${Chip} tone="warn">${p.open_notes} open note${p.open_notes > 1 ? "s" : ""}<//>`}
          ${p.version && html`<${Chip}>v${p.version.n}${p.version.final ? " final" : ""}<//>`}</div>
        ${p.stages.length > 0 && html`<${Pipe} stages=${p.stages} running=${p.last_run && p.last_run.status === "running" ? p.last_run.stage : null} />`}
        <div class="row between tiny muted">
          <span>${p.stages.filter((s) => s.done).length} of ${p.stages.length || "–"} stages</span>
          <span>${p.last_run ? `${p.last_run.stage} ${p.last_run.status} · ${ago(p.last_run.ended || p.last_run.started || p.last_run.queued)}` : "never run"}</span>
        </div>
      </a>`)}</div>`}
  </div>`;
}
