import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=5)

expr = """(() => {
    // Find row containing 欧伟英
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr'));
    const ouRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
    if (!ouRow) return { found: false };

    // Try clicking
    ouRow.click();
    
    // Also try clicking cell with 欧伟英
    const cell = Array.from(ouRow.querySelectorAll('td, .vxe-cell')).find(c => c.innerText && c.innerText.includes('欧伟英'));
    if (cell) cell.click();

    return {
        found: true,
        text: ouRow.innerText.replace(/\\s+/g, ' ')
    };
})()"""

ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
raw = ws.recv()
res = json.loads(raw).get('result', {}).get('result', {}).get('value')
print('Click result:', res)
time.sleep(2)

ws.send(json.dumps({'id': 2, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw_shot = ws.recv()
img_data = base64.b64decode(json.loads(raw_shot)['result']['data'])
open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\after_click_ouwei_row.png', 'wb').write(img_data)
print('Saved screenshot!')
ws.close()
