"""Prompt budget audit APIs."""

from __future__ import annotations

from fastapi import APIRouter

from app.config.prompts import get_prompt_registry, PromptError

router = APIRouter(prefix="/prompt-budgets", tags=["Prompt Budgets"])


def _risk_level(prompt_chars: int, budget: int) -> str:
    if budget <= 0:
        return "none"
    ratio = prompt_chars / max(1, budget)
    if ratio >= 0.9:
        return "high"
    if ratio >= 0.7:
        return "medium"
    if ratio >= 0.5:
        return "low"
    return "low"


def _quality_score(prompt_text: str, budget: int) -> int:
    base = 100
    if budget <= 0:
        return base
    ratio = len(prompt_text) / max(1, budget)
    if ratio >= 0.9:
        base -= 35
    elif ratio >= 0.75:
        base -= 20
    elif ratio >= 0.5:
        base -= 10
    if "examples are illustrative only" in prompt_text.lower():
        base += 5
    if "return json only" in prompt_text.lower() or "return only" in prompt_text.lower():
        base += 5
    return max(0, min(100, base))


@router.get("")
def list_prompt_budgets() -> dict:
    registry = get_prompt_registry()
    rows: list[dict[str, object]] = []
    for prompt_path in registry.list_prompts():
        try:
            category, prompt_id = prompt_path.split("/", 1) if "/" in prompt_path else ("", prompt_path)
            prompt = registry.load_prompt(prompt_id, category or None)
            constraints = prompt.get("constraints", {}) or {}
            budget = int(constraints.get("max_completion_tokens") or constraints.get("max_tokens") or 0)
            prompt_text = f"{prompt.get('system_message', '')}\n{prompt.get('user_prompt', '')}"
            rows.append(
                {
                    "prompt_path": prompt_path,
                    "prompt_id": prompt.get("id", prompt_id),
                    "category": category or prompt.get("metadata", {}).get("category", ""),
                    "version": prompt.get("version", "1.0"),
                    "current_token_limit": budget,
                    "recommended_token_limit": budget,
                    "truncation_risk": _risk_level(len(prompt_text), budget),
                    "prompt_quality_score": _quality_score(prompt_text, budget),
                    "description": prompt.get("description", ""),
                }
            )
        except PromptError:
            continue
    rows.sort(key=lambda item: (str(item["category"]), str(item["prompt_id"])))
    return {"prompts": rows, "total": len(rows)}
