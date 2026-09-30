import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 检查当前页面的 Vue 实例或注册方法
res = eval_js("""(() => {
    const appEl = document.querySelector('#app');
    if (!appEl || !appEl.__vue_app__) return { err: 'no vue app' };
    const globalProps = appEl.__vue_app__.config.globalProperties;
    return {
        hasAxios: !!globalProps.$http || !!globalProps.$axios || !!window.axios,
        routerRoutesCount: globalProps.$router ? globalProps.$router.getRoutes().length : 0
    };
})()""")
print("Vue check:", res)
ws.close()
