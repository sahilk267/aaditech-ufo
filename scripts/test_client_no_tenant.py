import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server.tenant_context as tc
tc.init_tenant_context = lambda app: None

from server.app import create_app

app = create_app()
with app.test_client() as c:
    headers = {'X-API-Key': app.config.get('AGENT_API_KEY')}
    r = c.get('/api/agent/releases', headers=headers)
    print('STATUS', r.status_code)
    print(r.get_data(as_text=True))
