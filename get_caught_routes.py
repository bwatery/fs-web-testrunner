import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': "localStorage.getItem('caughtRoutes')", 'returnByValue': True}}))
raw = ws.recv()
val = json.loads(raw).get('result', {}).get('result', {}).get('value', '')
try:
    print(json.dumps(json.loads(val), ensure_ascii=False, indent=2))
except Exception as e:
    print(val)
ws.close()
