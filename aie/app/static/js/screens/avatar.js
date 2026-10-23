// Avatar studio (CLAUDE.md's pronunciation gate): the Roman Hinglish script (captions come from it), the TTS script
// (Hindi in Devanagari, English in Latin, numbers spelled out, {Shown|बोला} pins), the exact text for HeyGen, a voice
// preview Paras approves by ear (tied to that exact audio), the next look in the rotation, then the render. HeyGen
// steps wait for its MCP connection.
import { useEffect, useState } from "preact/hooks";
import { get, media, post, put } from "../api.js";
import { html, Btn, Chip, Empty, toast, usePoll } from "../ui.js";

export function AvatarStudio() {
  const [list] = usePoll(() => get("/api/projects"), 5000);
  const mine = (list || []).filter((p) => p.mode === "avatar");
  return html`<div class="page">
    <div class="page-head"><div><h1>Avatar studio</h1><p>Topic → script → pronunciation check → avatar look → HeyGen render. The render enters the normal pipeline at the storyboard.</p></div>
      <a class="btn primary" href="#/new">New avatar brief</a></div>
    ${!list ? html`<div class="row muted"><span class="spin" /> Loading…</div>` : mine.length === 0
      ? html`<div class="panel"><${Empty} title="No avatar projects">Make a brief in Avatar mode to start one.<//></div>`
      : html`<div class="cards">${mine.map((p) => html`<a class="panel pcard" href=${`#/p/${p.id}/avatar`}><h3>${p.title}</h3><span class="path">${p.path}</span>
          <div class="row"><${Chip} tone=${p.has_job ? "ok" : "warn"}>${p.has_job ? "rendered" : "script stage"}<//></div></a>`)}</div>`}
  </div>`;
}

function Editor({ p, file, label, hint, rows = 8 }) {
  const [text, setText] = useState(null);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { get(`/api/projects/${p.id}/script/${file}`).then((r) => setText(r.text)); }, [p.id, file]);
  const save = async () => { try { await put(`/api/projects/${p.id}/script`, { file, text }); setDirty(false); toast(`${file} saved`, "ok"); } catch (e) { toast(e.message, "err"); } };
  return html`<label class="field">${label} ${hint && html`<span class="hint">${hint}</span>`}
    <textarea rows=${rows} value=${text == null ? "" : text} disabled=${text == null} onInput=${(e) => { setText(e.target.value); setDirty(true); }} />
    <div class="row"><${Btn} size="sm" kind=${dirty ? "primary" : ""} disabled=${!dirty} onClick=${save}>Save ${file}<//></div></label>`;
}

export function AvatarPanel({ p, reload }) {
  const [rot] = usePoll(() => get("/api/avatars"), 0);
  const [tts, setTts] = useState(null);
  const [busy, setBusy] = useState("");
  const brief = p.brief || {};
  const look = brief.look, pv = brief.preview, rnd = brief.render || {};
  const missing = (p.connectors || {}).heygen;
  const rendering = ["uploading", "rendering"].includes(rnd.status);
  usePoll(() => (rendering ? reload() : Promise.resolve()), rendering ? 5000 : 0, [rendering]);
  const report = usePoll(() => (pv && pv.report ? fetch(media(p.id, pv.report) + `?v=${pv.sha}`).then((r) => r.text()) : Promise.resolve(null)), 0, [pv && pv.sha])[0];
  const step = (n, title, done, body) => html`<section class="panel stack"><div class="row between"><h2><span class="muted">${n}</span> ${title}</h2>
    ${done ? html`<${Chip} tone="ok">done<//>` : html`<${Chip}>to do<//>`}</div>${body}</section>`;
  const act = (label, fn) => async () => { setBusy(label); try { await fn(); } catch (e) { toast(e.message, e.status === 409 ? "" : "err"); } setBusy(""); reload(); };
  const makeTts = act("tts", async () => setTts((await post(`/api/projects/${p.id}/avatar/tts`)).text));
  const pickLook = act("look", async () => { const l = await post(`/api/projects/${p.id}/avatar/look`); toast(`Next look: ${l.name}`, "ok"); });
  const makePreview = act("preview", async () => { await post(`/api/projects/${p.id}/avatar/preview`); toast("Preview ready: listen to the flagged words", "ok"); });
  const approve = (v) => act("approve", async () => { await post(`/api/projects/${p.id}/avatar/approve`, { value: v }); });
  const renderIt = act("render", async () => { const r = await post(`/api/projects/${p.id}/avatar/render`); toast(r.message, "ok"); });
  return html`
    ${missing && html`<div class="banner"><div><b>HeyGen isn't connected:</b> ${missing}. Writing the scripts and picking the look work now;
      the voice preview and the render wait for it (<a href="#/connections">Connections</a>).</div></div>`}
    <div class="grid cols-2">
      ${step(1, "Script", !!p.script, html`<${Editor} p=${p} file="script.txt" label="Roman Hinglish script" hint="captions are made from this" />`)}
      ${step(2, "TTS script", !!tts, html`<${Editor} p=${p} file="script_tts.txt" label="What the voice reads"
        hint="Hindi in Devanagari, English in Latin, numbers spelled out, {Claude|क्लॉड} pins a word" />
        <div class="row"><${Btn} size="sm" disabled=${busy === "tts"} onClick=${makeTts}>Make the HeyGen text<//></div>
        ${tts && html`<textarea rows="4" readonly value=${tts} aria-label="text for HeyGen" />`}`)}
    </div>
    <div class="grid cols-3">
      ${step(3, "Pronunciation", !!brief.pron_approved, html`<p class="small soft">HeyGen reads the exact text in the approved voice; Whisper flags
          every word that drifted. Whisper hears "Claude" as "Cloud": your ear decides.</p>
        ${pv && html`<audio controls preload="none" src=${media(p.id, pv.file) + `?v=${pv.sha}`} style="width:100%"></audio>
          ${report ? html`<details open><summary class="small" style="cursor:pointer;color:var(--blue-2)">Flagged words</summary><pre class="log" style="white-space:pre-wrap">${report}</pre></details>`
            : pv.report_error && html`<p class="tiny muted">No report on this machine (${pv.report_error.split("\n").pop()}); listen to the whole preview.</p>`}`}
        <div class="row"><${Btn} size="sm" disabled=${!!missing || busy === "preview"} title=${missing || ""} onClick=${makePreview}>
            ${busy === "preview" ? "Making the preview…" : pv ? "Make a new preview" : "Make a voice preview"}<//>
          ${brief.pron_approved ? html`<${Btn} size="sm" onClick=${approve(false)}>Withdraw<//>`
            : html`<${Btn} size="sm" kind="primary" icon="check" disabled=${!pv} title=${pv ? "" : "make a preview first: you approve audio you have heard"} onClick=${approve(true)}>I listened: approve<//>`}</div>`)}
      ${step(4, "Avatar look", !!look, html`${look ? html`<div><b>${look.name}</b><div class="tiny muted mono">${look.id} · ${look.orientation || ""}</div></div>`
          : html`<p class="small muted">A random recent look, never the previous one.</p>`}
        <${Btn} size="sm" disabled=${busy === "look"} onClick=${pickLook}>${look ? "Pick again" : "Pick the next look"}<//>
        ${rot && rot.looks && html`<details><summary class="small" style="cursor:pointer;color:var(--blue-2)">${rot.looks.length} looks in the rotation</summary>
          <ul class="small soft">${rot.looks.map((l) => html`<li>${l.name} <span class="muted">${l.orientation || ""}</span></li>`)}</ul></details>`}`)}
      ${step(5, "Render", rnd.status === "done", html`<p class="small soft">Renders the look lip-syncing the approved preview (not the look's default voice), so the words match exactly. Then transcribe and the storyboard run.</p>
        ${rnd.status && html`<div class="row" style="gap:8px"><${Chip} tone=${rnd.status === "done" ? "ok" : rnd.status === "failed" ? "err" : "blue"} live=${rendering}>${rnd.status}<//>
          <span class="tiny muted">${rnd.message || ""}</span></div>`}
        <${Btn} kind="primary" size="sm" disabled=${!!missing || !brief.pron_approved || !look || rendering || rnd.status === "done"}
          title=${missing || (!brief.pron_approved ? "approve the pronunciation first" : !look ? "pick a look first" : "")}
          onClick=${renderIt}>${rendering ? "Rendering…" : rnd.status === "failed" ? "Try the render again" : "Render on HeyGen"}<//>`)}
    </div>`;
}
