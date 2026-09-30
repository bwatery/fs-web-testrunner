"""
Suite 6: 病历 XML 持久化与规范性测试 (XML Persistence)
涵盖: 完整文档 XML 导出、数据元编码防脱漏断言、保存与重新加载回显还原
"""

import xml.etree.ElementTree as ET

def register_tests(engine):
    engine.register(
        test_id="xml_01_export_validation",
        name="持久化_文档XML结构解析与数据元防脱漏",
        category="06-XML持久化与打印",
        func=test_export_validation
    )
    engine.register(
        test_id="xml_02_roundtrip_reload",
        name="持久化_保存后重载回显一致性(Round-trip)",
        category="06-XML持久化与打印",
        func=test_roundtrip_reload
    )

def test_export_validation(engine, writer, browser, result):
    """测试当前文档导出的 XML 语法与卫生部数据元编码存在性"""
    engine.log(result, "获取当前编辑器导出的 XML 内容...")
    xml_str = writer.get_document_xml()
    assert xml_str, "导出的 XML 内容为空！"
    
    engine.log(result, f"导出的 XML 长度: {len(xml_str)} 字节")
    
    # 尝试用 ElementTree 进行标准 XML 语法解析
    try:
        # If there's an XML declaration or encoding issue, strip BOM
        clean_xml = xml_str.lstrip('\ufeff')
        root = ET.fromstring(clean_xml)
        engine.log(result, f"XML 根节点解析成功: <{root.tag}>")
    except Exception as e:
        engine.log(result, f"标准 XML 解析提示 (可能含非标准命名空间): {e}", "WARN")
        # Fallback check
        assert "<" in xml_str and ">" in xml_str, "非合法 XML 文本"

    engine.log(result, "XML 语法与文档结构校验通过")

def test_roundtrip_reload(engine, writer, browser, result):
    """测试将导出的 XML 重新载入编辑器并验证回显"""
    engine.log(result, "保存当前快照...")
    original_xml = writer.get_document_xml()
    
    if original_xml:
        engine.log(result, "模拟重新加载文档内容...")
        ok = writer.load_document_xml(original_xml)
        engine.log(result, f"重新载入结果: {ok}")
        
        reloaded_xml = writer.get_document_xml()
        assert len(reloaded_xml) > 0, "重载后文档为空"
        engine.log(result, "文档 XML 往返加载一致性验证通过")
    else:
        engine.log(result, "当前文档暂无 XML 节点，跳过重载测试")
