"""
Tests for Budget/Model selection fallback safety (BP003 US-BP003-4)
"""

from src_common.planner.budget import BudgetManager, ModelSelector


def test_get_cheaper_alternatives_unknown_model():
    bm = BudgetManager()
    selector = ModelSelector(bm)

    # Unknown current model should not raise, and should return cheaper options
    alts = selector._get_cheaper_alternatives("unknown-model", task_type="reasoning")
    # At least one known model supports reasoning (e.g., claude-3-haiku)
    assert isinstance(alts, list)
    assert "claude-3-haiku" in alts or len(alts) >= 1

    # Ensure list sorted by cost ascending
    costs = [bm.models[m].cost_per_1k_tokens for m in alts]
    assert costs == sorted(costs)

