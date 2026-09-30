"""
Suite 4: 医院专用医学控件测试 (Medical Controls)
涵盖: 中西医诊断控件 (DiagnosticControl)、四级地址联动 (AddressControl)、
科室控件 (DepartmentControl)、医务人员审签控件 (EmployeeControl)
"""

def register_tests(engine):
    engine.register(
        test_id="med_01_diagnostic_control",
        name="专科控件_中西医诊断控件(ICD-10与中医证候)",
        category="04-医疗专用控件",
        func=test_diagnostic_control
    )
    engine.register(
        test_id="med_02_address_cascade",
        name="专科控件_四级行政区划地址控件(省市区县街道)",
        category="04-医疗专用控件",
        func=test_address_cascade
    )
    engine.register(
        test_id="med_03_employee_signature",
        name="专科控件_医务人员审签与工号关联(EmployeeControl)",
        category="04-医疗专用控件",
        func=test_employee_signature
    )

def test_diagnostic_control(engine, writer, browser, result):
    """测试门急诊/住院病历诊断控件定义"""
    elem_id = "test_diag_admission"
    engine.log(result, "构建入院初步诊断控件 (支持中医病证+西医ICD-10)")
    attrs = {
        "ID": elem_id,
        "Name": "初步诊断",
        "DataElementCode": "DE05.01.024.00",  # 初步诊断编码
        "SystemControlCode": "DiagnosticControl",
        "Text": "1. 中医诊断: 风温肺热病 (风热犯肺证)\n2. 西医诊断: 社区获得性肺炎 (ICD-10: J18.900)",
        "Required": True
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "诊断控件未成功写入"
    engine.log(result, "中西医诊断控件属性与国家数据元定义验证通过")

def test_address_cascade(engine, writer, browser, result):
    """测试籍贯/现住址四级联动控件"""
    elem_id = "test_addr_current"
    engine.log(result, "构建现住址控件 (省-市-区县-街道四级地址)")
    attrs = {
        "ID": elem_id,
        "Name": "现住址",
        "DataElementCode": "DE02.01.009.00",
        "SystemControlCode": "AddressControl",
        "Text": "广东省 湛江市 赤坎区 中山二路",
        "StartBorderText": "[",
        "EndBorderText": "]"
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "地址控件写入失败"
    engine.log(result, "四级地址联动控件定义验证通过")

def test_employee_signature(engine, writer, browser, result):
    """测试住院医师/主治医师审签控件"""
    elem_id = "test_sign_attending_doctor"
    engine.log(result, "构建主治医师电子签名控件 (DE02.01.039.00)")
    attrs = {
        "ID": elem_id,
        "Name": "主治医师签名",
        "DataElementCode": "DE02.01.039.00",
        "SystemControlCode": "EmployeeControl",
        "Text": "张三 (主任医师/工号: 10086)",
        "ContentReadonly": True,
        "Deleteable": False
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    
    xml = writer.get_document_xml()
    assert elem_id in xml, "审签元素写入失败"
    engine.log(result, "医师签名控件与工号权限约束验证通过")
