import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    return {
        sessionKeys: Object.keys(sessionStorage),
        localKeys: Object.keys(localStorage),
        sessionItems: Object.fromEntries(Object.keys(sessionStorage).map(k => [k, sessionStorage.getItem(k).slice(0, 100)])),
        localItems: Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k).slice(0, 100)]))
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
