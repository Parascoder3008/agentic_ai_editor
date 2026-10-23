// Brief: a new project. Footage and client briefs with a take become a runnable job straight away; avatar briefs
// start from a topic and a script and go to the avatar studio.
import { useRef, useState } from "preact/hooks";
import { get, upload } from "../api.js";
import { html, Btn, Chip, Icon, toast, usePoll } from "../ui.js";

const MODES = [["footage", "Footage", "A camera take of you"], ["avatar", "Avatar", "Topic → script → HeyGen avatar"],
  ["client", "Client", "A client's footage and their own reels only"]];

export function Brief() {
  const [styles] = usePoll(() => get("/api/styles"), 0);
  const [b, setB] = useState({ mode: "footage", title: "", platforms: ["instagram", "youtube"], aspect: "9:16", language: "hi",
    cta: "", style: "ai-os-blue", client: "", topic: "", script: "", references: "", notes: "" });
  const [files, setFiles] = useState([]);
  const [over, setOver] = useState(false);
  const [pct, setPct] = useState(null);
  const pick = useRef(null);
  const set = (k) => (e) => setB({ ...b, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const plat = (name) => setB({ ...b, platforms: b.platforms.includes(name) ? b.platforms.filter((x) => x !== name) : [...b.platforms, name] });
  const add = (list) => setFiles([...files, ...Array.from(list)]);
  const allowed = (styles ? styles.styles : []).filter((s) => (b.mode === "client" ? s.use !== "own" : s.use !== "client"));
  const submit = async (e) => {
    e.preventDefault();
    if (!b.title.trim()) return toast("Give it a title", "err");
    if (b.mode !== "avatar" && !files.length && !confirm("No take attached. Make the project anyway and add the footage later?")) return;
    const f = new FormData();
    f.append("brief", JSON.stringify({ ...b, references: b.references.split(/\s+/).filter(Boolean) }));
    files.forEach((x) => f.append("files", x, x.name));
    try { setPct(0); const r = await upload("/api/projects", f, setPct); toast("Project made", "ok"); location.hash = `#/p/${r.id}`; }
    catch (err) { toast(err.message, "err"); setPct(null); }
  };
  return html`<form class="page" onSubmit=${submit}>
    <div class="page-head"><div><h1>New brief</h1><p>What the video is, where it goes and how it should look. The agents plan from this; you approve the storyboard before anything renders.</p></div></div>
    <div class="split">
      <div class="stack">
        <section class="panel stack">
          <h2>Mode</h2>
          <div class="grid cols-3">${MODES.map(([k, label, help]) => html`<button type="button" class=${`panel tight stack ${b.mode === k ? "on" : ""}`}
            style=${`text-align:left;cursor:pointer;gap:4px;${b.mode === k ? "border-color:var(--blue-2);background:rgba(26,159,209,.1)" : ""}`}
            onClick=${() => setB({ ...b, mode: k, style: k === "client" ? "" : "ai-os-blue" })} aria-pressed=${b.mode === k}>
            <b>${label}</b><span class="small muted">${help}</span></button>`)}</div>
          <label class="field">Title<input type="text" value=${b.title} onInput=${set("title")} placeholder="e.g. Claude ka apna WhatsApp number" required /></label>
          ${b.mode === "client" && html`<label class="field">Client<input type="text" value=${b.client} onInput=${set("client")} placeholder="e.g. Venom Tech (@venomstech)" /></label>`}
          <div class="grid cols-2">
            <label class="field">Language<select value=${b.language} onChange=${set("language")}><option value="hi">Hinglish</option><option value="en">English</option></select></label>
            <label class="field">Shape<select value=${b.aspect} onChange=${set("aspect")}><option value="9:16">9:16 reel</option><option value="16:9">16:9 long-form</option></select></label>
          </div>
          <div class="field"><span>Platforms</span><div class="row">
            ${[["instagram", "Instagram"], ["youtube", "YouTube Shorts"]].map(([k, l]) => html`<label class="check"><input type="checkbox" checked=${b.platforms.includes(k)} onChange=${() => plat(k)} />${l}</label>`)}</div></div>
          <label class="field">CTA keyword <span class="hint">Instagram: "comment KEYWORD, link in DM"</span><input type="text" value=${b.cta} onInput=${set("cta")} placeholder="AGENT" /></label>
        </section>
        ${b.mode === "avatar" ? html`<section class="panel stack">
          <h2>Topic and script</h2>
          <label class="field">Topic<input type="text" value=${b.topic} onInput=${set("topic")} placeholder="What the reel teaches" /></label>
          <label class="field">Script <span class="hint">Roman Hinglish (captions come from it). Leave empty and the Script Writer drafts it once the Claude API key is set.</span>
            <textarea rows="8" value=${b.script} onInput=${set("script")} /></label>
        </section>` : html`<section class="panel stack">
          <h2>Footage</h2>
          <div class=${`drop ${over ? "over" : ""}`} onClick=${() => pick.current.click()} onDragOver=${(e) => { e.preventDefault(); setOver(true); }}
            onDragLeave=${() => setOver(false)} onDrop=${(e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files); }} role="button" tabindex="0">
            <${Icon} name="upload" size=${26} /><div style="margin-top:8px"><b>Drop the take here</b> or click to pick it</div>
            <div class="small">One landscape tripod take is the house format. Several files = several takes.</div>
            <input ref=${pick} type="file" multiple accept="video/*,audio/*,image/*" style="display:none" onChange=${(e) => add(e.target.files)} />
          </div>
          ${files.length > 0 && html`<div class="stack">${files.map((f, i) => html`<div class="row between small"><span class="mono">${String.fromCharCode(97 + i)} · ${f.name}</span>
            <span class="row"><span class="muted">${(f.size / 1e6).toFixed(1)} MB</span><${Btn} size="sm" kind="ghost" icon="x" aria-label=${`remove ${f.name}`}
              onClick=${() => setFiles(files.filter((_, j) => j !== i))} /></span></div>`)}</div>`}
          ${b.mode === "client" && html`<p class="small muted">Client jobs use the client's own footage and reels only; nothing scraped for style ever goes into the edit.</p>`}
        </section>`}
      </div>
      <div class="stack">
        <section class="panel stack">
          <h2>Style</h2>
          <select value=${b.style} onChange=${set("style")} aria-label="style">
            <option value="">The Story Editor picks</option>
            ${allowed.map((s) => html`<option value=${s.name}>${s.title}${s.status !== "built" ? " (to learn)" : ""}</option>`)}</select>
          ${(() => { const s = allowed.find((x) => x.name === b.style); return s && html`<div class="stack" style="gap:8px">
            <span class="small soft">${s.look}</span>${s.palette && html`<div class="swatches">${s.palette.map((c) => html`<i style=${`background:${c}`} title=${c} />`)}</div>`}
            <div class="row"><${Chip} tone=${s.status === "built" ? "ok" : "warn"}>${s.status}<//>${s.best_for && html`<span class="tiny muted">${s.best_for}</span>`}</div></div>`; })()}
          <p class="tiny muted">Your own reels use AI-OS Blue (the brand); client styles are hidden here, and the reverse for client briefs.</p>
        </section>
        <section class="panel stack">
          <h2>References and notes</h2>
          <label class="field">Reference reels or profiles <span class="hint">links or @handles, space-separated</span><textarea rows="3" value=${b.references} onInput=${set("references")} /></label>
          <label class="field">Notes for the Story Editor<textarea rows="4" value=${b.notes} onInput=${set("notes")} placeholder="Hook idea, a word to stress, a beat that must be full screen…" /></label>
        </section>
        <section class="panel stack">
          ${pct != null && html`<div class="bar"><i style=${`width:${Math.round(pct * 100)}%`} /></div><span class="small muted">${pct < 1 ? `Uploading ${Math.round(pct * 100)}%` : "Making the project…"}</span>`}
          <${Btn} kind="primary" type="submit" disabled=${pct != null}>Make the project<//>
          <p class="tiny muted">Footage stays on this PC. Nothing renders until you approve the storyboard.</p>
        </section>
      </div>
    </div>
  </form>`;
}
