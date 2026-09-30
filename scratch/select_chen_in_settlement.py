import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Click 选择 button if dialog is not open
js_open = """(() => {
    let d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) {
        const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === '选择');
        if (btn) btn.click();
        return { opened: true };
    }
    return { alreadyOpen: true };
})()"""
print("Open dialog:", eval_js(js_open))
time.sleep(2.0)

# 2. Click 内一科 in the dialog left tree
js_click_dept = """(() => {
    const items = Array.from(document.querySelectorAll('.el-dialog .el-tree-node, .el-dialog span, .el-dialog div'));
    const n1 = items.find(i => i.innerText && i.innerText.trim() === '内一科');
    if (n1) {
        n1.click();
        return { clicked: true, text: n1.innerText.trim() };
    }
    return { clicked: false };
})()"""
print("Click 内一科 in dialog:", eval_js(js_click_dept))
time.sleep(2.0)

# 3. Check patient rows loaded in the dialog table
js_patients_in_dialog = """(() => {
    const rows = Array.from(document.querySelectorAll('.el-dialog .el-table__row, .el-dialog tr, .el-dialog .vxe-body--row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean);
    return {
        count: rows.length,
        rows
    };
})()"""

res_pats = eval_js(js_patients_in_dialog)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\settlement_dialog_patients.json', 'w', encoding='utf-8') as f:
    json.dump(res_pats, f, ensure_ascii=False, indent=2)
print("Patients in dialog:", res_pats.get('count'))

# 4. Double click 陈新强 row
js_dblclick_chen = """(() => {
    const rows = Array.from(document.querySelectorAll('.el-dialog .el-table__row, .el-dialog tr, .el-dialog .vxe-body--row'));
    const target = rows.find(r => r.innerText.includes('陈新强') || r.innerText.includes('012328') || r.innerText.includes('12328'));
    if (target) {
        target.click();
        target.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
        return { clicked: true, text: target.innerText.replace(/\\s+/g, ' ').trim() };
    }
    return { clicked: false, available: rows.map(r => r.innerText.replace(/\\s+/g, ' ').trim()) };
})()"""

print("Dblclick 陈新强:", eval_js(js_dblclick_chen))
time.sleep(2.5)

# 5. Check settlement interface loaded
js_settle_loaded = """(() => {
    const text = document.body.innerText.replace(/\\s+/g, ' ');
    const btns = Array.from(document.querySelectorAll('button')).map(b => ({ text: b.innerText.trim(), disabled: b.disabled }));
    return {
        bodySnippet: text.substring(0, 400),
        btns
    };
})()"""

print("Settlement interface loaded:", eval_js(js_settle_loaded))

# 6. Capture screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_settlement_active.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)

ws.close()
