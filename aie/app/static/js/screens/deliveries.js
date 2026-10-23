// Deliveries: the IG and YT cuts with their numbers, the cover and SRTs, the two approvals, Drive delivery and the NLE
// hand-off. Publish stays locked: the tool never posts; Paras does, from the files here.
import { useState } from "preact/hooks";
import { get, media, post } from "../api.js";
import { html, Btn, Chip, Empty, Icon, toast, usePoll } from "../ui.js";
import { runStage, setGate } from "./project.js";

function PostCopy({ p, file, ready }) {
  const [text, setText] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved] = usePoll(() => (file ? fetch(media(p.id, "build/publish/" + file) + `?t=${Date.now()}`).then((r) => r.text()) : Promise.resolve(null)), 0, [file]);
  const write = async () => {
    setBusy(true);
    try { const r = await post(`/api/projects/${p.id}/publish/copy`); setText(r.text); toast("Post copy written: check it before you post", "ok"); }
    catch (e) { toast(e.message, e.status === 409 ? "" : "err"); } finally { setBusy(false); }
  };
  const shown = text || saved;
  return html`<div class="stack" style="gap:8px"><div class="hr" />
    <div class="row between"><span><b>Post copy</b><br /><span class="small muted">Caption, first-comment hashtags, the YouTube title and
      description. Screened for income claims; you edit and post.</span></span>
      <${Btn} size="sm" disabled=${!ready || busy} title=${ready ? "" : "needs the Claude API key (Connections)"} onClick=${write}>${busy ? "Writing…" : shown ? "Write again" : "Write the post copy"}<//></div>
    ${shown && html`<textarea rows="10" readonly value=${shown} aria-label="post copy" />`}</div>`;
}

function NLE({ p, resolveReady }) {
  const nle = p.nle;
  const sendResolve = async () => { try { toast((await post(`/api/projects/${p.id}/nle/resolve`)).message, "ok"); } catch (e) { toast(e.message, "err"); } };
  return html`<div class="stack" style="gap:10px">
    <div class="row between"><span><b>Resolve / Premiere</b><br /><span class="small muted">The edit as a timeline: the framed base to grade,
      the camera originals (off), every overlay and the stems on their own tracks, a marker per beat.</span></span>
      <${Btn} size="sm" onClick=${() => runStage(p.id, "otio")}>${nle ? "Export again" : "Export the timeline"}<//></div>
    ${nle && html`<div class="files">
        <a class="btn sm" href=${media(p.id, rel(nle.otio))} download>${nle.otio.split(/[\\/]/).pop()}</a>
        ${nle.xml && html`<a class="btn sm" href=${media(p.id, rel(nle.xml))} download>${nle.xml.split(/[\\/]/).pop()}</a>`}
        ${(nle.srt || []).map((f) => html`<a class="btn sm" href=${media(p.id, rel(f))} download>${f.split(/[\\/]/).pop()}</a>`)}</div>
      <ul class="small soft" style="margin:0;padding-left:18px">
        <li><b>Resolve:</b> File → Import → Timeline… and pick the .otio${resolveReady ? ", or:" : " (set Resolve's path in Connections to import it from here)"}
          ${resolveReady && html` <${Btn} size="sm" kind="ghost" onClick=${sendResolve}>Import into Resolve<//>`}</li>
        <li><b>Premiere:</b> File → Import… and pick the .xml${nle.xml ? "" : html` <span class="muted">(not written: ${nle.xml_error})</span>`}</li>
        <li>Captions: import the .srt onto a subtitle track.</li></ul>`}
  </div>`;
}

const rel = (abs) => { const s = abs.replace(/\\/g, "/"); const i = s.lastIndexOf("/build/"); return i >= 0 ? s.slice(i + 1) : s; };

export function Deliveries({ p, reload }) {
  const [conns] = usePoll(() => get("/api/connections"), 0);
  const [busy, setBusy] = useState(false);
  const dl = p.deliveries || {};
  const final = p.job && p.job.gates && p.job.gates.final_approved;
  const qaOK = p.qa_report && p.qa_report.passed;
  const status = (id) => conns && (conns.items.find((c) => c.id === id) || {}).status;
  const driveReady = ["set", "tested OK"].includes(status("drive"));
  const toDrive = async () => {
    setBusy(true);
    try { const r = await post(`/api/projects/${p.id}/drive`); toast(`Copied ${r.files.length} files to ${r.folder}`, "ok"); }
    catch (e) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const others = (p.publish || []).filter((f) => !f.endsWith(".mp4"));
  if (!Object.keys(dl).length) return html`<div class="panel"><${Empty} title="No deliveries yet">
    Render the project (Overview → Render + QA). Until you approve the final, cuts render at preview quality and are named _PREVIEW.<//></div>`;
  return html`
    <div class="banner ${final ? "info" : ""}">
      ${final ? html`<div><b>Final approved.</b> These are final-quality files. ${qaOK ? "QA passes." : "QA hasn't passed on them yet."}</div>`
        : html`<div style="flex:1"><b>Preview files.</b> When the cut is right, approve the final: it re-renders at final quality, re-runs QA, and names the files without _PREVIEW.</div>
          <${Btn} kind="primary" icon="check" onClick=${async () => { if (await setGate(p.id, "final_approved", true)) { reload(); runStage(p.id, "all"); } }}>Approve final<//>`}
    </div>
    <div class="grid cols-2">${Object.entries(dl).map(([name, v]) => html`<section class="panel deliv stack">
      <div class="row between"><h2 style="text-transform:capitalize">${name}</h2>${v.path.includes("_PREVIEW") ? html`<${Chip} tone="warn">preview<//>` : html`<${Chip} tone="ok">final<//>`}</div>
      <video src=${media(p.id, rel(v.path))} controls preload="metadata" playsinline />
      <div class="grid cols-3">
        <div class="stat"><b>${v.seconds.toFixed(2)} s</b><span>Length</span></div>
        <div class="stat"><b>${v.lufs.toFixed(1)}</b><span>LUFS</span></div>
        <div class="stat"><b>${v.true_peak.toFixed(1)}</b><span>dBTP peak</span></div>
      </div>
      <div class="files"><a class="btn sm" href=${media(p.id, rel(v.path))} download><${Icon} name="film" />${rel(v.path).split("/").pop()}</a>
        ${others.filter((f) => f.includes(`_${name}`)).map((f) => html`<a class="btn sm" href=${media(p.id, "build/publish/" + f)} download>${f}</a>`)}</div>
      <p class="small muted">${name === "instagram" ? "Post with \"Upload at highest quality\" on; caption and hashtags go in the first comment." : name === "youtube" ? "CTA: the WhatsApp channel link in the description." : ""}</p>
    </section>`)}</div>
    <div class="grid cols-2">
      <section class="panel stack">
        <h2>Package</h2>
        ${others.includes("cover.jpg") ? html`<img src=${media(p.id, "build/publish/cover.jpg")} alt="cover" style="max-width:220px;border-radius:14px" />` : html`<p class="muted small">No cover in this job's package settings.</p>`}
        <div class="files">${others.map((f) => html`<a class="btn sm" href=${media(p.id, "build/publish/" + f)} download>${f}</a>`)}</div>
        <${PostCopy} p=${p} file=${others.find((f) => f.endsWith("_post.md"))} ready=${["set", "tested OK"].includes(status("anthropic"))} />
      </section>
      <section class="panel stack">
        <h2>Hand-off</h2>
        <div class="row between"><span><b>Google Drive</b><br /><span class="small muted">${driveReady ? "Copies the final files to your Drive folder" : "Set the Drive folder in Connections"}</span></span>
          <${Btn} icon="drive" disabled=${!driveReady || !final || !qaOK || busy} title=${!final ? "Approve the final first" : !qaOK ? "QA must pass first" : ""} onClick=${toDrive}>Copy to Drive<//></div>
        <div class="hr" />
        <${NLE} p=${p} resolveReady=${["set", "tested OK"].includes(status("resolve"))} />
        <div class="hr" />
        <div class="row between"><span><b>Publish</b><br /><span class="small muted">The tool never posts. Upload from these files yourself, with the post copy below.</span></span>
          <${Btn} icon="lock" disabled title="Publishing stays with you">Publish<//></div>
      </section>
    </div>`;
}
