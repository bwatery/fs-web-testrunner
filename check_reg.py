import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')
tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': "window.location.href = 'http://192.168.1.198:8088/#/inpatient/registration/medicalInsuranceRegistration';", 'returnByValue': True}}))
ws.recv()
time.sleep(2)

check_js = """(() => {
    return {
        title: document.title,
        hash: window.location.hash,
        is404: window.location.hash.includes('/404'),
        inputsCount: document.querySelectorAll('input').length,
        buttons: Array.from(document.querySelectorAll('.el-button')).map(b => b.innerText.trim()).filter(Boolean).slice(0, 10),
        snippet: document.body ? document.body.innerText.slice(0, 300).replace(/\\n+/g, ' ') : ''
    };
})()"""
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': check_js, 'returnByValue': True}}))
print(json.dumps(json.loads(ws.recv())['result']['result']['value'], ensure_ascii=False, indent=2))
ws.close()
