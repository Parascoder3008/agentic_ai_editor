// The app shell: sidebar, a hash router and the screens. Screens poll the local API; nothing leaves this PC.
import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { get } from "./api.js";
import { html, Icon, Chip, Toasts, usePoll } from "./ui.js";
import { Projects } from "./screens/projects.js";
import { Brief } from "./screens/brief.js";
import { Library } from "./screens/library.js";
import { AvatarStudio } from "./screens/avatar.js";
import { Connections } from "./screens/connections.js";
import { Project } from "./screens/project.js";

function useRoute() {
  const [hash, setHash] = useState(location.hash || "#/");
  useEffect(() => {
    const f = () => { setHash(location.hash || "#/"); window.scrollTo(0, 0); };
    addEventListener("hashchange", f);
    return () => removeEventListener("hashchange", f);
  }, []);
  return hash.slice(1).split("?")[0].split("/").filter(Boolean);
}

const NAV = [["#/", "Projects", "projects", (r) => !r[0] || r[0] === "p"], ["#/new", "New brief", "brief", (r) => r[0] === "new"],
  ["#/styles", "Style library", "styles", (r) => r[0] === "styles"], ["#/avatar", "Avatar studio", "avatar", (r) => r[0] === "avatar"],
  ["#/connections", "Connections", "conn", (r) => r[0] === "connections"]];

function Side({ route, open, close }) {
  const [health] = usePoll(() => get("/api/health"), 4000);
  const ph = health && health.placeholder;
  return html`<aside class=${`side ${open ? "open" : ""}`} onClick=${(e) => e.target.closest("a") && close()}>
    <div class="brand"><span class="brand-mark"><svg width="14" height="14" viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z" fill="#3AB0D8" /></svg></span>
      <span>AI Editor<small>Exponential World</small></span></div>
    <nav class="nav">${NAV.map(([href, label, icon, on]) =>
      html`<a href=${href} class=${on(route) ? "on" : ""}><${Icon} name=${icon} />${label}</a>`)}</nav>
    <div class="grow" />
    <div class="side-card">
      <b>Render worker</b>
      ${health ? (health.worker ? html`<${Chip} tone="blue" live>Rendering · run ${health.worker}<//>` : html`<${Chip} tone="ok">Idle<//>`)
        : html`<span class="muted small">connecting…</span>`}
      ${health && health.queued > 0 && html`<span class="tiny muted">${health.queued} queued</span>`}
    </div>
    ${ph && html`<a class="side-card" href="#/connections" style="text-decoration:none;color:inherit">
      <b>${ph.set < ph.total ? "Placeholder mode" : "Connected"}</b>
      <span class="small soft">${ph.set} of ${ph.total} connections set</span>
      ${!ph.agents && html`<span class="tiny muted">Agents wait for the Claude API key. The pipeline runs now.</span>`}
    </a>`}
  </aside>`;
}

function App() {
  const route = useRoute();
  const [open, setOpen] = useState(false);
  let screen;
  if (!route[0]) screen = html`<${Projects} />`;
  else if (route[0] === "new") screen = html`<${Brief} />`;
  else if (route[0] === "styles") screen = html`<${Library} tab=${route[1] || "styles"} />`;
  else if (route[0] === "avatar") screen = html`<${AvatarStudio} />`;
  else if (route[0] === "connections") screen = html`<${Connections} />`;
  else if (route[0] === "p" && route[1]) screen = html`<${Project} id=${Number(route[1])} tab=${route[2] || "overview"} />`;
  else screen = html`<div class="empty"><h3>Nothing here</h3><a href="#/">Back to projects</a></div>`;
  return html`<div class="shell">
    <header class="top"><b>AI Editor</b><button class="btn sm icon" aria-label="Menu" onClick=${() => setOpen(!open)}><${Icon} name="menu" /></button></header>
    <${Side} route=${route} open=${open} close=${() => setOpen(false)} />
    <main class="main">${screen}</main>
    <${Toasts} />
  </div>`;
}

render(html`<${App} />`, document.getElementById("app"));
