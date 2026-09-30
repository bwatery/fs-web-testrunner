import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    // Check routes from Vue router
    let routes = [];
    const appEl = document.querySelector('#app');
    if (appEl && appEl.__vue_app__) {
        const router = appEl.__vue_app__.config.globalProperties.$router;
        if (router) {
            routes = router.getRoutes().map(r => ({ path: r.path, name: r.name, title: r.meta && r.meta.title }));
        }
    }
    const menus = Array.from(document.querySelectorAll('.el-menu-item, .el-submenu__title, .vab-side-bar-item, .el-submenu, a'))
         .map(e => ({ text: e.innerText.trim(), href: e.getAttribute('href') || e.getAttribute('index') || '' }))
         .filter(x => x.text && x.text.length < 25);
    return { routes, menus, url: window.location.href };
})()""")

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\menus_dump.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)

print("Dumped successfully to menus_dump.json")
ws.close()
