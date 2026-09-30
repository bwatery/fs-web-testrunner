import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const items = Array.from(document.querySelectorAll('.el-menu-item'));
    const target = items.find(i => i.innerText && i.innerText.trim() === '住院工作站');
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim(), class: target.className };
    }
    return { clicked: false };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print('Clicked 住院工作站:', res)
time.sleep(2)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': '({ href: window.location.href, title: document.title, text: document.body.innerText.slice(0, 400) })', 'returnByValue': True}}))
raw2 = ws.recv()
res2 = json.loads(raw2).get('result', {}).get('result', {}).get('value', {})
print('Result page:', res2)

ws.send(json.dumps({'id': 3, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw_shot = ws.recv()
import base64
img_data = base64.b64decode(json.loads(raw_shot)['result']['data'])
open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\after_click_workstation.png', 'wb').write(img_data)
print('Screenshot saved!')
ws.close()
