"""FastAPI Dispatcher Service for MIRA."""

from mira.dispatcher.main import app, run
from mira.dispatcher.routes import router

__all__ = ["app", "run", "router"]
