import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Click 陈新强 patient card on the left
js_click_patient = """(() => {
    const items = Array.from(document.querySelectorAll('*')).filter(el => {
        return el.children.length === 0 && el.innerText && el.innerText.trim() === '陈新强';
    });
    if (items.length === 0) return { err: '陈新强 not found' };
    const target = items[0].closest('.patient-item, .item, .patient-card, li, tr, .el-card') || items[0];
    target.click();
    return { clicked: true, tag: target.tagName, text: target.innerText.replace(/\\s+/g, ' ').trim() };
})()"""

print("Click patient:", eval_js(js_click_patient))
time.sleep(2.0)

# 2. Look for 医嘱 tab or button and click it
js_click_order = """(() => {
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .menu-item, span, div, a')).filter(el => {
        const t = el.innerText?.trim();
        return t === '医嘱' || t === '医嘱录入' || t === '医嘱开立';
    });
    if (tabs.length === 0) return { err: '医嘱 tab not found', available: Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim()) };
    const orderTab = tabs[0];
    orderTab.click();
    return { clicked: true, text: orderTab.innerText.trim() };
})()"""

print("Click 医嘱:", eval_js(js_click_order))
time.sleep(2.5)

# 3. Inspect what is rendered in the order workspace
js_inspect_order = """(() => {
    const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim());
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({ placeholder: i.placeholder, val: i.value }));
    const tables = Array.from(document.querySelectorAll('.vxe-table, .el-table')).map(t => t.className);
    return {
        url: window.location.href,
        btns: btns.slice(0, 20),
        tabs,
        tablesCount: tables.length
    };
})()"""

res_order = eval_js(js_inspect_order)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\order_workspace_info.json', 'w', encoding='utf-8') as f:
    json.dump(res_order, f, ensure_ascii=False, indent=2)
print("Order workspace info:", json.dumps(res_order, ensure_ascii=False, indent=2))

# 4. Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_order_workspace.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved to:", path)

ws.close()
