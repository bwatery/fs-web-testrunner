import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

routes = eval_js("""(() => {
    let list = [];
    const appEl = document.querySelector('#app');
    if (appEl && appEl.__vue_app__) {
        const router = appEl.__vue_app__.config.globalProperties.$router;
        if (router) {
            list = router.getRoutes().map(r => ({
                path: r.path,
                name: r.name,
                title: (r.meta && r.meta.title) || ''
            }));
        }
    }
    return list;
})()""")

keywords = ["入院", "出院", "登记", "结算", "退", "药", "预交", "费用"]
filtered = [r for r in routes if any(k in r.get('title', '') or k in r.get('path', '') for k in keywords)]

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\lifecycle_routes.json", "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)

print(f"Total matching routes: {len(filtered)}")
for r in filtered:
    print(f"[{r.get('title')}] -> {r.get('path')}")

ws.close()
