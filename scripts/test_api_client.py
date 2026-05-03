from server.app import create_app

app = create_app()

with app.test_client() as client:
    headers = {'X-API-Key': app.config.get('AGENT_API_KEY')}
    resp = client.get('/api/agent/releases', headers=headers)
    print('STATUS', resp.status_code)
    print(resp.get_data(as_text=True))
