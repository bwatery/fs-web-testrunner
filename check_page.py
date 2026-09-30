import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.body.innerText', 'returnByValue': True}}))
print('Body:', repr(json.loads(ws.recv())['result']['result']['value']))

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': 'sessionStorage.getItem("shop-vite-token") || localStorage.getItem("token")', 'returnByValue': True}}))
print('Token:', json.loads(ws.recv())['result']['result'])

ws.close()
