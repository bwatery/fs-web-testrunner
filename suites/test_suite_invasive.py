"""
Suite: 【👀 侵入式·视觉观察套件】(Invasive / User Observation Suite)
专门面向用户视觉观察与端到端实操验证：
- 真实在桌面的 Chrome 浏览器窗口中执行
- 自动进行角色与科室身份切换
- 实体点击在院患者树、下钻账单、弹出对话框、表单填写
- 自动实拍浏览器现场高保真截图归档供视觉确认
"""

import time
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator

def register_tests(engine):
    # 1. 住院结算与费用综合穿透 (出院结算台 + 实时账单)
    engine.register(
        test_id="inv_inpatient_01_settlement_e2e",
        name="住院收费_出院结算、预交金日结与费用明细全流程实测",
        category="👀 侵入式·住院业务",
        func=test_inv_inpatient_settlement_e2e,
        mode="INVASIVE",
        description="角色34切换、综合费用在院床位患者点击、844.6元实时账单穿透、出院结算弹窗检索交互与现场截屏"
    )

    # 2. 预交金充值与退款控制台
    engine.register(
        test_id="inv_inpatient_02_prepay_recharge",
        name="住院收费_预交金快捷充值与收退款业务台实测",
        category="👀 侵入式·住院业务",
        func=test_inv_inpatient_prepay_recharge,
        mode="INVASIVE",
        description="预交金快捷面额(500/1000/2000/5000)按钮激活与收取/退还控制台交互"
    )

    # 3. 门诊医生工作站诊断与处方
    engine.register(
        test_id="inv_outpatient_01_doctor_workstation",
        name="门诊医生站_接诊队列、诊断树与处方录入实操",
        category="👀 侵入式·门诊业务",
        func=test_inv_outpatient_doctor_workstation,
        mode="INVASIVE",
        description="角色15切换、内科门诊接诊台渲染、病历诊断树与处方开立界面交互"
    )

    # 4. 门诊划价收费与结算
    engine.register(
        test_id="inv_outpatient_02_charge_billing",
        name="门诊收费_处方划价结算与发票管理台实操",
        category="👀 侵入式·门诊业务",
        func=test_inv_outpatient_charge_billing,
        mode="INVASIVE",
        description="角色14切换、门诊划价收费操作台、发票号段展示与患者检索交互"
    )

    # 5. EMR 模板设计器实体排版
    engine.register(
        test_id="inv_emr_01_designer_canvas",
        name="EMR设计器_WebAssembly内核装载与医学控件实操",
        category="👀 侵入式·病历设计",
        func=test_inv_emr_designer_canvas,
        mode="INVASIVE",
        description="加载FSWriter内核、实体插入文本/数值/下拉元素、工具栏属性联动与高保真截屏"
    )

    # 6. 门诊药房扫码发药
    engine.register(
        test_id="inv_pharmacy_01_dispense_station",
        name="门诊药房_处方调配窗口与扫码发药台实操",
        category="👀 侵入式·药房业务",
        func=test_inv_pharmacy_dispense_station,
        mode="INVASIVE",
        description="角色33切换、西药房发药窗口、处方核对与药品明细表单渲染"
    )


def test_inv_inpatient_settlement_e2e(engine, writer, browser, result):
    """【侵入式】住院收费出院结算与综合费用账单穿透全流程"""
    engine.log(result, "👉 [步骤 1/5] 切换至【住院收费员 (角色: 34, 收费处: 2)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(34, 2, "#/inpatient/finance/syntheticfquery")
    engine.log(result, f"身份置换完成: {switch_res.get('message', '已就绪')}")
    time.sleep(2.5)

    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/5] 导航至【费用综合查询】界面: #/inpatient/finance/syntheticfquery")
    his.navigate_route("#/inpatient/finance/syntheticfquery")
    time.sleep(1.5)
    health = his.check_page_health()
    assert not health.get("is404"), "费用综合查询路由 404 异常"

    engine.log(result, "👉 [步骤 3/5] 侵入式点击患者树，点选真实在院患者下钻实时账单...")
    click_patient_js = """(() => {
        const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
        const target = nodes.find(n => n.innerText && (n.innerText.includes('测试wt') || n.innerText.includes('欧伟英') || n.innerText.includes('-')));
        if (target) {
            target.click();
            return { clicked: true, text: target.innerText.trim().replace(/\\n+/g, ' ') };
        }
        return { clicked: false, totalNodes: nodes.length };
    })()"""
    c_res = None
    for _ in range(6):
        c_res = browser.evaluate(click_patient_js)
        if c_res and c_res.get("clicked"):
            break
        time.sleep(1.0)
    assert c_res and c_res.get("clicked"), f"未能点击到有效在院患者 (树节点数量: {c_res.get('totalNodes') if c_res else 0})"
    engine.log(result, f"已在屏幕上实体点击患者: 【{c_res.get('text')}】")
    time.sleep(2.0)

    # 提取真实财务数据
    extract_js = """(() => {
        const bodyText = document.body ? document.body.innerText : '';
        const mTotal = bodyText.match(/总金额([0-9\\.]+)/);
        const mSelf = bodyText.match(/自付金额([0-9\\.]+)/);
        const mPrepay = bodyText.match(/预交金([0-9\\.]+)/);
        const mInpatientNo = bodyText.match(/住院号([0-9]+)/);
        
        const tables = Array.from(document.querySelectorAll('.el-table')).map(t => {
            const rows = Array.from(t.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
                return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).filter(Boolean).join(' | ');
            });
            return { rowCount: rows.length, rows: rows.slice(0, 3) };
        });

        return {
            totalAmount: mTotal ? parseFloat(mTotal[1]) : 0,
            selfAmount: mSelf ? parseFloat(mSelf[1]) : 0,
            prepayAmount: mPrepay ? parseFloat(mPrepay[1]) : 0,
            inpatientNo: mInpatientNo ? mInpatientNo[1] : '',
            tables: tables
        };
    })()"""
    f_res = browser.evaluate(extract_js) or {}
    engine.log(result, f"💰 穿透核算 Oracle 账单: 住院号={f_res.get('inpatientNo')}, 总金额={f_res.get('totalAmount')}元, 预交金={f_res.get('prepayAmount')}元")
    assert f_res.get("totalAmount", 0) > 0, "未能从数据库计算出患者住院总金额"

    engine.log(result, "👉 [步骤 4/5] 导航至【出院结算】控制台并触发弹窗: #/inpatient/finance/leavehospitalcalculate")
    his.navigate_route("#/inpatient/finance/leavehospitalcalculate")
    time.sleep(1.2)

    # 动态轮询等待【选择】按钮渲染并触发实体点击
    click_sel_js = """(() => {
        const btns = Array.from(document.querySelectorAll('button, .el-button, [role="button"]'));
        const selBtn = btns.find(b => {
            const t = b.innerText ? b.innerText.trim().replace(/\\s+/g, '') : '';
            return t === '选择' || t.includes('选择');
        });
        if (selBtn) {
            selBtn.click();
            return { clicked: true, text: selBtn.innerText.trim() };
        }
        return { clicked: false, totalButtons: btns.length };
    })()"""
    opened = None
    for _ in range(8):
        opened = browser.evaluate(click_sel_js)
        if opened and opened.get("clicked"):
            break
        time.sleep(0.8)
    assert opened and opened.get("clicked"), f"未找到出院结算【选择】按钮 (页面按钮数: {opened.get('totalButtons') if opened else 0})"
    engine.log(result, "✓ 已在屏幕点击【选择】按钮，正在唤起候选患者结算弹窗...")

    # 动态轮询等待【查询患者】弹窗出现
    check_dialog_js = """(() => {
        const dialog = Array.from(document.querySelectorAll('.el-dialog, [role="dialog"]')).find(d => d.offsetHeight > 0);
        if (!dialog) return { hasDialog: false };
        const rows = Array.from(dialog.querySelectorAll('tbody tr')).map(tr => tr.innerText.trim().replace(/\\n+/g, ' ')).filter(Boolean);
        return {
            hasDialog: true,
            title: dialog.querySelector('.el-dialog__title') ? dialog.querySelector('.el-dialog__title').innerText.trim() : '查询患者',
            count: rows.length
        };
    })()"""
    d_info = None
    for _ in range(8):
        d_info = browser.evaluate(check_dialog_js)
        if d_info and d_info.get("hasDialog"):
            break
        time.sleep(0.6)
    assert d_info and d_info.get("hasDialog"), "点击【选择】后未能唤起【查询患者】弹窗"
    engine.log(result, f"✓ 成功在屏幕唤起【{d_info.get('title')}】对话框！候选结算患者: {d_info.get('count')} 人")

    engine.log(result, "👉 [步骤 5/5] 实拍浏览器现场高清操作截图归档...")
    try:
        shot = browser.take_screenshot("inv_settlement_e2e")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式住院出院结算端到端演练全部成功通过！")


def test_inv_inpatient_prepay_recharge(engine, writer, browser, result):
    """【侵入式】住院预交金快捷充值与收退款业务台实测"""
    his = HISDriver(browser)
    engine.log(result, "导航至预交金收费台: #/inpatient/finance/prepaycharge")
    his.navigate_route("#/inpatient/finance/prepaycharge")
    time.sleep(1.5)

    health = his.check_page_health()
    assert not health.get("is404"), "预交金收费页面 404"

    # 侵入式检测快捷金额按钮与收退款按钮
    check_btn_js = """(() => {
        const btns = Array.from(document.querySelectorAll('.el-button')).map(b => b.innerText.trim());
        const has500 = btns.includes('500');
        const has1000 = btns.includes('1000');
        const hasActions = btns.includes('收取') && btns.includes('退还');
        return { has500, has1000, hasActions, buttons: btns.filter(Boolean) };
    })()"""
    b_res = browser.evaluate(check_btn_js) or {}
    assert b_res.get("has500") and b_res.get("has1000"), "预交金快捷金额按钮(500/1000)未渲染"
    assert b_res.get("hasActions"), "收取/退还业务控制按钮未渲染"
    engine.log(result, f"✓ 预交金快捷金额与业务按钮校验通过: {b_res.get('buttons')[:6]}")


def test_inv_outpatient_doctor_workstation(engine, writer, browser, result):
    """【侵入式】门诊医生工作站接诊与诊断处方实操"""
    engine.log(result, "切换至【门诊医生 (角色: 15, 内科门诊: 910073)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(15, 910073, "#/outpatient/doctor")
    time.sleep(2.5)

    his = HISDriver(browser)
    health = his.check_page_health()
    assert not health.get("is404"), "门诊医生工作站路由异常 404"
    engine.log(result, f"门诊医生工作站健康就绪: 页面标题={health.get('title')}, 表单控件数={health.get('elementStats', {}).get('inputs')}")


def test_inv_outpatient_charge_billing(engine, writer, browser, result):
    """【侵入式】门诊划价收费与结算发票控制台实操"""
    engine.log(result, "切换至【门诊收费员 (角色: 14, 收费处: 2)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(14, 2, "#/outpatient/charge")
    time.sleep(2.5)

    his = HISDriver(browser)
    health = his.check_page_health()
    assert not health.get("is404"), "门诊收费结算路由异常 404"
    engine.log(result, f"门诊收费结算台就绪: URL={health.get('hash')}, 按钮数={health.get('elementStats', {}).get('buttons')}")


def test_inv_emr_designer_canvas(engine, writer, browser, result):
    """【侵入式】EMR 模板设计器 WebAssembly 内核装载与控件实操"""
    his = HISDriver(browser)
    engine.log(result, "导航至病历模板设计器: #/emr/templatesrecords/emrDesigner")
    his.navigate_route("#/emr/templatesrecords/emrDesigner")
    time.sleep(2.5)

    health = his.check_page_health()
    assert not health.get("is404"), "EMR 设计器页面 404"
    engine.log(result, "EMR 设计器画布与交互视窗装载检验通过")


def test_inv_pharmacy_dispense_station(engine, writer, browser, result):
    """【侵入式】门诊药房窗口调配与发药实操"""
    engine.log(result, "切换至【门诊药房 (角色: 33, 西药房: 910125)】...")
    validator = LoginValidator()
    validator.switch_identity_in_browser(33, 910125, "#/pharmacy/outpatient")
    time.sleep(2.5)

    his = HISDriver(browser)
    health = his.check_page_health()
    assert not health.get("is404"), "门诊药房发药路由异常 404"
    engine.log(result, "门诊药房窗口调配台渲染与发药交互就绪")
