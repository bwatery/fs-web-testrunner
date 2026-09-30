import requests, json, websocket, base64, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': 'http://127.0.0.1:8989'}}))
ws.recv()
time.sleep(1.5)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': 'switchTab("tab-cases"); expandAllCategories();'}}))
ws.recv()
time.sleep(1.2)

ws.send(json.dumps({'id': 3, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
res = json.loads(ws.recv())
img_data = base64.b64decode(res['result']['data'])

target_path = r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\tab_cases_canonical_view.png'
with open(target_path, 'wb') as f:
    f.write(img_data)

print("Saved to:", target_path)
ws.close()
