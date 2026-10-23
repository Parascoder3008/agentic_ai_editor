// The app's calls to the local API. Every error comes back as an Error whose message is the server's reason.
export async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    if (opts.body instanceof FormData) init.body = opts.body;
    else { init.body = JSON.stringify(opts.body); init.headers["Content-Type"] = "application/json"; }
  }
  const r = await fetch(path, init);
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) {
    const d = data && data.detail;
    const msg = typeof d === "string" ? d : d && d.errors ? d.errors.join("\n") : (typeof data === "string" ? data : r.statusText);
    const e = new Error(msg); e.status = r.status; e.detail = d; throw e;
  }
  return data;
}

export const get = (p) => api(p);
export const post = (p, body = {}) => api(p, { method: "POST", body });
export const put = (p, body) => api(p, { method: "PUT", body });
export const patch = (p, body) => api(p, { method: "PATCH", body });
export const del = (p) => api(p, { method: "DELETE" });

// Upload with progress (fetch can't report upload progress).
export function upload(path, form, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", path);
    x.upload.onprogress = (e) => e.lengthComputable && onProgress && onProgress(e.loaded / e.total);
    x.onload = () => {
      let d = null; try { d = JSON.parse(x.responseText); } catch { d = x.responseText; }
      if (x.status >= 200 && x.status < 300) resolve(d);
      else reject(new Error((d && d.detail) || x.statusText));
    };
    x.onerror = () => reject(new Error("upload failed: is the app still running?"));
    x.send(form);
  });
}

export const media = (pid, path) => `/media/${pid}/${path.split("/").map(encodeURIComponent).join("/")}`;
