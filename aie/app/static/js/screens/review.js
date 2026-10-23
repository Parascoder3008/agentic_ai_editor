// Review player: frame-accurate playback of a delivered cut (or any earlier version) with Instagram's UI zones on top,
// the QA report alongside, and notes pinned to a timecode that go to the agent who owns the fix.
import { useEffect, useRef, useState } from "preact/hooks";
import { del, get, media, patch, post } from "../api.js";
import { html, Btn, Chip, Empty, Icon, tc, toast, usePoll } from "../ui.js";

const rel = (abs) => { const i = abs.replace(/\\/g, "/").lastIndexOf("/build/"); return i >= 0 ? abs.replace(/\\/g, "/").slice(i + 1) : abs; };

function sources(p) {
  const out = [];
  Object.entries(p.deliveries || {}).forEach(([name, v]) => out.push({ key: `cur:${name}`, label: `${name} · current`, variant: name, path: rel(v.path) }));
  (p.versions || []).slice().reverse().forEach((v) => Object.entries(v.files).forEach(([name, f]) => {
    if (name !== "_stamp") out.push({ key: `v${v.n}:${name}`, label: `${name} · v${v.n}${v.final ? " final" : ""}`, variant: name, path: rel(f) });
  }));
  if (!out.length && p.picture) out.push({ key: "master", label: "master picture (no sound)", variant: null, path: "build/picture.mp4" });
  return out;
}

export function Review({ p }) {
  const srcs = sources(p);
  const [key, setKey] = useState(srcs[0] && srcs[0].key);
  const src = srcs.find((s) => s.key === key) || srcs[0];
  const [side, setSide] = useState(location.hash.includes("?qa") ? "qa" : "notes");
  if (!src) return html`<div class="panel"><${Empty} title="Nothing to review yet">Render the project first (Overview → Render + QA). Each delivery shows up here, and so does every earlier version.<//></div>`;
  const fps = (p.job && p.job.fps) || 25;
  const vertical = !p.job || p.job.size[1] > p.job.size[0];
  return html`<div class="player">
    <${Player} key=${src.key} p=${p} src=${src} srcs=${srcs} setKey=${setKey} fps=${fps} vertical=${vertical} side=${side} setSide=${setSide} />
  </div>`;
}

function Player({ p, src, srcs, setKey, fps, vertical, side, setSide }) {
  const v = useRef(null);
  const noteInput = useRef(null);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [zones, setZones] = useState(vertical);
  const [rate, setRate] = useState(1);
  const [notes, reloadNotes] = usePoll(() => get(`/api/projects/${p.id}/notes`), 5000, [p.id]);
  const mine = (notes || []).filter((n) => n.t != null && (!n.variant || !src.variant || n.variant === src.variant));

  useEffect(() => {
    let raf;
    const loop = () => { if (v.current) setT(v.current.currentTime); raf = requestAnimationFrame(loop); };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);
  const seek = (x) => { const el = v.current; if (!el) return; el.currentTime = Math.max(0, Math.min(dur || 1e9, Math.round(x * fps) / fps + 0.001)); };
  const step = (n) => { const el = v.current; if (!el) return; el.pause(); seek(el.currentTime + n / fps); };
  const toggle = () => { const el = v.current; if (!el) return; el.paused ? el.play() : el.pause(); };
  useEffect(() => {
    const k = (e) => {
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      if (e.key === " ") { e.preventDefault(); toggle(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); e.shiftKey ? seek(v.current.currentTime - 1) : step(-1); }
      else if (e.key === "ArrowRight") { e.preventDefault(); e.shiftKey ? seek(v.current.currentTime + 1) : step(1); }
      else if (e.key === "n") { e.preventDefault(); v.current.pause(); noteInput.current && noteInput.current.focus(); }
      else if (e.key === "z") setZones((z) => !z);
    };
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [dur]);
  useEffect(() => { if (v.current) v.current.playbackRate = rate; }, [rate]);

  return html`
    <div class="stack">
      <div class="stagebox">
        <div class=${`vwrap ${vertical ? "" : "land"}`}>
          <video ref=${v} src=${media(p.id, src.path)} preload="auto" playsinline onClick=${toggle}
            onLoadedMetadata=${(e) => setDur(e.target.duration)} onPlay=${() => setPlaying(true)} onPause=${() => setPlaying(false)} />
          ${zones && vertical && html`<div class="zones" aria-hidden="true">
            <i class="ln" style="top:${(200 / 1920) * 100}%" /><span class="tag" style="top:${(200 / 1920) * 100 + 0.4}%">IG top · y 200</span>
            <i class="ln" style="top:${(1560 / 1920) * 100}%" /><span class="tag" style="top:${(1560 / 1920) * 100 + 0.4}%">IG caption · y 1560</span>
            <i class="rail" style="left:${(930 / 1080) * 100}%;right:0;top:${(1000 / 1920) * 100}%;bottom:${(220 / 1920) * 100}%" /></div>`}
        </div>
      </div>
      <div class="panel tight">
        <input class="scrub" type="range" min="0" max=${dur || 0} step=${1 / fps} value=${t} aria-label="position" onInput=${(e) => seek(Number(e.target.value))} />
        <div class="marks">${dur > 0 && mine.map((n) => html`<i class=${n.status === "fixed" ? "fixed" : ""} style="left:${(n.t / dur) * 100}%" title=${`${tc(n.t)} ${n.text}`} onClick=${() => seek(n.t)} />`)}</div>
        <div class="ctrl">
          <${Btn} size="sm" icon=${playing ? "pause" : "play"} aria-label=${playing ? "Pause" : "Play"} onClick=${toggle} />
          <${Btn} size="sm" icon="prev" aria-label="Back one frame" title="Back one frame (←)" onClick=${() => step(-1)} />
          <${Btn} size="sm" icon="next" aria-label="Forward one frame" title="Forward one frame (→)" onClick=${() => step(1)} />
          <span class="tc" title=${`frame ${Math.round(t * fps)}`}>${tc(t)}</span><span class="muted small num">/ ${tc(dur)}</span>
          <span style="flex:1" />
          <select value=${rate} onChange=${(e) => setRate(Number(e.target.value))} style="width:auto" aria-label="speed">
            ${[0.25, 0.5, 1, 1.5, 2].map((r) => html`<option value=${r}>${r}×</option>`)}</select>
          ${vertical && html`<label class="check small"><input type="checkbox" checked=${zones} onChange=${(e) => setZones(e.target.checked)} /> IG zones</label>`}
          <select value=${src.key} onChange=${(e) => setKey(e.target.value)} style="width:auto;max-width:240px" aria-label="cut and version">
            ${srcs.map((s) => html`<option value=${s.key}>${s.label}</option>`)}</select>
        </div>
        <p class="tiny muted" style="margin-top:8px"><span class="kbd">space</span> play · <span class="kbd">←</span><span class="kbd">→</span> one frame ·
          <span class="kbd">shift</span>+<span class="kbd">←</span><span class="kbd">→</span> one second · <span class="kbd">n</span> note here · <span class="kbd">z</span> zones</p>
      </div>
    </div>
    <div class="stack">
      <div class="seg" role="tablist"><button class=${side === "notes" ? "on" : ""} onClick=${() => setSide("notes")}>Notes ${mine.filter((n) => n.status !== "fixed").length || ""}</button>
        <button class=${side === "qa" ? "on" : ""} onClick=${() => setSide("qa")}>QA ${p.qa ? p.qa.score.toFixed(1) : ""}</button></div>
      ${side === "notes" ? html`<${Notes} p=${p} t=${t} variant=${src.variant} notes=${mine} reload=${reloadNotes} seek=${seek} inputRef=${noteInput} />`
        : html`<${QA} p=${p} seek=${seek} />`}
    </div>`;
}

function Notes({ p, t, variant, notes, reload, seek, inputRef }) {
  const [text, setText] = useState("");
  const [at, setAt] = useState(null);
  const pinned = at == null ? t : at;
  const add = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    try { const n = await post(`/api/projects/${p.id}/notes`, { t: Math.round(pinned * 100) / 100, variant, text }); setText(""); setAt(null); reload();
      toast(`${tc(n.t)} → ${n.owner} (${n.reason})`, "ok"); }
    catch (err) { toast(err.message, "err"); }
  };
  const set = async (n, status) => { try { await patch(`/api/notes/${n.id}`, { status }); reload(); } catch (e) { toast(e.message, "err"); } };
  const send = async () => {
    try { const r = await post(`/api/projects/${p.id}/notes/send`); toast(r.message || "Sent to the agent team", "ok"); reload(); }
    catch (e) { toast(e.message, e.status === 409 ? "" : "err"); }
  };
  const open = notes.filter((n) => n.status === "open").length;
  return html`<section class="panel stack">
    <form class="stack" onSubmit=${add}>
      <label class="field">Note at <span class="tc" style="min-width:0">${tc(pinned)}</span>
        <textarea ref=${inputRef} rows="3" placeholder="What should change here? e.g. caption galat hai: 'clod' → Claude"
          value=${text} onFocus=${() => setAt(t)} onInput=${(e) => setText(e.target.value)}
          onKeyDown=${(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) add(e); }} /></label>
      <div class="row between"><span class="tiny muted">It goes to the agent that owns the fix.</span><${Btn} kind="primary" size="sm" type="submit" icon="note">Add note<//></div>
    </form>
    <div class="hr" />
    <div class="row between"><h3>${notes.length} note${notes.length === 1 ? "" : "s"}</h3>
      <${Btn} size="sm" disabled=${!open} onClick=${send} title="The Producer sends each note to its owner and a new version comes back">Send ${open || ""} to agents<//></div>
    <div class="notes">${notes.length === 0 ? html`<p class="muted small">No notes on this cut. Pause where something's wrong and press <span class="kbd">n</span>.</p>` :
      notes.map((n) => html`<div class=${`note ${n.status === "fixed" ? "fixed" : ""}`} onClick=${() => seek(n.t)}>
        <div class="row between"><span class="t">${tc(n.t)}</span><span class="row" style="gap:6px"><${Chip} tone="blue">${n.owner}<//>
          <${Chip} tone=${n.status === "fixed" ? "ok" : n.status === "sent" ? "blue" : "warn"}>${n.status}${n.fixed_in ? ` in v${n.fixed_in}` : ""}<//></span></div>
        <span class="small">${n.text}</span>
        <div class="row" style="gap:6px" onClick=${(e) => e.stopPropagation()}>
          ${n.status !== "fixed" ? html`<${Btn} size="sm" kind="ghost" icon="check" onClick=${() => set(n, "fixed")}>Fixed<//>` : html`<${Btn} size="sm" kind="ghost" onClick=${() => set(n, "open")}>Reopen<//>`}
          <${Btn} size="sm" kind="ghost" icon="x" aria-label="Delete note" onClick=${async () => { await del(`/api/notes/${n.id}`); reload(); }} /></div>
      </div>`)}</div>
  </section>`;
}

function QA({ p }) {
  const q = p.qa_report;
  if (!q) return html`<section class="panel"><${Empty} title="QA hasn't run">It runs after delivery (Overview → Render + QA).<//></section>`;
  return html`<section class="panel stack">
    <div class="row between"><div class="row"><span class=${`score ${q.passed ? "ok" : "err"}`}>${q.score.toFixed(1)}</span>
      <div><b>${q.passed ? "Passes" : "Fails"} the 9.5 gate</b><div class="tiny muted">${q.final ? "final" : "preview"} files</div></div></div></div>
    <div>${Object.entries(q.checks).map(([k, c]) => html`<div class="qrow">
      <${Chip} tone=${c.status === "OK" ? "ok" : c.status === "FAIL" ? "err" : c.status === "WARN" ? "warn" : ""}>${c.status}<//>
      <b class="small">${k}</b><span class="small soft">${c.summary}${c.status !== "OK" && c.owner ? html` <span class="muted">→ ${c.owner}</span>` : ""}</span></div>`)}</div>
    ${q.sheets && q.sheets.length > 0 && html`<div class="stack"><h3>Contact sheets</h3>${q.sheets.map((s) =>
      html`<a href=${media(p.id, rel(s))} target="_blank" rel="noopener"><img src=${media(p.id, rel(s))} alt=${rel(s)} style="width:100%;border-radius:10px;display:block" loading="lazy" /></a>`)}</div>`}
  </section>`;
}
