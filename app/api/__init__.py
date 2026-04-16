from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.scheduler import router as scheduler_router

__all__ = ["recommendations_router", "feedback_router", "scheduler_router"]