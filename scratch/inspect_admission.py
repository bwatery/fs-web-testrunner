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
v.switch_identity_in_browser(34, 2, "#/inpatient/registration")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/registration';")
time.sleep(2.0)

# 抓取页面表单字段
form_info = eval_js("""(() => {
    const inputs = Array.from(document.querySelectorAll('input, select, textarea')).map(i => ({
        placeholder: i.placeholder,
        name: i.name,
        type: i.type,
        label: (i.closest('.el-form-item') && i.closest('.el-form-item').innerText.split('\\n')[0]) || ''
    }));
    const buttons = Array.from(document.querySelectorAll('button, .el-button')).map(b => b.innerText.trim()).filter(Boolean);
    return {
        inputs: inputs.filter(x => x.label || x.placeholder),
        buttons: Array.from(new Set(buttons))
    };
})()""")

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\admission_form.json", "w", encoding="utf-8") as f:
    json.dump(form_info, f, ensure_ascii=False, indent=2)

print("Saved admission form info!")

# 截图
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\full_cycle_admission_reg.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
