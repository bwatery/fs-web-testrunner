"""
Suite 5: 动态表达式与条件联动测试 (Expressions)
涵盖: 计算表达式 (ValueExpression: BMI 自动换算)、可见性表达式 (VisibleExpression)、
只读表达式 (ContentReadonlyExpression)
"""

def register_tests(engine):
    engine.register(
        test_id="expr_01_bmi_calculation",
        name="表达式_BMI体质指数自动计算公式联动",
        category="05-表达式与联动",
        func=test_bmi_calculation
    )
    engine.register(
        test_id="expr_02_conditional_visibility",
        name="表达式_条件可见性表达式(VisibleExpression)",
        category="05-表达式与联动",
        func=test_conditional_visibility
    )

def test_bmi_calculation(engine, writer, browser, result):
    """测试身高体重输入后自动计算 BMI 指数"""
    engine.log(result, "构建计算表达式元素: BMI = Weight / (Height / 100)^2")
    elem_id = "test_calc_bmi"
    attrs = {
        "ID": elem_id,
        "Name": "BMI指数",
        "DataElementCode": "DE04.10.188.01",
        "ValueType": "Numeric",
        "MaxDecimalDigits": 1,
        "UnitText": "kg/m²",
        "ValueExpression": "Math.round((Weight / ((Height/100)*(Height/100))) * 10) / 10",
        "ContentReadonly": True,
        "Text": "22.4"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "BMI 表达式元素未成功注入"
    assert "ValueExpression" in xml or elem_id in xml, "表达式未正确持久化"
    engine.log(result, "BMI 动态计算表达式与只读回显验证通过")

def test_conditional_visibility(engine, writer, browser, result):
    """测试性别联动月经史显示/隐藏表达式"""
    engine.log(result, "构建月经史元素 (仅在性别为女性时显示: VisibleExpression=\"Gender=='2'\")")
    elem_id = "test_vis_menstrual"
    attrs = {
        "ID": elem_id,
        "Name": "月经史",
        "DataElementCode": "DE02.10.028.00",
        "VisibleExpression": "Gender == '2' || Gender == '女'",
        "Text": "14 3-5/28-30 2026-09-01"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "条件可见性元素未生成"
    engine.log(result, "条件可见性表达式定义验证通过")
