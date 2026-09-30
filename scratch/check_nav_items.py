import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

menus = eval_js("""(() => {
    // 触发顶部导航项悬浮/点击
    const titles = Array.from(document.querySelectorAll('.el-sub-menu__title, .el-menu-item, span'));
    const items = titles.map(t => t.innerText && t.innerText.trim()).filter(Boolean);
    return Array.from(new Set(items)).filter(t => t.length < 20);
})()""")

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\top_menus.json", "w", encoding="utf-8") as f:
    json.dump(menus, f, ensure_ascii=False, indent=2)

print("Menus dumped!")
ws.close()
