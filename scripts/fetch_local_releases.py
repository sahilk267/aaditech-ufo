import urllib.request

url = 'http://127.0.0.1:5001/api/agent/releases'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        print('STATUS', r.status)
        print(r.read().decode('utf-8'))
except Exception as e:
    print('ERROR', e)
