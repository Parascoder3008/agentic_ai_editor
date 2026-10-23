// Style library: the style packs (built, learned, to learn) and the effects catalog with each effect's preview.
import { useState } from "preact/hooks";
import { get, post } from "../api.js";
import { html, Btn, Chip, Empty, Tabs, toast, usePoll } from "../ui.js";

export function Library({ tab }) {
  return html`<div class="page">
    <div class="page-head"><div><h1>Style library</h1><p>Styles are saved looks the agents edit in; effects are the pieces they place. Your own reels use AI-OS Blue, the brand.</p></div></div>
    <${Tabs} items=${[["#/styles", "Styles", "styles"], ["#/styles/effects", "Effects", "effects"]]} current=${tab} />
    ${tab === "effects" ? html`<${Effects} />` : html`<${Styles} />`}
  </div>`;
}

function LearnForm({ data, ready, reload }) {
  const toLearn = data.styles.filter((s) => s.status === "to learn");
  const [pick, setPick] = useState(toLearn[0] ? toLearn[0].name : "");
  const [name, setName] = useState("");
  const [handles, setHandles] = useState("");
  const [use, setUse] = useState("any");
  const target = pick || name.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-");
  const submit = async (e) => {
    e.preventDefault();
    try { const r = await post("/api/styles/learn", { name: target, use, handles: handles.split(/[\s,]+/).filter(Boolean) }); toast(r.message, "ok"); reload(); }
    catch (err) { toast(err.message, err.status === 409 ? "" : "err"); }
  };
  const live = Object.entries(data.learning || {});
  return html`<section class="panel stack">
    <div><h2>Learn a style from profiles</h2><p class="small muted" style="margin-top:4px">The Style Learner ranks the profiles' reels by plays, keeps the top 6,
      measures their cuts, and writes a pack you approve once (Apify bills about $0.25 a learn). Scraped reels only teach the style; they never go into an edit.</p></div>
    <form class="learn" onSubmit=${submit}>
      <label class="field">Style<select value=${pick} onChange=${(e) => setPick(e.target.value)}>
        ${toLearn.map((s) => html`<option value=${s.name}>${s.title}</option>`)}<option value="">A new style…</option></select></label>
      ${!pick && html`<label class="field">Name<input type="text" placeholder="e.g. desi-explainer" value=${name} onInput=${(e) => setName(e.target.value)} /></label>`}
      <label class="field">Profiles (1–3)<input type="text" placeholder="@handle, @handle" value=${handles} onInput=${(e) => setHandles(e.target.value)} /></label>
      <label class="field">Use<select value=${use} onChange=${(e) => setUse(e.target.value)}><option value="any">Any reel</option><option value="client">Client reels only</option></select></label>
      <${Btn} kind="primary" type="submit" disabled=${!ready || !target || !handles.trim()} title=${ready ? "" : "needs the Apify token and the Claude API key (Connections)"}>Learn<//>
    </form>
    ${!ready && html`<p class="tiny muted">Waits for the Apify token and the Claude API key (<a href="#/connections">Connections</a>).</p>`}
    ${live.map(([n, st]) => html`<div class="row" style="gap:8px"><${Chip} tone=${st.status === "done" ? "ok" : st.status === "failed" ? "err" : "blue"} live=${st.status === "running"}>${n}<//>
      <span class="small soft">${st.message}</span></div>`)}
  </section>`;
}

function Styles() {
  const [data, reload] = usePoll(() => get("/api/styles"), 4000);
  const [conns] = usePoll(() => get("/api/connections"), 0);
  const [open, setOpen] = useState(null);
  if (!data) return html`<div class="row muted"><span class="spin" /> Loading…</div>`;
  const on = (id) => conns && ["set", "tested OK"].includes((conns.items.find((c) => c.id === id) || {}).status);
  const counts = data.styles.reduce((a, s) => ({ ...a, [s.status]: (a[s.status] || 0) + 1 }), {});
  const approve = async (s, v) => { try { const p = await post(`/api/styles/${s.name}/approve`, { value: v }); setOpen({ ...open, ...p }); reload(); toast(v ? "Approved: the agents can use it" : "Approval withdrawn", "ok"); } catch (e) { toast(e.message, "err"); } };
  const chip = (s) => s.status === "learned" && !s.approved ? html`<${Chip} tone="warn">learned · approve<//>`
    : html`<${Chip} tone=${s.status === "built" ? "ok" : s.status === "learned" ? "blue" : "warn"}>${s.status}<//>`;
  return html`
    <${LearnForm} data=${data} ready=${on("apify") && on("anthropic")} reload=${reload} />
    <div class="row"><${Chip} tone="ok">${counts.built || 0} built<//><${Chip} tone="blue">${counts.learned || 0} learned<//><${Chip} tone="warn">${counts["to learn"] || 0} to learn<//></div>
    <div class="cards">${data.styles.map((s) => html`<button type="button" class="panel pcard" style="text-align:left;cursor:pointer" onClick=${() => setOpen(s)}>
      ${s.preview ? html`<img src=${s.preview} alt="" style="width:100%;border-radius:14px" />` : html`<div class="placeholder-art" style="aspect-ratio:16/7">${s.status === "to learn" ? "learn it from 2–3 profiles" : "no preview yet"}</div>`}
      <div class="row between"><h3>${s.title}</h3>${chip(s)}</div>
      <span class="small soft">${s.look}</span>
      <div class="row between">${s.palette ? html`<div class="swatches">${s.palette.slice(0, 6).map((c) => html`<i style=${`background:${c}`} />`)}</div>` : html`<span />`}
        <span class="tiny muted">${s.use === "own" ? "your brand" : s.use === "client" ? "client style" : s.best_for || ""}</span></div>
    </button>`)}</div>
    ${open && html`<div class="drawer-bg" onClick=${(e) => e.target === e.currentTarget && setOpen(null)}><div class="drawer" role="dialog" aria-label=${open.title}>
      <div class="row between"><h2>${open.title}</h2><${Btn} size="sm" icon="x" aria-label="Close" onClick=${() => setOpen(null)} /></div>
      <p class="soft">${open.look}</p>
      ${open.status === "learned" && html`<div class=${`banner ${open.approved ? "info" : ""}`}><div style="flex:1">${open.approved
        ? html`<b>Approved.</b> The agents can edit in this style.` : html`<b>Waiting for your approval.</b> Check the look, palette and effects; the agents don't use it until you approve.`}</div>
        <${Btn} size="sm" kind=${open.approved ? "" : "primary"} icon=${open.approved ? "" : "check"} onClick=${() => approve(open, !open.approved)}>${open.approved ? "Withdraw" : "Approve"}<//></div>`}
      <dl class="kv">${[["Status", open.status], ["Use", open.use], ["Best for", open.best_for], ["Learned from", open.learned_from], ["Jobs", (open.jobs || []).join(", ")],
        ["Type", open.type && Object.entries(open.type).map(([k, v]) => `${k}: ${v}`).join(" · ")], ["Layouts", (open.layouts || []).join(", ")],
        ["Storyboard", open.storyboard], ["Hits", open.hits], ["SFX", (open.sfx || []).join(", ")],
        ["Pacing", open.pacing && Object.entries(open.pacing).map(([k, v]) => `${k} ${v}`).join(" · ")], ["Components", open.components],
        ["Notes", open.notes]].filter(([, v]) => v).map(([k, v]) => html`<dt>${k}</dt><dd>${v}</dd>`)}</dl>
      ${open.palette && html`<div class="swatches">${open.palette.map((c) => html`<i style=${`background:${c};width:34px;height:34px`} title=${c} />`)}</div>`}
      ${open.effects && html`<div class="stack"><h3>Effects (${open.effects.length})</h3><div class="row">${open.effects.map((e) => html`<${Chip}>${e}<//>`)}</div></div>`}
      ${open.references && open.references.length > 0 && html`<div class="stack"><h3>Reference reels</h3>${open.references.map((u) =>
        html`<a class="small" href=${u} target="_blank" rel="noopener noreferrer">${u}</a>`)}</div>`}
    </div></div>`}`;
}

function Effects() {
  const [data] = usePoll(() => get("/api/effects"), 0);
  const [fmt, setFmt] = useState("9:16");
  const [q, setQ] = useState("");
  if (!data) return html`<div class="row muted"><span class="spin" /> Loading…</div>`;
  const list = data.effects.filter((e) => (!fmt || (e.formats || []).includes(fmt)) &&
    (!q || `${e.name} ${e.title} ${(e.tags || []).join(" ")}`.toLowerCase().includes(q.toLowerCase())));
  return html`
    <div class="row between"><div class="seg">${[["9:16", "Reels 9:16"], ["16:9", "Long-form 16:9"], ["", "All"]].map(([k, l]) =>
      html`<button class=${fmt === k ? "on" : ""} onClick=${() => setFmt(k)}>${l}</button>`)}</div>
      <input type="text" placeholder="Search effects" value=${q} onInput=${(e) => setQ(e.target.value)} style="max-width:260px" aria-label="search effects" /></div>
    ${data.errors.length > 0 && html`<div class="banner err"><b>${data.errors.length} catalog problem(s)</b> ${data.errors[0]}</div>`}
    ${list.length === 0 ? html`<div class="panel"><${Empty} title="No effects match" /></div>` : html`<div class="cards">${list.map((e) => html`<article class="panel fx stack">
      ${e.preview ? html`<img src=${e.preview} alt=${`${e.title} preview`} loading="lazy" class=${(e.formats || [])[0] === "16:9" ? "land" : ""} />` : html`<div class="placeholder-art">no preview</div>`}
      <div class="row between"><h3>${e.title}</h3><span class="mono tiny muted">${e.name}</span></div>
      <span class="small soft">${e.description}</span>
      <div class="row">${(e.formats || []).map((f) => html`<${Chip}>${f}<//>`)}${e.zone && html`<${Chip} tone="blue">${e.zone === "stage" ? "top-half stage" : "full frame"}<//>`}
        ${e.brand === "own" && html`<${Chip} tone="warn" title="Carries Paras's brand: never in client jobs">your brand<//>`}
        ${e.duration && html`<span class="tiny muted">${e.duration.min}–${e.duration.max} s</span>`}</div>
      <details><summary class="small" style="cursor:pointer;color:var(--blue-2);font-weight:600">${Object.keys(e.params).length} parameters</summary>
        <dl class="kv small" style="margin-top:8px">${Object.entries(e.params).map(([k, v]) => html`<dt class="mono">${k}</dt><dd>${v.description || ""}${v.required ? html` <b>required</b>` : ""}${v.type && v.type !== "text" ? ` (${v.type})` : ""}</dd>`)}</dl></details>
    </article>`)}</div>`}`;
}
