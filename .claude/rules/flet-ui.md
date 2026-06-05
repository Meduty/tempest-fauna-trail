---
paths:
  - "src/ui/**/*.py"
  - "src/main.py"
---

# Flet UI Rules

> **Before editing:** complete the required reading in [CLAUDE.md](../../CLAUDE.md) → "Required reading before any task work" — SPEC.md (§I routes, §V), ARCHITECTURE.md (§11 UI layer), the LIVING UI doc if one exists ([docs/live/](../../docs/live/README.md)), the task plan doc, `views_spec.md` (FROZEN), and the touched code.
>
> **After editing:** add/update a `docs/live/systems/ui.md` for the UI as it solidifies (real code taxonomy), then run `/check`. A stale living doc is a bug; `views_spec.md` stays FROZEN.

- Each screen is a function returning `ft.View`, not a class
- Navigate with `page.go("/route")`, handle in `page.on_route_change`
- Root control in each View: single `ft.Container` or `ft.Column`
- Do not call `page.clean()` — replace `page.views` list
- API calls must run on `threading.Thread` — never block main thread
- Use `page.update()` once after batch mutations, not per-control
- Style via `src/ui/theme.py` constants — no hardcoded color strings
- Event handlers: `lambda _: do_thing()` for click callbacks
- Use `expand=True` for responsive layouts
- Set `wrap=True` on long Text controls
- Image assets referenced as relative paths from `src/assets/`
