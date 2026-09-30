import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()
v.switch_identity_in_browser(37, 910127, "#/inpatient/pharmacy/inhospitalputmedicine")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/pharmacy/inhospitalputmedicine';")
time.sleep(2.0)

# 探索左侧调配申请面板的科室选择与 tab 点击
info = eval_js("""(() => {
    // 查找科室选择下拉框
    const inputs = Array.from(document.querySelectorAll('input'));
    const deptInput = inputs.find(i => i.placeholder && i.placeholder.includes('科室'));
    if (deptInput) {
        deptInput.click();
    }
    // 查找已发药 / 已发送 tabs
    const tabs = Array.from(document.querySelectorAll('.el-button, span, div'))
                      .map(e => e.innerText && e.innerText.trim())
                      .filter(t => ['已发送', '已打印', '已发药', '退药单'].includes(t));
    return { hasDeptInput: !!deptInput, tabs };
})()""")
print("Pharmacy info:", info)
time.sleep(1.0)

# 如果下拉框打开了，查看下拉选项
options = eval_js("""(() => {
    const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item, .el-cascader-node'));
    return opts.map(o => o.innerText.trim()).filter(Boolean);
})()""")
print("Dept options:", options)

# 点击内一科或内一科病区
click_dept = eval_js("""(() => {
    const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item, .el-cascader-node'));
    const target = opts.find(o => o.innerText.includes('内一科'));
    if (target) {
        target.click();
        return { clicked: true, name: target.innerText.trim() };
    }
    return { clicked: false };
})()""")
print("Click dept option:", click_dept)
time.sleep(1.5)

# 点击【已发药】或【已发送】
click_tab = eval_js("""(() => {
    const buttons = Array.from(document.querySelectorAll('.el-button, div, span'));
    const fted = buttons.find(b => b.innerText && b.innerText.trim() === '已发药');
    if (fted) {
        fted.click();
        return { clicked: true, text: '已发药' };
    }
    return { clicked: false };
})()""")
print("Click tab:", click_tab)
time.sleep(2.0)

ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\plan_b_act3_inhospital_pharmacy_detailed.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
