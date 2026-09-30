import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()

# 1. 检查护士站 (Role 36, Dept 910131)
v.switch_identity_in_browser(36, 910131, "#/index")
time.sleep(2.0)
nurse_routes = eval_js("""(() => {
    let list = [];
    const appEl = document.querySelector('#app');
    if (appEl && appEl.__vue_app__) {
        const router = appEl.__vue_app__.config.globalProperties.$router;
        if (router) {
            list = router.getRoutes().map(r => ({ path: r.path, name: r.name, title: (r.meta && r.meta.title) || '' }));
        }
    }
    return list;
})()""")

# 2. 检查药房 (Role 37, Dept 910127)
v.switch_identity_in_browser(37, 910127, "#/index")
time.sleep(2.0)
pha_routes = eval_js("""(() => {
    let list = [];
    const appEl = document.querySelector('#app');
    if (appEl && appEl.__vue_app__) {
        const router = appEl.__vue_app__.config.globalProperties.$router;
        if (router) {
            list = router.getRoutes().map(r => ({ path: r.path, name: r.name, title: (r.meta && r.meta.title) || '' }));
        }
    }
    return list;
})()""")

all_info = {
    "nurse_routes": [r for r in nurse_routes if r.get('title') and not r.get('title').startswith('http')],
    "pha_routes": [r for r in pha_routes if r.get('title') and not r.get('title').startswith('http')]
}

with open(r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\nurse_pha_routes.json", "w", encoding="utf-8") as f:
    json.dump(all_info, f, ensure_ascii=False, indent=2)

print("Dumped nurse and pharmacy routes!")
ws.close()
