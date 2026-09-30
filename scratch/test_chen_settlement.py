import requests, json, websocket, time, sys, base64
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator

v = LoginValidator()
print("Switching identity to Cashier (Role 34, Dept 2 住院收费处)...")
v.switch_identity_in_browser(34, 2, "#/inpatient/finance/leavehospitalcalculate")
time.sleep(3.5)

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Click 选择 button to open search dialog
js_open_dialog = """(() => {
    const selBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === '选择');
    if (!selBtn) return { err: 'btn not found' };
    selBtn.click();
    return { clicked: true };
})()"""
print("Click 选择:", eval_js(js_open_dialog))
time.sleep(2.0)

# 2. Type 012328 or 陈新强 into 请输入
js_search_pat = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    const input = Array.from(d.querySelectorAll('input')).find(i => i.placeholder === '请输入');
    if (!input) return { err: 'no search input' };
    
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, '陈新强');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
    
    const icon = d.querySelector('.el-input__suffix, .el-input__icon, .el-icon-search');
    if (icon) icon.click();
    return { ok: true, val: input.value };
})()"""
print("Search patient:", eval_js(js_search_pat))
time.sleep(2.0)

# 3. Double-click patient row in dialog
js_pick_pat = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    const rows = Array.from(d.querySelectorAll('.vxe-body--row, tr.el-table__row'));
    const target = rows.find(r => r.innerText.includes('陈新强') || r.innerText.includes('012328') || r.innerText.includes('12328'));
    if (!target) return { err: 'row not found', available: rows.map(r => r.innerText.trim()) };
    
    target.click();
    target.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    return { ok: true, text: target.innerText.replace(/\\s+/g, ' ').trim() };
})()"""
print("Pick patient row:", eval_js(js_pick_pat))
time.sleep(2.5)

# 4. Check settlement form values
js_check_settle = """(() => {
    const inputs = Array.from(document.querySelectorAll('.el-form-item, .item, .info-item')).map(item => ({
        text: item.innerText.replace(/\\s+/g, ' ').trim()
    })).filter(i => i.text.length > 0 && i.text.length < 150);
    
    const btns = Array.from(document.querySelectorAll('button')).map(b => ({
        text: b.innerText.trim(),
        disabled: b.disabled || b.classList.contains('is-disabled')
    })).filter(b => b.text);
    
    return {
        inputsSample: inputs.slice(0, 15),
        btns
    };
})()"""

res_settle = eval_js(js_check_settle)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\settlement_chen_result.json', 'w', encoding='utf-8') as f:
    json.dump(res_settle, f, ensure_ascii=False, indent=2)
print("Settlement check:", json.dumps(res_settle, ensure_ascii=False, indent=2))

# 5. Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_discharge_settlement.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
