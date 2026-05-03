"""Run the Flask app for local testing with DB/auth disabled.

This script monkeypatches tenant/context and auth decorators to avoid
requiring a real Postgres/Redis instance or API keys. It is for local
verification only and MUST NOT be used in production.
"""
import sys
from pathlib import Path

# Ensure repo root on path so `server` package imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Monkeypatch tenant DB lookups and auth decorators before app import
import server.tenant_context as tenant_context
import server.auth as auth

# No-op tenant context initializer
tenant_context.init_tenant_context = lambda app: None

def _noop_decorator_factory(*args, **kwargs):
    def decorator(f):
        return f
    return decorator

# Replace auth decorators with no-op versions for local testing
auth.require_api_key = lambda f: f
auth.require_api_key_or_permission = lambda *args, **kwargs: _noop_decorator_factory
auth.require_web_permission = lambda *args, **kwargs: _noop_decorator_factory

from server.app import create_app
from server.services.agent_release_service import AgentReleaseService
from flask import send_file, abort, current_app

app = create_app()

# Add an auth-free local download route for quick verification
@app.route('/local/agent/releases/download/<path:filename>', methods=['GET'])
def local_download(filename):
    file_path = AgentReleaseService.resolve_download_path(filename, current_app.config, current_app.instance_path)
    if file_path is None:
        abort(404)
    return send_file(file_path, as_attachment=True, download_name=file_path.name)

if __name__ == '__main__':
    print('Starting local server (auth/tenant disabled) on http://127.0.0.1:5001')
    app.run(host='127.0.0.1', port=5001, debug=False)
