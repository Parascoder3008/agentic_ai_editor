// Style library: the style packs (built, learned, to learn) and the effects catalog with each effect's preview.
import { useState } from "preact/hooks";
import { get } from "../api.js";
import { html, Btn, Chip, Empty, Tabs, toast, usePoll } from "../ui.js";

export function Library({ tab }) {
  return html`<div class="page">
    <div class="page-head"><div><h1>Style library</h1><p>Styles are saved looks the agents edit in; effects are the pieces they place. Your own reels use AI-OS Blue, the brand.</p></div></div>
    <${Tabs} items=${[["#/styles", "Styles", "styles"], ["#/styles/effects", "Effects", "effects"]]} current=${tab} />
    ${tab === "effects" ? html`<${Effects} />` : html`<${Styles} />`}
  </div>`;
}

function Styles() {
  const [data] = usePoll(() => get("/api/styles"), 0);
  const [conns] = usePoll(() => get("/api/connections"), 0);
  const [open, setOpen] = useState(null);
  const [handle, setHandle] = useState("");
  if (!data) return html`<div class="row muted"><span class="spin" /> Loading…</div>`;
  const apify = conns && ["set", "tested OK"].includes((conns.items.find((c) => c.id === "apify") || {}).status);
  const counts = data.styles.reduce((a, s) => ({ ...a, [s.status]: (a[s.status] || 0) + 1 }), {});
  return html`
    <section class="panel row between">
      <div><h2>Learn a style from a profile</h2><p class="small muted" style="margin-top:4px">The Style Learner ranks a profile's reels by plays, takes the top 5–8 and writes a pack you approve once. Scraped reels only teach the style; they never go into an edit.</p></div>
      <form class="row" onSubmit=${(e) => { e.preventDefault(); toast(apify ? "Queued for the Style Learner (Phase 1 agent): needs the Claude API key too" : "Needs the Apify token (Connections) to scrape the profile", apify ? "" : "err"); }}>
        <input type="text" placeholder="@handle" value=${handle} onInput=${(e) => setHandle(e.target.value)} style="width:200px" aria-label="Instagram handle" />
        <${Btn} kind="primary" type="submit">Learn<//></form>
    </section>
    <div class="row"><${Chip} tone="ok">${counts.built || 0} built<//><${Chip} tone="blue">${counts.learned || 0} learned<//><${Chip} tone="warn">${counts["to learn"] || 0} to learn<//></div>
    <div class="cards">${data.styles.map((s) => html`<button type="button" class="panel pcard" style="text-align:left;cursor:pointer" onClick=${() => setOpen(s)}>
      ${s.preview ? html`<img src=${s.preview} alt="" style="width:100%;border-radius:14px" />` : html`<div class="placeholder-art" style="aspect-ratio:16/7">${s.status === "to learn" ? "learn it from 2–3 profiles" : "no preview yet"}</div>`}
      <div class="row between"><h3>${s.title}</h3><${Chip} tone=${s.status === "built" ? "ok" : s.status === "learned" ? "blue" : "warn"}>${s.status}<//></div>
      <span class="small soft">${s.look}</span>
      <div class="row between">${s.palette ? html`<div class="swatches">${s.palette.slice(0, 6).map((c) => html`<i style=${`background:${c}`} />`)}</div>` : html`<span />`}
        <span class="tiny muted">${s.use === "own" ? "your brand" : s.use === "client" ? "client style" : s.best_for || ""}</span></div>
    </button>`)}</div>
    ${open && html`<div class="drawer-bg" onClick=${(e) => e.target === e.currentTarget && setOpen(null)}><div class="drawer" role="dialog" aria-label=${open.title}>
      <div class="row between"><h2>${open.title}</h2><${Btn} size="sm" icon="x" aria-label="Close" onClick=${() => setOpen(null)} /></div>
      <p class="soft">${open.look}</p>
      <dl class="kv">${[["Status", open.status], ["Use", open.use], ["Best for", open.best_for], ["Learned from", open.learned_from], ["Jobs", (open.jobs || []).join(", ")],
        ["Type", open.type && Object.entries(open.type).map(([k, v]) => `${k}: ${v}`).join(" · ")], ["Layouts", (open.layouts || []).join(", ")],
        ["Storyboard", open.storyboard], ["Hits", open.hits], ["SFX", (open.sfx || []).join(", ")],
        ["Pacing", open.pacing && Object.entries(open.pacing).map(([k, v]) => `${k} ${v}`).join(" · ")], ["Components", open.components],
        ["Notes", open.notes]].filter(([, v]) => v).map(([k, v]) => html`<dt>${k}</dt><dd>${v}</dd>`)}</dl>
      ${open.palette && html`<div class="swatches">${open.palette.map((c) => html`<i style=${`background:${c};width:34px;height:34px`} title=${c} />`)}</div>`}
      ${open.effects && html`<div class="stack"><h3>Effects (${open.effects.length})</h3><div class="row">${open.effects.map((e) => html`<${Chip}>${e}<//>`)}</div></div>`}
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
