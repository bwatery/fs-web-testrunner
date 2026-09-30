import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const all = Array.from(document.querySelectorAll('*'));
    const classes = new Set();
    all.forEach(el => {
        if (el.className && typeof el.className === 'string') {
            el.className.split(' ').forEach(c => {
                if (c.includes('patient') || c.includes('drawer') || c.includes('doctor') || c.includes('workstation') || c.includes('collapse') || c.includes('sidebar')) {
                    classes.add(c);
                }
            });
        }
    });

    const buttons = Array.from(document.querySelectorAll('button, .el-button, [class*="btn"]')).map(b => b.innerText ? b.innerText.trim().replace(/\\n+/g, ' ') : '');
    
    // Check if there is an iframe or router-view
    const routerViews = Array.from(document.querySelectorAll('router-view, [class*="view"], [class*="container"]')).map(r => r.className);

    return {
        url: window.location.href,
        matchingClasses: Array.from(classes).slice(0, 30),
        buttons: buttons.filter(b => b.length > 0).slice(0, 20),
        bodyHtmlSnippet: document.body.innerHTML.slice(0, 1000)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
