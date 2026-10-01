"""
WebSocket Event Dispatcher Router.
Provides real-time, bi-directional telemetry to browser dashboard clients.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fs_web_testrunner.core.logger import get_logger
from fs_web_testrunner.web_runner.state import ws_manager

router = APIRouter(tags=["websocket"])
logger = get_logger("websocket")

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Client WebSocket connection endpoint for real-time dashboard events."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive & receive any incoming control messages from client
            msg = await websocket.receive_text()
            logger.debug(f"Received WS message: {msg}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection error: {e}")
        ws_manager.disconnect(websocket)
