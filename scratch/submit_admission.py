import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Close any open poppers
eval_js("document.body.click()")
time.sleep(0.5)

# Click 入院登记
js_submit = """(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const regBtn = btns.find(b => b.innerText.trim() === '入院登记' || b.innerText.includes('入院登记'));
    if (!regBtn) return { error: 'btn not found', available: btns.map(b => b.innerText.trim()) };
    
    regBtn.click();
    return { ok: true, clicked: regBtn.innerText.trim() };
})()"""

res_sub = eval_js(js_submit)
print("Submit clicked:", res_sub)
time.sleep(2.0)

# Check message toast or dialog
js_check = """(() => {
    const msgs = Array.from(document.querySelectorAll('.el-message, .el-message-box, .el-notification')).map(m => m.innerText.trim());
    // Also check if 住院号 was generated in form
    const items = Array.from(document.querySelectorAll('.el-form-item'));
    const zyItem = items.find(i => i.querySelector('.el-form-item__label')?.innerText?.includes('住院号'));
    const zyNo = zyItem?.querySelector('input')?.value;
    return {
        msgs,
        zyNo,
        url: window.location.href
    };
})()"""

res_after = eval_js(js_check)
print("After submit:", json.dumps(res_after, ensure_ascii=False, indent=2))

# Capture screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_admission_result.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved to:", path)

ws.close()
