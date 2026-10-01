"""
Modular WebRunner Routers package.
"""
from .tests import router as tests_router
from .rules import router as rules_router
from .validator import router as validator_router
from .system import router as system_router
from .websocket import router as ws_router
from .ai import router as ai_router

__all__ = [
    "tests_router",
    "rules_router",
    "validator_router",
    "system_router",
    "ws_router",
    "ai_router",
]
