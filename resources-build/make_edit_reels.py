"""Web version of the 'Let Claude Edit Your Reels' playbook (print HTML -> responsive page on the resources site)."""
from pathlib import Path

SRC = Path(r"D:\Claude code\ai-os\content\lead-magnets\let-claude-edit-your-reels.html")
OUT = Path(__file__).resolve().parent.parent / "resources-site" / "edit-reels" / "index.html"
WA = "https://whatsapp.com/channel/0029Vb89QG1HltYFE2iFAf1y"

HEAD = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Free playbook: let Claude edit your reels from one raw take. Setup prompt, filming rules, every editing prompt, and every fix. By Paras Arora, AI with Paras.">
<meta property="og:title" content="Let Claude edit your reels: the free playbook">
<meta property="og:description" content="One raw take, zero editing apps. Setup, prompts and fixes from my Claude Opus edit.">
<meta property="og:image" content="https://aiwithparas-resources.netlify.app/assets/og-edit-reels.jpg">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../assets/favicon.png">"""

SCREEN = """
  .webbar{display:none}
  @media screen {
    body{font-size:15px;padding:0 16px 48px;
      background-image:radial-gradient(900px 500px at 15% -10%, rgba(17,50,76,.75), transparent 60%)}
    .webbar{display:flex;align-items:center;justify-content:space-between;gap:10px;max-width:620px;margin:0 auto;padding:16px 0}
    .webbar a{color:var(--muted);text-decoration:none;font-weight:600;font-size:14px}
    .webbar a.dl{background:var(--blue);color:#fff;padding:9px 16px;border-radius:999px;font-weight:800}
    .page{width:auto;max-width:620px;height:auto;margin:0 auto 16px;padding:28px 22px;border:1px solid var(--glass-line);
      border-radius:28px;overflow:visible}
    .pnum{display:none}
    .cover{min-height:0;gap:28px}
    h1{font-size:clamp(32px,9vw,46px)}
    .deck{max-width:none}
    .stats{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
    .tool{grid-template-columns:1fr;gap:2px}
    .tool .c{text-align:left}
    .prompt .bd{font-size:12.5px;overflow-wrap:anywhere}
    .prompt .hd button{all:unset;cursor:pointer;color:var(--blue-br);font:inherit;letter-spacing:inherit;text-transform:inherit}
    .prompt .hd button:focus-visible{outline:2px solid var(--blue-br);outline-offset:3px;border-radius:4px}
    .cta .btn{margin-right:8px}
  }
  @media print { .webbar{display:none} }"""

COPY_JS = """<script>
document.querySelectorAll('.prompt .hd span:last-child').forEach(function (s) {
  var b = document.createElement('button'); b.type = 'button'; b.textContent = 'copy';
  b.setAttribute('aria-label', 'Copy this prompt'); s.replaceWith(b);
  b.addEventListener('click', function () {
    var t = b.closest('.prompt').querySelector('.bd').innerText;
    (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(
      function () { b.textContent = 'copied ✓'; setTimeout(function () { b.textContent = 'copy'; }, 1500); },
      function () { b.textContent = 'select + copy'; });
  });
});
</script>"""

h = SRC.read_text(encoding="utf-8")
subs = [
    ('<meta charset="utf-8">', HEAD),
    ("<title>Let Claude Edit Your Reels — Playbook</title>",
     "<title>Let Claude Edit Your Reels · Free Playbook | AI with Paras</title>"),
    ('src="https://exponentialworld.ai/logo.png"', 'src="../assets/logo.png"'),
    ("</style>", SCREEN + "\n</style>"),
    ("<body>\n", '<body>\n<nav class="webbar"><a href="../">← All free resources</a>'
                 '<a class="dl" href="Let-Claude-Edit-Your-Reels.pdf" download>Download PDF</a></nav>\n'),
    ('Join the free community →</a>',
     'Join the free community →</a><a class="btn" href="' + WA + '">📲 WhatsApp channel</a>'),
    ("</body>", COPY_JS + "\n</body>"),
]
for old, new in subs:
    assert h.count(old) == 1, old
    h = h.replace(old, new)
OUT.write_text(h, encoding="utf-8")
print("wrote", OUT)
