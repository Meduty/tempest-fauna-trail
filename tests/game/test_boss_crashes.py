"""Boss-fight crash regressions (B.64) — three latent crashes surfaced by
playtesting a boss with items/champions equipped:

1. Giantsbane read `ev.tag` in an `on_attack_landed` hook, but that fires an
   ``AttackEvent`` (no ``tag`` field) → AttributeError on every basic attack.
2. Aegis Tortoise's damage-reduction read ``event.attacker.position_q`` on
   map-effect environmental damage, whose ``attacker`` is ``None``.
3. Bramble Carapace reflected ITEM_PROC/REFLECT damage, ping-ponging forever
   with a reflecting boss (Cinder Husk) → RecursionError.

Each test resolves a real boss encounter with the offending piece and asserts
the fight completes (no exception).
"""

from __future__ import annotations

from src.game.combat.resolve import resolve_boss_combat
from src.game.content import CHAMPION_ROSTER, build_champion_at_level
from src.game.encounter import generate_boss_encounter
from src.game.models import WeatherState
from src.game.route import STAGES


def _team_with(item_or_champ, *, item: bool):
    team = [build_champion_at_level(c.id, 3) for c in list(CHAMPION_ROSTER.values())[:5]]
    if item:
        team[0].items = [item_or_champ]
    else:
        team.insert(0, build_champion_at_level(item_or_champ, 3))
    return team


def _resolve_all_bosses(team) -> None:
    for st in STAGES:
        enc = generate_boss_encounter(7, st.index * 8, st)
        # THUNDER exercises weather procs; every boss brings its map effect.
        resolve_boss_combat(team, enc.all_enemies, WeatherState.THUNDER,
                            map_effect_id=enc.map_effect_id, run_seed=7)


def test_boss_fight_with_giantsbane_does_not_crash():
    _resolve_all_bosses(_team_with("giantsbane", item=True))


def test_boss_fight_with_bramble_carapace_does_not_recurse():
    _resolve_all_bosses(_team_with("bramble_carapace", item=True))


def test_boss_fight_with_aegis_tortoise_handles_env_damage():
    _resolve_all_bosses(_team_with("champ_aegis_tortoise", item=False))
