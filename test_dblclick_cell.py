import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // Find the cell with 欧伟英
    const allCells = Array.from(document.querySelectorAll('.vxe-body--column, .vxe-cell, .vxe-cell--wrapper'));
    const target = allCells.find(c => c.innerText && c.innerText.includes('欧伟英'));
    if (!target) return { found: false };

    // Trigger dblclick
    const evt = new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window });
    target.dispatchEvent(evt);
    target.click();

    return {
        found: true,
        tag: target.tagName,
        class: target.className,
        text: target.innerText.trim()
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
print('Dblclick result:', json.loads(raw).get('result', {}).get('result', {}).get('value'))
time.sleep(2)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': '({ href: window.location.href, text: document.body.innerText.slice(0, 300) })', 'returnByValue': True}}))
raw2 = ws.recv()
print('After dblclick:', json.loads(raw2).get('result', {}).get('result', {}).get('value'))

ws.close()
