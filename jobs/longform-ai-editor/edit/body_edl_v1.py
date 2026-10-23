"""Body cut list for the long-form (master = clean WAV timeline).
Editorial KEEP spans (word-level choices from the Hinglish transcript) -> remove internal pauses >= GAP
(measured on the audio) -> pad + snap edges to the quietest 10 ms -> frame-exact pieces.
Writes body_pieces.json: [{"m0","m1","sec"}] in output order, plus a report.
"""
import json
import subprocess

import numpy as np

E = r"C:\Users\PARAS ARORA\AI_Editor\inbox\longform-ai-editor\edit"
WAV = r"D:\october videos\ai editor\ai editor.wav"
FPS, GAP, PAD_IN, PAD_OUT = 25, 0.40, 0.08, 0.12

# (m0, m1, section, note) — m0/m1 are word starts/ends from the transcript; edges get padded+snapped below
KEEP = [
    (9.10, 22.61, "open", "sach mein maine video editor ki chhutti kar di hai ... Claude Opus 5.5 ne edit kari hai"),
    (24.20, 37.28, "open", "aur yahan tak ki ... iske bhi kuch parts AI ne edit kar rahe hain"),
    (38.06, 40.90, "open", "100% to nahi, lekin kuch parts AI ne edit kare hain"),
    (50.25, 54.55, "open", "ab bahut saare log ko ... aisa bhi ho sakta hai"),
    (55.11, 59.62, "open", "to tension lene ki zaroorat nahi ... breakdown karunga bhai, is video mein"),
    (61.65, 63.20, "open", "kaise yeh process maine kiya"),
    (63.82, 66.13, "open", "poori ki poori video ko AI se edit karwaya"),
    (73.02, 85.25, "promise", "at the end of the video ... cost ka breakdown ... kya cheez better ho sakti hai"),
    (88.04, 98.45, "promise", "kya iske implication ... quality of work ka kya difference hai"),
    (104.58, 107.95, "promise", "to bhai video ko end tak zaroor dekhna, agar aapko yeh sab jaanna hai to"),
    (115.40, 128.41, "why", "main ye video isliye bana raha hoon ... editing ek bahut bada bottleneck hai"),
    (129.67, 140.45, "why", "content record hone ke baad ... bahut zyada time"),
    (141.61, 142.15, "why", "jaata hai"),
    (143.69, 146.70, "why", "aur vo result unke content se nahi aa pata jo aana chahiye"),
    (149.81, 153.10, "why", "to isliye main poora breakdown karunga, step by step"),
    (158.73, 161.05, "sub", "aur agar video end tak dekhne mein maza aaye to"),
    (163.29, 168.75, "sub", "like kar dena, subscribe kar dena, share kar dena ... help kar sake"),
    (168.79, 188.33, "editors", "aur editor log jo hain ... end tak dekh lena hai bhai"),
    (242.41, 259.22, "time", "ab yeh poora process ... 3-4 ghante to lagenge"),
    (259.31, 271.09, "time", "AI ko ... sava ghante mein ... step by step guide"),
    (272.68, 277.60, "time", "jo bhi cheezein maine use kari ... description mein daal doonga"),
    (282.19, 286.13, "time", "aap usko use kar sako ..."),
    (293.23, 305.43, "s_skill", "is project ko maine create kiya ... skill ... zip file ... attach kar di"),
    (308.46, 314.55, "s_skill", "then maine kuch GitHub repository ... video use ... HyperFrames"),
    (319.99, 340.55, "s_skill", "jo bhi main resource attach karunga ... Claude Code ko samajh mein aa jaata hai"),
    (346.41, 356.69, "s_skill", "aur doosra jo hai, HyperFrames ... saare add kar deta hai"),
    (358.38, 361.80, "s_scratch", "ab bahut saare logon ko ... ek baar poora"),
    (363.04, 372.20, "s_scratch", "scratch se process bata deta hoon ... new project select karoge"),
    (375.75, 387.03, "s_scratch", "new project select karne ke baad ... naya folder create"),
    (388.30, 397.91, "s_scratch", "ek naya folder create karoge ... new folder create kar doonga"),
    (398.92, 416.25, "s_scratch", "aur uska naam likh doonga, AI Editor ... choose kar loonga"),
    (416.91, 423.19, "s_scratch", "uske baad ... resource ... process follow karna hai"),
    (423.34, 439.51, "s_scratch", "ab jo main aapko bata raha hoon ... isi folder mein saara kaam karega"),
    (439.63, 446.17, "s_scratch", "jo main resource doonga ... koi sawaal ho to pooch lena"),
    (448.11, 461.80, "install", "uske baad skill install kar leni hai ... aap khud samajhdar ho"),
    (512.65, 523.55, "s_guide", "ab jo meri guide hai ... 20 dollar ka plan aapke paas hona chahiye"),
    (535.85, 568.79, "s_guide", "aap baat karke usse kaam karaoge ... HyperFrames ... Whisper ... Node.js aur Python"),
    (569.19, 585.59, "s_guide", "jo editor hai ... apne aap install kar lega"),
    (585.71, 589.14, "s_guide", "this is just to make you understand"),
    (607.47, 619.93, "inputs", "raw footage naam ka folder ... audio file"),
    (620.01, 629.49, "inputs", "brand ke colors ... brand guidelines"),
    (629.58, 640.20, "inputs", "editing style ... download ... style copy karke mera video edit karna"),
    (642.09, 646.58, "inputs", "Claude Opus 5.5 itna smart hai"),
    (649.58, 664.92, "s_frames", "isne saari video ko frame by frame toda ..."),
    (665.10, 678.45, "tip", "thodi kami lagi ... 9.5 on 10 rate karoge"),
    (679.59, 693.49, "tip", "AI apne aap ko rate karta hai ... galti kar di"),
    (697.03, 707.10, "tip", "for example koi text mein galti ... improve karta hai"),
    (707.29, 708.85, "tip", "aur phir isne thoda sa time liya"),
    (717.26, 720.89, "output", "poori ki poori audio sync karke ... poora output"),
    (721.93, 734.61, "output", "nikaal ke de diya ... raw footage neeche ... reel format"),
    (735.56, 745.72, "s_reel", "studio mein ... long form video ke liye"),
    (749.48, 766.90, "doc", "9.5 nahi hai to ... document bana de ... better document"),
    (767.43, 780.47, "doc", "AI hi AI se video bana raha hai ... confusing state"),
    (785.35, 798.84, "projects", "poora process ... document guide ... separate projects ... skills"),
    (798.99, 806.26, "projects", "assets ... context ... AI aapke liye saara kaam kar deta hai"),
    (814.60, 824.89, "rule", "80% of the task by AI"),
    (825.35, 848.63, "rule", "10, 80, 10 rule"),
    (849.48, 851.67, "rule", "10x more effective"),
    (852.33, 864.95, "cta", "single person AI business ... AI employees"),
    (869.42, 881.24, "cta", "revenue making activity ... human touch ... recurring"),
    (881.29, 895.29, "cta", "community ka link ... WhatsApp community ... webinars, workshops"),
    (901.26, 911.80, "cta", "Skool community ka link ... tools ke link description mein"),
    (912.27, 921.11, "cta", "Instagram par bhi ... like share subscribe bell"),
    (921.61, 935.32, "cta", "aage kya seekhna chahte ho ... ab sabse important"),
    (935.43, 946.04, "cost", "cost kitna laga ... normal video editor ... 500 se leke"),
    (946.76, 953.37, "cost", "500 se 1000 ke beech ... complexity"),
    (954.76, 963.06, "cost", "global clients 20-30 dollar ek reel"),
    (963.63, 974.93, "cost", "AI ... guide ... free mein de raha hoon"),
    (975.37, 989.33, "cost", "community mein ... guide mein free install"),
    (989.58, 995.20, "cost", "Claude 20 dollar ke plan par hi hua hai"),
    (996.81, 1010.35, "cost", "one time limit ... 5 ghante ... limit gayi thi, to mere hisaab se"),
    (1011.21, 1024.41, "cost", "jo cost aayega ... 120 limit milti hai 20 dollar ke plan mein"),
    (1028.17, 1037.43, "cost", "ek limit ka cost ... 10-20-30 rupee ... ultimate cheez"),
    (1037.96, 1059.32, "cost", "editors bulk ... Max plan ... 100 reel"),
    (1060.55, 1063.25, "cost", "to aapko jo cost aayega, vo 100 rupe aayega ek reel ka"),
    # 1063.19-1068.11 '80% profitability' claim removed (Constitution §4: no income/profit claims) — flagged to Paras
    (1068.71, 1071.86, "cost", "aur jo khud ke liye use karna chahte hain vo yeh system use kar sakte hain"),
    (1073.19, 1087.13, "outro", "yeh tha cost ka breakdown ... long form ka cost next video mein"),
    (1087.34, 1096.60, "outro", "like share subscribe ... milte hain next video mein, bye bye"),
]

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", WAV, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
env = np.sqrt(np.convolve(x ** 2, np.ones(160) / 160, mode="same"))[::160]     # 10 ms RMS
db = 20 * np.log10(env + 1e-9)
thr = -55.0                                        # speech ~-36 dBFS, pauses ~-87 dBFS (noise-reduced WAV)


def quiet(t0, t1):
    a, b = int(max(0, t0) * 100), int(t1 * 100) + 1
    return (a + int(np.argmin(env[a:b]))) / 100 if b > a else t0


def speech_islands(m0, m1):
    """Split [m0,m1] at silences >= GAP (from the audio itself)."""
    a, b = int(m0 * 100), int(m1 * 100)
    loud = db[a:b] > thr
    islands, start, last_loud = [], None, None
    for i, l in enumerate(loud):
        t = (a + i) / 100
        if l:
            if start is None:
                start = t
            elif t - last_loud >= GAP:
                islands.append((start, last_loud + 0.01))
                start = t
            last_loud = t
    if start is not None:
        islands.append((start, last_loud + 0.01))
    return islands


pieces, out_t = [], 0.0
for m0, m1, sec, note in KEEP:
    for s, e in speech_islands(m0 - 0.05, m1 + 0.10):
        if e - s < 0.12:                           # clicks / breaths
            continue
        s2 = quiet(s - PAD_IN - 0.04, s - PAD_IN + 0.02)
        e2 = quiet(e + PAD_OUT - 0.02, e + PAD_OUT + 0.05)
        if pieces and s2 < pieces[-1]["m1"]:
            s2 = pieces[-1]["m1"]
        s2 = round(round(s2 * FPS) / FPS, 3)
        d = max(1, round((e2 - s2) * FPS)) / FPS
        pieces.append({"m0": s2, "m1": round(s2 + d, 3), "sec": sec, "out0": round(out_t, 3)})
        out_t += d

json.dump(pieces, open(E + r"\body_pieces.json", "w"), indent=0)
raw_speech = sum(m1 - m0 for m0, m1, _, _ in KEEP)
print(f"{len(pieces)} pieces, body {out_t:.1f}s ({out_t / 60:.1f} min) from {raw_speech:.0f}s of kept spans; silence thr {thr:.1f} dBFS")
from collections import OrderedDict
secs = OrderedDict()
for p in pieces:
    secs.setdefault(p["sec"], [p["out0"], 0])[1] = p["out0"] + (p["m1"] - p["m0"])
for k, (a, b) in secs.items():
    print(f"  {k:10s} out {a:7.2f}-{b:7.2f}  ({b - a:5.1f}s)")
