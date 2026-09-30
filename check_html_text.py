import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const text = document.body.innerText;
    return {
        hasOuwei: text.includes('欧伟英'),
        has40110: text.includes('401-10'),
        hasWenshu: text.includes('文书类型'),
        hasBingli: text.includes('病案首页'),
        hasYizhu: text.includes('医嘱查看'),
        visibleTextSample: text.slice(0, 500)
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print(json.dumps(res, ensure_ascii=False, indent=2))
ws.close()
