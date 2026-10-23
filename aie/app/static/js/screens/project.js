// One project: its header, the next action, the stages, live run logs, and the tabs for the review screens.
import { useEffect, useState } from "preact/hooks";
import { get, post } from "../api.js";
import { html, Btn, Chip, Icon, NextChip, Score, Tabs, ago, toast, usePoll } from "../ui.js";
import { Storyboard } from "./storyboard.js";
import { Review } from "./review.js";
import { Deliveries } from "./deliveries.js";
import { AvatarPanel } from "./avatar.js";
import { JobFile } from "./jobfile.js";

export const STAGE_HELP = {
  transcribe: "every spoken word with its time (Whisper, PC)", cut: "frame-exact pieces, silences out", captions: "words on the timeline, styled",
  storyboard: "every beat for your approval", voice: "the voice stem", sfx: "synthesized hits", music: "the original score",
  mix: "-14 LUFS per variant", graphics: "the HyperFrames composition", effects: "each catalog effect", base: "footage framed by layout",
  picture: "graphics, effects, captions over the base", deliver: "each variant, muxed", qa: "the 9.5 audit",
};

export function useRuns(id) {
  const [runs, reload] = usePoll(() => get(`/api/runs?project=${id}&limit=12`), 1500, [id]);
  return [runs || [], reload];
}

export async function runStage(id, stage, force = false) {
  try { await post(`/api/projects/${id}/run`, { stage, force }); toast(`Queued: ${stage}${force ? " (forced)" : ""}`); }
  catch (e) { toast(e.message, "err"); }
}

export async function setGate(id, gate, value) {
  try { await post(`/api/projects/${id}/gates`, { [gate]: value }); toast(value ? "Approved" : "Approval withdrawn", "ok"); return true; }
  catch (e) { toast(e.message, "err"); return false; }
}

export function Project({ id, tab }) {
  const [p, reload, err] = usePoll(() => get(`/api/projects/${id}`), 3000, [id]);
  const [runs] = useRuns(id);
  const running = runs.find((r) => r.status === "running" || r.status === "queued");
  useEffect(() => { reload(); }, [running && running.id, running && running.status]);
  if (err) return html`<div class="page"><div class="banner err"><b>Couldn't open this project.</b> ${err.message}</div></div>`;
  if (!p) return html`<div class="page"><div class="row muted"><span class="spin" /> Loading…</div></div>`;
  const tabs = [[`#/p/${id}`, "Overview", "overview"], [`#/p/${id}/storyboard`, "Storyboard", "storyboard"],
    [`#/p/${id}/review`, "Review", "review"], [`#/p/${id}/deliveries`, "Deliveries", "deliveries"]];
  if (p.mode === "avatar") tabs.push([`#/p/${id}/avatar`, "Avatar", "avatar"]);
  tabs.push([`#/p/${id}/job`, "Job file", "job"]);
  const body = { overview: html`<${Overview} p=${p} runs=${runs} reload=${reload} />`, storyboard: html`<${Storyboard} p=${p} reload=${reload} />`,
    review: html`<${Review} p=${p} />`, deliveries: html`<${Deliveries} p=${p} reload=${reload} />`, avatar: html`<${AvatarPanel} p=${p} reload=${reload} />`,
    job: html`<${JobFile} p=${p} reload=${reload} />` }[tab] || null;
  return html`<div class="page">
    <div class="page-head">
      <div><div class="crumb"><a href="#/">Projects</a> <span>/</span> <span class="mono">${p.path}</span></div>
        <h1>${p.title}</h1>
        <div class="row" style="margin-top:10px"><${Chip}>${p.mode}<//><${NextChip} next=${p.next} />
          ${running && html`<${Chip} tone="blue" live>${running.stage} ${running.status}<//>`}
          ${p.version && html`<${Chip}>v${p.version.n}${p.version.final ? " final" : " preview"}<//>`}</div></div>
      <div class="row"><${Score} qa=${p.qa} /><${NextAction} p=${p} reload=${reload} busy=${!!running} /></div>
    </div>
    <${Tabs} items=${tabs} current=${tab} />
    ${body}
  </div>`;
}

export function NextAction({ p, reload, busy }) {
  const id = p.id;
  const go = (h) => () => { location.hash = h; };
  const approve = (g) => async () => { if (await setGate(id, g, true)) { reload(); if (g === "final_approved") runStage(id, "all"); } };
  switch (p.next) {
    case "script": return html`<${Btn} kind="primary" onClick=${go(`#/p/${id}/avatar`)}>Open the avatar studio<//>`;
    case "brief": return html`<${Btn} disabled title="Add a take to this project's raw/ folder, or make a new brief with footage">Waiting for footage<//>`;
    case "fix job.json": return html`<${Btn} kind="primary" onClick=${go(`#/p/${id}/job`)}>Fix job.json<//>`;
    case "storyboard": return html`<${Btn} kind="primary" disabled=${busy} onClick=${() => runStage(id, "storyboard")}>Build the storyboard<//>`;
    case "approve storyboard": return html`<div class="row"><${Btn} onClick=${go(`#/p/${id}/storyboard`)}>Review storyboard<//>
      <${Btn} kind="primary" icon="check" onClick=${approve("storyboard_approved")}>Approve storyboard<//></div>`;
    case "render": return html`<${Btn} kind="primary" disabled=${busy} onClick=${() => runStage(id, "all")}>Render + QA<//>`;
    case "approve final": return html`<div class="row"><${Btn} onClick=${go(`#/p/${id}/review`)}>Review<//>
      <${Btn} kind="primary" icon="check" onClick=${approve("final_approved")}>Approve final<//></div>`;
    case "fix QA": return html`<${Btn} kind="primary" onClick=${go(`#/p/${id}/review?qa`)}>See what QA found<//>`;
    case "delivered": return html`<${Btn} kind="primary" onClick=${go(`#/p/${id}/deliveries`)}>Deliveries<//>`;
    default: return null;
  }
}

function Overview({ p, runs, reload }) {
  const [sel, setSel] = useState(null);
  const shown = runs.find((r) => r.id === sel) || runs[0];
  const [run] = usePoll(() => (shown ? get(`/api/runs/${shown.id}`) : Promise.resolve(null)), shown && shown.status !== "done" && shown.status !== "failed" ? 1200 : 0, [shown && shown.id, shown && shown.status]);
  const [force, setForce] = useState(false);
  const qa = p.qa_report;
  return html`
    ${p.errors.length > 0 && html`<div class="banner err"><div><b>job.json has ${p.errors.length} problem${p.errors.length > 1 ? "s" : ""}.</b>
      <ul style="margin:6px 0 0;padding-left:18px">${p.errors.slice(0, 6).map((e) => html`<li class="small">${e}</li>`)}</ul></div></div>`}
    ${!p.has_job && html`<div class="banner info"><div><b>No job.json yet.</b> ${p.mode === "avatar"
      ? "Avatar briefs become a job once the script is approved and the avatar is rendered (Avatar tab)."
      : "This brief has no take yet. Put the camera file in the project's raw/ folder, or make a new brief with the file attached."}</div></div>`}
    <div class="split">
      <div class="stack">
        <section class="panel">
          <div class="panel-head"><h2>Pipeline</h2><label class="check small"><input type="checkbox" checked=${force} onChange=${(e) => setForce(e.target.checked)} /> Force (rerun even if up to date)</label></div>
          ${p.stages.length ? html`<div class="stages">${p.stages.map((s) => html`<button class=${`stage ${s.done ? "done" : ""} ${runs.some((r) => r.stage === s.stage && r.status === "running") ? "run" : ""}`}
              title=${`Run ${s.stage}: ${STAGE_HELP[s.stage] || ""}`} onClick=${() => runStage(p.id, s.stage, force)}>${s.stage}</button>`)}</div>
            <p class="small muted" style="margin-top:12px">Click a stage to run it; it brings the stages it needs up to date first. Pictures wait for your storyboard approval; until you approve the final they render at preview quality.</p>
            <div class="row" style="margin-top:12px"><${Btn} kind="primary" size="sm" onClick=${() => runStage(p.id, "all", force)}>Run everything through QA<//>
              <${Btn} size="sm" onClick=${() => runStage(p.id, "storyboard", force)}>Storyboard<//></div>`
          : html`<p class="muted">The stages appear once there is a job.json.</p>`}
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Runs</h2>${runs.length > 0 && html`<span class="tiny muted">newest first</span>`}</div>
          ${runs.length === 0 ? html`<p class="muted">Nothing has run yet.</p>` : html`
            <div class="row" style="gap:6px;margin-bottom:12px">${runs.map((r) => html`<button class=${`btn sm ${shown && r.id === shown.id ? "primary" : "ghost"}`} onClick=${() => setSel(r.id)}>
              #${r.id} ${r.stage} <${Chip} tone=${r.status === "done" ? "ok" : r.status === "failed" ? "err" : "blue"} live=${r.status === "running"}>${r.status}<//></button>`)}</div>
            ${run && html`<div class="log" aria-live="polite">${(run.log || (run.status === "queued" ? "waiting for the worker…" : "starting…")).split("\n").map((l) =>
              html`<div class=${l.startsWith("FAIL") ? "fail" : /PASS|-> |done/.test(l) ? "okl" : ""}>${l}</div>`)}</div>
              <p class="tiny muted" style="margin-top:8px">${run.stage} · queued ${ago(run.queued)}${run.ended ? ` · took ${Math.round(run.ended - run.started)} s` : ""}</p>`}`}
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head"><h2>QA</h2>${qa && html`<${Chip} tone=${qa.passed ? "ok" : "err"}>${qa.passed ? "passes" : "fails"} the 9.5 gate<//>`}</div>
          ${!qa ? html`<p class="muted">The audit runs after delivery: length, loudness, sync, joints, words, spelling, safe zones, effects on their word, rights and compliance.</p>`
            : html`<div>${Object.entries(qa.checks).map(([k, c]) => html`<div class="qrow">
                <${Chip} tone=${c.status === "OK" ? "ok" : c.status === "FAIL" ? "err" : c.status === "WARN" ? "warn" : ""}>${c.status}<//>
                <b class="small">${k}</b><span class="small soft">${c.summary}${c.status === "FAIL" ? html` <span class="muted">→ ${c.owner}</span>` : ""}</span></div>`)}</div>`}
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Versions</h2></div>
          ${p.versions.length === 0 ? html`<p class="muted">Each delivery becomes a version you can compare in Review.</p>` :
            html`<div class="stack">${p.versions.slice().reverse().map((v) => html`<div class="row between">
              <span><b>v${v.n}</b> <span class="muted small">${ago(v.created)}</span></span>
              <span class="row">${v.final ? html`<${Chip} tone="ok">final<//>` : html`<${Chip}>preview<//>`}${v.qa_score != null && html`<${Chip} tone=${v.qa_passed ? "ok" : "err"}>QA ${v.qa_score.toFixed(1)}<//>`}</span></div>`)}</div>`}
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Brief</h2></div>
          <dl class="kv">${Object.entries(p.brief || {}).filter(([k]) => k !== "look").map(([k, v]) => html`<dt>${k}</dt><dd>${Array.isArray(v) ? v.join(", ") : String(v)}</dd>`)}</dl>
          ${(!p.brief || Object.keys(p.brief).length === 0) && html`<p class="muted small">Made before the app (from job.json only).</p>`}
        </section>
      </div>
    </div>`;
}
