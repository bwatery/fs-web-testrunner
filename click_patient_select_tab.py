import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .vab-tabs__item, [class*="tab"]'));
    const target = tabs.find(t => t.innerText && t.innerText.includes('患者选择'));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false, availableTabs: tabs.map(t => t.innerText.trim()) };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value', {})
print('Clicked 患者选择 tab:', res)
time.sleep(2)

ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {'expression': '({ href: window.location.href, text: document.body.innerText.slice(0, 500) })', 'returnByValue': True}}))
raw2 = ws.recv()
res2 = json.loads(raw2).get('result', {}).get('result', {}).get('value', {})
print('Result page:', res2)

ws.send(json.dumps({'id': 3, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw_shot = ws.recv()
img_data = base64.b64decode(json.loads(raw_shot)['result']['data'])
open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\patient_select_tab.png', 'wb').write(img_data)
print('Screenshot saved!')
ws.close()
