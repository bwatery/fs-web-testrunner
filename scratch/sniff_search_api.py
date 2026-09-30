import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

# Enable Network domain
ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
print("Network enabled:", ws.recv())

# Trigger search in the dialog
js_search = """(() => {
    const d = document.querySelector('.el-dialog:not([style*="display: none"])');
    const input = Array.from(d.querySelectorAll('input')).find(i => i.placeholder === '请输入');
    input.value = '陈新强';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    const searchBtn = d.querySelector('.el-input-group__append button');
    if (searchBtn) searchBtn.click();
    return 'clicked';
})()"""

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': js_search, 'returnByValue': True}}))

# Listen for network requests for 2 seconds
start_t = time.time()
reqs = []
while time.time() - start_t < 2.0:
    try:
        raw = ws.recv()
        msg = json.loads(raw)
        if msg.get('method') == 'Network.requestWillBeSent':
            req = msg['params']['request']
            url = req['url']
            if '192.168.1.198' in url or 'patient' in url or 'inpatient' in url:
                reqs.append({
                    'url': url,
                    'method': req['method'],
                    'postData': req.get('postData')
                })
    except Exception:
        break

with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\search_network_sniff.json', 'w', encoding='utf-8') as f:
    json.dump(reqs, f, ensure_ascii=False, indent=2)
print("Captured network requests count:", len(reqs))

ws.close()
