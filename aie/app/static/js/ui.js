// Shared pieces of the interface: icons, chips, buttons, toasts, tabs, timecodes.
import { h } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import htm from "htm";

export const html = htm.bind(h);

const P = {
  projects: "M3 4h7v7H3zM14 4h7v7h-7zM3 13h7v7H3zM14 13h7v7h-7z",
  brief: "M12 5v14M5 12h14",
  styles: "M4 20l4-1 11-11-3-3L5 16zM14 6l3 3",
  avatar: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c1.5-4 4.5-6 8-6s6.5 2 8 6",
  conn: "M9 7V3M15 7V3M7 7h10v4a5 5 0 01-10 0zM12 16v5",
  play: "M8 5l11 7-11 7z", pause: "M7 5h4v14H7zM13 5h4v14h-4z",
  prev: "M15 6l-6 6 6 6", next: "M9 6l6 6-6 6", back: "M19 12H5M11 18l-6-6 6-6",
  check: "M5 12l5 5 9-10", x: "M6 6l12 12M18 6L6 18", refresh: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
  lock: "M7 11V8a5 5 0 0110 0v3M5 11h14v10H5z", drive: "M8 3h8l6 11-4 7H6l-4-7z", film: "M4 4h16v16H4zM8 4v16M16 4v16M4 9h4M4 15h4M16 9h4M16 15h4",
  spark: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z", note: "M5 4h14v12l-4 4H5zM15 20v-4h4", eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
  menu: "M4 7h16M4 12h16M4 17h16", upload: "M12 16V4M7 9l5-5 5 5M5 20h14", key: "M14 10a4 4 0 11-1-3l7-7v4h-3v3h-3z",
};
export const Icon = ({ name, size = 18 }) => html`<svg width=${size} height=${size} viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d=${P[name]} /></svg>`;

export const Chip = ({ tone = "", live, children, title }) =>
  html`<span class=${`chip ${tone} ${live ? "live" : ""}`} title=${title}>${(live || tone) && html`<i class="dot" />`}${children}</span>`;

export const Btn = ({ kind = "", size = "", icon, children, ...rest }) =>
  html`<button class=${`btn ${kind} ${size} ${icon && !children ? "icon" : ""}`} type="button" ...${rest}>${icon && html`<${Icon} name=${icon} />`}${children}</button>`;

export const Empty = ({ title, children }) => html`<div class="empty"><h3>${title}</h3><div>${children}</div></div>`;

export function Tabs({ items, current }) {
  return html`<nav class="tabs">${items.map(([href, label, key]) =>
    html`<a href=${href} class=${key === current ? "on" : ""}>${label}</a>`)}</nav>`;
}

// toasts: toast("Saved") from anywhere
let pushToast = () => {};
export const toast = (msg, tone = "") => pushToast({ msg, tone, id: Math.random() });
export function Toasts() {
  const [t, setT] = useState(null);
  useEffect(() => { pushToast = (x) => { setT(x); setTimeout(() => setT((cur) => (cur && cur.id === x.id ? null : cur)), 4200); }; }, []);
  return t && html`<div class=${`toast ${t.tone}`} role="status">${t.msg}</div>`;
}

export function usePoll(fn, ms, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const tick = useRef(0);
  const load = async () => {
    const my = ++tick.current;
    try { const d = await fn(); if (my === tick.current) { setData(d); setError(null); } }
    catch (e) { if (my === tick.current) setError(e); }
  };
  useEffect(() => {
    load();
    if (!ms) return;
    const id = setInterval(load, ms);
    return () => clearInterval(id);
  }, deps);
  return [data, load, error];
}

// Timecodes as Paras writes them in notes: mm:ss.cc ("00:47.80").
export const tc = (t) => {
  if (t == null || isNaN(t)) return "--:--.--";
  const cs = Math.round(t * 100), m = Math.floor(cs / 6000), s = Math.floor((cs % 6000) / 100), c = cs % 100;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(c).padStart(2, "0")}`;
};
export const secs = (t) => (t == null ? "" : `${Number(t).toFixed(2)} s`);
export const ago = (ts) => {
  if (!ts) return "";
  const d = Date.now() / 1000 - ts;
  return d < 60 ? "just now" : d < 3600 ? `${Math.round(d / 60)} min ago` : d < 86400 ? `${Math.round(d / 3600)} h ago` : `${Math.round(d / 86400)} d ago`;
};

export const NEXT = {
  "brief": ["Waiting for footage", "warn"], "script": ["Write the script", "warn"], "avatar": ["Avatar studio", "blue"], "avatar failed": ["Avatar render failed", "err"], "fix job.json": ["Fix job.json", "err"],
  "storyboard": ["Build the storyboard", "blue"], "approve storyboard": ["Approve the storyboard", "warn"],
  "render": ["Ready to render", "blue"], "approve final": ["Approve the final", "warn"], "fix QA": ["QA failed", "err"],
  "delivered": ["Delivered", "ok"],
};
export const NextChip = ({ next }) => { const [label, tone] = NEXT[next] || [next, ""]; return html`<${Chip} tone=${tone}>${label}<//>`; };

export function Score({ qa }) {
  if (!qa) return html`<span class="score" title="QA hasn't run">–</span>`;
  return html`<span class=${`score ${qa.passed ? "ok" : "err"}`} title=${qa.passed ? "QA passed (gate 9.5)" : "QA failed"}>${qa.score.toFixed(1)}</span>`;
}

export function Pipe({ stages, running }) {
  return html`<div class="pipe" aria-label="pipeline progress">${stages.map((s) =>
    html`<i class=${s.stage === running ? "run" : s.done ? "done" : ""} title=${`${s.stage}${s.done ? ": done" : ""}`} />`)}</div>`;
}
