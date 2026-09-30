import requests, json, websocket, time, sys

sys.stdout.reconfigure(encoding='utf-8')

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

# Inspect the top search bar and inputs on leavehospitalcalculate
inspect_js = """(() => {
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
        placeholder: i.placeholder,
        value: i.value,
        className: i.className,
        parentText: i.parentElement ? i.parentElement.innerText.trim() : ''
    }));
    const forms = Array.from(document.querySelectorAll('.el-form-item')).map(f => ({
        label: f.querySelector('.el-form-item__label') ? f.querySelector('.el-form-item__label').innerText : '',
        text: f.innerText.replace(/\\n/g, ' ')
    }));
    return {
        inputs: inputs,
        forms: forms
    };
})()"""
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': inspect_js, 'returnByValue': True}}))
res = json.loads(ws.recv())['result']['result']['value']
print("Inputs and forms:")
print(json.dumps(res, ensure_ascii=False, indent=2))

ws.close()
