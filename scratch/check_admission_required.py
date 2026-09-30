import requests, json, websocket, time, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

v = LoginValidator()
v.switch_identity_in_browser(34, 2, "#/inpatient/registration/inpatientmodification")
time.sleep(2.0)

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

eval_js("window.location.hash = '#/inpatient/registration/inpatientmodification';")
time.sleep(2.0)

required_fields = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-form-item.is-required, .el-form-item'));
    return items.map(item => {
        const label = item.querySelector('.el-form-item__label') ? item.querySelector('.el-form-item__label').innerText.trim() : '';
        const isRequired = item.classList.contains('is-required') || (label && label.startsWith('*'));
        const input = item.querySelector('input');
        const select = item.querySelector('.el-select');
        return {
            label: label.replace('*', '').trim(),
            isRequired,
            hasInput: !!input,
            hasSelect: !!select,
            placeholder: input ? input.placeholder : '',
            value: input ? input.value : ''
        };
    }).filter(x => x.label);
})()""")

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\admission_required_fields.json", "w", encoding="utf-8") as f:
    json.dump(required_fields, f, ensure_ascii=False, indent=2)

print("Total form fields:", len(required_fields))
print("Required fields:")
for f in required_fields:
    if f.get('isRequired'):
        print(f"  * {f.get('label')} (Select: {f.get('hasSelect')}, Input: {f.get('hasInput')})")

ws.close()
