"""Regression: attacker-less (environmental) damage must not crash.

Hazard tiles / boss map effects call ``ctx.deal_damage(None, piece, ...)``.
Before the fix this raised ``AttributeError: 'NoneType' object has no attribute
'affinity'`` (context affinity clash) and then ``'NoneType' ... 'id'`` (recorder
damage attribution). Both now guard a ``None`` attacker. (B — see SPEC §B.)
"""

from src.game.combat.context import CombatContext
from src.game.combat.recorder import BattleResultRecorder
from src.game.content import build_champion_at_level, build_enemy_at_level
from src.game.effects import EventBus, SourceTag
from src.game.loadout import piece_from_champion, piece_from_enemy
from src.game.models import WeatherState


def _piece(cid, q, r, enemy):
    p = (piece_from_enemy(build_enemy_at_level(cid, 1)) if cid.startswith("enemy_")
         else piece_from_champion(build_champion_at_level(cid, 1)))
    p.position_q, p.position_r = q, r
    p.is_enemy = enemy
    p.hp = p.max_hp
    return p


def test_environmental_damage_no_attacker_does_not_crash():
    target = _piece("champ_sunmane_lion", 0, 0, False)
    ctx = CombatContext([target], EventBus(), WeatherState.CLEAR)
    before = target.hp
    dealt = ctx.deal_damage(None, target, 50.0, SourceTag.TRUE)
    assert dealt > 0
    assert target.hp < before


def test_environmental_damage_recorded_as_taken_not_dealt():
    target = _piece("champ_sunmane_lion", 0, 0, False)
    bus = EventBus()
    recorder = BattleResultRecorder([target], WeatherState.CLEAR, "node", [])
    recorder.register(bus)
    ctx = CombatContext([target], bus, WeatherState.CLEAR)
    ctx.deal_damage(None, target, 50.0, SourceTag.TRUE)
    # Counted as taken by the target; not attributed to any dealer (no None key).
    assert recorder._damage_taken.get(target.id, 0) > 0
    assert None not in recorder._damage_dealt


def test_environmental_damage_can_kill_with_none_killer():
    target = _piece("champ_sunmane_lion", 0, 0, False)
    target.hp = 1.0
    ctx = CombatContext([target], EventBus(), WeatherState.CLEAR)
    ctx.deal_damage(None, target, 9999.0, SourceTag.TRUE)
    assert not target.alive
