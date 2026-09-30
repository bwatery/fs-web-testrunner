import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 找到欧伟英的行并双击
click_res = eval_js("""(() => {
    const rows = Array.from(document.querySelectorAll('.el-dialog tr, .el-dialog .el-table__row'));
    const ouRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
    if (!ouRow) return { success: false, reason: '未找到欧伟英行' };
    
    // 双击单元格与行
    const cell = ouRow.querySelector('td') || ouRow;
    const dbl = new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window });
    cell.dispatchEvent(dbl);
    ouRow.dispatchEvent(dbl);
    return { success: true, text: ouRow.innerText.trim().replace(/\\s+/g, ' ') };
})()""")
print("Double click Ou Weiying:", click_res)
time.sleep(2.5)

# 检查页面是否加载了欧伟英的结算数据
settle_data = eval_js("""(() => {
    const text = document.body ? document.body.innerText : '';
    const nameMatch = text.match(/欧伟英/);
    const moneyMatch = text.match(/总金额([0-9\\.]+)/);
    const prepayMatch = text.match(/预交金([0-9\\.]+)/);
    const selfMatch = text.match(/自付金额([0-9\\.]+)/);
    return {
        hasName: !!nameMatch,
        total: moneyMatch ? moneyMatch[1] : null,
        prepay: prepayMatch ? prepayMatch[1] : null,
        self: selfMatch ? selfMatch[1] : null
    };
})()""")
print("Settlement data on page:", settle_data)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\settlement_ouwei_loaded.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
