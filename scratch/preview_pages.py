import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

def capture(name):
    ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
    raw = ws.recv()
    b64 = json.loads(raw).get('result', {}).get('data', '')
    path = rf"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\{name}.png"
    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64))
    print("Captured:", path)
    return path

# 1. 查看出院结算
eval_js("window.location.hash = '#/inpatient/finance/leavehospitalcalculate';")
time.sleep(2.0)
capture("preview_leavehospitalcalculate")

# 2. 查看住院信息修改 / 住院登记
eval_js("window.location.hash = '#/inpatient/registration/inpatientmodification';")
time.sleep(2.0)
capture("preview_inpatientmodification")

# 3. 查看预交金收费
eval_js("window.location.hash = '#/inpatient/finance/prepaycharge';")
time.sleep(2.0)
capture("preview_prepaycharge")

ws.close()
