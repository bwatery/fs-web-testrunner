import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()

# 切到住院收费 (Role 34, Dept 2)
v.switch_identity_in_browser(34, 2, "#/inpatient/registration/inpatientmodification")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/registration/inpatientmodification';")
time.sleep(2.0)

# 探索入院登记表单的 DOM 结构与 Vue 数据绑定
form_structure = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-form-item')).map(item => {
        const label = item.querySelector('.el-form-item__label') ? item.querySelector('.el-form-item__label').innerText.trim() : '';
        const input = item.querySelector('input');
        return {
            label,
            placeholder: input ? input.placeholder : '',
            className: input ? input.className : '',
            hasSelect: !!item.querySelector('.el-select')
        };
    });
    const buttons = Array.from(document.querySelectorAll('button, .el-button')).map(b => b.innerText.trim()).filter(Boolean);
    return { items: items.filter(x => x.label), buttons };
})()""")

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\admission_details.json", "w", encoding="utf-8") as f:
    json.dump(form_structure, f, ensure_ascii=False, indent=2)

print("Admission Form Details:", json.dumps(form_structure, ensure_ascii=False, indent=2))
ws.close()
