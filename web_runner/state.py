"""
Shared Application State, Engine Registry & WebSocket Event Dispatcher.
Follows Clean Architecture pattern separating core domain state from HTTP route handlers.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from fastapi import WebSocket
from fs_web_testrunner.core.test_engine import TestEngine
from fs_web_testrunner.core.business_rules_manager import BusinessRulesManager
from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.suites import register_all_suites

logger = get_logger("state")

class WebSocketManager:
    """Manages active WebSocket connections and thread-safe event broadcasting."""
    def __init__(self):
        self.active_websockets: List[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_websockets)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_websockets)}")

    def broadcast_sync(self, msg: Dict[str, Any]):
        """Thread-safe event broadcast to all connected WebSocket clients."""
        if not self.loop:
            return
        text = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.active_websockets):
            try:
                asyncio.run_coroutine_threadsafe(ws.send_text(text), self.loop)
            except Exception as e:
                logger.debug(f"Failed to send to client: {e}")

# Shared Singletons
ws_manager = WebSocketManager()
engine = TestEngine(headless=False, login_mode="A", username="admin", password="admin123")
register_all_suites(engine)
rules_mgr = BusinessRulesManager()

# Subscribe WebSocket event broadcast to TestEngine execution events
engine.subscribe(ws_manager.broadcast_sync)

def normalize_category(cat: str, test_id: str) -> str:
    """Map any technical/raw category into canonical hospital business domains."""
    c = cat.lower()
    t = test_id.lower()
    if '收费' in cat or '医保' in cat or 'billing' in t or 'charge' in t:
        return '收费与医保'
    if '医技' in cat or 'lis' in t or 'pacs' in t or 'med_tech' in t:
        return '医技交互'
    if '接口' in cat or '集成' in cat or 'integration' in t:
        return '接口集成'
    if 'cpoe' in t or '医嘱' in cat or 'order' in t:
        return '医嘱闭环'
    if '药房' in cat or '药库' in cat or 'pharmacy' in t or 'stock' in t or 'dispense' in t:
        return '药房药库'
    if '门诊' in cat or 'outpatient' in t or '患者主索引' in cat or '建档' in cat:
        return '门诊业务'
    if '住院' in cat or '护理' in cat or 'inpatient' in t or 'settle' in t or 'fee' in t or 'prepay' in t:
        return '住院业务'
    if '病历' in cat or '文本' in cat or '数值' in cat or '单选' in cat or '专用控件' in cat or '表达式' in cat or 'xml' in cat or 'emr' in t or 'text_' in t or 'num_' in t or 'choice_' in t or 'med_' in t or 'expr_' in t or 'xml_' in t:
        return '电子病历'
    if 'oracle' in c or '底座' in c or '平台' in c or 'api_' in t or 'db_' in t or 'rule_' in t:
        return '系统底座'
    return '系统底座'
