import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

res = eval_js("""(() => {
    const leftPanel = document.querySelector('.vab-column-tabs') || document.body;
    const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
        placeholder: i.placeholder,
        value: i.value,
        className: i.className,
        parentClass: i.parentElement.className
    }));
    return inputs;
})()""")
import json
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
