"""python -m aie app [--port 8765] [--no-browser]: the local web app on http://127.0.0.1:8765."""
import argparse
import threading
import webbrowser


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m aie app")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="127.0.0.1 keeps it on this PC (the default)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    try:
        import uvicorn
        from .server import create_app
    except ImportError as e:
        print(f"FAIL the app needs {e.name}: pip install -e .[app]  (fastapi, uvicorn, python-multipart)")
        return 1
    url = f"http://{a.host}:{a.port}"
    if not a.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"AI Editor on {url}  (Ctrl+C stops it; renders in progress stop too)")
    uvicorn.run(create_app(), host=a.host, port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
