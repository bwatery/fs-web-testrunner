import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

eval_js("window.location.hash = '#/inpatient/pharmacy/inhospitalputmedicine';")
time.sleep(2)
print("Current hash:", eval_js("window.location.hash"))
text = eval_js("document.body.innerText")
print("Text length:", len(text))
print("Snippet:", text[:800])

ws.close()
