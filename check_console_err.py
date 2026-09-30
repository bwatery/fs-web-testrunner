import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

# Check console messages or window.__errors
expr = """(() => {
    // Check if there are error messages in DOM or console
    const alerts = Array.from(document.querySelectorAll('.el-alert, .el-message, [class*="error"], [class*="warn"]')).map(a => a.innerText);
    
    // Check vue app instance
    let vueInfo = {};
    try {
        const appEl = document.querySelector('#app');
        if (appEl && appEl.__vue_app__) {
            vueInfo.hasVue = true;
        }
    } catch(e) {
        vueInfo.err = String(e);
    }

    return {
        alerts: alerts,
        vueInfo: vueInfo,
        htmlLen: document.body.innerHTML.length
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
