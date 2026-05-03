"""Minimal test agent executable used for CI test builds.

This is intentionally tiny to avoid PyInstaller analysis failures when
building the full agent in limited environments. It reads `agent/version.py`
for a version string and prints a simple heartbeat message.
"""
from __future__ import annotations

import time
from pathlib import Path

VERSION_FILE = Path(__file__).parent / 'version.py'

def get_version() -> str:
    try:
        namespace = {}
        exec(VERSION_FILE.read_text(encoding='utf-8'), namespace)
        return str(namespace.get('AGENT_VERSION', '0.0.0'))
    except Exception:
        return '0.0.0'

def main() -> None:
    ver = get_version()
    print(f"aaditech-agent (minimal) version={ver}")
    # Keep process alive briefly so smoke tests can observe it
    time.sleep(2)

if __name__ == '__main__':
    main()
