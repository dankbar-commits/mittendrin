"""
dev.py

Starts the whole project (FastAPI backend + Vite frontend) with a single
command, run from the repo root:

    uv run dev.py

Stdlib only — no dependencies to install, so `uv run` can execute this
script directly even though it lives outside backend/'s pyproject.toml.

On first run, creates backend/.env and frontend/.env from their
.env.example files automatically if they don't exist yet (never
overwrites an existing .env). You'll still need to open backend/.env and
fill in ANTHROPIC_API_KEY / SMTP_USERNAME / SMTP_PASSWORD for Claude and
email to actually work — this just removes the "forgot to copy the file
at all" failure mode.

Backend runs via `uv run uvicorn ...` (uses backend/.venv + uv.lock).
Frontend still runs via `npm run dev` under the hood (Vite has no uv
equivalent), just launched automatically instead of by hand in a second
terminal. Ctrl+C stops both.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

BACKEND_CMD = ["uv", "run", "uvicorn", "app.main:app", "--reload", "--port", "8000"]
FRONTEND_CMD = ["npm", "run", "dev"]


def ensure_env_file(directory: Path) -> None:
    """Creates .env from .env.example if .env doesn't exist yet. Never
    overwrites an existing .env — only ever fills the gap on first run,
    so this can't clobber real credentials you've already filled in."""
    env_path = directory / ".env"
    example_path = directory / ".env.example"

    if env_path.exists() or not example_path.exists():
        return

    shutil.copy(example_path, env_path)
    print(f"Created {env_path.relative_to(ROOT)} from .env.example — fill in your real keys before relying on it.")


def ensure_frontend_deps() -> None:
    if (FRONTEND_DIR / "node_modules").exists():
        return
    print("No frontend/node_modules found — running npm install first...")
    result = subprocess.run(["npm", "install"], cwd=FRONTEND_DIR)
    if result.returncode != 0:
        print("error: npm install failed", file=sys.stderr)
        sys.exit(result.returncode)


def main() -> int:
    if not (BACKEND_DIR / "pyproject.toml").exists():
        print(
            f"error: {BACKEND_DIR} doesn't look like the backend (no pyproject.toml)",
            file=sys.stderr,
        )
        return 1
    if not (FRONTEND_DIR / "package.json").exists():
        print(
            f"error: {FRONTEND_DIR} doesn't look like the frontend (no package.json)",
            file=sys.stderr,
        )
        return 1

    ensure_env_file(BACKEND_DIR)
    ensure_env_file(FRONTEND_DIR)
    ensure_frontend_deps()

    print("Starting backend  (http://localhost:8000) ...")
    backend = subprocess.Popen(BACKEND_CMD, cwd=BACKEND_DIR)

    print("Starting frontend (http://localhost:5173) ...")
    frontend = subprocess.Popen(FRONTEND_CMD, cwd=FRONTEND_DIR)

    try:
        # Wait on either process; if one dies unexpectedly, tear down the other.
        while True:
            backend_status = backend.poll()
            frontend_status = frontend.poll()
            if backend_status is not None:
                print(f"\nbackend exited ({backend_status}), stopping frontend...")
                frontend.terminate()
                break
            if frontend_status is not None:
                print(f"\nfrontend exited ({frontend_status}), stopping backend...")
                backend.terminate()
                break
            try:
                backend.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        print("\nStopping backend and frontend...")
        backend.terminate()
        frontend.terminate()

    backend.wait()
    frontend.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())