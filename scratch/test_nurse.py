import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    return json.loads(ws.recv()).get('result', {}).get('result', {}).get('value')

# 切换为护士身份
import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()
v.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/nurse/orderExecutionQuery';")
time.sleep(2.0)

# 寻找欧伟英树节点并点击
click_res = eval_js("""(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node'));
    const target = nodes.find(n => {
        const label = n.querySelector('.el-tree-node__label') || n;
        return label.innerText && label.innerText.includes('欧伟英');
    });
    if (target) {
        const content = target.querySelector('.el-tree-node__content') || target;
        content.click();
        return { clicked: true, text: content.innerText.trim() };
    }
    return { clicked: false, totalNodes: nodes.length };
})()""")
print("Nurse patient click:", click_res)
time.sleep(1.5)

# 点击查询按钮
search_res = eval_js("""(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const qBtn = btns.find(b => b.innerText && b.innerText.trim() === '查询');
    if (qBtn) {
        qBtn.click();
        return { clicked: true, text: qBtn.innerText.trim() };
    }
    return { clicked: false };
})()""")
print("Search button click:", search_res)
time.sleep(2.0)

# 截屏
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\plan_b_act2_nurse_ouwei_fixed.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)
ws.close()
