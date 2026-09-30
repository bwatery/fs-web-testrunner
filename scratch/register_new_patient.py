import requests, json, websocket, time, base64

tabs = requests.get('http://127.0.0.1:9222/json').json()
page = [t for t in tabs if t.get('type') == 'page'][0]
ws = websocket.create_connection(page['webSocketDebuggerUrl'])

def eval_js(expr):
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}}))
    msg = json.loads(ws.recv())
    return msg.get('result', {}).get('result', {}).get('value')

# 自动填写入院登记表单函数
fill_script = """(() => {
    function setInputByLabel(labelKeyword, value) {
        const items = Array.from(document.querySelectorAll('.el-form-item'));
        const item = items.find(i => i.innerText && i.innerText.includes(labelKeyword));
        if (!item) return false;
        const input = item.querySelector('input');
        if (!input) return false;
        input.value = value;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }

    function selectOptionByLabel(labelKeyword, targetOptionText) {
        const items = Array.from(document.querySelectorAll('.el-form-item'));
        const item = items.find(i => i.innerText && i.innerText.includes(labelKeyword));
        if (!item) return { success: false, reason: '未找到 item ' + labelKeyword };
        const select = item.querySelector('.el-select__wrapper') || item.querySelector('.el-select');
        if (!select) return { success: false, reason: '未找到 select' };
        select.click();
        
        // 查找下拉选项
        const opts = Array.from(document.querySelectorAll('.el-select-dropdown__item'));
        const opt = opts.find(o => o.innerText.trim() === targetOptionText || o.innerText.includes(targetOptionText));
        if (opt) {
            opt.click();
            return { success: true, chosen: opt.innerText.trim() };
        }
        return { success: false, reason: '未找到选项 ' + targetOptionText };
    }

    const log = [];
    
    // 1. 姓名
    log.push({ field: '姓名', ok: setInputByLabel('姓名', '陈新强') });
    
    // 2. 性别
    log.push({ field: '性别', res: selectOptionByLabel('性别', '男') });

    // 3. 出生日期
    log.push({ field: '出生日期', ok: setInputByLabel('出生日期', '1988-08-08') });

    // 4. 证件号
    log.push({ field: '证件号', ok: setInputByLabel('证件号', 'QT88992211') });

    // 5. 结算类别
    log.push({ field: '结算类别', res: selectOptionByLabel('结算类别', '自费') });

    // 6. 结算种类
    log.push({ field: '结算种类', res: selectOptionByLabel('结算种类', '全自费病人') });

    // 7. 本人电话
    log.push({ field: '本人电话', ok: setInputByLabel('本人电话', '13812345678') });

    // 8. 详细住址
    log.push({ field: '详细住址', ok: setInputByLabel('详细住址', '广东省广州市越秀区健康路88号') });

    // 9. 联系人
    log.push({ field: '联系人', ok: setInputByLabel('联系人', '李女士') });

    // 10. 联系人关系
    log.push({ field: '联系人关系', res: selectOptionByLabel('联系人关系', '其他') });

    // 11. 入院途径
    log.push({ field: '入院途径', res: selectOptionByLabel('入院途径', '其他') });

    // 12. 入院类型
    log.push({ field: '入院类型', res: selectOptionByLabel('入院类型', '普通住院') });

    // 13. 入院科室
    log.push({ field: '入院科室', res: selectOptionByLabel('入院科室', '内一科') });

    // 14. 入院病区
    log.push({ field: '入院病区', res: selectOptionByLabel('入院病区', '内一科病区') });

    // 15. 入院医生
    log.push({ field: '入院医生', res: selectOptionByLabel('入院医生', '系统管理员') });

    return log;
})()"""

res_fill = eval_js(fill_script)
print("Form Fill Results:")
print(json.dumps(res_fill, ensure_ascii=False, indent=2))
time.sleep(2.0)

# 抓取填报后的页面截图
ws.send(json.dumps({'id': 100, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
raw = ws.recv()
b64 = json.loads(raw).get('result', {}).get('data', '')
path = r"D:\CSsoft\AI\googleAntiGravity\cliProject\fs_web_testrunner\reports\screenshots\new_patient_form_filled.png"
with open(path, 'wb') as f:
    f.write(base64.b64decode(b64))
print("Captured:", path)

ws.close()
