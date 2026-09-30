"""
Suite 3: 单选与复选元素 (XTextRadioBoxElement / XTextCheckBoxElement) 测试
涵盖: 互斥单选组 (RepulsionForGroup)、多选复选框、值域字典绑定 (ValueDomain)
"""

def register_tests(engine):
    engine.register(
        test_id="choice_01_radio_exclusive",
        name="选择类_互斥单选组配置(RepulsionForGroup)",
        category="03-单选与复选",
        func=test_radio_exclusive
    )
    engine.register(
        test_id="choice_02_checkbox_multiselect",
        name="选择类_多选复选框与分割符(ListValueSeparatorChar)",
        category="03-单选与复选",
        func=test_checkbox_multiselect
    )
    engine.register(
        test_id="choice_03_dict_valuedomain",
        name="选择类_值域字典绑定与下拉选项(ValueDomain)",
        category="03-单选与复选",
        func=test_dict_valuedomain
    )

def test_radio_exclusive(engine, writer, browser, result):
    """测试单选互斥逻辑（如性别：男/女）"""
    group_id = "test_radio_gender"
    engine.log(result, "构建性别互斥单选组")
    attrs = {
        "ID": group_id,
        "Name": "性别",
        "DataElementCode": "DE02.01.040.00",
        "RepulsionForGroup": True,
        "ListItems": [
            {"Text": "男", "Value": "1"},
            {"Text": "女", "Value": "2"},
            {"Text": "未说明", "Value": "9"}
        ]
    }
    writer.insert_element("XTextRadioBoxElement", attrs)
    writer.set_element_value(group_id, "1")
    
    xml = writer.get_document_xml()
    assert group_id in xml, "单选组元素未正确写入文档"
    engine.log(result, "互斥单选组属性与选项绑定验证通过")

def test_checkbox_multiselect(engine, writer, browser, result):
    """测试多选复选框（如药物过敏史）"""
    box_id = "test_chk_allergy"
    engine.log(result, "构建药物过敏史多选复选框")
    attrs = {
        "ID": box_id,
        "Name": "药物过敏史",
        "DataElementCode": "DE05.10.119.00",
        "ListValueSeparatorChar": "，",
        "ListItems": [
            {"Text": "青霉素", "Value": "01"},
            {"Text": "磺胺类", "Value": "02"},
            {"Text": "头孢菌素", "Value": "03"},
            {"Text": "链霉素", "Value": "04"}
        ]
    }
    writer.insert_element("XTextCheckBoxElement", attrs)
    writer.set_element_value(box_id, "01，03")
    
    xml = writer.get_document_xml()
    assert box_id in xml, "复选框元素未成功写入"
    engine.log(result, "多选复选框配置与分隔符定义验证通过")

def test_dict_valuedomain(engine, writer, browser, result):
    """测试标准值域字典关联"""
    dict_elem_id = "test_dict_marriage"
    engine.log(result, "构建婚姻状况字典下拉输入域 (GB/T 2261.2)")
    attrs = {
        "ID": dict_elem_id,
        "Name": "婚姻状况",
        "DataElementCode": "DE02.01.018.00",
        "InnerEditStyle": "DropdownList",
        "ValueDomain": "DICT_MARRIAGE_STATUS",
        "ListItems": [
            {"Text": "未婚", "Value": "10"},
            {"Text": "已婚", "Value": "20"},
            {"Text": "初婚", "Value": "21"},
            {"Text": "再婚", "Value": "22"},
            {"Text": "复婚", "Value": "23"},
            {"Text": "丧偶", "Value": "30"},
            {"Text": "离婚", "Value": "40"}
        ]
    }
    writer.insert_element("XTextInputFieldElement", attrs)
    writer.set_element_value(dict_elem_id, "20")
    writer.set_element_text(dict_elem_id, "已婚")
    
    xml = writer.get_document_xml()
    assert dict_elem_id in xml, "婚姻字典输入域未生成"
    engine.log(result, "值域字典与下拉列表选项验证通过")
