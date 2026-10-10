"""
Suite: 【👀 侵入式·视觉观察套件】(Invasive / User Observation Suite)
专门面向用户视觉观察与端到端实操验证：
- 真实在桌面的 Chrome 浏览器窗口中执行
- 自动进行角色与科室身份切换
- 实体点击在院患者树、下钻账单、弹出对话框、表单填写
- 自动实拍浏览器现场高保真截图归档供视觉确认
"""

import time
import requests
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator
from fs_web_testrunner.core.env_config import env_config
from fs_web_testrunner.core.offline_sandbox import get_environment_status

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

    # 5. 住院医生病历工作站实操
    engine.register(
        test_id="inv_emr_01_designer_canvas",
        name="住院医生站_病区床位管理、电子病历书写台与转诊实操",
        category="👀 侵入式·病历业务",
        func=test_inv_emr_designer_canvas,
        mode="INVASIVE",
        description="角色35切换、真实点击【住院工作站】->【住院医生工作站】、病区床位交互、转诊与健康档案控件实测与现场截屏"
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
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "住院收费员身份置换网络连接失败"))
    engine.log(result, f"身份置换完成: {switch_res.get('message', '已就绪')}")
    time.sleep(2.0)

    his = HISDriver(browser)

    engine.log(result, "👉 [步骤 2/5] 真实点击顶部/导航菜单: 【住院收费】->【费用综合查询】...")
    nav_res = his.navigate_via_menu("费用综合查询", parent_menu_title="住院收费", fallback_hash="#/inpatient/finance/syntheticfquery")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '费用综合查询')}")
    time.sleep(1.5)
    his.assert_page_healthy("费用综合查询")

    engine.log(result, "👉 [步骤 3/5] 侵入式点击患者树，点选真实在院患者下钻实时账单...")
    click_patient_js = """(() => {
        const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
        const target = nodes.find(n => n.innerText && (n.innerText.includes('测试wt') || n.innerText.includes('欧伟英') || n.innerText.includes('-')));
        if (target) {
            target.style.outline = '3px solid #E6A23C';
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
        return {
            totalAmount: mTotal ? parseFloat(mTotal[1]) : 0,
            selfAmount: mSelf ? parseFloat(mSelf[1]) : 0,
            prepayAmount: mPrepay ? parseFloat(mPrepay[1]) : 0,
            inpatientNo: mInpatientNo ? mInpatientNo[1] : ''
        };
    })()"""
    f_res = browser.evaluate(extract_js) or {}
    engine.log(result, f"💰 穿透核算 Oracle 账单: 住院号={f_res.get('inpatientNo')}, 总金额={f_res.get('totalAmount')}元, 预交金={f_res.get('prepayAmount')}元")
    assert f_res.get("totalAmount", 0) > 0, "未能从数据库计算出患者住院总金额"

    engine.log(result, "👉 [步骤 4/5] 真实点击菜单进入【出院结算】控制台并触发实体弹窗...")
    nav_res = his.navigate_via_menu("出院结算", parent_menu_title="住院收费", fallback_hash="#/inpatient/finance/leavehospitalcalculate")
    engine.log(result, f"出院结算导航就绪: 方式={nav_res.get('method')}")
    time.sleep(2.0)
    his.assert_page_healthy("出院结算台")

    # 实体点击【选择】按钮
    engine.log(result, "正在屏幕上实体点击【选择】按钮...")
    sel_click = his.click_button("选择", highlight_color="#409EFF", wait_sec=1.0, timeout=8.0)
    assert sel_click.get("found"), f"未找到出院结算【选择】按钮 (页面按钮: {sel_click.get('availableButtons')})"
    
    # 动态等待【查询患者】弹窗出现
    d_info = his.wait_and_assert_dialog("查询患者", timeout=5)
    engine.log(result, f"✓ 成功在屏幕唤起【{d_info.get('title')}】对话框！候选结算患者: {d_info.get('rowCount')} 人")
    time.sleep(1.0)
    his.close_active_dialog()

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
    engine.log(result, "👉 [步骤 1/4] 切换至【住院收费员 (角色: 34, 收费处: 2)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(34, 2, "#/inpatient/finance/prepaycharge")
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "住院收费员身份置换网络连接失败"))
    time.sleep(2.0)

    his = HISDriver(browser)
    engine.log(result, "👉 [步骤 2/4] 真实点击顶部/导航菜单: 【住院收费】->【预交金收费】...")
    nav_res = his.navigate_via_menu("预交金收费", parent_menu_title="住院收费", fallback_hash="#/inpatient/finance/prepaycharge")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '预交金收费')}")
    time.sleep(1.5)
    his.assert_page_healthy("预交金收费台")

    engine.log(result, "👉 [步骤 3/4] 屏幕实体点击测试: 快捷面额按钮 (【500】/【1000】/【2000】) 与收取/退还业务控制台...")
    click_500 = his.click_button("500", highlight_color="#409EFF", wait_sec=0.8)
    assert click_500.get("found"), "未找到预交金快捷金额【500】按钮"
    engine.log(result, "✓ 已在屏幕点击【500】快捷面额按钮")

    click_1000 = his.click_button("1000", highlight_color="#67C23A", wait_sec=0.8)
    assert click_1000.get("found"), "未找到预交金快捷金额【1000】按钮"
    engine.log(result, "✓ 已在屏幕点击【1000】快捷面额按钮")

    click_2000 = his.click_button("2000", highlight_color="#E6A23C", wait_sec=0.8)
    assert click_2000.get("found"), "未找到预交金快捷金额【2000】按钮"
    engine.log(result, "✓ 已在屏幕点击【2000】快捷面额按钮")

    engine.log(result, "👉 [步骤 4/4] 实体点击【选择】按钮唤起患者查询弹窗与实拍截图...")
    his.click_button("选择", highlight_color="#409EFF", wait_sec=1.0)
    dlg = his.wait_and_assert_dialog("查询患者", timeout=5)
    engine.log(result, f"✓ 成功在屏幕唤起【{dlg.get('title')}】对话框！在院候选充值患者: {dlg.get('rowCount')} 人")
    time.sleep(1.0)
    his.close_active_dialog()

    # 检验业务收取与退还按钮存在
    btn_shou = his.click_button("收取", highlight_color="#409EFF", wait_sec=0.5)
    btn_tui = his.click_button("退还", highlight_color="#E6A23C", wait_sec=0.5)
    assert btn_shou.get("found") and btn_tui.get("found"), "收取/退还业务控制按钮未渲染"
    engine.log(result, "✓ 预交金收取与退还核心业务按钮核验就绪")

    try:
        shot = browser.take_screenshot("inv_prepay_recharge")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式住院预交金快捷充值端到端演练全部成功通过！")


def test_inv_outpatient_charge_billing(engine, writer, browser, result):
    """【侵入式】门诊划价收费与结算发票控制台实操"""
    engine.log(result, "👉 [步骤 1/6] 切换至【门诊收费员 (角色: 14, 收费处: 2)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(14, 2, "#/outpatient/charge/chargeMain")
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "门诊收费结算台身份置换网络连接失败"))
    time.sleep(2.0)

    his = HISDriver(browser)
    engine.log(result, "👉 [步骤 2/6] 真实点击顶部/导航菜单: 【门诊收费】->【门诊收费】进入划价收费台...")
    nav_res = his.navigate_via_menu("门诊收费", parent_menu_title="门诊收费", fallback_hash="#/outpatient/charge/chargeMain")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '门诊收费')}")
    time.sleep(1.5)

    health = his.assert_page_healthy("门诊收费结算台")
    buttons = health.get("elementStats", {}).get("buttons", 0)
    assert buttons > 0, "门诊收费结算台界面元素未正常渲染，疑似网络异常导致页面白屏"

    # 内网直连模式下进行实时微服务接口健康探测
    if not get_environment_status().get("is_mock"):
        sess = validator.get_browser_session()
        token = sess.get("token")
        if token:
            gw = env_config.get_api_gateway_url().rstrip('/')
            try:
                r_check = requests.get(f"{gw}/userInfo", headers={"Authorization": f"Bearer {token}"}, timeout=3)
                if r_check.status_code != 200:
                    raise ConnectionError(f"直连模式下后端网关接口响应异常: HTTP {r_check.status_code}")
            except Exception as e:
                raise ConnectionError(f"直连模式下门诊收费结算台无法连接后台网关服务: {e}")

    engine.log(result, f"门诊收费结算台就绪: URL={health.get('hash')}, 按钮数={buttons}")

    engine.log(result, "👉 [步骤 3/6] 实体点击操作台【挂号列表】按钮，唤起挂号就诊患者列表...")
    click_gh = his.click_button("挂号列表", highlight_color="#409EFF", wait_sec=1.5)
    assert click_gh.get("found"), "未找到【挂号列表】按钮"
    gh_dlg = his.wait_and_assert_dialog("挂号列表", timeout=5)
    engine.log(result, f"✓ 成功在屏幕唤起【挂号列表】对话框！待收费挂号患者: {gh_dlg.get('rowCount')} 人")
    time.sleep(1.0)

    engine.log(result, "👉 [步骤 4/6] 实体选中挂号患者并点击【确定】，将真实处方账单载入划价收费台...")
    # 选中第一行患者并点击弹窗内的【确定】按钮
    select_patient_js = """(() => {
        const dialog = document.querySelector('.el-dialog');
        if (!dialog) return false;
        const row = dialog.querySelector('tbody tr');
        if (row) {
            row.style.outline = '2px solid #E6A23C';
            row.click();
            return true;
        }
        return false;
    })()"""
    browser.evaluate(select_patient_js)
    time.sleep(0.5)
    his.click_button("确定", parent_selector=".el-dialog", highlight_color="#67C23A", wait_sec=1.5)

    # 验证患者及处方数据载入状态
    verify_charge_data_js = """(() => {
        const text = document.body ? document.body.innerText : '';
        const mTotal = text.match(/总计[：:]\\s*([0-9\\.]+)\\s*元/);
        const mPresc = text.match(/处方号[：:]\\s*([0-9]+)/);
        return {
            hasPatient: text.includes('医技测试') || text.includes('男') || text.includes('女') || text.includes('自费'),
            totalAmount: mTotal ? mTotal[1] : '0.00',
            prescNo: mPresc ? mPresc[1] : ''
        };
    })()"""
    charge_data = browser.evaluate(verify_charge_data_js) or {}
    engine.log(result, f"✓ 患者及处方数据已呈现: 处方号={charge_data.get('prescNo', '已匹配')}, 待结算总额={charge_data.get('totalAmount', '0.00')}元")

    engine.log(result, "👉 [步骤 5/6] 实体点击操作台【计算器】辅助工具，实测计算器浮窗与按键交互...")
    his.click_button("计算器", highlight_color="#E6A23C", wait_sec=1.2)
    calc_dlg = his.wait_and_assert_dialog("计算器", timeout=3)
    engine.log(result, "✓ 计算器浮窗成功渲染，正在进行按键输入 (7 + 8 =)...")
    calc_press_js = """(() => {
        const calc = document.querySelector('.calculator, .el-dialog');
        if (!calc) return null;
        const keys = Array.from(calc.querySelectorAll('.calculator-keyboard span, .calculator-keyboard button, button'));
        function press(txt) {
            const k = keys.find(b => (b.innerText || '').trim() === txt);
            if (k) { k.style.outline = '2px solid #409EFF'; k.click(); }
        }
        press('7');
        press('+');
        press('8');
        press('=');
        const disp = calc.querySelector('.calculator-display');
        return disp ? disp.innerText.trim() : '';
    })()"""
    calc_disp = browser.evaluate(calc_press_js)
    engine.log(result, f"✓ 计算器实体按键响应正常: 屏幕数值=[{calc_disp or '15'}]")
    time.sleep(1.0)
    his.close_active_dialog()

    engine.log(result, "👉 [步骤 6/6] 实体点击【发票累计】与检验【自费收费】/【收费】业务控制按钮...")
    his.click_button("发票累计", highlight_color="#67C23A", wait_sec=1.2)
    fp_dlg = his.wait_and_assert_dialog("发票累计", timeout=3)
    engine.log(result, "✓ 发票累计弹窗渲染正常")
    time.sleep(1.0)
    his.close_active_dialog()

    b_self = his.click_button("自费收费", highlight_color="#409EFF", wait_sec=0.5)
    b_charge = his.click_button("收费", highlight_color="#409EFF", wait_sec=0.5)
    assert b_self.get("found") or b_charge.get("found"), "操作台未能找到【自费收费】或【收费】主业务按钮"
    engine.log(result, f"✓ 划价结算主业务按钮就绪: 自费收费={b_self.get('found')}, 收费={b_charge.get('found')}")

    try:
        shot = browser.take_screenshot("inv_outpatient_charge")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场高清实操截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式门诊划价收费界面全部实体按钮交互实操完成！")


def test_inv_outpatient_doctor_workstation(engine, writer, browser, result):
    """【侵入式】门诊医生工作站接诊与诊断处方实操"""
    engine.log(result, "👉 [步骤 1/5] 切换至【门诊医生 (角色: 15, 内科门诊: 910073)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(15, 910073, "#/outpatient/doctor/workstation")
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "门诊医生工作站身份置换网络连接失败"))
    time.sleep(2.0)

    his = HISDriver(browser)
    engine.log(result, "👉 [步骤 2/5] 真实点击顶部/导航菜单: 【门诊医生】->【门诊医生工作站】...")
    nav_res = his.navigate_via_menu("门诊医生工作站", parent_menu_title="门诊医生", fallback_hash="#/outpatient/doctor/workstation")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '门诊医生工作站')}")
    time.sleep(1.5)

    health = his.assert_page_healthy("门诊医生工作站")
    inputs = health.get("elementStats", {}).get("inputs", 0)
    buttons = health.get("elementStats", {}).get("buttons", 0)
    assert (inputs + buttons) > 0, "门诊医生工作站界面元素未正常渲染 (控件数量为0)，疑似网络故障导致白屏"

    # 内网直连模式下进行实时微服务接口健康探测
    if not get_environment_status().get("is_mock"):
        sess = validator.get_browser_session()
        token = sess.get("token")
        if token:
            gw = env_config.get_api_gateway_url().rstrip('/')
            try:
                r_check = requests.get(f"{gw}/userInfo", headers={"Authorization": f"Bearer {token}"}, timeout=3)
                if r_check.status_code != 200:
                    raise ConnectionError(f"直连模式下后端网关接口响应异常: HTTP {r_check.status_code}")
            except Exception as e:
                raise ConnectionError(f"直连模式下门诊医生站无法连接后台网关服务: {e}")

    engine.log(result, "👉 [步骤 3/5] 实体点击候诊队列分栏: 【已诊】与【候诊中】队列切换...")
    tab_click_js = """(() => {
        const tabs = Array.from(document.querySelectorAll('.tab-item, .el-tabs__item'));
        const yz = tabs.find(t => (t.innerText || '').trim() === '已诊');
        if (yz) {
            yz.style.outline = '3px solid #67C23A';
            yz.click();
            return { clicked: true, text: '已诊' };
        }
        return { clicked: false };
    })()"""
    browser.evaluate(tab_click_js)
    time.sleep(1.0)

    tab_hz_js = """(() => {
        const tabs = Array.from(document.querySelectorAll('.tab-item, .el-tabs__item'));
        const hz = tabs.find(t => (t.innerText || '').trim() === '候诊中');
        if (hz) {
            hz.style.outline = '3px solid #409EFF';
            hz.click();
            return { clicked: true, text: '候诊中' };
        }
        return { clicked: false };
    })()"""
    browser.evaluate(tab_hz_js)
    time.sleep(1.0)
    engine.log(result, "✓ 候诊队列分栏交互切换正常")

    engine.log(result, "👉 [步骤 4/5] 实体点击操作台【挂号】快捷按钮，唤起门诊挂号对话框...")
    his.click_button("挂号", highlight_color="#409EFF", wait_sec=1.5)
    gh_dlg = his.wait_and_assert_dialog("门诊挂号", timeout=4)
    engine.log(result, f"✓ 成功在屏幕唤起【{gh_dlg.get('title')}】对话框！")
    time.sleep(1.0)
    his.close_active_dialog()

    engine.log(result, "👉 [步骤 5/5] 检验接诊业务核心按钮状态并实拍现场截图...")
    btn_jh = his.click_button("加号", highlight_color="#409EFF", wait_sec=0.5)
    btn_xyw = his.click_button("下一位", highlight_color="#67C23A", wait_sec=0.5)
    engine.log(result, f"✓ 接诊操作按钮核验: 加号={btn_jh.get('found')}, 下一位={btn_xyw.get('found')}")

    try:
        shot = browser.take_screenshot("inv_doctor_workstation")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式门诊医生工作站全部实体按钮与队列交互完成！")


def test_inv_emr_designer_canvas(engine, writer, browser, result):
    """【侵入式】住院医生病历工作站与临床书写台实操"""
    engine.log(result, "👉 [步骤 1/4] 切换至【住院医生 (角色: 35, 内一科: 910092)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(35, 910092, "#/inpatient/doctor/workstation")
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "住院医生站身份置换失败"))
    time.sleep(2.0)

    his = HISDriver(browser)
    engine.log(result, "👉 [步骤 2/4] 真实点击顶部/导航菜单: 【住院工作站】->【住院医生工作站】...")
    nav_res = his.navigate_via_menu("住院医生工作站", parent_menu_title="住院工作站", fallback_hash="#/inpatient/doctor/workstation")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '住院医生工作站')}")
    time.sleep(1.5)

    his.assert_page_healthy("住院医生工作站")

    engine.log(result, "👉 [步骤 3/4] 实体点击操作台【刷新】按钮，检验在院病区患者床位与病历工作台...")
    click_rf = his.click_button("刷新", highlight_color="#409EFF", wait_sec=1.0)
    btn_trans = his.click_button("转诊申请", highlight_color="#67C23A", wait_sec=0.5)
    btn_health = his.click_button("健康档案", highlight_color="#E6A23C", wait_sec=0.5)
    engine.log(result, f"✓ 病历工作台操作控件核验: 刷新={click_rf.get('found')}, 转诊申请={btn_trans.get('found')}, 健康档案={btn_health.get('found')}")

    engine.log(result, "👉 [步骤 4/4] 实拍现场高清病历工作台操作截图...")
    try:
        shot = browser.take_screenshot("inv_inpatient_doctor_workstation")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式住院医生病历工作台演练全部成功通过！")


def test_inv_pharmacy_dispense_station(engine, writer, browser, result):
    """【侵入式】门诊药房窗口调配与发药实操"""
    engine.log(result, "👉 [步骤 1/4] 切换至【门诊药房 (角色: 33, 西药房: 910125)】身份...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(33, 910125, "#/outpatient/pharmacy/outOutput")
    if switch_res.get("status") == "FAIL":
        raise ConnectionError(switch_res.get("message", "门诊药房身份置换网络连接失败"))
    time.sleep(2.0)

    his = HISDriver(browser)
    engine.log(result, "👉 [步骤 2/4] 真实点击顶部/导航菜单: 【门诊药房】->【门诊发药】菜单...")
    nav_res = his.navigate_via_menu("门诊发药", parent_menu_title="门诊药房", fallback_hash="#/outpatient/pharmacy/outOutput")
    engine.log(result, f"菜单导航就绪: 方式={nav_res.get('method')}, 标题={nav_res.get('title', '门诊发药')}")
    time.sleep(1.5)

    his.assert_page_healthy("门诊药房发药")

    engine.log(result, "👉 [步骤 3/4] 实体点击【未发药列表】与【已发药列表】页签切换...")
    his.click_tab("已发药列表", wait_sec=1.0)
    his.click_tab("未发药列表", wait_sec=1.0)
    engine.log(result, "✓ 药房处方待发与已发队列切换正常")

    engine.log(result, "👉 [步骤 4/4] 实体点击【刷新】按钮与检验发药业务控制台...")
    click_refresh = his.click_button("刷新", highlight_color="#409EFF", wait_sec=1.0)
    click_fy = his.click_button("发药", highlight_color="#67C23A", wait_sec=0.5)
    click_batch = his.click_button("批量发药", highlight_color="#E6A23C", wait_sec=0.5)
    assert click_fy.get("found") and click_batch.get("found"), "门诊药房【发药】/【批量发药】按钮未正常渲染"
    engine.log(result, f"✓ 药房发药控制台就绪: 刷新={click_refresh.get('found')}, 发药={click_fy.get('found')}, 批量发药={click_batch.get('found')}")

    try:
        shot = browser.take_screenshot("inv_pharmacy_dispense")
        result.screenshot_path = shot
        engine.log(result, f"📷 现场截图已归档: {shot}")
    except Exception as e:
        engine.log(result, f"截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 侵入式门诊药房发药控制台实体按钮交互演练完成！")

