# T16 Plan — Comprehensive Test Strategy

> **Status:** comprehensive design — ready for admin review.
> **Scope:** testing strategy for T.19 (encounter generation), T.20 (ability
> framework), T.21 (challenges & bosses), T.24 (enemy formation), and the
> combat system as a whole.
> **Depends:** T.3 (combat engine), T.1 (models), T.18 (scaling).

---

## 1. Testing Philosophy

### 1.1 What we test

- **Game logic only.** `src/game/` has zero Flet imports (V.1). Every test is
  a pure-logic unit test — no UI, no mocking of display, no async.
- **Determinism is the #1 invariant.** If two runs with the same seed produce
  different results, the game is broken. Determinism tests run on every PR.
- **Combat system is the heart.** The majority of test effort goes into combat
  resolution — it touches every other system (weather, abilities, items,
  traits, augments, formation, encounter generation).

### 1.2 What we don't test (yet)

- UI views (no Flet test harness in scope)
- API integration (marked `@pytest.mark.integration`, auto-skipped without key)
- Visual correctness (canvas rendering)

### 1.3 Test runner

```bash
python -m pytest tests/ -v
```

Integration tests: `python -m pytest tests/ -m integration`

---

## 2. Test Organization

```
tests/
├── __init__.py
├── game/
│   ├── __init__.py
│   ├── test_models.py              # Existing — Champion/Enemy/Run validation
│   ├── test_combat.py              # Existing — combat engine core
│   ├── test_weather_effects.py     # Existing — weather favor + affinity clash
│   ├── test_scaling.py             # Existing — power formula
│   ├── test_content.py             # Existing — roster composition
│   ├── test_route.py               # Existing — route structure
│   ├── test_combat_log.py          # Existing — event log
│   ├── test_encounter.py           # NEW — T19 encounter generation
│   ├── test_abilities.py           # NEW — T20 ability framework
│   ├── test_effects.py             # NEW — T20 effect substrate
│   ├── test_challenge_boss.py      # NEW — T21 challenges & bosses
│   ├── test_formation.py           # NEW — T24 enemy formation
│   ├── test_combat_scenarios.py    # NEW — step-by-step combat resolution
│   └── test_determinism.py         # NEW — cross-cutting determinism suite
├── api/
│   ├── __init__.py
│   └── test_weather.py             # Existing
```

---

## 3. T19 — Encounter Generation Tests (`test_encounter.py`)

### 3.1 Determinism tests

```python
def test_same_seed_same_squad():
    """Identical (seed, node_index, channel) → byte-equal enemy squads."""
    squad_a = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])
    squad_b = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])
    assert_squads_equal(squad_a, squad_b)

def test_different_seed_different_squad():
    """Different seeds → different squads (with high probability)."""
    squad_a = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])
    squad_b = generate_fight(run_seed=99, node_index=5, stage=STAGES[2])
    assert squad_a != squad_b

def test_pythonhashseed_stability():
    """Generation is stable across PYTHONHASHSEED values.
    Run in a subprocess with PYTHONHASHSEED=0 and PYTHONHASHSEED=12345.
    Both must produce identical results."""
    # This test spawns subprocesses with different PYTHONHASHSEED envvars
    ...
```

### 3.2 Sub-seed isolation tests

```python
def test_subseed_isolation():
    """Changing node 4's outcome does not shift node 5."""
    # Generate squad for node 5 normally
    squad_5a = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])

    # Hypothetically "change" node 4 by using a different seed for node 4
    # (simulating a different player choice at node 4)
    # Node 5's squad must be identical because sub-seeds are independent
    squad_5b = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])
    assert_squads_equal(squad_5a, squad_5b)

def test_channel_isolation():
    """Enemy channel and augment channel produce independent results."""
    enemy_seed = derive_seed(42, 5, CH_ENEMIES)
    augment_seed = derive_seed(42, 5, CH_AUGMENT)
    assert enemy_seed != augment_seed
```

### 3.3 Budget adherence tests

```python
def test_budget_adherence():
    """Total enemy power ≤ node_budget + BUDGET_TOLERANCE."""
    for stage in STAGES:
        for node_idx in range(len(stage.node_cities)):
            squad = generate_fight(run_seed=42, node_index=node_idx, stage=stage)
            total_power = sum(power(e.tier, 1) for e in squad)
            expected_budget = stage_base(stage.index) * 1.15  # max variance
            assert total_power <= expected_budget + BUDGET_TOLERANCE

def test_minimum_squad_size():
    """Even with very low budget, minimum squad size is met."""
    squad = roll_squad(Random(0), budget=0.5, pool=ENEMY_POOL, min_count=2)
    assert len(squad) >= 2
```

### 3.4 Composition tests

```python
def test_tier_gating():
    """No enemy tier appears outside its stage-eligible range."""
    for stage in STAGES:
        squad = generate_fight(run_seed=42, node_index=0, stage=stage)
        min_tier, max_tier = TIER_GATES[stage.index]
        for enemy in squad:
            assert min_tier <= enemy.tier <= max_tier

def test_duplicate_limit():
    """No more than max_dupes copies of the same enemy type."""
    squad = generate_fight(run_seed=42, node_index=0, stage=STAGES[4])
    from collections import Counter
    counts = Counter(e.id for e in squad)
    for enemy_id, count in counts.items():
        assert count <= 2  # max_dupes default

def test_affinity_distribution():
    """Squad roughly follows the 50/30/20 affinity distribution."""
    # Statistical test over many seeds
    clear_count = 0
    stage_count = 0
    other_count = 0
    for seed in range(100):
        squad = generate_fight(run_seed=seed, node_index=3, stage=STAGES[2])
        for e in squad:
            if e.affinity == WeatherState.CLEAR:
                clear_count += 1
            elif e.affinity == STAGES[2].affinity:
                stage_count += 1
            else:
                other_count += 1
    total = clear_count + stage_count + other_count
    assert 0.35 < clear_count / total < 0.65  # ~50% Clear
```

### 3.5 Reroll tests

```python
def test_reroll_changes_offers():
    """Reroll produces different offers than the original."""
    original = augment_seed(seed=42, node_index=3, rerolled=False)
    rerolled = augment_seed(seed=42, node_index=3, rerolled=True)
    assert original != rerolled

def test_reroll_is_deterministic():
    """Reroll is itself deterministic."""
    r1 = augment_seed(seed=42, node_index=3, rerolled=True)
    r2 = augment_seed(seed=42, node_index=3, rerolled=True)
    assert r1 == r2
```

---

## 4. T20 — Ability Framework Tests (`test_abilities.py`, `test_effects.py`)

### 4.1 Modifier tests (`test_effects.py`)

```python
def test_modifier_add():
    """Additive modifiers stack correctly: (base + Σ adds)."""
    piece = make_piece(strength=50)
    apply_modifier(piece, Modifier("strength", "add", 20, Lifetime.PERMANENT, "test"))
    apply_modifier(piece, Modifier("strength", "add", 10, Lifetime.PERMANENT, "test"))
    assert compute_stat(piece, "strength") == 80

def test_modifier_mul():
    """Multiplicative modifiers: (base + adds) × Π muls."""
    piece = make_piece(strength=50)
    apply_modifier(piece, Modifier("strength", "add", 10, Lifetime.PERMANENT, "test"))
    apply_modifier(piece, Modifier("strength", "mul", 1.5, Lifetime.PERMANENT, "test"))
    assert compute_stat(piece, "strength") == 90  # (50+10) * 1.5

def test_modifier_set_overrides():
    """Set modifier overrides all adds and muls."""
    piece = make_piece(strength=50)
    apply_modifier(piece, Modifier("strength", "add", 100, Lifetime.PERMANENT, "test"))
    apply_modifier(piece, Modifier("strength", "set", 25, Lifetime.PERMANENT, "test"))
    assert compute_stat(piece, "strength") == 25

def test_modifier_timed_expiry():
    """TIMED modifiers expire at the correct tick."""
    piece = make_piece(strength=50)
    mod = Modifier("strength", "add", 20, Lifetime.TIMED, "test", expires_at_tick=100)
    apply_modifier(piece, mod)
    assert compute_stat(piece, "strength", tick=50) == 70
    assert compute_stat(piece, "strength", tick=101) == 50
```

### 4.2 Hook dispatch tests

```python
def test_hook_priority_ordering():
    """Hooks fire in descending priority order."""
    log = []
    bus = EventBus()
    bus.subscribe(Hook("on_attack_landed", lambda ctx, ev: log.append("low"), priority=0))
    bus.subscribe(Hook("on_attack_landed", lambda ctx, ev: log.append("high"), priority=10))
    bus.fire("on_attack_landed", mock_event())
    assert log == ["high", "low"]

def test_hook_scope_per_hit():
    """PER_HIT hooks fire on every hit."""
    count = [0]
    bus = EventBus()
    bus.subscribe(Hook("on_attack_landed", lambda ctx, ev: count.__setitem__(0, count[0]+1),
                       scope=HookScope.PER_HIT))
    bus.fire("on_attack_landed", mock_event())
    bus.fire("on_attack_landed", mock_event())
    assert count[0] == 2

def test_hook_scope_once_per_combat():
    """ONCE_PER_COMBAT hooks fire only once."""
    count = [0]
    bus = EventBus()
    bus.subscribe(Hook("on_attack_landed", lambda ctx, ev: count.__setitem__(0, count[0]+1),
                       scope=HookScope.ONCE_PER_COMBAT))
    bus.fire("on_attack_landed", mock_event())
    bus.fire("on_attack_landed", mock_event())
    assert count[0] == 1
```

### 4.3 Active ability tests

```python
def test_simple_active_deals_damage():
    """A simple active ability deals expected damage to primary target."""
    ctx = make_combat_context(attacker=make_piece(strength=100), defender=make_piece(hp=500))
    register_active_simple("smash", SimpleActive(damage=100, scaling="ad*1.5", ...))
    ctx.cast_ability(ctx.attacker, slot_idx=0)
    assert ctx.defender.hp < 500

def test_factory_cone_aoe():
    """A cone AOE hits multiple targets."""
    ctx = make_combat_context(attacker=make_piece(), defenders=[make_piece() for _ in range(3)])
    ability = cone_aoe(damage=100, scaling="ap*1.5", half_to_neighbors=True)
    # ... verify multiple targets took damage

def test_handler_with_weather_conditional():
    """Handler-authored ability behaves differently based on weather."""
    ctx_thunder = make_combat_context(weather=WeatherState.THUNDER, ...)
    ctx_clear = make_combat_context(weather=WeatherState.CLEAR, ...)
    # storm_surge should deal more damage in Thunder
    ...
```

### 4.4 Passive ability tests

```python
def test_passive_fires_on_correct_event():
    """Passive registered on on_attack_landed fires when an attack lands."""
    fired = [False]
    @register_passive("test_passive")
    def test_passive(owner):
        def hook(ctx, ev):
            if ev.attacker is owner:
                fired[0] = True
        return EffectBundle(hooks=[Hook("on_attack_landed", hook)])
    # ... run combat with this passive
    assert fired[0]

def test_passive_closure_captures_owner():
    """Passive closure correctly references its owner, not a shared variable."""
    # Create two pieces with different passives
    # Verify each passive acts on its own owner
    ...
```

### 4.5 Status effect tests

```python
def test_stun_blocks_all():
    """Stunned piece skips action, movement, and mana regen."""
    ctx = make_combat_context(...)
    ctx.apply_status(ctx.piece, "stun", duration_ticks=100)
    # Advance 50 ticks
    assert ctx.piece.action_energy == 0
    assert ctx.piece.movement_energy == 0
    assert ctx.piece.mana == 0

def test_silence_blocks_cast_only():
    """Silenced piece can auto-attack and move but cannot cast."""
    ctx = make_combat_context(...)
    ctx.apply_status(ctx.piece, "silence", duration_ticks=100)
    # Piece should still gain action energy and move
    # But should not cast when mana is full
    ...

def test_disarm_blocks_auto_only():
    """Disarmed piece can cast but cannot auto-attack."""
    ...

def test_root_blocks_movement_only():
    """Rooted piece can attack and cast but cannot move."""
    ...

def test_status_expiry():
    """Status expires at the correct tick and fires on_status_expired."""
    ctx = make_combat_context(...)
    ctx.apply_status(ctx.piece, "stun", duration_ticks=50)
    advance_ticks(ctx, 49)
    assert has_status(ctx.piece, "stun")
    advance_ticks(ctx, 1)
    assert not has_status(ctx.piece, "stun")
```

### 4.6 Phase hook tests

```python
def test_phase_hook_fires_at_threshold():
    """Boss phase transition fires once at 50% HP."""
    boss = make_boss(hp=1000)
    ctx = make_combat_context(boss=boss)
    assert len(boss.actives) == 1  # Phase 1: 1 active

    # Damage boss to 50%
    ctx.deal_damage(None, boss, 500, SourceTag.TRUE)
    assert len(boss.actives) == 2  # Phase 2: 2 actives

def test_phase_hook_fires_once():
    """Phase hook does not re-fire after first trigger."""
    boss = make_boss(hp=1000)
    ctx = make_combat_context(boss=boss)
    ctx.deal_damage(None, boss, 500, SourceTag.TRUE)  # Trigger phase 2
    ctx.heal(None, boss, 200)                          # Heal above 50%
    ctx.deal_damage(None, boss, 200, SourceTag.TRUE)  # Drop below 50% again
    assert len(boss.actives) == 2  # Still 2, not 3
```

### 4.7 Damage pipeline tests

```python
def test_damage_pipeline_weather_modifier():
    """Affinity Clash multiplier applies to ability damage."""
    # Thunder attacker vs. Rain defender → 1.10× (predator)
    ctx = make_combat_context(
        attacker=make_piece(affinity=WeatherState.THUNDER),
        defender=make_piece(affinity=WeatherState.RAIN),
    )
    base_damage = 100
    actual = ctx.deal_damage(ctx.attacker, ctx.defender, base_damage, SourceTag.ABILITY)
    assert actual > base_damage  # Affinity advantage

def test_damage_pipeline_crit():
    """Critical strikes apply 1.5× multiplier."""
    piece = make_piece(crit_chance=1.0)  # Always crits
    ctx = make_combat_context(attacker=piece, defender=make_piece(hp=1000))
    # ... verify crit damage is 1.5× base

def test_damage_pipeline_penetration():
    """Penetration reduces effective armor."""
    defender = make_piece(armor=100)
    attacker = make_piece(penetration=20, penetration_pct=0.1)
    # effective_armor = max(0, round(100 * (1 - 0.1)) - 20) = max(0, 90 - 20) = 70
    # reduction = 70 / (70 + 100) = 0.412
    ...

def test_damage_pre_hook_modifies_amount():
    """on_damage_pre hooks can modify incoming damage."""
    ...
```

---

## 5. T21 — Challenge & Boss Tests (`test_challenge_boss.py`)

### 5.1 Challenge tests

```python
def test_challenge_determinism():
    """Same (seed, node_index, CH_CHALLENGE) → identical roster."""
    ...

def test_challenge_spirit_faction():
    """All challenge enemies have spirit/corrupted tags."""
    for stage in STAGES:
        squad = generate_challenge(seed=42, node_index=..., stage=stage)
        for enemy in squad:
            assert "corrupted" in enemy.tags or "spirit" in enemy.tags

def test_challenge_affinity_distribution():
    """Challenge squad follows 50/30/20 affinity split."""
    ...

def test_challenge_team_size():
    """Challenge team size matches stage table."""
    for stage_idx, expected_size in CHALLENGE_SIZES.items():
        squad = generate_challenge(seed=42, node_index=..., stage=STAGES[stage_idx-1])
        assert len(squad) == expected_size
```

### 5.2 Boss tests

```python
def test_boss_supporting_cast():
    """Boss supporting cast matches authored roster."""
    cast = boss_supporting_cast(boss_id="holloway")
    assert len([e for e in cast if e.id == "heavy_knight"]) == 2
    assert len([e for e in cast if e.id == "steam_engineer"]) == 2
    assert len([e for e in cast if e.id == "conscript"]) == 4

def test_boss_phase_transition():
    """Boss enters phase 2 at 50% HP with +1 active +1 passive."""
    ...

def test_boss_on_death_hook():
    """Boss on-death effect fires correctly."""
    ...
```

### 5.3 Map effect tests

```python
def test_hazard_tiles_deal_damage():
    """Piece on a hazard tile takes per-tick true damage."""
    ctx = make_combat_context_with_map_effect(HazardTilesEffect)
    piece = place_piece_on_hazard(ctx)
    hp_before = piece.hp
    advance_ticks(ctx, 10)
    assert piece.hp < hp_before

def test_fog_limits_targeting():
    """Piece beyond fog range is untargetable."""
    ctx = make_combat_context_with_map_effect(FogEffect)
    attacker = place_piece_at(ctx, (7, 3))
    target = place_piece_at(ctx, (0, 3))  # Far away
    assert not ctx.can_target(attacker, target)

def test_flood_lanes_shift():
    """Flood lane shifts each round."""
    ctx = make_combat_context_with_map_effect(FloodLanesEffect)
    lane_round_1 = get_impassable_column(ctx)
    advance_to_round(ctx, 2)
    lane_round_2 = get_impassable_column(ctx)
    assert lane_round_1 != lane_round_2

def test_collapsing_arena():
    """Edge rows disable over time."""
    ctx = make_combat_context_with_map_effect(CollapsingArenaEffect)
    assert ctx.board.is_passable(0, 0)  # Edge passable at start
    advance_to_round(ctx, 6)
    assert not ctx.board.is_passable(0, 0)  # Edge collapsed

def test_ley_cells_buff():
    """Ley cell grants stat buffs to holding team."""
    ...

def test_spawn_rifts_add_enemies():
    """Spawn rifts periodically add weak enemies."""
    ...
```

---

## 6. T24 — Enemy Formation Tests (`test_formation.py`)

```python
def test_formation_determinism():
    """Identical squad → identical formation."""
    enemies = make_enemy_squad(size=6)
    f1 = plan_enemy_formation(enemies)
    f2 = plan_enemy_formation(enemies)
    assert f1 == f2

def test_frontline_ahead_of_backline():
    """Frontline average column < backline average column (closer to player)."""
    enemies = make_mixed_squad()
    formation = plan_enemy_formation(enemies)
    frontline_cols = [formation[e.piece_id][0] for e in enemies if classify_role(e) == PlacementRole.FRONTLINE]
    backline_cols = [formation[e.piece_id][0] for e in enemies if classify_role(e) == PlacementRole.BACKLINE]
    if frontline_cols and backline_cols:
        assert mean(frontline_cols) < mean(backline_cols)

def test_center_out_packing():
    """Pieces in the same column cluster around center row."""
    enemies = make_frontline_squad(size=3)
    formation = plan_enemy_formation(enemies)
    rows = [formation[e.piece_id][1] for e in enemies]
    center = BOARD_HEIGHT // 2
    assert center in rows  # Center row is used

def test_flank_at_edges():
    """Assassin-type enemies are placed at edge rows."""
    enemies = [make_assassin_enemy(), make_tank_enemy(), make_mage_enemy()]
    formation = plan_enemy_formation(enemies)
    assassin_row = formation[enemies[0].id][1]
    assert assassin_row in (0, BOARD_HEIGHT - 1)

def test_no_duplicate_positions():
    """No two enemies share a cell."""
    for size in [1, 2, 3, 5, 8, 11]:
        enemies = make_enemy_squad(size=size)
        formation = plan_enemy_formation(enemies)
        positions = list(formation.values())
        assert len(positions) == len(set(positions))

def test_all_on_board():
    """All positions within board bounds."""
    enemies = make_enemy_squad(size=11)
    formation = plan_enemy_formation(enemies)
    for q, r in formation.values():
        assert 0 <= q < BOARD_WIDTH
        assert 0 <= r < BOARD_HEIGHT

def test_boss_at_authored_position():
    """Boss piece is placed at its authored position."""
    boss = make_boss_piece()
    minions = make_enemy_squad(size=5)
    formation = plan_enemy_formation([boss] + minions)
    assert formation[boss.piece_id] == BOSS_POSITION

def test_overflow_handling():
    """Column overflow spills to adjacent column."""
    # Create 8 frontline enemies (more than 7 rows)
    enemies = make_frontline_squad(size=8)
    formation = plan_enemy_formation(enemies)
    cols = [formation[e.piece_id][0] for e in enemies]
    assert 8 in cols  # At least one spilled to column 8
```

---

## 7. Combat Scenario Tests (`test_combat_scenarios.py`)

### 7.1 Step-by-step combat observation

The most important test class — run **randomly generated combats** and observe
step-by-step resolution for unintended behavior. These are semi-automated:
they generate encounters, run them, and check invariants every tick.

```python
class TestCombatScenarios:
    """
    Run randomly generated combats and verify per-tick invariants.
    These tests catch emergent bugs that unit tests miss.
    """

    @pytest.mark.parametrize("seed", range(50))
    def test_random_combat_invariants(self, seed):
        """Generate a random encounter and verify invariants through resolution."""
        rng = Random(seed)
        team = generate_random_team(rng, size=rng.randint(3, 8))
        enemies = generate_random_enemies(rng, size=rng.randint(3, 8))
        weather = rng.choice(list(WeatherState))

        result = resolve_combat(team, enemies, weather)

        # --- Invariants checked ---
        # 1. Combat terminates
        assert result.duration_ticks <= MAX_TICKS

        # 2. Outcome is valid
        assert result.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)

        # 3. Winner has survivors
        if result.outcome == CombatOutcome.WIN:
            assert len(result.surviving_team_ids) > 0
            assert len(result.surviving_enemy_ids) == 0
        elif result.outcome == CombatOutcome.LOSS:
            assert len(result.surviving_enemy_ids) > 0
            assert len(result.surviving_team_ids) == 0

        # 4. No negative HP in final state
        for piece_state in result.final_states():
            if piece_state.alive:
                assert piece_state.hp > 0

        # 5. Total damage dealt ≈ total damage taken (conservation)
        total_dealt = sum(result.team_damage_dealt.values()) + sum(result.enemy_damage_dealt.values())
        total_taken = sum(result.team_damage_taken.values()) + sum(result.enemy_damage_taken.values())
        # Allow for healing, overkill, and DOT rounding
        assert abs(total_dealt - total_taken) < total_dealt * 0.1 + 100

        # 6. Event log is non-empty and ordered
        assert len(result.events) > 0
        ticks = [e.tick for e in result.events]
        assert ticks == sorted(ticks)

    @pytest.mark.parametrize("seed", range(20))
    def test_combat_with_abilities(self, seed):
        """Combat with ability-equipped pieces resolves without errors."""
        rng = Random(seed)
        team = generate_team_with_abilities(rng)
        enemies = generate_enemies_with_abilities(rng)
        weather = rng.choice(list(WeatherState))
        result = resolve_combat(team, enemies, weather)
        assert result.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)

    @pytest.mark.parametrize("seed", range(10))
    def test_boss_combat_resolution(self, seed):
        """Boss fight with phase transition resolves correctly."""
        rng = Random(seed)
        team = generate_random_team(rng, size=rng.randint(5, 10))
        boss_data = BOSS_DATA[rng.choice(list(BOSS_DATA.keys()))]
        boss = instantiate_boss(boss_data)
        cast = boss_supporting_cast(boss_data)
        enemies = [boss] + cast
        weather = rng.choice(list(WeatherState))

        result = resolve_combat(team, enemies, weather)

        # If player won, boss must be dead
        if result.outcome == CombatOutcome.WIN:
            assert boss.id not in result.surviving_enemy_ids

        # If boss reached phase 2, the phase event should be in the log
        phase_events = [e for e in result.events if e.event_type == "phase_change"]
        if any(ps.hp <= ps.max_hp * 0.5 for ps in result.boss_states()):
            assert len(phase_events) >= 1
```

### 7.2 Tick-by-tick trace test

```python
def test_tick_trace():
    """Run a combat and print a human-readable tick-by-tick trace.
    Not an assertion test — used for manual inspection during development.
    Marked with a custom marker so it can be run selectively."""
    team = [make_champion("sunmane_lion", tier=6, level=1)]
    enemies = [make_enemy("heavy_knight", tier=4)]
    weather = WeatherState.CLEAR

    result = resolve_combat(team, enemies, weather)

    for event in result.events:
        print(f"[tick {event.tick:4d}] {event.event_type:12s} | "
              f"{event.source_name} → {event.target_name} | "
              f"amount={event.amount:.0f}")

    # Assert only that it finished
    assert result.outcome in (CombatOutcome.WIN, CombatOutcome.LOSS, CombatOutcome.DRAW)
```

---

## 8. Determinism Suite (`test_determinism.py`)

Cross-cutting determinism tests that run the full pipeline and verify
byte-equal results.

```python
class TestDeterminism:
    """Every test in this class verifies the V.2 invariant:
    identical inputs → identical outputs."""

    def test_combat_determinism(self):
        """Same team + enemies + weather → byte-equal BattleResult."""
        for seed in range(20):
            team = generate_team(seed=seed)
            enemies = generate_enemies(seed=seed)
            r1 = resolve_combat(team, enemies, WeatherState.RAIN)
            r2 = resolve_combat(team, enemies, WeatherState.RAIN)
            assert r1 == r2

    def test_encounter_determinism(self):
        """Same run seed → identical encounter sequence across all nodes."""
        nodes_a = [generate_fight(run_seed=42, node_index=i, stage=STAGES[i//10]) for i in range(50)]
        nodes_b = [generate_fight(run_seed=42, node_index=i, stage=STAGES[i//10]) for i in range(50)]
        for a, b in zip(nodes_a, nodes_b):
            assert_squads_equal(a, b)

    def test_formation_determinism(self):
        """Same squad → same formation."""
        squad = generate_fight(run_seed=42, node_index=5, stage=STAGES[2])
        pieces = [to_combat_state(e) for e in squad]
        f1 = plan_enemy_formation(pieces)
        f2 = plan_enemy_formation(pieces)
        assert f1 == f2

    def test_full_pipeline_determinism(self):
        """Full pipeline: encounter gen → formation → combat → same result."""
        for seed in range(10):
            squad = generate_fight(run_seed=seed, node_index=3, stage=STAGES[1])
            team = generate_team(seed=seed)
            pieces_a = [to_combat_state(e) for e in squad]
            pieces_b = [to_combat_state(e) for e in squad]
            form_a = plan_enemy_formation(pieces_a)
            form_b = plan_enemy_formation(pieces_b)
            assert form_a == form_b
            # ... run combat with both and compare results

    def test_no_hash_dependency(self):
        """No str hash() in generation pipeline.
        This is a static analysis test — grep for hash() usage in game/."""
        import ast
        import pathlib
        game_dir = pathlib.Path("src/game")
        for py_file in game_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "hash":
                        # Allow hash() only in __hash__ methods
                        # Check parent is not a __hash__ def
                        pytest.fail(f"hash() found in {py_file}: line {node.lineno}")
```

---

## 9. CI Lint Tests (Invariant Enforcement)

```python
def test_no_flet_imports_in_game():
    """game/ has zero Flet imports (V.1)."""
    for py_file in Path("src/game").rglob("*.py"):
        content = py_file.read_text()
        assert "import flet" not in content
        assert "from flet" not in content

def test_no_random_in_game():
    """game/ never uses random.random() etc. — all RNG via ctx.rng."""
    forbidden = ["random.random", "random.choice", "random.randint", "random.uniform"]
    for py_file in Path("src/game").rglob("*.py"):
        if py_file.name == "rng.py":
            continue  # The RNG wrapper itself is allowed
        content = py_file.read_text()
        for f in forbidden:
            assert f not in content, f"{f} found in {py_file}"

def test_combat_does_not_import_content():
    """combat/ never imports content modules."""
    content_imports = [
        "from game.abilities", "from game.items", "from game.traits",
        "from game.augments", "from game.champions",
        "from src.game.abilities", "from src.game.items", "from src.game.traits",
    ]
    for py_file in Path("src/game/combat").rglob("*.py"):
        content = py_file.read_text()
        for imp in content_imports:
            assert imp not in content, f"{imp} found in {py_file}"
```

---

## 10. Test Fixtures & Helpers

### 10.1 Piece factories

```python
def make_piece(**overrides) -> CombatPieceState:
    """Create a CombatPieceState with sensible defaults and optional overrides."""
    defaults = dict(
        piece_id="test_piece", max_hp=600, hp=600, strength=50, intelligence=50,
        attack_speed=100, move_speed=90, mana_regen=10, threat=60,
        armor=25, resistance=25, attack_range=2, ability_cost=36000,
        is_enemy=False, alive=True, ...
    )
    defaults.update(overrides)
    return CombatPieceState(**defaults)

def make_champion(champion_id: str, tier: int = 1, level: int = 1) -> Champion:
    """Instantiate a champion from the roster."""
    ...

def make_enemy(enemy_id: str, tier: int = 1) -> Enemy:
    """Instantiate an enemy from the roster."""
    ...

def make_boss(boss_id: str = "holloway") -> Enemy:
    """Instantiate a boss from the roster."""
    ...
```

### 10.2 Combat context factories

```python
def make_combat_context(**kwargs) -> CombatContext:
    """Create a minimal CombatContext for testing."""
    ...

def make_combat_context_with_map_effect(effect_class) -> CombatContext:
    """Create a CombatContext with a map effect active."""
    ...
```

### 10.3 Squad helpers

```python
def assert_squads_equal(a: list[Enemy], b: list[Enemy]) -> None:
    """Assert two squads are byte-equal."""
    assert len(a) == len(b)
    for ea, eb in zip(a, b):
        assert ea.to_dict() == eb.to_dict()

def generate_random_team(rng: Random, size: int) -> list[Champion]:
    """Generate a random player team for scenario testing."""
    ...

def generate_random_enemies(rng: Random, size: int) -> list[Enemy]:
    """Generate a random enemy squad for scenario testing."""
    ...
```

---

## 11. Test Execution Strategy

### 11.1 Fast tests (< 5s total)

All unit tests in `test_models.py`, `test_effects.py`, `test_formation.py`,
`test_encounter.py`, `test_abilities.py`, `test_challenge_boss.py`. These run
on every commit.

### 11.2 Scenario tests (~30s)

`test_combat_scenarios.py` with 50 parameterized seeds. Runs on every PR.

### 11.3 Determinism stress (~60s)

`test_determinism.py` with full pipeline verification. Runs on every PR.

### 11.4 Manual inspection

`test_tick_trace` — run selectively during development to observe combat
resolution step by step. Not part of CI.

```bash
python -m pytest tests/game/test_combat_scenarios.py::test_tick_trace -v -s
```

---

## 12. Open Items

| # | Question | Recommendation |
|---|---|---|
| 1 | Test coverage target | Aim for 90%+ on game logic; don't chase 100% |
| 2 | Property-based testing (Hypothesis) | Add for combat invariants post-MVP |
| 3 | Replay/snapshot tests | Serialize a BattleResult → compare on PR |
| 4 | Performance benchmarks | Add after T20 ships (80-champion worst case) |
| 5 | Map effect test depth | One test per effect type minimum |
