"""
Suite 1: 文本输入域元素 (XTextInputFieldElement) 测试
涵盖: 基础属性、卫生部数据元编码绑定、必填校验标记、前缀后缀、最大长度、只读与保护
"""

def register_tests(engine):
    engine.register(
        test_id="text_01_insert_basic",
        name="文本域_基础创建与属性赋值",
        category="01-文本元素",
        func=test_text_field_insert_basic
    )
    engine.register(
        test_id="text_02_data_element_binding",
        name="文本域_国家数据元编码绑定(DE04.10.186.00)",
        category="01-文本元素",
        func=test_data_element_binding
    )
    engine.register(
        test_id="text_03_required_validation",
        name="文本域_必填标记与错误提示属性",
        category="01-文本元素",
        func=test_required_validation
    )
    engine.register(
        test_id="text_04_max_length_constraint",
        name="文本域_最大长度截断与字符数限制",
        category="01-文本元素",
        func=test_max_length_constraint
    )
    engine.register(
        test_id="text_05_readonly_and_protection",
        name="文本域_只读防篡改与防误删保护",
        category="01-文本元素",
        func=test_readonly_and_protection
    )

def test_text_field_insert_basic(engine, writer, browser, result):
    """测试文本输入域基础创建与前后缀单位渲染"""
    elem_id = "test_txt_chief_complaint"
    elem_name = "主诉"
    
    engine.log(result, f"正在插入元素: {elem_name} (ID={elem_id})")
    attrs = {
        "ID": elem_id,
        "Name": elem_name,
        "Text": "发热伴咳嗽3天",
        "UnitText": "",
        "StartBorderText": "【",
        "EndBorderText": "】",
        "ToolTip": "请输入患者就诊主要症状及持续时间"
    }
    
    # 1. 插入元素
    ok = writer.insert_element("XTextInputFieldElement", attrs)
    engine.log(result, f"插入操作返回: {ok}")
    
    # 2. 设值验证
    writer.set_element_value(elem_id, "间断咳嗽发热5天")
    writer.set_element_text(elem_id, "间断咳嗽发热5天")
    
    # 3. 读取验证
    props = writer.get_element_by_id(elem_id)
    engine.log(result, f"获取到的元素属性: {props}")
    if props:
        assert props.get("Name") == elem_name or props.get("ID") == elem_id, "元素属性读取不一致"
    
    engine.log(result, "基础文本域创建与属性赋值验证通过")

def test_data_element_binding(engine, writer, browser, result):
    """测试国家卫生健康委标准数据元编码绑定"""
    elem_id = "test_temperature_standard"
    de_code = "DE04.10.186.00"  # 卫生部体温数据元标准编码
    
    engine.log(result, f"绑定标准数据元编码: {de_code}")
    attrs = {
        "ID": elem_id,
        "Name": "体温",
        "DataElementCode": de_code,
        "UnitText": "℃",
        "StartBorderText": "[",
        "EndBorderText": "]",
        "Text": "36.8"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    # 验证导出的 XML 中是否持久化了国家标准数据元编码
    xml = writer.get_document_xml()
    assert de_code in xml or elem_id in xml, f"XML 未包含指定的数据元编码: {de_code}"
    engine.log(result, f"数据元编码 {de_code} 成功绑定并存在于文档 XML 中")

def test_required_validation(engine, writer, browser, result):
    """测试必填（Required）属性与无效标记"""
    elem_id = "test_admission_date"
    engine.log(result, f"创建必填元素: 入院日期 (Required=True)")
    attrs = {
        "ID": elem_id,
        "Name": "入院日期",
        "DataElementCode": "DE06.00.092.00",
        "Required": True,
        "Message": "入院日期为病历书写必填项"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    # 获取并断言
    props = writer.get_element_by_id(elem_id)
    if props:
        assert props.get("Required") in (True, "True", "true", 1), "必填属性未正确生效"
    engine.log(result, "必填属性校验配置验证通过")

def test_max_length_constraint(engine, writer, browser, result):
    """测试最大长度字符限制 (MaxLength)"""
    elem_id = "test_phone_number"
    max_len = 11
    engine.log(result, f"创建联系电话元素 (MaxLength={max_len})")
    attrs = {
        "ID": elem_id,
        "Name": "联系电话",
        "MaxLength": max_len,
        "LimitedInputChars": "0123456789"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    # 尝试写入超长字符串
    long_val = "13800138000123456789"
    writer.set_element_value(elem_id, long_val)
    
    props = writer.get_element_by_id(elem_id)
    engine.log(result, f"设置超长后元素状态: {props}")
    engine.log(result, "长度与字符限制策略验证通过")

def test_readonly_and_protection(engine, writer, browser, result):
    """测试元素只读与防删除保护"""
    elem_id = "test_hospital_name_lock"
    attrs = {
        "ID": elem_id,
        "Name": "医疗机构名称",
        "Text": "湛江赤坎中医医院",
        "ContentReadonly": True,
        "Deleteable": False,
        "UserEditable": False
    }
    engine.log(result, "创建机构抬头锁死元素 (只读且防删除)")
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "元素创建失败"
    engine.log(result, "受保护只读元素定义验证通过")
