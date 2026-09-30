import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Close dropdowns
eval_js("document.body.click()")
time.sleep(0.5)

# Click 入院登记
js_click = """(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const regBtn = btns.find(b => b.innerText.trim() === '入院登记');
    if (!regBtn) return { err: 'btn not found' };
    regBtn.click();
    return { clicked: true };
})()"""

print("Click submit:", eval_js(js_click))
time.sleep(3.0)

# Check messages, popups, or zyNo
js_after = """(() => {
    const msgs = Array.from(document.querySelectorAll('.el-message, .el-message-box, .el-notification, .el-dialog')).filter(e => e.offsetHeight > 0).map(e => e.innerText.trim());
    const items = Array.from(document.querySelectorAll('.el-form-item'));
    const zyItem = items.find(i => i.querySelector('.el-form-item__label')?.innerText?.includes('住院号'));
    const zyNo = zyItem?.querySelector('input')?.value;
    const errors = Array.from(document.querySelectorAll('.el-form-item.is-error')).map(i => i.innerText.trim());
    return {
        msgs,
        zyNo,
        errors,
        url: window.location.href
    };
})()"""

res_after = eval_js(js_after)
print("After submit:", json.dumps(res_after, ensure_ascii=False, indent=2))

# Capture screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_admitted_success.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
