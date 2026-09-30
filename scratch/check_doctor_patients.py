import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 1. Switch role to 35 (内一科住院医生)
js_switch_role = """(() => {
    // Check current role in localStorage or switch
    const userRole = localStorage.getItem('userRole') || localStorage.getItem('roleId');
    return {
        userInfo: localStorage.getItem('userInfo') ? JSON.parse(localStorage.getItem('userInfo')) : null,
        currentRole: userRole
    };
})()"""
print("User info:", eval_js(js_switch_role))

# Let's navigate to doctor workstation
eval_js("window.location.hash = '#/inpatient/doctor/workstation'")
time.sleep(3.0)

# Check patients in the table
js_patients = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row'));
    return rows.map(r => {
        const text = r.innerText.replace(/\\s+/g, ' ').trim();
        return text;
    });
})()"""

patients = eval_js(js_patients)
with open(r'D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\scratch\doctor_patients.json', 'w', encoding='utf-8') as f:
    json.dump(patients, f, ensure_ascii=False, indent=2)
print("Patient rows count:", len(patients) if isinstance(patients, list) else 0)

# Take screenshot
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_doctor_workstation.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Screenshot saved to:", path)

ws.close()
