"""AI copilot: Claude, ChatGPT or Gemini that understands and (with permission) operates the
current page."""

from .panel import apply_pending_changes, render
from .providers import PROVIDERS, ProviderError, Reply, call, list_models
from .registry import install, start_run

__all__ = ["install", "start_run", "render", "apply_pending_changes", "PROVIDERS", "call",
           "list_models", "Reply", "ProviderError"]
