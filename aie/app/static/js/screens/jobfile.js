// Job file: the job.json behind the edit, editable with the same validation the runner uses.
import { useEffect, useState } from "preact/hooks";
import { put } from "../api.js";
import { html, Btn, Empty, toast } from "../ui.js";

export function JobFile({ p, reload }) {
  const [text, setText] = useState("");
  const [errs, setErrs] = useState([]);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (!dirty) setText(p.job ? JSON.stringify(p.job, null, 2) : ""); }, [p.job]);
  if (!p.has_job) return html`<div class="panel"><${Empty} title="No job.json yet" /></div>`;
  const save = async () => {
    let body;
    try { body = JSON.parse(text); } catch (e) { setErrs([`not valid JSON: ${e.message}`]); return; }
    try { await put(`/api/projects/${p.id}/job`, body); setErrs([]); setDirty(false); toast("job.json saved and valid", "ok"); reload(); }
    catch (e) { setErrs(e.detail && e.detail.errors ? e.detail.errors : [e.message]); }
  };
  return html`<section class="panel stack">
    <div class="row between"><p class="small muted">Every editorial decision lives here; the stages rebuild from it. Saving checks it the way the runner does.</p>
      <div class="row"><${Btn} size="sm" disabled=${!dirty} onClick=${() => { setDirty(false); setText(JSON.stringify(p.job, null, 2)); setErrs([]); }}>Revert<//>
        <${Btn} size="sm" kind="primary" disabled=${!dirty} onClick=${save}>Validate and save<//></div></div>
    ${errs.length > 0 && html`<div class="banner err"><div><b>${errs.length} problem${errs.length > 1 ? "s" : ""}, not saved.</b>
      <ul style="margin:6px 0 0;padding-left:18px">${errs.map((e) => html`<li class="small">${e}</li>`)}</ul></div></div>`}
    <textarea class="code" spellcheck="false" value=${text} onInput=${(e) => { setText(e.target.value); setDirty(true); }} aria-label="job.json" />
  </section>`;
}
