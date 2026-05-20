---
paths:
  - "src/ui/**/*.py"
  - "src/main.py"
---

# Flet UI Rules

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
