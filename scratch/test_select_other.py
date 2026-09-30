import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 查找证件类型并选择 "其他"
res = eval_js("""(() => {
    // 找到包含 "证件类型" 的表单项
    const items = Array.from(document.querySelectorAll('.el-form-item'));
    const idItem = items.find(i => i.innerText && i.innerText.includes('证件类型'));
    if (!idItem) return { success: false, err: '未找到证件类型项' };

    const select = idItem.querySelector('.el-select__wrapper') || idItem.querySelector('.el-select');
    if (select) {
        select.click();
        return { clicked: true, item: idItem.innerText.split('\\n')[0] };
    }
    return { success: false, err: '未找到 select 元素' };
})()""")
print("Click 证件类型 select:", res)
time.sleep(1.0)

# 查看并点击 "其他" 选项
opt_res = eval_js("""(() => {
    const options = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
    const list = options.map(o => o.innerText.trim()).filter(Boolean);
    const otherOpt = options.find(o => o.innerText.trim() === '其他' || o.innerText.includes('其他'));
    if (otherOpt) {
        otherOpt.click();
        return { success: true, chosen: otherOpt.innerText.trim(), list };
    }
    return { success: false, list };
})()""")
print("Select '其他':", opt_res)
time.sleep(1.0)

# 抓图查看
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\test_select_id_type_other.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)

ws.close()
