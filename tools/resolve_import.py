"""Import an edit's timeline (build/nle/<id>.otio, from the otio stage) into the open DaVinci Resolve project.

Resolve 18 or later. Run it from inside Resolve (Workspace > Scripts) or from outside while Resolve is open; outside
scripting needs Resolve Studio with Preferences > System > General > External scripting using: Local.

Usage: python tools/resolve_import.py <path/to/<id>.otio> [--name TIMELINE_NAME] [--resolve "C:/.../Resolve.exe"]
"""
import argparse
import os
import sys
from pathlib import Path

MODULES = {"win32": r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
           "darwin": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules",
           "linux": "/opt/resolve/Developer/Scripting/Modules"}
LIBS = {"win32": "fusionscript.dll", "darwin": "Contents/Libraries/Fusion/fusionscript.so", "linux": "libs/Fusion/fusionscript.so"}


def connect(resolve_exe: str | None):
    """The running Resolve, through its scripting module (the paths Blackmagic documents, unless already set)."""
    plat = "win32" if sys.platform.startswith("win") else sys.platform if sys.platform == "darwin" else "linux"
    if resolve_exe and "RESOLVE_SCRIPT_LIB" not in os.environ:
        os.environ["RESOLVE_SCRIPT_LIB"] = str(Path(resolve_exe).parent / LIBS[plat])
    mods = os.environ.setdefault("RESOLVE_SCRIPT_API", os.path.expandvars(MODULES[plat]))
    sys.path.append(mods if mods.endswith("Modules") else os.path.join(mods, "Modules"))
    try:
        import DaVinciResolveScript as dvr                          # noqa: N813 (Blackmagic's module name)
    except ImportError:
        sys.exit(f"Resolve's scripting module isn't at {mods}: is DaVinci Resolve installed?")
    r = dvr.scriptapp("Resolve")
    if r is None:
        sys.exit("Resolve isn't answering: open it, and for outside scripting turn on Preferences > System > General > "
                 "External scripting using: Local (a Resolve Studio feature). Or run this from Workspace > Scripts.")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("otio")
    ap.add_argument("--name")
    ap.add_argument("--resolve", help="Resolve.exe, to find its scripting library")
    a = ap.parse_args()
    path = Path(a.otio).resolve()
    if not path.exists():
        sys.exit(f"{path} not found: run the otio stage first")
    r = connect(a.resolve)
    project = r.GetProjectManager().GetCurrentProject()
    if project is None:
        sys.exit("no project is open in Resolve")
    name = a.name or path.stem
    tl = project.GetMediaPool().ImportTimelineFromFile(str(path), {"timelineName": name, "importSourceClips": True})
    if not tl:
        sys.exit(f"Resolve didn't import {path.name}: check its media paths exist on this PC")
    project.SetCurrentTimeline(tl)
    print(f"imported {path.name} into '{project.GetName()}' as timeline '{tl.GetName()}' ({tl.GetTrackCount('video')} "
          f"video, {tl.GetTrackCount('audio')} audio tracks)")


if __name__ == "__main__":
    main()
