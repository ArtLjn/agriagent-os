"""兼容入口：意图路由已迁移到 app.agent.router.intent。"""

from app.agent.router.intent import IntentType, classify_intent, get_greeting_reply

__all__ = ["IntentType", "classify_intent", "get_greeting_reply"]
