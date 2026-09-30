import requests, json, websocket

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

js = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    if (!d) return 'no dialog';
    return {
        inputs: Array.from(d.querySelectorAll('input')).map(i => ({
            name: i.name,
            placeholder: i.placeholder,
            value: i.value,
            cls: i.className,
            parentText: i.parentElement?.parentElement?.innerText?.substring(0, 50)
        })),
        buttons: Array.from(d.querySelectorAll('button')).map(b => b.innerText.trim())
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}))
res = json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\dialog_structure.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("Saved dialog_structure.json")
ws.close()
