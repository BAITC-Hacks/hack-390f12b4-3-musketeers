"""Start both services with the active Python environment: python run.py."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def load_environment():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ensure_port(port):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is already in use. Choose another port or stop its service.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--ui-port", type=int, default=8501)
    args = parser.parse_args()
    if args.api_port == args.ui_port or not all(1 <= p <= 65535 for p in (args.api_port, args.ui_port)):
        raise SystemExit("Choose two different ports between 1 and 65535.")
    load_environment()
    ensure_port(args.api_port)
    ensure_port(args.ui_port)
    os.environ["API_BASE_URL"] = f"http://127.0.0.1:{args.api_port}"
    children = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app",
                                    "--host", "127.0.0.1", "--port", str(args.api_port)],
                                   cwd=ROOT, creationflags=flags)
        children.append(backend)
        for _ in range(60):
            if backend.poll() is not None:
                raise RuntimeError("Backend failed to start. See its error above.")
            try:
                with urlopen(os.environ["API_BASE_URL"] + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.25)
        else:
            raise RuntimeError("Backend startup timed out.")
        frontend = subprocess.Popen([sys.executable, "-m", "uvicorn", "frontend.server:app",
                                     "--host", "127.0.0.1", "--port", str(args.ui_port)],
                                    cwd=ROOT, creationflags=flags)
        children.append(frontend)
        print(f"Open http://127.0.0.1:{args.ui_port} | API docs: http://127.0.0.1:{args.api_port}/docs", flush=True)
        print("Press Ctrl+C to stop both services.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    main()
