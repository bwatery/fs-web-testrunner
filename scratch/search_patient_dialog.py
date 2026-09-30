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
    
    const inputs = Array.from(d.querySelectorAll('input'));
    const btns = Array.from(d.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    
    // Type 陈新强 into the first input or name input
    const input = inputs[0];
    if (input) {
        input.value = '陈新强';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
    }
    
    // Look for search button inside dialog
    const searchBtn = Array.from(d.querySelectorAll('button')).find(b => b.innerText.includes('查') || b.innerText.includes('搜'));
    if (searchBtn) searchBtn.click();
    
    return {
        inputsCount: inputs.length,
        btns,
        searchClicked: !!searchBtn
    };
})()"""

print("Search in dialog:", eval_js(js_search))
time.sleep(2.0)

# Check rows now
js_rows = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return { err: 'no dialog' };
    const rows = Array.from(d.querySelectorAll('.vxe-body--row, tr.el-table__row')).map(r => r.innerText.replace(/\\s+/g, ' ').trim());
    return {
        count: rows.length,
        rows
    };
})()"""

res_rows = eval_js(js_rows)
print("Found rows:", res_rows)

# Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\patient_search_dialog.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)
ws.close()
