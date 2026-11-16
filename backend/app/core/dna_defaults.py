"""Default Shopper DNA values and allowed preference dimensions.

These are illustrative defaults for demos — not scientifically validated.
Confidence 0 + source "default" means the value is a placeholder, not evidence.
"""

from typing import Final

PREFERENCE_DIMENSIONS: Final[tuple[str, ...]] = (
    "comfort_priority",
    "brand_loyalty",
    "price_sensitivity",
    "quality_preference",
    "portability_preference",
    "battery_life_priority",
)

# Mid-scale placeholders until behavioural learning exists (later phase).
DEFAULT_INFERRED_PREFERENCES: Final[dict[str, int]] = {
    dimension: 50 for dimension in PREFERENCE_DIMENSIONS
}

DEFAULT_CONFIDENCE_SCORES: Final[dict[str, int]] = {
    dimension: 0 for dimension in PREFERENCE_DIMENSIONS
}

DEFAULT_PREFERENCE_SOURCES: Final[dict[str, str]] = {
    dimension: "default" for dimension in PREFERENCE_DIMENSIONS
}

# Allowed source labels for Phase 2 manual updates.
ALLOWED_PREFERENCE_SOURCES: Final[frozenset[str]] = frozenset(
    {"default", "explicit_override", "behavioural", "manual"}
)
