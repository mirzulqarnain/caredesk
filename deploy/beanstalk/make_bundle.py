#!/usr/bin/env python3
"""Build caredesk-eb.zip for Elastic Beanstalk (works on Windows, macOS and Linux).

    python deploy/beanstalk/make_bundle.py

manage.py, Procfile, .ebextensions and .platform must sit at the TOP of the zip,
not inside a folder. Zipping the folder by hand usually gets this wrong.
"""
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "caredesk-eb.zip"
SKIP_DIRS = {"venv", ".venv", "__pycache__", "media", "staticfiles", ".git", "ec2", "docs"}
SKIP_FILES = {".env", "db.sqlite3", "caredesk-eb.zip", "caredesk-project.zip"}


def main():
    if OUT.exists():
        OUT.unlink()
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if name in SKIP_FILES or name.endswith((".pyc", ".zip")):
                    continue
                path = Path(folder) / name
                zf.write(path, path.relative_to(ROOT).as_posix())
                count += 1
    print(f"Created {OUT} with {count} files ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
