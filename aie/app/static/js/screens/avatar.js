// Avatar studio (CLAUDE.md's pronunciation gate): the Roman Hinglish script (captions come from it), the TTS script
// (Hindi in Devanagari, English in Latin, numbers spelled out, {Shown|बोला} pins), the exact text for HeyGen, a voice
// preview Paras approves by ear, the next look in the rotation, then the render. HeyGen steps wait for its key.
import { useEffect, useState } from "preact/hooks";
import { get, post, put } from "../api.js";
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
  const [conns] = usePoll(() => get("/api/connections"), 0);
  const [rot] = usePoll(() => get("/api/avatars"), 0);
  const [tts, setTts] = useState(null);
  const heygen = conns && ["set", "tested OK"].includes((conns.items.find((c) => c.id === "heygen") || {}).status);
  const brief = p.brief || {};
  const look = brief.look;
  const step = (n, title, done, body) => html`<section class="panel stack"><div class="row between"><h2><span class="muted">${n}</span> ${title}</h2>
    ${done ? html`<${Chip} tone="ok">done<//>` : html`<${Chip}>to do<//>`}</div>${body}</section>`;
  const makeTts = async () => { try { setTts((await post(`/api/projects/${p.id}/avatar/tts`)).text); } catch (e) { toast(e.message, "err"); } };
  const pickLook = async () => { try { const l = await post(`/api/projects/${p.id}/avatar/look`); toast(`Next look: ${l.name}`, "ok"); reload(); } catch (e) { toast(e.message, "err"); } };
  const approve = async (v) => { try { await post(`/api/projects/${p.id}/brief`, { pron_approved: v }); reload(); } catch (e) { toast(e.message, "err"); } };
  const renderIt = async () => { try { const r = await post(`/api/projects/${p.id}/avatar/render`); toast(r.message || "Render started", "ok"); } catch (e) { toast(e.message, e.status === 409 ? "" : "err"); } };
  return html`
    ${!heygen && html`<div class="banner"><div><b>HeyGen isn't connected.</b> Writing the scripts and picking the look work now; the voice preview and the render wait for the key (<a href="#/connections">Connections</a>).</div></div>`}
    <div class="grid cols-2">
      ${step(1, "Script", !!p.script, html`<${Editor} p=${p} file="script.txt" label="Roman Hinglish script" hint="captions are made from this" />`)}
      ${step(2, "TTS script", false, html`<${Editor} p=${p} file="script_tts.txt" label="What the voice reads"
        hint="Hindi in Devanagari, English in Latin, numbers spelled out, {Claude|क्लॉड} pins a word" />
        <div class="row"><${Btn} size="sm" onClick=${makeTts}>Make the HeyGen text<//></div>
        ${tts && html`<textarea rows="4" readonly value=${tts} aria-label="text for HeyGen" />`}`)}
    </div>
    <div class="grid cols-3">
      ${step(3, "Pronunciation", !!brief.pron_approved, html`<p class="small soft">A voice preview (HeyGen create_speech, audio only) is transcribed and every drifted word flagged.
          Whisper hears "Claude" as "Cloud"; your ear decides.</p>
        <div class="row"><${Btn} size="sm" disabled=${!heygen} title=${heygen ? "" : "needs the HeyGen key"} onClick=${() => toast("The Avatar Producer makes the preview (Phase 4 agent)")}>Make a voice preview<//>
          ${brief.pron_approved ? html`<${Btn} size="sm" onClick=${() => approve(false)}>Withdraw<//>` : html`<${Btn} size="sm" kind="primary" icon="check" onClick=${() => approve(true)}>I listened: approve<//>`}</div>`)}
      ${step(4, "Avatar look", !!look, html`${look ? html`<div><b>${look.name}</b><div class="tiny muted mono">${look.id} · ${look.orientation || ""}</div></div>`
          : html`<p class="small muted">A random recent look, never the previous one.</p>`}
        <${Btn} size="sm" onClick=${pickLook}>${look ? "Pick again" : "Pick the next look"}<//>
        ${rot && rot.looks && html`<details><summary class="small" style="cursor:pointer;color:var(--blue-2)">${rot.looks.length} looks in the rotation</summary>
          <ul class="small soft">${rot.looks.map((l) => html`<li>${l.name} <span class="muted">${l.orientation || ""}</span></li>`)}</ul></details>`}`)}
      ${step(5, "Render", p.has_job, html`<p class="small soft">Renders with the approved preview's audio (not the look's default voice), so the words match exactly.</p>
        <${Btn} kind="primary" size="sm" disabled=${!brief.pron_approved || !look} title=${!brief.pron_approved ? "approve the pronunciation first" : !look ? "pick a look first" : ""}
          onClick=${renderIt}>Render on HeyGen<//>`)}
    </div>`;
}
