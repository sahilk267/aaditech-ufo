#!/usr/bin/env python3
import sys
from pathlib import Path

try:
    import requests
except Exception:
    print('requests library not installed; install with: pip install requests')
    raise

def main():
    if len(sys.argv) < 3:
        print('Usage: local_publish.py <path-to-exe> <version> [tenant] [url]')
        return 2

    exe_path = Path(sys.argv[1])
    version = sys.argv[2]
    tenant = sys.argv[3] if len(sys.argv) > 3 else ''
    base = sys.argv[4] if len(sys.argv) > 4 else 'http://127.0.0.1:5001'

    if not exe_path.exists():
        print('EXE not found:', exe_path)
        return 3

    url = f"{base.rstrip('/')}/api/agent/releases/upload"
    headers = {}
    if tenant:
        headers['X-Tenant-Slug'] = tenant

    with exe_path.open('rb') as fh:
        files = {'release_file': (exe_path.name, fh, 'application/octet-stream')}
        data = {'version': version}
        print('POST', url, 'tenant=', tenant)
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        print('STATUS', resp.status_code)
        print(resp.text)
        return 0 if resp.status_code in (200,201) else 4

if __name__ == '__main__':
    raise SystemExit(main())
