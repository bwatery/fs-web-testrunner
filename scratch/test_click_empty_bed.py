import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

js_click_empty_bed = """(() => {
    const cards = Array.from(document.querySelectorAll('.bed-card'));
    const emptyBed = cards.find(c => c.innerText.includes('401-2床') || c.innerText.includes('空床'));
    if (!emptyBed) return { err: 'no empty bed found' };
    
    emptyBed.click();
    emptyBed.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    return { clicked: true, text: emptyBed.innerText };
})()"""

print("Click empty bed:", eval_js(js_click_empty_bed))
time.sleep(2.0)

# Check what dialog or drawer opened
js_dialog = """(() => {
    const dialogs = Array.from(document.querySelectorAll('.el-dialog, .el-drawer')).filter(d => d.offsetHeight > 0);
    return dialogs.map(d => ({
        tag: d.tagName,
        cls: d.className,
        title: d.querySelector('.el-dialog__title, .el-drawer__title')?.innerText,
        text: d.innerText.substring(0, 300)
    }));
})()"""

res_dialog = eval_js(js_dialog)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\empty_bed_dialog.json', 'w', encoding='utf-8') as f:
    json.dump(res_dialog, f, ensure_ascii=False, indent=2)
print("Dialog opened count:", len(res_dialog) if isinstance(res_dialog, list) else 0)
ws.close()
