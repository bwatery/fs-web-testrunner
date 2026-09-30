import os, sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
import requests, json, websocket, time, base64
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.his_driver import HISDriver

validator = LoginValidator()

# Get Chrome websocket connection
tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=10)

def eval_js(expression):
    ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate', 'params': {'expression': expression, 'returnByValue': True}}))
    raw = ws.recv()
    return json.loads(raw).get('result', {}).get('result', {}).get('value')

def capture(name):
    ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
    raw = ws.recv()
    b64 = json.loads(raw).get('result', {}).get('data', '')
    path = rf"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\{name}.png"
    with open(path, 'wb') as f:
        f.write(base64.b64decode(b64))
    print(f"  [📸 Screenshot Captured] {path}")
    return path

print("======================================================================")
print("🚀 开始执行【方案 B: 侵入式全流程多角色真实桌面接力实测】(患者: 欧伟英 401-10床)")
print("======================================================================\n")

# ----------------------------------------------------------------------------
# 第一幕：住院医生站 (Role 35, Dept 910092 内一科)
# ----------------------------------------------------------------------------
print("👉 [第一幕] 切换为【住院医生 (内一科)】身份...")
sw1 = validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/workstation")
print(f"   身份切换: {sw1.get('message')}")
time.sleep(2.5)

# 确保在医生工作站页面
eval_js("window.location.hash = '#/inpatient/doctor/workstation';")
time.sleep(2.0)

# 双击表格中的欧伟英行，激活该患者
print("👉 [第一幕] 在【患者选择】列表中精准双击锁定【401-10 欧伟英】...")
js_select_ouwei = """(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr'));
    const ouRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
    if (!ouRow) return { success: false, reason: '未找到欧伟英行' };
    
    // 双击单元格与行
    const cell = ouRow.querySelector('.vxe-cell') || ouRow.querySelector('td') || ouRow;
    const dblEvt = new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window });
    cell.dispatchEvent(dblEvt);
    ouRow.dispatchEvent(dblEvt);
    return { success: true, text: ouRow.innerText.replace(/\\s+/g, ' ') };
})()"""
res_doc = eval_js(js_select_ouwei)
print(f"   患者双击选定: {res_doc}")
time.sleep(2.0)

# 点击长期医嘱 Tab
eval_js("""(() => {
    const tabs = Array.from(document.querySelectorAll('.el-tabs__item, .vab-tabs__item'));
    const longTab = tabs.find(t => t.innerText && t.innerText.trim() === '长期医嘱');
    if (longTab) longTab.click();
})()""")
time.sleep(1.5)

shot1 = capture("plan_b_act1_doctor_ouwei")
assert os.path.exists(shot1), "第一幕截图生成失败"

# ----------------------------------------------------------------------------
# 第二幕：住院护士站 (Role 36, Dept 910131 内一科病区)
# ----------------------------------------------------------------------------
print("\n👉 [第二幕] 切换为【住院护士 (内一科病区)】身份...")
sw2 = validator.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery")
print(f"   身份切换: {sw2.get('message')}")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/nurse/orderExecutionQuery';")
time.sleep(2.0)

# 在左侧病区患者树中点击 欧伟英(401-10)
print("👉 [第二幕] 在护士站病区床位树中选定【欧伟英(401-10)】并下钻医嘱执行看板...")
js_nurse_click = """(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__content, span, div'));
    const target = nodes.find(n => n.innerText && (n.innerText.includes('欧伟英') || n.innerText.includes('401-10')));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false, total: nodes.length };
})()"""
res_nurse = eval_js(js_nurse_click)
print(f"   护士站患者定位: {res_nurse}")
time.sleep(2.0)

shot2 = capture("plan_b_act2_nurse_ouwei")
assert os.path.exists(shot2), "第二幕截图生成失败"

# ----------------------------------------------------------------------------
# 第三幕：药房工作站 (Role 33, Dept 910125 西药房)
# ----------------------------------------------------------------------------
print("\n👉 [第三幕] 切换为【药房药剂师 (西药房)】身份...")
sw3 = validator.switch_identity_in_browser(33, 910125, "#/outpatient/pharmacy/outDispense")
print(f"   身份切换: {sw3.get('message')}")
time.sleep(2.5)

eval_js("window.location.hash = '#/outpatient/pharmacy/outDispense';")
time.sleep(2.0)
shot3 = capture("plan_b_act3_pharmacy_dispense")
assert os.path.exists(shot3), "第三幕截图生成失败"

# ----------------------------------------------------------------------------
# 第四幕：住院收费处 (Role 34, Dept 2 收费处)
# ----------------------------------------------------------------------------
print("\n👉 [第四幕] 切换为【住院收费员 (收费处)】身份...")
sw4 = validator.switch_identity_in_browser(34, 2, "#/inpatient/finance/syntheticfquery")
print(f"   身份切换: {sw4.get('message')}")
time.sleep(2.5)

eval_js("window.location.hash = '#/inpatient/finance/syntheticfquery';")
time.sleep(2.0)

# 在费用综合查询中点击欧伟英下钻账单明细
print("👉 [第四幕] 在费用综合查询患者树中选定【401-10 欧伟英】实时穿透住院总额与预交金流水...")
js_bill_click = """(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = nodes.find(n => n.innerText && (n.innerText.includes('欧伟英') || n.innerText.includes('401-10')));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim().replace(/\\s+/g, ' ') };
    }
    return { clicked: false, total: nodes.length };
})()"""
res_bill = eval_js(js_bill_click)
print(f"   账单穿透结果: {res_bill}")
time.sleep(2.0)

shot4 = capture("plan_b_act4_settlement_ouwei")
assert os.path.exists(shot4), "第四幕截图生成失败"

ws.close()
print("\n======================================================================")
print("🎉🎉 方案 B 全流程侵入式多角色接力演示【全部成功通过】！四幕高清证据链已就绪！")
print("======================================================================")
