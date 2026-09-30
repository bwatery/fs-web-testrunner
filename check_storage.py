import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    return {
        sessionStorage: { ...sessionStorage },
        localStorage: { ...localStorage }
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
res = json.loads(ws.recv())['result']['result']['value']
print("sessionStorage keys:", list(res['sessionStorage'].keys()))
print("localStorage keys:", list(res['localStorage'].keys()))
if 'token' in res['sessionStorage']:
    print("sessionStorage token:", res['sessionStorage']['token'][:30])
if 'shop-vite-token' in res['sessionStorage']:
    print("sessionStorage shop-vite-token:", res['sessionStorage']['shop-vite-token'][:30])
if 'token' in res['localStorage']:
    print("localStorage token:", res['localStorage']['token'][:30])
