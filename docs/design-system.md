# Design system — Quiet Commerce

Chosen direction for SmartShopper (Phase 1 tokens live in `frontend/src/index.css`).

## Principles

- One job per screen; generous whitespace
- Product photography will lead discovery (later phases)
- No admin-dashboard density; no neon; no heavy shadows
- Accent colour used for meaningful actions only

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| Ivory | `#F7F4EF` | Page background |
| Surface | `#FFFFFF` | Content panels |
| Navy | `#1A2433` | Primary text |
| Navy muted | `#3D4A5C` | Secondary text |
| Sage | `#5F7A6A` | Accents / labels |
| Sage soft | `#D8E3DC` | Soft success / chips |
| Border | `#E4DDD3` | Hairline borders |

## Typography

- **Manrope** — UI, body, controls
- **Source Serif 4** — occasional display headlines only (not dense editorial columns)

## Components (so far)

- `AppShell` — brand header + content frame
- `StatusPill` — small status chip
- Foundation status cards — temporary Phase 1 verification UI

Full navigation (Overview, Discover, AI Assistant, Shopper DNA, Decision Lab, History) ships when each screen has real data.
