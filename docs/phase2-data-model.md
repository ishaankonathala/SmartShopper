# Phase 2 data model

## Relationships (plain language)

1. **UserProfile** stores what the shopper *told* us (budget, preferred brands, etc.).
2. **ShopperDNA** stores *inferred or default* preference scores (0–100) with confidence
   and source labels. One DNA row per profile.
3. **Product** is the demo catalogue (SKUs like `SS-HP-001`). Attributes are flexible JSON
   because headphones and air purifiers do not share the same fields.
4. **ShoppingHistory** is an append-only list of actions linking a user to a product
   (`viewed`, `liked`, `purchased`, `dismissed`, `not_interested`).

Explicit profile fields and DNA inferred fields are never mixed in the same table.
Updating DNA cannot change preferred_brands / max_budget on the profile.

## Preference dimensions

`comfort_priority`, `brand_loyalty`, `price_sensitivity`, `quality_preference`,
`portability_preference`, `battery_life_priority`.

Defaults are mid-scale (50) with confidence `0` and source `default` until later
behavioural learning exists.
