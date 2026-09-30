import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 检查当前页面的控制台错误与网络状态
res = eval_js("""(() => {
    return {
        href: window.location.href,
        title: document.title,
        tokenExists: !!(sessionStorage.getItem('shop-vite-token') || localStorage.getItem('token')),
        roleDept: localStorage.getItem('userRoleDeptCache'),
        performance: {
            memory: window.performance && window.performance.memory ? {
                usedJSHeapSizeMB: Math.round(window.performance.memory.usedJSHeapSize / 1024 / 1024),
                totalJSHeapSizeMB: Math.round(window.performance.memory.totalJSHeapSize / 1024 / 1024)
            } : null
        }
    };
})()""")

print("Current System State:")
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
