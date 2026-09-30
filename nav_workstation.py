import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': 'http://192.168.1.198:8088/#/inpatient/doctor/workstation'}}))
ws.recv()
time.sleep(2)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': 'document.querySelector(".vab-app-main").innerText.slice(0, 500)', 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value')
print('Workstation text:', res)

ws.send(json.dumps({'id': 3, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw_shot = ws.recv()
img_data = base64.b64decode(json.loads(raw_shot)['result']['data'])
open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\workstation_view_test.png', 'wb').write(img_data)
print('Saved workstation view screenshot!')
ws.close()
