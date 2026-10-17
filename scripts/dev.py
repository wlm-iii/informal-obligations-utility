#!/usr/bin/env python3
"""Explicit local development tasks for Windows, macOS, and Linux (Python 3.12)."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
PYTHON = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
BASE = ROOT / ".local" / "postgres"
DATA = BASE / "data"
PORT = "54329"
TASKS = {
    "install": "Install locked dependencies and create .env if missing",
    "lock": "Refresh Python dependency locks (review the diff)",
    "frontend": "Run Vite on http://localhost:5173",
    "backend": "Run FastAPI on http://127.0.0.1:8000",
    "db-init": "Initialize an isolated local PostgreSQL cluster",
    "db-start": "Start local PostgreSQL and create the iou database",
    "db-stop": "Stop only this project's PostgreSQL cluster",
    "db-status": "Show local PostgreSQL status (nonzero if stopped)",
    "migrate": "Apply committed migrations",
    "migration": "Generate a migration: migration --message 'add loans'",
    "lint": "Run frontend and backend linters",
    "test": "Run backend unit/API tests (no database needed)",
    "test-db": "Run database smoke tests (applies migrations)",
    "check": "Lint, unit/API tests, tooling tests, and frontend build",
}


def run(*args, cwd=ROOT, env=None, capture=False, check=True):
    # Resolve npm.cmd on Windows without requiring a PowerShell execution-policy change.
    executable = shutil.which(str(args[0]))
    if executable is None:
        raise RuntimeError(f"Missing executable: {args[0]}. See docs/DEVELOPMENT.md for setup.")
    return subprocess.run(
        [executable, *map(str, args[1:])],
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=check,
    )


def module(name, *args, **kwargs):
    return run(PYTHON, "-m", name, *args, **kwargs)


def database(task):
    if task == "db-init":
        if (DATA / "PG_VERSION").exists():
            print(f"Cluster already exists at {DATA} (left untouched).")
            return
        BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
        run(
            "initdb",
            "-D",
            DATA,
            "--username=iou",
            "--auth-local=trust",
            "--auth-host=trust",
            "--encoding=UTF8",
            "--locale=C",
        )
        return

    if not (DATA / "PG_VERSION").exists():
        raise RuntimeError("Run the db-init task first.")
    if task == "db-status":
        run("pg_ctl", "-D", DATA, "status")
        return

    running = run("pg_ctl", "-D", DATA, "status", capture=True, check=False).returncode == 0
    if task == "db-stop":
        if running:
            run("pg_ctl", "-D", DATA, "-m", "fast", "-w", "stop")
        else:
            print("Project database is already stopped.")
        return

    if not running:
        # TCP loopback only; no Unix sockets (also avoids repository path-length limits).
        run(
            "pg_ctl",
            "-D",
            DATA,
            "-l",
            BASE / "server.log",
            "-o",
            f"-h 127.0.0.1 -p {PORT} -c unix_socket_directories=",
            "-w",
            "start",
        )
    connection = ("-w", "-h", "127.0.0.1", "-p", PORT, "-U", "iou")

    def query(sql):
        return run(
            "psql",
            "-X",
            *connection,
            "-d",
            "postgres",
            "-Atc",
            sql,
            env={"PGCONNECT_TIMEOUT": "5"},
            capture=True,
        ).stdout.strip()

    # Never create a database on an unrelated service occupying our port.
    if Path(query("SHOW data_directory")).resolve() != DATA.resolve():
        raise RuntimeError(
            f"Port {PORT} is not serving this project's cluster; refusing to proceed."
        )
    if query("SELECT 1 FROM pg_database WHERE datname = 'iou'") != "1":
        run("createdb", *connection, "iou", env={"PGCONNECT_TIMEOUT": "5"})
    print(f"IOU database ready at 127.0.0.1:{PORT}/iou (local development only).")


def task(name, message=None):
    if name == "install":
        run("uv", "venv", "--python", "3.12", "--allow-existing", ROOT / "backend/.venv")
        run("uv", "pip", "sync", "--python", PYTHON, ROOT / "backend/requirements-dev.txt")
        run("npm", "ci", cwd=ROOT / "frontend")
        # Never overwrite an existing .env, even when install is re-run.
        try:
            with (ROOT / ".env").open("x", encoding="utf-8") as target:
                target.write((ROOT / ".env.example").read_text(encoding="utf-8"))
        except FileExistsError:
            pass
    elif name == "lock":
        run(
            "uv",
            "pip",
            "compile",
            "--universal",
            "--python-version",
            "3.12",
            "requirements.in",
            "-o",
            "requirements.txt",
            cwd=ROOT / "backend",
        )
        run(
            "uv",
            "pip",
            "compile",
            "--universal",
            "--python-version",
            "3.12",
            "--constraint",
            "requirements.txt",
            "requirements-dev.in",
            "-o",
            "requirements-dev.txt",
            cwd=ROOT / "backend",
        )
    elif name == "frontend":
        run("npm", "run", "dev", cwd=ROOT / "frontend")
    elif name == "backend":
        module(
            "uvicorn",
            "iou.api:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            env={"PYTHONPATH": str(ROOT / "backend/src")},
        )
    elif name.startswith("db-"):
        database(name)
    elif name == "migrate":
        module("alembic", "-c", "backend/alembic.ini", "upgrade", "head")
    elif name == "migration":
        if not message or not message.strip():
            raise RuntimeError('Use migration --message "add loans".')
        module("alembic", "-c", "backend/alembic.ini", "revision", "--autogenerate", "-m", message)
    elif name == "lint":
        run("npm", "run", "lint", cwd=ROOT / "frontend")
        module("ruff", "check", "--config", "backend/pyproject.toml", "backend", "scripts")
        module(
            "ruff", "format", "--check", "--config", "backend/pyproject.toml", "backend", "scripts"
        )
    elif name in ("test", "test-db"):
        marker = "database" if name == "test-db" else "not database"
        module("pytest", "-c", "backend/pyproject.toml", "backend/tests", "-m", marker)
    elif name == "check":
        task("lint")
        task("test")
        run(sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests")
        run("npm", "run", "build", cwd=ROOT / "frontend")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="help", choices=["help", *TASKS])
    parser.add_argument("--message", help="Description for the migration task")
    args = parser.parse_args()
    if args.task == "help":
        for name, description in TASKS.items():
            print(f"{name:12} {description}")
        return 0
    try:
        task(args.task, args.message)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        return error.returncode
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
