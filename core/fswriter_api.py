"""
FSWriter WebAssembly API Wrapper.
Directly interfaces with the in-browser WebAssembly editor instance, exactly
mirroring the WinForms FSWriterControl / DCWriterControl API used in fs.testrunner.
"""

from typing import Any, Dict, List, Optional
import json
import base64

class FSWriterAPI:
    def __init__(self, browser_driver):
        self.driver = browser_driver

    def is_writer_ready(self) -> bool:
        """Check if WebAssembly FSWriter control is mounted and loaded."""
        js = """
        (() => {
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            return !!(writer && (writer.FSExecuteCommand || writer.AboutControl));
        })()
        """
        return bool(self.driver.evaluate(js))

    def wait_for_ready(self, timeout_sec: int = 15) -> bool:
        """Wait until FSWriter runtime is fully initialized."""
        import time
        start = time.time()
        while time.time() - start < timeout_sec:
            if self.is_writer_ready():
                return True
            time.sleep(0.5)
        return False

    def about_control(self) -> str:
        """Get version and license info of the FSWriter WebAssembly control."""
        js = """
        (() => {
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (writer && typeof writer.AboutControl === 'function') {
                return String(writer.AboutControl());
            }
            return 'FSWriter WebAssembly Control Ready';
        })()
        """
        return str(self.driver.evaluate(js))

    def execute_command(self, command: str, show_dialog: bool = False, param: Any = None) -> Any:
        """
        Execute native FSWriter command.
        Mirrors C# WinForms: this.writerControl.FSExecuteCommand(command, show_dialog, param);
        """
        param_json = json.dumps(param) if param is not None else "null"
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer || typeof writer.FSExecuteCommand !== 'function') {{
                throw new Error("FSWriter.FSExecuteCommand is not available");
            }}
            const param = {param_json};
            return writer.FSExecuteCommand('{command}', {'true' if show_dialog else 'false'}, param);
        }})()
        """
        return self.driver.evaluate(js)

    def insert_element(self, element_type: str, attributes: Dict[str, Any]) -> bool:
        """
        Insert a medical record element (e.g., XTextInputFieldElement, XTextRadioBoxElement).
        """
        attrs_json = json.dumps(attributes, ensure_ascii=False)
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return false;
            const attrs = {attrs_json};
            
            // Prefer InsertInputField or FSExecuteCommand
            if (typeof writer.InsertElement === 'function') {{
                return writer.InsertElement('{element_type}', attrs);
            }}
            if (writer.FSExecuteCommand) {{
                return writer.FSExecuteCommand('InsertInputField', false, attrs);
            }}
            return false;
        }})()
        """
        return bool(self.driver.evaluate(js))

    def get_element_by_id(self, elem_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve element attributes by ID."""
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer || typeof writer.GetElementById !== 'function') return null;
            const elem = writer.GetElementById('{elem_id}');
            if (!elem) return null;
            
            // Extract common EMR element properties
            const props = {{
                ID: elem.ID || '{elem_id}',
                Name: elem.Name,
                Text: elem.Text,
                InnerText: elem.InnerText,
                DataElementCode: elem.DataElementCode,
                UnitText: elem.UnitText,
                StartBorderText: elem.StartBorderText,
                EndBorderText: elem.EndBorderText,
                Required: elem.Required,
                ContentReadonly: elem.ContentReadonly,
                UserEditable: elem.UserEditable,
                Deleteable: elem.Deleteable,
                MaxLength: elem.MaxLength,
                MinValue: elem.MinValue,
                MaxValue: elem.MaxValue,
                MaxDecimalDigits: elem.MaxDecimalDigits,
                ValueExpression: elem.ValueExpression,
                VisibleExpression: elem.VisibleExpression,
                PrintVisibility: elem.PrintVisibility,
                HiddenPrintWhenEmpty: elem.HiddenPrintWhenEmpty
            }};
            return props;
        }})()
        """
        return self.driver.evaluate(js)

    def set_element_value(self, elem_id: str, value: str) -> bool:
        """
        Set element inner value by ID.
        Mirrors C#: writerControl.SetElementInnerValueStringByID(id, val);
        """
        val_escaped = json.dumps(value, ensure_ascii=False)
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return false;
            const val = {val_escaped};
            if (typeof writer.SetElementInnerValueStringByID === 'function') {{
                writer.SetElementInnerValueStringByID('{elem_id}', val);
                return true;
            }}
            return false;
        }})()
        """
        return bool(self.driver.evaluate(js))

    def set_element_text(self, elem_id: str, text: str) -> bool:
        """Set element display text by ID."""
        text_escaped = json.dumps(text, ensure_ascii=False)
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return false;
            const txt = {text_escaped};
            if (typeof writer.SetElementTextByID === 'function') {{
                writer.SetElementTextByID('{elem_id}', txt);
                return true;
            }}
            return false;
        }})()
        """
        return bool(self.driver.evaluate(js))

    def set_element_properties(self, elem_id: str, properties: Dict[str, Any]) -> bool:
        """Update element properties."""
        props_json = json.dumps(properties, ensure_ascii=False)
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return false;
            const props = {props_json};
            if (typeof writer.SetElementPropertiesById === 'function') {{
                writer.SetElementPropertiesById('{elem_id}', props, true);
                return true;
            }}
            const elem = writer.GetElementById ? writer.GetElementById('{elem_id}') : null;
            if (elem && typeof writer.SetElementProperties === 'function') {{
                writer.SetElementProperties(elem, props);
                return true;
            }}
            return false;
        }})()
        """
        return bool(self.driver.evaluate(js))

    def get_all_input_fields(self) -> List[Dict[str, Any]]:
        """List all input field elements in the current document."""
        js = """
        (() => {
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer || typeof writer.GetAllInputFields !== 'function') return [];
            const fields = writer.GetAllInputFields() || [];
            const res = [];
            for (let i = 0; i < fields.length; i++) {
                const f = fields[i];
                res.push({
                    ID: f.ID,
                    Name: f.Name,
                    DataElementCode: f.DataElementCode,
                    Text: f.Text,
                    InnerText: f.InnerText,
                    UnitText: f.UnitText,
                    Required: f.Required
                });
            }
            return res;
        })()
        """
        res = self.driver.evaluate(js)
        return res if isinstance(res, list) else []

    def get_document_xml(self) -> str:
        """
        Export and return the full EMR XML text.
        Mirrors C#: writerControl.SaveDocumentToBase64String() or SaveXML()
        """
        js = """
        (() => {
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return '';
            
            if (typeof writer.SaveXML === 'function') {
                return writer.SaveXML();
            }
            if (typeof writer.SaveDocumentToBase64String === 'function') {
                const b64 = writer.SaveDocumentToBase64String();
                try {
                    // Base64 decode in browser
                    return decodeURIComponent(escape(window.atob(b64)));
                } catch(e) {
                    return b64;
                }
            }
            if (typeof writer.GetXML === 'function') {
                return writer.GetXML();
            }
            return '';
        })()
        """
        val = self.driver.evaluate(js)
        if not val:
            return ""
        # If it returned raw base64, decode in python
        if val.startswith("PD94b") or val.startswith("77u/"):
            try:
                return base64.b64decode(val).decode("utf-8")
            except Exception:
                pass
        return str(val)

    def load_document_xml(self, xml_content: str) -> bool:
        """Load document from XML string."""
        xml_escaped = json.dumps(xml_content, ensure_ascii=False)
        js = f"""
        (() => {{
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (!writer) return false;
            const xml = {xml_escaped};
            if (typeof writer.LoadDocumentFromString === 'function') {{
                writer.LoadDocumentFromString(xml);
                return true;
            }}
            return false;
        }})()
        """
        return bool(self.driver.evaluate(js))

    def get_body_text(self) -> str:
        """Get plain text content of document."""
        js = """
        (() => {
            const writer = document.querySelector('.emr-writer') || document.querySelector('[fstype="WriterControlForWASM"]');
            if (writer && typeof writer.BodyText === 'function') {
                return writer.BodyText();
            }
            return '';
        })()
        """
        return str(self.driver.evaluate(js) or "")
