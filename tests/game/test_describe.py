"""T.41a — shared description render-layer (items).

Covers V.78 (every item has ITEM_META; stat line introspected from the
EffectBundle, never re-typed), V.80 (pure presentation — no Flet, no mutation),
and the stat-line derivation.
"""

from __future__ import annotations

import src.game.items  # noqa: F401 — populate ITEM_REGISTRY
from src.game.describe import RenderedEntry, render_item, stat_line
from src.game.items.meta import ITEM_META
from src.game.registries import ITEM_REGISTRY


# --------------------------------------------------------------------------
# V.78 — completeness: every registered item has metadata
# --------------------------------------------------------------------------
def test_every_item_has_meta():
    assert set(ITEM_META) == set(ITEM_REGISTRY), (
        f"missing meta: {set(ITEM_REGISTRY) - set(ITEM_META)}; "
        f"orphan meta: {set(ITEM_META) - set(ITEM_REGISTRY)}"
    )


def test_item_count_is_fifty():
    assert len(ITEM_META) == 50


def test_every_meta_has_name_and_blurb():
    for iid, meta in ITEM_META.items():
        assert meta.name and not meta.name[0].islower(), f"{iid}: bad name {meta.name!r}"
        assert meta.blurb, f"{iid}: empty blurb"


# --------------------------------------------------------------------------
# stat_line — fractional muls + flat/pct adds
# --------------------------------------------------------------------------
def test_stat_line_muls():
    assert stat_line({"strength": 0.08, "attack_speed": 0.08}) == "+8% STR, +8% AS"


def test_stat_line_empty():
    assert stat_line() == ""


def test_stat_line_crit_add_renders_as_percent():
    # crit_chance is a fractional "add" → shown as a percentage, not a flat 0.15.
    assert stat_line(adds={"crit_chance": 0.15}) == "+15% CRIT"


# --------------------------------------------------------------------------
# V.78 — render_item derives the stat line from the EffectBundle (never re-typed)
# --------------------------------------------------------------------------
def test_render_component_name_and_derived_stat():
    r = render_item("fang")
    assert isinstance(r, RenderedEntry)
    assert r.name == "Fang"
    assert r.stat_line == "+12% STR"   # = the Modifier mul 1.12, introspected
    assert r.text  # has a blurb


def test_render_talon_attack_speed():
    assert render_item("talon").stat_line == "+12% AS"


def test_render_keen_claw_crit():
    assert render_item("keen_claw").stat_line == "+15% CRIT"


def test_render_combined_two_stats_and_blurb():
    # Witherbloom Censer = Heartseed (INT) + Old Hide (HP) → both derived.
    r = render_item("witherbloom_censer")
    assert r.name == "Witherbloom Censer"
    assert "INT" in r.stat_line and "HP" in r.stat_line
    assert "rot" in r.text.lower()


def test_render_item_with_hooks_still_derives_headline_stat():
    # Apex Fang carries a takedown hook but the headline STR mul still derives.
    r = render_item("apex_fang")
    assert "STR" in r.stat_line


def test_derived_stat_matches_modifier_exactly():
    # The promise of V.78: the shown number == the number combat applies.
    for iid in ITEM_REGISTRY:
        bundle = ITEM_REGISTRY[iid](None)
        for mod in bundle.modifiers:
            if mod.op == "mul":
                pct = f"{(mod.value - 1.0) * 100:+.0f}%"
                assert pct in render_item(iid).stat_line, (
                    f"{iid}: {pct} from {mod.stat} not in stat line"
                )


def test_unknown_item_renders_none():
    assert render_item("not_an_item") is None


# --------------------------------------------------------------------------
# V.80 — pure presentation: no Flet, deterministic, no mutation
# --------------------------------------------------------------------------
def test_describe_module_has_no_flet():
    import src.game.describe as d
    src = __import__("inspect").getsource(d)
    assert "flet" not in src and "import ft" not in src


def test_render_is_deterministic():
    assert render_item("fang") == render_item("fang")


def test_render_does_not_mutate_registry_or_bundle():
    before = dict(ITEM_REGISTRY)
    render_item("apex_fang")
    render_item("witherbloom_censer")
    assert ITEM_REGISTRY == before  # introspection mutated nothing


# --------------------------------------------------------------------------
# T.41b — trait descriptions (V.79)
# --------------------------------------------------------------------------
import src.game.traits  # noqa: E402,F401 — populate TRAIT_REGISTRY
from src.game.describe import render_trait  # noqa: E402
from src.game.registries import TRAIT_REGISTRY  # noqa: E402
from src.game.traits.meta import TRAIT_META  # noqa: E402


def _code_counts(tid: str) -> set:
    return {bp.count if isinstance(bp.count, int) else "full"
            for bp in TRAIT_REGISTRY[tid]()}


def test_every_trait_has_meta():
    assert set(TRAIT_META) == set(TRAIT_REGISTRY), (
        f"missing: {set(TRAIT_REGISTRY) - set(TRAIT_META)}; "
        f"orphan: {set(TRAIT_META) - set(TRAIT_REGISTRY)}"
    )


def test_trait_count_is_25():
    assert len(TRAIT_META) == 25


def test_meta_rungs_match_code_breakpoints():
    # V.79: one description per ACTUAL factory() breakpoint (no more, no less).
    for tid in TRAIT_REGISTRY:
        assert set(TRAIT_META[tid].rungs) == _code_counts(tid), (
            f"{tid}: meta rungs {set(TRAIT_META[tid].rungs)} != code {_code_counts(tid)}"
        )


def test_reconciled_drift_follows_code_not_catalog():
    # Catalog said Bruiser @8 / Stalker @7, but code apexes are @10 / @8 — meta
    # must follow code (the V.79 guard above enforces it; assert the specifics).
    assert 10 in TRAIT_META["Bruiser"].rungs and 8 not in TRAIT_META["Bruiser"].rungs
    assert 8 in TRAIT_META["Stalker"].rungs and 7 not in TRAIT_META["Stalker"].rungs


def test_render_trait_derives_stat_line_from_packs():
    rt = render_trait("Beast")
    assert rt is not None and rt.name == "Beast" and rt.blurb
    by_count = {r.count: r for r in rt.rungs}
    assert by_count[2].stat_line == "+8% HP"          # = the rung's mul, derived
    assert by_count[2].text                            # has effect prose
    # Packmate carries a dynamic "full" apex rung.
    assert any(r.count == "full" for r in render_trait("Packmate").rungs)


def test_render_trait_rung_scope_matches_factory():
    # Each rung's scope ("carriers"/"team") must match the breakpoint's TraitScope.
    from src.game.traits.types import TraitScope
    for tid in TRAIT_REGISTRY:
        by_count = {bp.count if isinstance(bp.count, int) else "full": bp
                    for bp in TRAIT_REGISTRY[tid]()}
        for r in render_trait(tid).rungs:
            expected = "team" if by_count[r.count].scope is TraitScope.TEAM_WIDE else "carriers"
            assert r.scope == expected, f"{tid} @{r.count}: scope {r.scope} != {expected}"


def test_apex_rungs_go_team_wide():
    # The classic Kinship/Calling shape: body = carriers, apex = team.
    beast = {r.count: r.scope for r in render_trait("Beast").rungs}
    assert beast[2] == "carriers" and beast[8] == "team"
    # Packmate is team-wide on every rung by design.
    assert all(r.scope == "team" for r in render_trait("Packmate").rungs)


def test_render_trait_unknown_is_none():
    assert render_trait("not_a_trait") is None


def test_render_trait_deterministic():
    assert render_trait("Hunter") == render_trait("Hunter")
