import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

# 启用 Network 监听
ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
time.sleep(0.5)

# 点击页面上的【选择】或清空查看请求
ws.send(json.dumps({
    'id': 2,
    'method': 'Runtime.evaluate',
    'params': {
        'expression': """(() => {
            const btns = Array.from(document.querySelectorAll('button, .el-button'));
            const b = btns.find(x => x.innerText.trim() === '刷新');
            if (b) b.click();
            return { clicked: !!b };
        })()""",
        'returnByValue': True
    }
}))

urls = []
start = time.time()
while time.time() - start < 3:
    try:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get('method') == 'Network.requestWillBeSent':
            req = msg.get('params', {}).get('request', {})
            urls.append({'url': req.get('url'), 'method': req.get('method')})
    except Exception:
        break

print("Captured Network requests:", json.dumps(urls, ensure_ascii=False, indent=2))
ws.close()
