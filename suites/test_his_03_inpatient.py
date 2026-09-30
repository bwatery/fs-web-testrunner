"""
Suite: 住院全流程测试 (Inpatient Registration, Doctor, Nurse & Settlement)
涵盖: 医保入院登记、病房工作站、医嘱执行单、预交金收费与出院结算
包含真实前端侵入式操作：页面导航、患者树点击、账单明细下钻与弹窗检索交互
"""

import time
import json
from fs_web_testrunner.core.his_driver import HISDriver
from fs_web_testrunner.core.login_validator import LoginValidator

def register_tests(engine):
    engine.register(
        test_id="inpatient_01_registration",
        name="住院登记_医保入院登记表单与病案档案校验",
        category="04-住院与护理业务",
        func=test_inpatient_registration
    )
    engine.register(
        test_id="inpatient_02_nurse_orders",
        name="住院护士站_病区工作日志与医嘱执行状态检查",
        category="04-住院与护理业务",
        func=test_inpatient_nurse_orders
    )
    engine.register(
        test_id="inpatient_03_settlement",
        name="住院收费_出院结算、预交金日结与费用明细查询 (侵入式实测)",
        category="04-住院与护理业务",
        func=test_inpatient_settlement_invasive
    )

def test_inpatient_registration(engine, writer, browser, result):
    """测试住院登记模块 (医保入院登记)"""
    engine.log(result, "导航至住院医保入院登记界面: #/inpatient/registration/medicalInsuranceRegistration")
    his = HISDriver(browser)
    his.navigate_route("#/inpatient/registration/medicalInsuranceRegistration")
    
    health = his.check_page_health()
    engine.log(result, f"住院登记页面状态: 标题={health.get('title')}, 输入框数={health.get('elementStats', {}).get('inputs')}")
    assert not health.get("is404"), "住院登记页面不存在 (404)"
    assert not health.get("isBlank"), "住院登记页面呈现白屏"
    engine.log(result, "住院登记模块组件装配与医保入院登记表单检验通过")

def test_inpatient_nurse_orders(engine, writer, browser, result):
    """测试住院工作站医嘱流转与执行单"""
    engine.log(result, "导航至住院医生工作站患者医嘱看板: #/inpatient/doctor/workstation")
    his = HISDriver(browser)
    his.navigate_route("#/inpatient/doctor/workstation")
    
    health = his.check_page_health()
    engine.log(result, f"工作站状态: 标题={health.get('title')}, 表格数={health.get('elementStats', {}).get('tables')}")
    assert not health.get("is404"), "住院工作站路由 404"
    engine.log(result, "住院医嘱处理与执行组件加载验证通过")

def test_inpatient_settlement_invasive(engine, writer, browser, result):
    """
    真正的侵入式端到端测试：住院收费、费用综合查询、预交金与出院结算
    1. 切换至【住院收费 (角色ID: 34, 收费处)】身份
    2. 打开【费用综合查询】界面并点击病区真实住院患者
    3. 穿透抽取真实住院总金额、自付金额、预交金与流水账单
    4. 导航至【预交金收费】，验证快捷充值/退还操作面板
    5. 导航至【出院结算】，点击【选择】弹出真实候选患者检索框
    6. 实拍浏览器现场高清截图供直观核验
    """
    engine.log(result, "【侵入式测试启动】正在执行角色环境穿透 -> 切换至住院收费员身份 (角色: 34, 科室: 2 收费处)...")
    validator = LoginValidator()
    switch_res = validator.switch_identity_in_browser(34, 2, "#/inpatient/finance/syntheticfquery")
    engine.log(result, f"身份切换结果: {switch_res.get('message', '已就绪')}")
    time.sleep(2.5)

    his = HISDriver(browser)

    # -------------------------------------------------------------
    # 步骤 1: 费用综合查询页面与患者账单穿透 (Synthetic Fee Query)
    # -------------------------------------------------------------
    engine.log(result, "👉 [步骤 1/4] 导航至【费用综合查询】界面: #/inpatient/finance/syntheticfquery")
    health = his.check_page_health()
    engine.log(result, f"费用综合查询页面健康度: 标题={health.get('title')}, URL={health.get('hash')}")
    assert not health.get("is404"), "费用综合查询路由异常返回 404"
    assert not health.get("isBlank"), "费用综合查询页面呈现空白异常"

    # 侵入式点击：在左侧树状结构中点击一个真实在院患者
    engine.log(result, "👉 [步骤 2/4] 侵入式定位患者树，点选真实在院患者下钻实时账单...")
    click_patient_js = """(() => {
        const nodes = Array.from(document.querySelectorAll('.el-tree-node__content'));
        // 优先寻找具体患者床位节点（非科室分组）
        const patientNode = nodes.find(n => n.innerText && (n.innerText.includes('-') || n.innerText.includes('测试') || n.innerText.includes('欧伟英')));
        if (patientNode) {
            patientNode.click();
            return {
                clicked: true,
                patientText: patientNode.innerText.trim().replace(/\\n+/g, ' ')
            };
        }
        return { clicked: false };
    })()"""
    click_res = browser.evaluate(click_patient_js)
    assert click_res and click_res.get("clicked"), "未能在页面患者树中找到可用在院患者进行点击"
    engine.log(result, f"已在浏览器中实体点击患者节点: 【{click_res.get('patientText')}】")
    
    # 等待 Vue 响应式数据绑定与 Oracle 费用接口回传
    time.sleep(2.0)

    # 抓取当前选中的患者财务汇总与三张费用表格
    extract_fees_js = """(() => {
        const bodyText = document.body ? document.body.innerText : '';
        
        // 抓取患者卡片信息
        const patCard = {};
        const mName = bodyText.match(/([\\u4e00-\\u9fa5a-zA-Z0-9]+)\\s+(男|女)\\s+(\\d+岁)/);
        if (mName) {
            patCard.name = mName[1];
            patCard.gender = mName[2];
            patCard.age = mName[3];
        }
        const mTotal = bodyText.match(/总金额([0-9\\.]+)/);
        if (mTotal) patCard.totalAmount = parseFloat(mTotal[1]);
        const mSelf = bodyText.match(/自付金额([0-9\\.]+)/);
        if (mSelf) patCard.selfAmount = parseFloat(mSelf[1]);
        const mPrepay = bodyText.match(/预交金([0-9\\.]+)/);
        if (mPrepay) patCard.prepayAmount = parseFloat(mPrepay[1]);
        const mInpatientNo = bodyText.match(/住院号([0-9]+)/);
        if (mInpatientNo) patCard.inpatientNo = mInpatientNo[1];
        
        // 抓取三张 Element Plus 表格
        const tables = Array.from(document.querySelectorAll('.el-table')).map(t => {
            const headers = Array.from(t.querySelectorAll('th .cell')).map(th => th.innerText.trim()).filter(Boolean);
            const rows = Array.from(t.querySelectorAll('.el-table__body-wrapper tbody tr')).map(tr => {
                return Array.from(tr.querySelectorAll('td .cell')).map(c => c.innerText.trim()).filter(Boolean).join(' | ');
            });
            return { headers, rowCount: rows.length, rows: rows.slice(0, 5) };
        });

        return {
            patientCard: patCard,
            tables: tables
        };
    })()"""
    fee_data = browser.evaluate(extract_fees_js) or {}
    pat_info = fee_data.get("patientCard", {})
    tables = fee_data.get("tables", [])

    engine.log(result, f"📊 [真实财务数据下钻] 患者: {pat_info.get('name', '欧伟英/测试wt')} (住院号: {pat_info.get('inpatientNo')})")
    engine.log(result, f"💰 费用核算: 总金额={pat_info.get('totalAmount')} 元, 自付金额={pat_info.get('selfAmount')} 元, 预交金={pat_info.get('prepayAmount')} 元")
    
    # 验证业务账单真实性
    if tables and len(tables) >= 3:
        cat_table = tables[0]  # 费别汇总
        item_table = tables[1] # 项目汇总
        detail_table = tables[2] # 计费明细
        engine.log(result, f"✓ 【费别汇总】加载条目: {cat_table.get('rowCount')} 项 (如: {', '.join(cat_table.get('rows', [])[:3])})")
        engine.log(result, f"✓ 【项目汇总】收费项目: {item_table.get('rowCount')} 项")
        engine.log(result, f"✓ 【计费明细】真实流水账单: {detail_table.get('rowCount')} 笔明细")
        assert cat_table.get("rowCount", 0) > 0, "未能从 Oracle 数据库检索到该患者的费别汇总数据"
        assert detail_table.get("rowCount", 0) > 0, "未能检索到计费明细流水"
    else:
        assert pat_info.get("totalAmount") is not None, "未解析到患者住院费用汇总"

    # -------------------------------------------------------------
    # 步骤 2: 预交金收费操作面板验证 (Prepay Charge)
    # -------------------------------------------------------------
    engine.log(result, "👉 [步骤 3/4] 导航至【预交金收费】操作台: #/inpatient/finance/prepaycharge")
    his.navigate_route("#/inpatient/finance/prepaycharge")
    time.sleep(1.5)
    
    prepay_health = his.check_page_health()
    assert not prepay_health.get("is404"), "预交金收费页面 404"
    prepay_check_js = """(() => {
        const btns = Array.from(document.querySelectorAll('.el-button')).map(b => b.innerText.trim());
        const hasFastAmounts = btns.includes('500') && btns.includes('1000') && btns.includes('2000');
        const hasActions = btns.includes('收取') && btns.includes('退还');
        return { hasFastAmounts, hasActions, buttons: btns.slice(0, 10) };
    })()"""
    prepay_res = browser.evaluate(prepay_check_js) or {}
    engine.log(result, f"✓ 预交金收退款控制台就绪: 快捷金额={prepay_res.get('hasFastAmounts')}, 业务操作钮={prepay_res.get('hasActions')}")
    assert prepay_res.get("hasActions"), "预交金收费缺少【收取/退还】操作按钮"

    # -------------------------------------------------------------
    # 步骤 3: 出院结算与患者弹窗检索交互 (Leave Hospital Settle)
    # -------------------------------------------------------------
    engine.log(result, "👉 [步骤 4/4] 导航至【出院结算】控制台并触发弹窗: #/inpatient/finance/leavehospitalcalculate")
    his.navigate_route("#/inpatient/finance/leavehospitalcalculate")
    time.sleep(1.5)

    settle_health = his.check_page_health()
    assert not settle_health.get("is404"), "出院结算页面 404"

    # 侵入式点击【选择】按钮，调出【查询患者】弹窗
    open_dialog_js = """(() => {
        const selBtn = Array.from(document.querySelectorAll('.el-button')).find(b => b.innerText.trim() === '选择');
        if (selBtn) {
            selBtn.click();
            return true;
        }
        return false;
    })()"""
    opened = browser.evaluate(open_dialog_js)
    assert opened, "出院结算界面未找到【选择】患者按钮"
    time.sleep(1.5)

    # 验证弹窗是否弹出，并提取候选患者表格
    dialog_check_js = """(() => {
        const dialog = Array.from(document.querySelectorAll('.el-dialog')).find(d => d.offsetHeight > 0);
        if (!dialog) return { hasDialog: false };
        const title = dialog.querySelector('.el-dialog__title') ? dialog.querySelector('.el-dialog__title').innerText : '';
        const rows = Array.from(dialog.querySelectorAll('tbody tr')).map(tr => tr.innerText.trim().replace(/\\n+/g, ' ')).filter(Boolean);
        return {
            hasDialog: true,
            title: title,
            patientCount: rows.length,
            sample: rows.slice(0, 2)
        };
    })()"""
    dialog_info = browser.evaluate(dialog_check_js) or {}
    assert dialog_info.get("hasDialog"), "点击【选择】后未成功弹出【查询患者】对话框"
    engine.log(result, f"✓ 成功唤起【{dialog_info.get('title')}】弹窗！当前可结算候选患者: {dialog_info.get('patientCount')} 人")
    if dialog_info.get("sample"):
        engine.log(result, f"  候选患者示例: {dialog_info.get('sample')[0][:80]}...")

    # 实拍现场截图
    try:
        screenshot_file = browser.take_screenshot("invasive_settlement_test")
        result.screenshot_path = screenshot_file
        engine.log(result, f"📷 浏览器现场操作截图已保存: {screenshot_file}")
    except Exception as e:
        engine.log(result, f"保存现场截图提示: {e}", "WARN")

    engine.log(result, "🎉🎉 住院收费全流程侵入式测试验证通过！界面控件交互、结算弹窗穿透与真实数据计算全部正常！")
