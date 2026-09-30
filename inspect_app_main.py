import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const appMain = document.querySelector('.vab-app-main') || document.querySelector('[class*="app-main"]');
    return {
        hasAppMain: !!appMain,
        tag: appMain ? appMain.tagName : '',
        class: appMain ? appMain.className : '',
        childrenCount: appMain ? appMain.children.length : 0,
        text: appMain ? appMain.innerText.slice(0, 300) : '',
        innerSnippet: appMain ? appMain.innerHTML.slice(0, 500) : ''
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
