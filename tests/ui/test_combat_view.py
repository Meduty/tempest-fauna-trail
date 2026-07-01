"""Combat view (T.12) — render smoke asserting per-slot mana bars (B.63).

Constructing the view builds the board overlays, so this catches the multicaster
regression (only ``p.mana[0]`` rendered) without a live Flet client.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.game.content import (
    CHAMPION_ROSTER,
    ENEMY_ROSTER,
    build_champion_at_level,
    build_enemy_at_level,
)
from src.game.models import WeatherState
from src.ui.combat_playback import CombatSession
from src.ui.views.combat import build_combat_view


class _FakePage:
    def __init__(self) -> None:
        self.views: list = []
        self.overlay: list = []
        self.on_keyboard_event = None
        self.window = SimpleNamespace()

    def update(self) -> None:
        pass

    def run_thread(self, *a, **k) -> None:
        pass


def _keys(control, out: list[str]) -> list[str]:
    k = getattr(control, "key", None)
    if isinstance(k, str):
        out.append(k)
    for attr in ("controls", "content", "shapes"):
        child = getattr(control, attr, None)
        if isinstance(child, list):
            for c in child:
                _keys(c, out)
        elif child is not None and not isinstance(child, str):
            _keys(child, out)
    return out


def _build(team_ids, enemy_id="enemy_conscript"):
    team = [build_champion_at_level(cid, 2) for cid in team_ids]
    enemies = [build_enemy_at_level(enemy_id, 1)]
    session = CombatSession(team=team, enemies=enemies, weather=WeatherState.CLEAR)
    view = build_combat_view(_FakePage(), session, on_exit=lambda _r: None)
    return _keys(view, [])


def _first_multicaster() -> str:
    return next(c.id for c in CHAMPION_ROSTER.values() if len(c.active_abilities or []) == 2)


def _first_single_caster() -> str:
    return next(c.id for c in CHAMPION_ROSTER.values() if len(c.active_abilities or []) == 1)


def test_multicaster_renders_all_mana_bars():
    """B.63: a 2-slot multicaster shows one mana bar per active slot, not just one."""
    mc = _first_multicaster()
    keys = _build([mc])
    bars = sorted(k for k in keys if k.startswith(f"mp-{mc}-"))
    assert bars == [f"mp-{mc}-0", f"mp-{mc}-1"]


def test_single_caster_renders_one_mana_bar():
    """No regression: a single-slot caster still renders exactly one mana bar."""
    sc = _first_single_caster()
    keys = _build([sc])
    bars = [k for k in keys if k.startswith(f"mp-{sc}-")]
    assert bars == [f"mp-{sc}-0"]


def test_enemy_ids_are_stable():
    """Guard the roster ids the smoke relies on still exist."""
    assert "enemy_conscript" in ENEMY_ROSTER


def test_base_id_strips_instance_suffix():
    """`_base_id` maps a uniquified instance id back to the roster/def id so the
    view's base-id-keyed metadata dicts resolve for twins (B.65 review)."""
    from src.ui.views.combat import _base_id

    assert _base_id("enemy_conscript#1") == "enemy_conscript"
    assert _base_id("enemy_conscript#2") == "enemy_conscript"
    assert _base_id("enemy_conscript") == "enemy_conscript"      # no suffix → unchanged
    assert _base_id("champ_ember_salamander") == "champ_ember_salamander"


def test_twin_enemies_get_unique_token_keys():
    """Two enemies of the same type render with distinct control keys (the base id
    + a `#n`-suffixed instance id), so the client no longer animates one piece's
    token/bars between its twins (B.65)."""
    team = [build_champion_at_level(_first_single_caster(), 2)]
    enemies = [build_enemy_at_level("enemy_conscript", 1),
               build_enemy_at_level("enemy_conscript", 1)]
    session = CombatSession(team=team, enemies=enemies, weather=WeatherState.CLEAR)
    view = build_combat_view(_FakePage(), session, on_exit=lambda _r: None)
    keys = _keys(view, [])
    tok = sorted(k for k in keys if k.startswith("tok-enemy_conscript"))
    assert tok == ["tok-enemy_conscript", "tok-enemy_conscript#1"]
    # ...and no key collides (every token/bar key is unique).
    assert len(keys) == len(set(keys))
