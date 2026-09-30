import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // 1. Inspect window router or pinia/vuex store
    let routes = [];
    try {
        const app = document.querySelector('#app').__vue_app__;
        if (app && app.config && app.config.globalProperties && app.config.globalProperties.$router) {
            routes = app.config.globalProperties.$router.getRoutes().map(r => ({
                path: r.path,
                name: r.name,
                meta: r.meta ? r.meta.title : ''
            }));
        }
    } catch(e) {}

    // 2. Also search for keywords in loaded scripts
    return {
        routesCount: routes.length,
        inpatientRoutes: routes.filter(r => r.path && r.path.includes('inpatient'))
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
