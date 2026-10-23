"""Running ffmpeg and ffprobe. No third-party imports, so the CLI can catch FFmpegError on a bare machine."""
import subprocess


class FFmpegError(RuntimeError):
    pass


def run(cmd) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise FFmpegError(f"{cmd[0]} failed ({r.returncode}): {r.stderr.strip()[-600:]}")
    return r


def duration(path) -> float:
    """Container duration in seconds."""
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout)


def video_info(path) -> dict:
    """Width, height and frame rate of the first video stream."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
               "-of", "csv=p=0", path]).stdout.strip().split(",")
    num, den = out[2].split("/")
    return {"size": [int(out[0]), int(out[1])], "fps": int(num) / int(den)}
