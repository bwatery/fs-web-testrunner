import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // Find the router-view or main content
    const main = document.querySelector('.vab-main') || document.querySelector('.vab-app-main') || document.querySelector('main');
    if (!main) return { err: 'no main found' };
    
    // Check all visible text
    const divs = Array.from(main.querySelectorAll('*')).map(e => ({
        tag: e.tagName,
        class: e.className,
        style: e.getAttribute('style') || '',
        text: e.innerText ? e.innerText.slice(0, 100) : ''
    }));

    return {
        mainTag: main.tagName,
        mainClass: main.className,
        childrenCount: main.children.length,
        items: divs.slice(0, 20)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
