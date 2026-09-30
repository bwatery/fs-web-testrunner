import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js = """(() => {
    const cards = Array.from(document.querySelectorAll('.bed-card')).map(c => ({
        text: c.innerText.replace(/\\s+/g, ' ').trim(),
        html: c.innerHTML.substring(0, 200)
    }));
    return {
        count: cards.length,
        cards: cards.slice(0, 10)
    };
})()"""

res = eval_js(js)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\empty_beds_result.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved empty_beds_result.json, count:", res.get('count'))
ws.close()
