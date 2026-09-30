import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_search = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    
    // Find the input with placeholder '请输入'
    const input = Array.from(d.querySelectorAll('input')).find(i => i.placeholder === '请输入');
    if (!input) return { err: 'input 请输入 not found' };
    
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, '陈新强');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
    
    // Look for search icon or button next to it
    const searchIcon = d.querySelector('.el-input__suffix, .el-icon-search, .el-input__icon');
    if (searchIcon) searchIcon.click();
    
    return { ok: true, setVal: input.value };
})()"""

print("Search triggered:", eval_js(js_search))
time.sleep(2.0)

# Check table rows in dialog
js_table = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    const rows = Array.from(d.querySelectorAll('.vxe-body--row, tr.el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim());
    return {
        count: rows.length,
        rows
    };
})()"""

res_table = eval_js(js_table)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\searched_patient_result.json', 'w', encoding='utf-8') as f:
    json.dump(res_table, f, ensure_ascii=False, indent=2)
print("Searched result count:", res_table.get('count'))

# Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\patient_search_exact_result.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved to:", path)
ws.close()
