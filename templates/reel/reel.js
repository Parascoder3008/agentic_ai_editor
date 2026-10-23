// Shared motion of the 9:16 reel effects, ported from reel-05's composition. Each effect builds one paused timeline
// and calls these with times in seconds from its own start.
window.reel = function (tl, DUR) {
  const $ = (s) => document.querySelector(s);
  const chip = $("#chip");
  if (chip && !chip.textContent.trim()) chip.style.display = "none";    // no CHIP given: no empty pill
  const at = (f) => Math.max(0, Math.min(DUR - 0.05, f * DUR));          // a fraction of the effect's length
  return {
    $,
    at,
    text: (sel) => $(sel).textContent.trim(),                              // a parameter kept in a hidden element
    pop: (sel, t, d = 0.28) => tl.fromTo(sel, { opacity: 0, scale: 0.86, y: 24 }, { opacity: 1, scale: 1, y: 0, duration: d, ease: "back.out(2)" }, t),
    hide: (sel, t, d = 0.18) => tl.to(sel, { opacity: 0, duration: d, ease: "power2.in" }, t),
    slam: (sel, t, rot = -6) => tl.fromTo(sel, { opacity: 0, scale: 2.2, rotation: rot }, { opacity: 1, scale: 1, rotation: rot, duration: 0.16, ease: "power4.in" }, t),
    type: (sel, text, t0, t1) => {
      const el = $(sel), p = { n: 0 };
      tl.fromTo(p, { n: 0 }, { n: text.length, duration: Math.max(0.05, t1 - t0), ease: "none",
        onUpdate: () => { el.textContent = text.slice(0, Math.round(p.n)); } }, t0);
    },
    press: (sel, t, extra = {}) => tl.to(sel, { scale: 0.92, duration: 0.08, yoyo: true, repeat: 1, ...extra }, t),
  };
};
