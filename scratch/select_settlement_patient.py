import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 在弹窗左侧点击内一科
click_dept = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-dialog .el-tree-node, .el-dialog div, .el-dialog span'));
    const n1 = items.find(i => i.innerText && i.innerText.trim() === '内一科');
    if (n1) {
        n1.click();
        return { clicked: true, text: n1.innerText.trim() };
    }
    return { clicked: false };
})()""")
print("Click 内一科 in dialog:", click_dept)
time.sleep(1.5)

# 点击表格中的患者（如欧伟英）
click_pat = eval_js("""(() => {
    const rows = Array.from(document.querySelectorAll('.el-dialog tr, .el-dialog .el-table__row'));
    const targetRow = rows.find(r => r.innerText && (r.innerText.includes('欧伟英') || r.innerText.includes('测试wt')));
    if (targetRow) {
        targetRow.click();
        const dbl = new MouseEvent('dblclick', { bubbles: true, cancelable: true });
        targetRow.dispatchEvent(dbl);
        return { clicked: true, text: targetRow.innerText.trim().replace(/\\s+/g, ' ') };
    }
    return { clicked: false, availableRows: rows.slice(0, 5).map(r => r.innerText.trim().replace(/\\s+/g, ' ')) };
})()""")
print("Click patient row:", click_pat)
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\settlement_patient_selected.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
