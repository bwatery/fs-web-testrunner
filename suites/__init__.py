"""
FS Web TestRunner - Full Suite Registry
Registers both:
1. 【👀 侵入式·视觉观察套件】(Invasive / User Observation Suite)
   - Real interactive UI, route hopping, dialog clicking, live screenshots for human user viewing.
2. 【🤖 非侵入式·AI静默验证套件】(Non-Invasive / AI Verification Suite)
   - Zero UI disruption, direct backend REST API contracts, Oracle DB persistence, mathematical rules, XML schema.
"""

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from fs_web_testrunner.core.test_engine import TestEngine

def register_all_suites(engine: "TestEngine"):
    # 1. 核心套件 A: 【👀 侵入式·视觉演示套件】(针对用户，大屏UI演示)
    from .test_suite_invasive import register_tests as r_invasive
    r_invasive(engine)

    # 2. 核心套件 B: 【🤖 非侵入式·AI静默验证套件】(针对AI，快速代码质检)
    from .test_suite_non_invasive import register_tests as r_non_invasive
    r_non_invasive(engine)

    # 3. 原始 EMR 控件设计器套件 (归入非侵入/静默内核)
    from .test_01_text_field import register_tests as r_text
    from .test_02_numeric_range import register_tests as r_num
    from .test_03_radio_checkbox import register_tests as r_choice
    from .test_04_medical_controls import register_tests as r_med
    from .test_05_expressions import register_tests as r_expr
    from .test_06_xml_persistence import register_tests as r_xml

    r_text(engine)
    r_num(engine)
    r_choice(engine)
    r_med(engine)
    r_expr(engine)
    r_xml(engine)

    # 4. 医嘱闭环全流程实测套件 (医生开单 -> 护士校对 -> 药房发药 -> 费用穿透)
    from .test_suite_cpoe_closed_loop import register_tests as r_cpoe
    r_cpoe(engine)

    # 5. 住院全流程实测套件 (兼容老测试用例引用)
    from .test_his_03_inpatient import register_tests as r_inpatient
    r_inpatient(engine)

    # 6. 住院全生命周期大闭环套件 (入院登记 -> 预交金 -> 开嘱核对 -> 药房发药 -> 退药退费 -> 出院结算)
    from .test_suite_inpatient_full_lifecycle import register_tests as r_lifecycle
    r_lifecycle(engine)

    # 7. 住院业务规则与核心流转套件 (医嘱时间继承、同组频次用法一致性、状态机、退药退费)
    from .test_suite_inpatient_business_rules import register_tests as r_rules
    r_rules(engine)

    # 8. 门诊全生命周期大闭环实测与业务规则套件 (建档 -> 挂号 -> 分诊 -> 开嘱 -> 收费 -> 退费 -> 退号 -> 状态机)
    from .test_suite_outpatient_full_lifecycle import register_tests as r_op_lifecycle
    r_op_lifecycle(engine)

    # 9. 医院六大核心工作站模块测试套件 (住院工作站、门诊工作站、药房、门诊收费、住院收费、住院护士)
    from .test_suite_workstations_modular import register_workstation_modular_tests
    register_workstation_modular_tests(engine)

    # 10. 医院上线测试用例追踪表全量业务套件 (覆盖Excel追踪表359项临床与财务全生命周期用例)
    from .test_suite_excel_cases import register_excel_tests
    register_excel_tests(engine)

    # 11. 【新】根据Excel用例追踪表深度生成的六大业务域专属真实页面UI实测套件 (覆盖门诊、住院、EMR、收费医保、药房药库、医技底座)
    from .test_suite_ui_outpatient_excel import register_outpatient_excel_tests
    from .test_suite_ui_inpatient_excel import register_inpatient_excel_tests
    from .test_suite_ui_emr_excel import register_emr_excel_tests
    from .test_suite_ui_billing_excel import register_billing_excel_tests
    from .test_suite_ui_pharmacy_excel import register_pharmacy_excel_tests
    from .test_suite_ui_medtech_excel import register_medtech_excel_tests

    register_outpatient_excel_tests(engine)
    register_inpatient_excel_tests(engine)
    register_emr_excel_tests(engine)
    register_billing_excel_tests(engine)
    register_pharmacy_excel_tests(engine)
    register_medtech_excel_tests(engine)


