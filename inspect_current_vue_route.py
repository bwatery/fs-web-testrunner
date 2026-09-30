import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // Navigate router to /inpatient/doctor/medicalRecord with router.push
    const app = document.querySelector('#app').__vue_app__;
    const router = app.config.globalProperties.$router;
    
    // Check current route and matched components
    const current = router.currentRoute.value;
    
    return {
        currentPath: current.path,
        currentQuery: current.query,
        currentParams: current.params,
        matched: current.matched.map(m => m.path)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
