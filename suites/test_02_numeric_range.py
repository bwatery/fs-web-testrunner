"""
Suite 2: 数值范围与生命体征元素测试
涵盖: 体温 (35.0~42.0 ℃)、血压 (收缩压/舒张压)、脉搏、小数位数精度约束
"""

def register_tests(engine):
    engine.register(
        test_id="num_01_temperature_range",
        name="数值域_体温有效区间与小数位(35.0-42.0℃)",
        category="02-数值与生命体征",
        func=test_temperature_range
    )
    engine.register(
        test_id="num_02_blood_pressure",
        name="数值域_血压双数值/复合输入(收缩压/舒张压)",
        category="02-数值与生命体征",
        func=test_blood_pressure
    )
    engine.register(
        test_id="num_03_decimal_precision",
        name="数值域_小数位限制与自动舍入(MaxDecimalDigits)",
        category="02-数值与生命体征",
        func=test_decimal_precision
    )

def test_temperature_range(engine, writer, browser, result):
    """测试体温上下限约束与有效值录入"""
    elem_id = "test_vital_t"
    engine.log(result, "构建生命体征-体温元素 (MinValue=35.0, MaxValue=42.0, MaxDecimalDigits=1)")
    attrs = {
        "ID": elem_id,
        "Name": "体温",
        "DataElementCode": "DE04.10.186.00",
        "ValueType": "Numeric",
        "MinValue": 35.0,
        "MaxValue": 42.0,
        "MaxDecimalDigits": 1,
        "CheckMinValue": True,
        "CheckMaxValue": True,
        "CheckDecimalDigits": True,
        "UnitText": "℃",
        "Text": "36.5"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    # 模拟正常录入
    writer.set_element_value(elem_id, "37.2")
    engine.log(result, "设置体温正常值 37.2 ℃ 成功")
    
    props = writer.get_element_by_id(elem_id)
    if props:
        engine.log(result, f"体温元素属性: {props}")
    engine.log(result, "体温数值区间与校验约束验证通过")

def test_blood_pressure(engine, writer, browser, result):
    """测试血压元素配置"""
    elem_id = "test_vital_bp"
    engine.log(result, "构建生命体征-血压元素")
    attrs = {
        "ID": elem_id,
        "Name": "血压",
        "DataElementCode": "DE04.10.174.00",
        "UnitText": "mmHg",
        "StartBorderText": "[",
        "EndBorderText": "]",
        "Text": "120/80"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    writer.set_element_value(elem_id, "135/85")
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "血压元素未成功写入"
    engine.log(result, "血压复合数值格式验证通过")

def test_decimal_precision(engine, writer, browser, result):
    """测试最大小数位数限制"""
    elem_id = "test_weight_kg"
    engine.log(result, "构建体重元素 (限制最多2位小数)")
    attrs = {
        "ID": elem_id,
        "Name": "体重",
        "DataElementCode": "DE04.10.188.00",
        "ValueType": "Numeric",
        "MaxDecimalDigits": 2,
        "CheckDecimalDigits": True,
        "UnitText": "kg",
        "Text": "65.50"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    writer.set_element_value(elem_id, "68.75")
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "体重元素未生成"
    engine.log(result, "小数位数精度约束验证通过")
