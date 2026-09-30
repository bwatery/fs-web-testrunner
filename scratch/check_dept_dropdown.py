import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    const input = document.querySelector('input[placeholder*="科室"]');
    if (input) {
        input.click();
        input.focus();
        return { clicked: true, ph: input.placeholder };
    }
    return { clicked: false };
})()""")
print("Click input:", res)
time.sleep(1.0)

opts = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-select-dropdown__item, .el-cascader-node__label, li'));
    return items.map(i => i.innerText.trim()).filter(t => t.length > 0 && t.length < 20);
})()""")
print("Dropdown items:", opts)
ws.close()
