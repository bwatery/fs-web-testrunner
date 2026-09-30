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
v.switch_identity_in_browser(34, 2, "#/inpatient/finance/leavehospitalcalculate")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/finance/leavehospitalcalculate';")
time.sleep(2.0)

# 在出院结算输入框填入住院号 000005 并回车
res = eval_js("""(() => {
    const input = document.querySelector('input');
    if (input) {
        input.value = '000005';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
        return { success: true, val: input.value };
    }
    return { success: false };
})()""")
print("Input res:", res)
time.sleep(2.5)

# 抓取页面文本
page_text = eval_js("document.body.innerText")
print("Text length:", len(page_text))
print("Snippet:", page_text[:800].replace('\n', ' '))

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\leavehospitalcalculate_search_result.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
