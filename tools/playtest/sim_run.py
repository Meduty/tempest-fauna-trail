"""Full 50-node run walker.

    python -m tools.playtest.sim_run \\
        --run-seed 12345 \\
        --team champ_dawnwisp,champ_veldt_pronghorn,champ_aegis_tortoise \\
        --weather-strategy stage-affinity \\
        --csv run_12345.csv

Walks every node in route order. For each node, picks weather per the
strategy, generates the encounter, resolves combat, and records the result.
Aborts the moment the team wipes (LOSS or DRAW with zero survivors).

Per-node CSV columns:
    node_index, stage, node_type, city_id, weather, outcome, ticks,
    survivors, damage_dealt
"""
from __future__ import annotations

import argparse
import csv
import sys

from src.game.combat import resolve_combat
from src.game.encounter import (
    DEFAULT_DC,
    generate_boss_encounter,
    generate_challenge,
    generate_fight,
    generate_reward,
)
from src.game.models import BattleResult, Champion, CombatOutcome, NodeType, WeatherState
from src.game.route import CITIES, STAGES

from tools.playtest._common import (
    default_team,
    parse_champion_ids,
    parse_weather,
    resolve_boss_combat,
)


WEATHER_STRATEGIES = ("stage-affinity", "city-default")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sim_run",
        description="Walk a full 50-node run with a fixed team.",
    )
    parser.add_argument(
        "--run-seed",
        type=int,
        default=0,
        help="Run seed driving encounter generation. Default: 0.",
    )
    parser.add_argument(
        "--team",
        type=parse_champion_ids,
        default=None,
        help="Comma-separated champion ids. Defaults to default_team(stage_1).",
    )
    parser.add_argument(
        "--weather-strategy",
        default="stage-affinity",
        help=(
            f"Weather selection: one of {', '.join(WEATHER_STRATEGIES)}, or "
            "fixed:<state> (e.g. fixed:rain). Default: stage-affinity."
        ),
    )
    parser.add_argument(
        "--dc",
        type=float,
        default=DEFAULT_DC,
        help=f"Difficulty coefficient. Default: {DEFAULT_DC}.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional path to write a per-node CSV summary.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-node stdout lines; print only the final summary.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Drop into a prep shell (craft/equip/special run-actions) before walking.",
    )
    parser.add_argument(
        "--augment-policy",
        choices=("first", "random", "highest-quality", "none"),
        default="highest-quality",
        help=(
            "How AUGMENT nodes auto-pick from the 1-of-3 offer (T.31): first | "
            "random (seeded) | highest-quality | none (decline, reproduces the old "
            "skip baseline). Default: highest-quality. --interactive prompts instead."
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Interactive prep shell (T.29b — special run-actions + crafting + equip)
# ---------------------------------------------------------------------------

_PREP_HELP = """\
prep commands:
  show                      list team, inventory, amber, bench
  give <id> [n]             add n of an item/component to inventory (debug)
  combine <a> <b>           craft two components / Spirit Gem → item or emblem
  equip <team#> <item>      move an inventory item onto a team champion (<=3)
  reforge <item>            Wildwood Reforging Stone
  unbind <team#>            Unbinding Totem — strip a champ's items to components
  echo <champ_id>           Echo Acorn — add a bench copy
  glimmer <item>            Glimmerdust — upgrade item to Heartwood
  salvage <comp> [comp...]  Reclaimer's Cache — components -> Amber
  run                       finish prep and walk the route
  help                      this list
"""


def _new_prep_run(run_seed: int, team: list[Champion]):
    """Minimal Run for the prep shell (route + the team as roster)."""
    from src.game.models import Run, RunStatus, NodeState
    from src.game.route import build_route
    route = build_route()
    for node in route:
        node.state = NodeState.CURRENT if node.index == 1 else NodeState.UPCOMING
    return Run(
        run_id=f"simrun_{run_seed}", schema_version=1, seed=run_seed,
        status=RunStatus.IN_PROGRESS, roster=team, bench=[], route=route,
        current_node_index=1,
    )


def _interactive_prep(run, team: list[Champion]) -> None:
    """Prep shell over a Run; crafting + special run-actions + equip onto `team`.
    Mutates `team[i].items` and `run` in place; the walk then uses the team."""
    from src.game.registries import RUN_ACTION_REGISTRY
    from src.game.items import combine

    def _dec(item: str) -> None:
        run.inventory[item] = run.inventory.get(item, 0) - 1
        if run.inventory[item] <= 0:
            run.inventory.pop(item, None)

    def show() -> None:
        print("team:", ", ".join(f"{i}:{c.id}[{','.join(c.items) or '-'}]" for i, c in enumerate(team)))
        print("inventory:", dict(run.inventory) or "(empty)", "| amber:", run.amber,
              "| bench:", [c.id for c in run.bench])

    print(_PREP_HELP)
    show()
    while True:
        try:
            parts = input("prep> ").strip().split()
        except EOFError:
            break
        if not parts:
            continue
        cmd, a = parts[0], parts[1:]
        try:
            if cmd in ("run", "go", "done", "q", "quit"):
                break
            elif cmd == "help":
                print(_PREP_HELP)
            elif cmd == "show":
                show()
            elif cmd == "give":
                run.inventory[a[0]] = run.inventory.get(a[0], 0) + (int(a[1]) if len(a) > 1 else 1)
            elif cmd == "combine":
                out = combine(a[0], a[1])
                need = {a[0]: a.count(a[0]), a[1]: a.count(a[1])}
                if out is None:
                    print("  no recipe")
                elif any(run.inventory.get(c, 0) < q for c, q in need.items()):
                    print("  components not in inventory")
                else:
                    _dec(a[0]); _dec(a[1])
                    run.inventory[out] = run.inventory.get(out, 0) + 1
                    print(f"  crafted {out}")
            elif cmd == "equip":
                champ = team[int(a[0])]
                if run.inventory.get(a[1], 0) <= 0:
                    print("  not in inventory")
                elif len(champ.items) >= 3:
                    print("  3 items already")
                else:
                    champ.items.append(a[1]); _dec(a[1])
                    print(f"  equipped {a[1]} on {champ.id}")
            elif cmd == "reforge":
                RUN_ACTION_REGISTRY["reforger"](run, a[0])
            elif cmd == "unbind":
                RUN_ACTION_REGISTRY["unbinding_totem"](run, team[int(a[0])].id)
            elif cmd == "echo":
                RUN_ACTION_REGISTRY["echo_acorn"](run, a[0])
            elif cmd == "glimmer":
                RUN_ACTION_REGISTRY["glimmerdust"](run, a[0])
            elif cmd == "salvage":
                RUN_ACTION_REGISTRY["reclaimers_cache"](run, a)
            else:
                print("  unknown command (try 'help')")
        except (IndexError, ValueError, KeyError) as exc:
            print(f"  error: {exc}")


def _pick_weather(strategy: str, stage_idx: int, city_id: str) -> WeatherState:
    if strategy == "stage-affinity":
        return STAGES[stage_idx - 1].affinity
    if strategy == "city-default":
        return CITIES[city_id].default_weather
    if strategy.startswith("fixed:"):
        return parse_weather(strategy.split(":", 1)[1])
    raise argparse.ArgumentTypeError(
        f"Unknown weather strategy {strategy!r}. "
        f"Try one of: {', '.join(WEATHER_STRATEGIES)}, or fixed:<state>."
    )


def _resolve_node(
    team: list[Champion],
    stage_idx: int,
    node_index: int,
    position: int,
    weather: WeatherState,
    run_seed: int,
    dc: float,
    run_mods: object = None,
) -> tuple[BattleResult | None, NodeType, str]:
    """Resolve one node. Returns (result_or_None, node_type, city_id).

    `run_mods` (a `RunModifiers`, T.31) threads active augments into every combat;
    `None` reproduces the pre-augment walk.
    """
    stage = STAGES[stage_idx - 1]
    city_id = stage.node_cities[position]
    node_type = stage.node_types[position]
    node_id = f"s{stage_idx}-n{node_index}-{city_id}"

    if node_type == NodeType.FIGHT:
        enemies = generate_fight(run_seed, node_index, stage, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id, run_mods=run_mods), node_type, city_id
    if node_type == NodeType.REWARD:
        enemies = generate_reward(run_seed, node_index, stage, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id, run_mods=run_mods), node_type, city_id
    if node_type == NodeType.CHALLENGE:
        enemies, _reward = generate_challenge(run_seed, node_index, stage, weather, dc)
        return resolve_combat(team, enemies, weather, node_id=node_id, run_mods=run_mods), node_type, city_id
    if node_type == NodeType.BOSS_FIGHT:
        encounter = generate_boss_encounter(run_seed, node_index, stage)
        return (
            resolve_boss_combat(team, encounter, weather, run_seed=run_seed, node_id=node_id, run_mods=run_mods),
            node_type,
            city_id,
        )
    # Non-combat node (AUGMENT / SUPPLY) — handled by the caller (augment pick).
    return None, node_type, city_id


def _pick_from_offer(offer: list, policy: str, rng) -> object | None:
    """Auto-pick one augment from a 1-of-3 offer per `--augment-policy` (T.31)."""
    if not offer or policy == "none":
        return None
    if policy == "first":
        return offer[0]
    if policy == "random":
        return offer[rng.randint(0, len(offer) - 1)]
    # highest-quality: rank by quality, ties broken by the seeded offer order
    # (first-offered wins) so the pick honors the deterministic offer the player saw.
    from src.game.augments import AugmentQuality
    order = {q: i for i, q in enumerate(
        (AugmentQuality.COMMON, AugmentQuality.RARE, AugmentQuality.EPIC, AugmentQuality.PRISMATIC))}
    return max(enumerate(offer), key=lambda iv: (order[iv[1].quality], -iv[0]))[1]


def _resolve_augment_node(run, stage_idx: int, node_index: int, policy: str, interactive: bool) -> str:
    """Generate the 1-of-3 offer, pick (policy or prompt), apply. Returns picked id."""
    from src.game.augments import apply_augment, generate_augment_offer
    from src.game.rng import SeededRng

    exclude = tuple(run.active_augments)
    offer = generate_augment_offer(run.seed, node_index, stage_idx, exclude=exclude)
    if not offer:
        return ""
    if interactive:
        picked = _prompt_augment(run, stage_idx, node_index, offer)
    else:
        rng = SeededRng(node_index * 101 + stage_idx)
        picked = _pick_from_offer(offer, policy, rng)
    if picked is None:
        return ""
    apply_augment(run, picked)
    return picked.id


def _prompt_augment(run, stage_idx: int, node_index: int, offer: list):
    """Interactive 1/2/3/r/s augment prompt — rudimentary CLI mirror of the view.

    Returns the chosen `Augment` (or None to skip); the caller applies it."""
    from src.game.augments import generate_augment_offer

    rerolled = False
    while True:
        print(f"\n  AUGMENT offer (stage {stage_idx}, node {node_index}):")
        for i, a in enumerate(offer, 1):
            print(f"    {i}. {a.name:22} [{a.quality.value:9}|{a.scope.value:5}] {a.blurb}")
        prompt = "  pick 1/2/3" + ("" if rerolled else " · r reroll") + " · s skip > "
        try:
            choice = input(prompt).strip().lower()
        except EOFError:
            return None
        if choice == "s":
            return None
        if choice == "r" and not rerolled:
            rerolled = True
            offer = generate_augment_offer(run.seed, node_index, stage_idx,
                                           reroll_count=1, exclude=tuple(run.active_augments))
            continue
        if choice in ("1", "2", "3"):
            idx = int(choice) - 1
            if idx < len(offer):
                return offer[idx]
        print("  (invalid)")


def _team_alive(result: BattleResult) -> bool:
    return bool(result.surviving_team_ids)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        weather = _pick_weather(args.weather_strategy, 1, STAGES[0].node_cities[0])
    except argparse.ArgumentTypeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    team = args.team if args.team is not None else default_team(1)
    if not team:
        print("error: empty team", file=sys.stderr)
        return 2

    # A walk-level Run holds augment state across the route (T.31). roster=team so
    # Crest/Worldroot dominant-trait picks read the real board.
    from src.game.augments import RunModifiers
    run = _new_prep_run(args.run_seed, team)
    if args.interactive:
        _interactive_prep(run, team)

    rows: list[dict[str, object]] = []
    cleared = 0
    died_at_node: int | None = None
    total_damage = 0

    node_index = 0
    for stage_idx, stage in enumerate(STAGES, start=1):
        for position, _ in enumerate(stage.node_cities):
            node_index += 1
            # Advance the walk Run's position so RUN-augment seeds (Forage's
            # `_run_action_seed`) vary per node and future quest trackers can read
            # the live node off `run.current_node()`.
            run.current_node_index = node_index
            city_id = stage.node_cities[position]
            weather = _pick_weather(args.weather_strategy, stage_idx, city_id)
            node_type = stage.node_types[position]

            # AUGMENT node: pick 1-of-3 (policy or interactive), apply to the Run.
            if node_type == NodeType.AUGMENT:
                picked = _resolve_augment_node(
                    run, stage_idx, node_index, args.augment_policy, args.interactive,
                )
                rows.append({
                    "node_index": node_index, "stage": stage_idx, "node_type": node_type.value,
                    "city_id": city_id, "weather": weather.value,
                    "outcome": f"augment:{picked}" if picked else "augment:skip",
                    "ticks": 0, "survivors": "", "damage_dealt": 0, "augment_picked": picked,
                })
                if not args.quiet:
                    label = picked or "(skip)"
                    print(f"[{node_index:02d}/{stage_idx}] {city_id:25} {node_type.value:9} weather={weather.value:7} → augment {label}")
                cleared += 1
                continue

            # Combat / other nodes: thread the current augment set in (rebuilt so
            # newly-picked augments + shared quest state propagate).
            run_mods = RunModifiers.from_run(run)
            result, node_type, city_id = _resolve_node(
                team, stage_idx, node_index, position, weather, args.run_seed, args.dc, run_mods,
            )

            if result is None:
                row = {
                    "node_index": node_index,
                    "stage": stage_idx,
                    "node_type": node_type.value,
                    "city_id": city_id,
                    "weather": weather.value,
                    "outcome": "skipped",
                    "ticks": 0,
                    "survivors": "",
                    "damage_dealt": 0,
                    "augment_picked": "",
                }
                rows.append(row)
                if not args.quiet:
                    print(f"[{node_index:02d}/{stage_idx}] {city_id:25} {node_type.value:9} weather={weather.value:7} → skipped")
                cleared += 1
                continue

            outcome = result.outcome.value
            dmg = sum(
                amt for pid, amt in result.team_damage_dealt.items()
                if pid in {c.id for c in team}
            )
            total_damage += dmg
            survivors = ",".join(result.surviving_team_ids)
            row = {
                "node_index": node_index,
                "stage": stage_idx,
                "node_type": node_type.value,
                "city_id": city_id,
                "weather": weather.value,
                "outcome": outcome,
                "ticks": result.duration_ticks,
                "survivors": survivors,
                "damage_dealt": dmg,
                "augment_picked": "",
            }
            rows.append(row)

            if not args.quiet:
                print(
                    f"[{node_index:02d}/{stage_idx}] {city_id:25} {node_type.value:9} "
                    f"weather={weather.value:7} → {outcome:4} "
                    f"({result.duration_ticks:>5}t, dmg={dmg:>5}, survivors={len(result.surviving_team_ids)})"
                )

            if result.outcome == CombatOutcome.WIN:
                cleared += 1
            elif result.outcome == CombatOutcome.DRAW and _team_alive(result):
                # Timed-out DRAW but team still has survivors — continue
                cleared += 1
            else:
                # LOSS or DRAW with zero survivors (wipe) — abort the run
                died_at_node = node_index
                break
        if died_at_node is not None:
            break

    print()
    print("=== Run summary ===")
    print(f"Team        : {[c.id for c in team]}")
    print(f"Seed        : {args.run_seed}")
    print(f"Strategy    : {args.weather_strategy}")
    print(f"Nodes cleared: {cleared}/50")
    print(f"Total damage : {total_damage}")
    if died_at_node is not None:
        last = rows[-1]
        print(
            f"Run ended at node {died_at_node} (stage {last['stage']}, "
            f"{last['city_id']}, {last['node_type']}, {last['outcome']})"
        )
    else:
        print("Run reached node 50 — victory!")

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV written: {args.csv}")

    return 0 if died_at_node is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
