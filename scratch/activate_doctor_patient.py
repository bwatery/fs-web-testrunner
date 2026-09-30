import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# Double click 陈新强 row
js_dblclick = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row'));
    const target = rows.find(r => r.innerText.includes('陈新强') || r.innerText.includes('012328'));
    if (!target) return { err: 'row not found' };
    
    // click then dblclick
    target.click();
    target.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
    return { ok: true, text: target.innerText.replace(/\\s+/g, ' ').trim() };
})()"""

print("Dblclick result:", eval_js(js_dblclick))
time.sleep(2.5)

# Check patient header banner
js_header = """(() => {
    const header = document.querySelector('.patient-header, .patient-info, .head, .header') || document.body;
    const bannerTexts = Array.from(document.querySelectorAll('span, div')).filter(el => {
        const t = el.innerText?.trim();
        return t && (t.includes('陈新强') || t.includes('012328') || t.includes('401-2'));
    }).map(e => e.innerText.trim());
    
    // Check available buttons on the right panel
    const btns = Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item')).map(t => t.innerText.trim());
    return {
        matchedTexts: bannerTexts.slice(0, 10),
        btns: btns.slice(0, 15),
        tabs
    };
})()"""

res_head = eval_js(js_header)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\doctor_patient_activated.json', 'w', encoding='utf-8') as f:
    json.dump(res_head, f, ensure_ascii=False, indent=2)
print("Patient activated:", res_head.get('matchedTexts')[:3])

# Capture screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_doctor_activated.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Saved screenshot:", path)
ws.close()
