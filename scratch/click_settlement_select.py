import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 确保在出院结算页面
eval_js("window.location.hash = '#/inpatient/finance/leavehospitalcalculate';")
time.sleep(1.5)

# 点击【选择】按钮
res = eval_js("""(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const selectBtn = btns.find(b => b.innerText.trim() === '选择');
    if (selectBtn) {
        selectBtn.click();
        return { clicked: true, text: selectBtn.innerText.trim() };
    }
    return { clicked: false, allBtns: btns.map(b => b.innerText.trim()) };
})()""")
print("Click select button:", res)
time.sleep(2.0)

# 查看弹出的弹窗与候选患者表格
dialog_info = eval_js("""(() => {
    const dialogs = Array.from(document.querySelectorAll('.el-dialog, .vxe-modal--box, .el-overlay'));
    const rows = Array.from(document.querySelectorAll('.el-dialog tr, .vxe-modal--box tr, .el-table__body-wrapper tr'));
    return {
        dialogCount: dialogs.length,
        rows: rows.map(r => r.innerText.trim().replace(/\\s+/g, ' ')).filter(Boolean).slice(0, 10)
    };
})()""")
print("Dialog info:", json.dumps(dialog_info, ensure_ascii=False, indent=2))

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\leavehospitalcalculate_dialog_opened.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
