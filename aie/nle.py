"""The edit as an OpenTimelineIO timeline, for finishing in an NLE (pip install opentimelineio otio-fcp-adapter).

build/nle/<id>.otio   DaVinci Resolve: File > Import > Timeline (Resolve 18 and later read .otio)
build/nle/<id>.xml    FCP 7 XML for Premiere Pro: File > Import
build/nle/*.srt       the captions, for the NLE's subtitle track

Tracks, bottom up:
  V1 originals   each beat's source file at its source time, switched off (and under the base, so it stays hidden
                 where an NLE ignores the switch): to re-frame or re-grade from the camera files
  V2 base        the framed footage (build/base.mp4) the picture is built on: grade here
  V3 graphics    the HyperFrames composition (transparent webm)
  V4.. effects   each catalog effect at its time (transparent webm); effects that overlap take separate tracks
  A1 voice, A2 sfx, A3 music   the stems before the -14 LUFS master
Markers: one per beat (its layout and note), on the timeline. Layout framing (the split card, crops, zooms) is baked
into the base; the originals are placed on time, not framed.
"""
import math
from pathlib import Path

from .ffmpeg import duration


def _otio():
    try:
        import opentimelineio as otio
    except ImportError:
        raise RuntimeError("the NLE export needs OpenTimelineIO: pip install opentimelineio otio-fcp-adapter") from None
    return otio


class Builder:
    def __init__(self, fps: int):
        self.otio, self.fps, self._dur = _otio(), fps, {}

    def rt(self, sec: float):
        return self.otio.opentime.RationalTime(round(sec * self.fps), self.fps)

    def tr(self, start: float, dur: float):
        return self.otio.opentime.TimeRange(self.rt(start), self.rt(dur))

    def length_of(self, path: Path) -> float:
        k = str(path)
        if k not in self._dur:
            self._dur[k] = duration(path)
        return self._dur[k]

    def ref(self, path: Path):
        return self.otio.schema.ExternalReference(target_url=Path(path).resolve().as_uri(),
                                                  available_range=self.tr(0, self.length_of(path)))

    def track(self, name: str, kind: str, items: list, enabled: bool = True):
        """items: (at, name, path, source_start, dur, metadata) on the output timeline; gaps fill between them. An item
        starts on the first frame at or after its time, where the picture's overlay first shows it."""
        o = self.otio
        frames = lambda a, n: o.opentime.TimeRange(o.opentime.RationalTime(a, self.fps), o.opentime.RationalTime(n, self.fps))
        t = o.schema.Track(name=name, kind=o.schema.TrackKind.Video if kind == "video" else o.schema.TrackKind.Audio)
        t.enabled = enabled
        pos = 0
        for at, nm, path, start, dur, meta in sorted(items, key=lambda x: x[0]):
            a, n = max(pos, math.ceil(at * self.fps - 1e-6)), round(dur * self.fps)
            if n <= 0:
                continue
            if a > pos:
                t.append(o.schema.Gap(source_range=frames(0, a - pos)))
            t.append(o.schema.Clip(name=nm, media_reference=self.ref(path), source_range=frames(round(start * self.fps), n),
                                   metadata={"aie": meta} if meta else {}))
            pos = a + n
        return t


def lanes(items: list) -> list:
    """Overlapping items onto separate lanes, first fit, in time order."""
    out = []
    for it in sorted(items, key=lambda x: x[0]):
        for lane in out:
            last = lane[-1]
            if last[0] + last[4] <= it[0] + 1e-6:
                lane.append(it)
                break
        else:
            out.append([it])
    return out


def timeline(name: str, fps: int, length: float, base: Path, beats: list, sources: dict, gfx: tuple | None,
             effects: list, stems: dict, variants: dict):
    """gfx: (path, source_offset) or None; effects: [(path, at, label)]; stems: {"voice"|"sfx"|"music": path}."""
    b = Builder(fps)
    o = b.otio
    tl = o.schema.Timeline(name=name, global_start_time=o.opentime.RationalTime(0, fps))
    tl.metadata["aie"] = {"variants": variants, "length": length}
    orig = []
    for i, bt in enumerate(beats, 1):
        t0, t1 = bt["t"]
        src = sources[bt["src"]]
        dur = min(t1 - t0, max(0.0, (b.length_of(src) - bt["in"]) / bt.get("speed", 1.0)))
        orig.append((t0, f"beat {i} {bt['src']}", src, bt["in"], dur,
                     {"layout": bt["layout"], "speed": bt.get("speed", 1.0), "zoom": bt.get("zoom", 1.0)}))
    tl.tracks.append(b.track("V1 originals", "video", orig, enabled=False))
    tl.tracks.append(b.track("V2 base", "video", [(0.0, "base", base, 0.0, min(length, b.length_of(base)), None)]))
    if gfx:
        path, off = gfx
        tl.tracks.append(b.track("V3 graphics", "video",
                                 [(0.0, "graphics", path, off, min(length, b.length_of(path) - off), None)]))
    fx = [(at, label, p, 0.0, min(b.length_of(p), length - at), None) for p, at, label in effects if at < length]
    for n, lane in enumerate(lanes(fx)):
        tl.tracks.append(b.track(f"V{4 + n} effects" if gfx else f"V{3 + n} effects", "video", lane))
    for n, kind in enumerate(("voice", "sfx", "music"), 1):
        if stems.get(kind):
            p = stems[kind]
            tl.tracks.append(b.track(f"A{n} {kind}", "audio", [(0.0, kind, p, 0.0, min(length, b.length_of(p)), None)]))
    for i, bt in enumerate(beats, 1):
        t0, t1 = bt["t"]
        tl.tracks.markers.append(o.schema.Marker(name=f"beat {i}: {bt['layout']}" + (f" ({bt['note'][:60]})" if bt.get("note") else ""),
                                          marked_range=b.tr(t0, 0), color=o.schema.MarkerColor.CYAN))
    return tl


def write(tl, out_dir: Path, name: str) -> dict:
    """<name>.otio, and <name>.xml when the FCP XML adapter is installed."""
    o = _otio()
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"otio": str(out_dir / f"{name}.otio"), "xml": None, "xml_error": None}
    o.adapters.write_to_file(tl, res["otio"])
    try:
        xml = out_dir / f"{name}.xml"
        o.adapters.write_to_file(tl, str(xml), adapter_name="fcp_xml")
        _switch_off(xml, [i for i, t in enumerate(t for t in tl.tracks if t.kind == "Video") if not t.enabled])
        res["xml"] = str(xml)
    except Exception as e:                       # the adapter is a separate package; the .otio stands without it
        res["xml_error"] = f"{type(e).__name__}: {e}"[:300]
    return res


def _switch_off(xml: Path, video_tracks: list):
    """The FCP XML adapter drops a track's enabled flag; FCP 7 XML carries it as <enabled>FALSE</enabled>."""
    if not video_tracks:
        return
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml)
    tracks = tree.getroot().findall("./project/children/sequence/media/video/track") or \
        tree.getroot().findall(".//sequence/media/video/track")
    for i in video_tracks:
        if i < len(tracks):
            e = tracks[i].find("enabled")
            if e is None:
                e = ET.SubElement(tracks[i], "enabled")
            e.text = "FALSE"
    tree.write(xml, encoding="UTF-8", xml_declaration=True)
