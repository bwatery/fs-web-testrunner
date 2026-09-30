import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    const wrappers = Array.from(document.querySelectorAll('.el-select__wrapper, .el-select'));
    if (wrappers.length > 0) {
        wrappers[0].click();
        return { clicked: true, count: wrappers.length };
    }
    return { clicked: false };
})()""")
print("Click wrapper:", res)
time.sleep(1.0)

opts = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-select-dropdown__item, .el-popper'));
    return items.map(i => i.innerText.trim()).filter(Boolean);
})()""")
print("Options:", opts)
ws.close()
