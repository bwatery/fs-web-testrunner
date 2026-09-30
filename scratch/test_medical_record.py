import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

print("Navigating to #/inpatient/doctor/medicalRecord...")
eval_js("window.location.hash = '#/inpatient/doctor/medicalRecord'")
time.sleep(3.0)

js = """(() => {
    return {
        url: window.location.href,
        title: document.title,
        text: document.body.innerText.substring(0, 500).replace(/\\s+/g, ' ')
    };
})()"""
print(eval_js(js))

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\medical_record_page.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved:", path)

ws.close()
