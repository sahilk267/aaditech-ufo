import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server.tenant_context as tenant_context
import server.auth as auth

tenant_context.init_tenant_context = lambda app: None
auth.require_api_key = lambda f: f
auth.require_api_key_or_permission = lambda *a, **k: (lambda f: f)
auth.require_web_permission = lambda *a, **k: (lambda f: f)

from server.app import create_app

app = create_app()
with app.test_client() as c:
    r = c.get('/api/agent/releases')
    print('STATUS', r.status_code)
    print(r.get_data(as_text=True))
