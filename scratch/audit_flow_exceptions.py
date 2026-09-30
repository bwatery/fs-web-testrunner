import requests, json, websocket, time

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

# 启用 CDP 日志与网络监听
ws.send(json.dumps({'id': 1, 'method': 'Console.enable'}))
ws.send(json.dumps({'id': 2, 'method': 'Log.enable'}))
ws.send(json.dumps({'id': 3, 'method': 'Network.enable'}))

errors = []
api_failures = []

def eval_js(expr):
    ws.send(json.dumps({'id': 99, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

def drain_events():
    ws.settimeout(0.5)
    while True:
        try:
            raw = ws.recv()
            msg = json.loads(raw)
            method = msg.get('method')
            if method == 'Log.entryAdded':
                entry = msg.get('params', {}).get('entry', {})
                if entry.get('level') in ['error', 'warning']:
                    errors.append(f"[Browser Log {entry.get('level')}] {entry.get('text')}")
            elif method == 'Console.messageAdded':
                cmsg = msg.get('params', {}).get('message', {})
                if cmsg.get('level') in ['error']:
                    errors.append(f"[Console Error] {cmsg.get('text')}")
            elif method == 'Network.responseReceived':
                resp = msg.get('params', {}).get('response', {})
                status = resp.get('status')
                if status >= 400:
                    api_failures.append(f"[HTTP {status}] {resp.get('url')}")
        except Exception:
            break
    ws.settimeout(10)

print(">>> 开始端到端无死角异常监控流测试...")

# 1. 检查医生站
print("\n[Step 1] 校验住院医生工作站加载与患者上下文激活...")
eval_js("window.location.hash = '#/inpatient/doctor/workstation';")
time.sleep(2.0)
drain_events()

# 双击欧伟英
res_doc = eval_js("""(() => {
    const rows = Array.from(document.querySelectorAll('.vxe-body--row, tr'));
    const ouRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
    if (!ouRow) return { success: false, reason: '未找到欧伟英' };
    const cell = ouRow.querySelector('.vxe-cell') || ouRow;
    const dbl = new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window });
    cell.dispatchEvent(dbl);
    ouRow.dispatchEvent(dbl);
    return { success: true };
})()""")
print("  双击欧伟英结果:", res_doc)
time.sleep(1.5)
drain_events()

# 2. 检查护士站
print("\n[Step 2] 校验护士站医嘱执行查询看板...")
import sys
sys.path.insert(0, r"D:\CSsoft\AI\googleAntiGravity\cliProject")
from fs_web_testrunner.core.login_validator import LoginValidator
v = LoginValidator()
v.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/orderExecutionQuery")
time.sleep(2.0)
drain_events()

eval_js("window.location.hash = '#/inpatient/nurse/orderExecutionQuery';")
time.sleep(1.5)
drain_events()

# 点击欧伟英叶子节点
res_nurse = eval_js("""(() => {
    const contents = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = contents.find(c => c.innerText.trim() === '欧伟英(401-10)' || (c.innerText.includes('欧伟英') && !c.innerText.includes('住院患者')));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false };
})()""")
print("  护士站选定结果:", res_nurse)
time.sleep(1.5)
drain_events()

# 3. 检查药房住院摆药
print("\n[Step 3] 校验药房住院摆药工作台...")
v.switch_identity_in_browser(37, 910127, "#/inpatient/pharmacy/inhospitalputmedicine")
time.sleep(2.0)
drain_events()

eval_js("window.location.hash = '#/inpatient/pharmacy/inhospitalputmedicine';")
time.sleep(1.5)
drain_events()

# 4. 检查退费申请
print("\n[Step 4] 校验退药退费申请看板...")
v.switch_identity_in_browser(36, 910131, "#/inpatient/nurse/returnpremium")
time.sleep(2.0)
drain_events()

eval_js("window.location.hash = '#/inpatient/nurse/returnpremium';")
time.sleep(1.5)
res_ref = eval_js("""(() => {
    const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
    const target = nodes.find(n => n.innerText && n.innerText.includes('欧伟英'));
    if (target) {
        target.click();
        return { clicked: true, text: target.innerText.trim() };
    }
    return { clicked: false };
})()""")
print("  退费申请拉取结果:", res_ref)
time.sleep(1.5)
drain_events()

# 5. 检查出院结算
print("\n[Step 5] 校验出院结算操作台...")
v.switch_identity_in_browser(34, 2, "#/inpatient/finance/leavehospitalcalculate")
time.sleep(2.0)
drain_events()

eval_js("window.location.hash = '#/inpatient/finance/leavehospitalcalculate';")
time.sleep(1.5)
drain_events()

# 点击选择按钮
res_sel = eval_js("""(() => {
    const btns = Array.from(document.querySelectorAll('button, .el-button'));
    const b = btns.find(x => x.innerText.trim() === '选择');
    if (b) { b.click(); return { clicked: true }; }
    return { clicked: false };
})()""")
print("  调起患者弹窗结果:", res_sel)
time.sleep(1.5)
drain_events()

# 选中内一科并双击欧伟英
res_pick = eval_js("""(() => {
    const items = Array.from(document.querySelectorAll('.el-dialog .el-tree-node, .el-dialog div, .el-dialog span'));
    const n1 = items.find(i => i.innerText && i.innerText.trim() === '内一科');
    if (n1) n1.click();
    setTimeout(() => {
        const rows = Array.from(document.querySelectorAll('.el-dialog tr, .el-dialog .el-table__row'));
        const ouRow = rows.find(r => r.innerText && r.innerText.includes('欧伟英'));
        if (ouRow) {
            const cell = ouRow.querySelector('td') || ouRow;
            const dbl = new MouseEvent('dblclick', { bubbles: true, cancelable: true, view: window });
            cell.dispatchEvent(dbl);
            ouRow.dispatchEvent(dbl);
        }
    }, 600);
    return { success: true };
})()""")
time.sleep(2.5)
drain_events()

# 检查最终结算界面状态与按钮
settle_state = eval_js("""(() => {
    const text = document.body ? document.body.innerText : '';
    const hasOuwei = text.includes('欧伟英');
    const hasMoney = text.includes('495.7');
    const btns = Array.from(document.querySelectorAll('button, .el-button')).map(b => b.innerText.trim());
    return {
        hasOuwei,
        hasMoney,
        hasSettleBtn: btns.includes('结算'),
        buttons: btns.filter(b => b.length > 0 && b.length < 15)
    };
})()""")
print("  出院结算终态核验:", settle_state)

print("\n=======================================================")
print(f"📊 异常监控审计总结:")
print(f"  前端 JS 错误/告警数: {len(errors)}")
for err in errors[:5]:
    print("    ", err)
print(f"  后端 HTTP 4xx/5xx 异常请求数: {len(api_failures)}")
for f in api_failures[:5]:
    print("    ", f)
print("=======================================================")

ws.close()
