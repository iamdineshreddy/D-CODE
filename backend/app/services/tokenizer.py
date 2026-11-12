import re

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # heuristic: ~4 chars per token for English/code mix
    return max(1, len(text) // 4)


def classify_task(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["debug", "error", "traceback", "fix bug", "failing"]):
        return "debugging"
    if any(k in t for k in ["architecture", "design system", "system design", "schema design"]):
        return "architecture"
    if any(k in t for k in ["test", "pytest", "unit test", "coverage"]):
        return "testing"
    if any(k in t for k in ["document", "readme", "docstring", "explain"]):
        return "documentation"
    if any(k in t for k in ["analyze data", "csv", "dataframe", "pandas", "ml", "train"]):
        return "data_analysis"
    if any(k in t for k in ["image", "screenshot", "vision", "multimodal"]):
        return "multimodal"
    if any(k in t for k in ["research", "compare", "investigate", "explore"]):
        return "research"
    # coding complexity
    if len(text) > 1200 or any(k in t for k in ["refactor", "migrate", "full-stack", "full stack", "implement entire", "build app"]):
        return "complex_coding"
    return "simple_coding"


TASK_MODEL_PREFERENCE = {
    "simple_coding": ["coding", "general"],
    "complex_coding": ["coding", "reasoning"],
    "debugging": ["coding", "reasoning"],
    "research": ["general", "reasoning"],
    "architecture": ["reasoning", "general"],
    "data_analysis": ["general", "coding"],
    "documentation": ["general"],
    "testing": ["coding", "general"],
    "multimodal": ["vision", "general"],
}
