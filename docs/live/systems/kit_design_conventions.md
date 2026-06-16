> **Status: LIVING** — conventions for authoring champion/enemy kits + axes. Must match the
> formulas in `src/game/combat/context.py`, `src/game/scaling.py`, `src/game/content.py`.
> Audited by `/check` (cited constants must hold; the prose rules are review-enforced).
> **Scope:** the balance/identity anti-patterns to watch when writing or re-axising a kit.
> **Reconciled:** 2026-06-16 @ T.36 roster rebalance (kings + the 3 caster→auto flips).

# Kit design conventions — faults to watch

Hard-won from the T.36 Primordial rework + the 12-piece distribution re-axis. Each rule
below was paid for by a real misfit caught mid-design. Read before authoring or re-axising.

## Identity & role

1. **The Calling fixes the *playstyle*; the stat stays flexible.**
   Cast-Callings (Channeler / Mystic / Multicaster / Warden / Mender) → `ability`.
   Auto-Callings (Hunter / Skirmisher / Stalker / Bruiser) → `auto`. Guardian = tank,
   *leans* cast but soft. **Never put a Channeler in an `auto` cell or a Hunter in an
   `ability` cell** — the kit reads wrong even when the numbers are fine. (T.36 caught this
   in 3 of 6 kings + 4 of 12 distribution pieces; the original plan draft had them
   backwards.) When a target cell needs a playstyle the Calling fights, the cheap fix is a
   **minimal, lore-natural Calling tweak** (add an auto-Calling), not a forced playstyle.

2. **Hold `intent` → preserve the role. Flex `stat` + `playstyle` freely.**
   `classify_role(stat, reach, durability, playstyle, speed, intent)` — `intent` (with
   durability) is the dominant role lever. Changing stat/playstyle reshapes *how* a piece
   fights; changing intent silently changes *what role it is*. A Hunter at `intent=utility`
   is still a **support** that happens to auto-attack — not all auto-Callings are dealers.
   Verify `build_role_code` before/after any re-axis; if the role moved and you didn't mean
   it to, you changed intent by accident.

3. **Don't erase a piece's soul when you re-axis it — relocate it.**
   dusk_bat (debuff-support) flipped to `str/auto` kept its blind by moving it *onto the
   autos*. phantom_lynx kept its pen/ghost identity by moving "ignore defense" onto a
   true-damage empowered auto. The mechanic moves to the new playstyle; the fantasy stays.

## Coefficients & scaling

4. **`str/ability`: the ability is the main value; the STR coeff sits *below* the INT
   baseline.** The free auto-attack tagalong already pays STR (autos are `1.0·STR + 0.25·INT`,
   `context.py:~409`). Parity vs the INT coeff it replaces:
   `coeff_str ≈ coeff_int − 0.667·(autos_per_cast)` → a ranged caster lands ~1.1–1.7; AoE+CC
   sits at the low end (the CC is the payoff). **Not** the old "ability empowers autos"
   steroid. (Mournhollow's naive `STR·2.7` was ~2× over.)

5. **`*/auto` (str/auto, int/auto, hybrid/auto): the autos must carry — fold the active's
   payoff *into* an auto.** Patterns: on-hit proc (`int/auto` = on-hit-INT, no STR),
   empower-next-auto (Yorick-style), discharge-on-auto. If the piece "doesn't care about its
   autos," it isn't really an auto piece. (phantom_lynx's whole active resolves through an
   auto; granite_gorilla discharges its bank through autos.)

6. **Beware the hidden multiplier: per-event scaling × event count.**
   `charge += STR·k` *per blow* over `N` blows = an effective coeff of `k·N`, not `k`. A tank
   eats many hits → `N` is large → a normal-looking `k` becomes a hypercarry coeff, and stat
   items then scale it. **Fix:** keep `k` low *and* hard-cap the accumulator (`charge ≤
   STR·1.5`) so the `N` multiplier can't run — leaving linear stat scaling. Same family as
   the Aurion bug (`+1 primary/tick` → ~600% over a fight); both are unbounded per-tick/
   per-event ramps. Always bound a ramp by stacks or a cap.

7. **Size penetration against the actual resistance ceiling.**
   Penetration is a **global attacker stat** (`penetration` / `penetration_pct`,
   `context.py:256-257`), *not* per-hit — you cannot scope it to one damage instance. Flat
   pen subtracts from mitigation, so it **zeroes any target whose res < pen**. Max resistance
   in the roster ≈ **359** (T7 tanky_arm), typical big tank ~286, `MITIGATION_CONSTANT=100`.
   Size flat pen so it shreds tanks *partially* and never blankets the midfield (phantom's
   `INT·0.12` peaks ~49 ≈ 14% of max res; `INT·0.3` zeroed everything under 123).

8. **True damage is premium → lower its coeff than a magic hit.**
   `SourceTag.TRUE` bypasses **all** mitigation (`context.py:253-254`). Prefer it over
   penetration for an "ignore defense" finisher, but price it below a mitigated nuke.

## Retaliation, sustain, persistence

9. **Never tie retaliation to a flat/% of *incoming* damage when HP pools are asymmetric.**
   A tank reflecting %-of-hit returns trivial damage to itself but *lethal* chip to a squishy
   — worst case **a squishy dies faster attacking the tank than the tank dies**. Punishes the
   wrong axis. Use a banked-and-discharged model directed at the retaliator's *own* target,
   capped, scaled by the retaliator's own stat (not enemy damage). (granite_gorilla.)

10. **Scope a diver's sustain to its own commitment, not a passive omni-stat.**
    A squishy auto-carry/swashbuckler gets lifesteal tied to its burst/true-strike (so it
    must commit and land to be rewarded), never free lifesteal on every hit. (phantom_lynx
    reaps only off the empowered true-damage auto.)

11. **Piece stat-stacking is in-combat only; cross-`Run` permastacking is augment-exclusive.**
    Combat is a pure function (V.2) — all piece runtime state rebuilds per `resolve_combat`,
    so nothing persists across battles by construction. Write blurbs as "until end of battle,"
    never "permanently" (which mislabels an in-combat ramp).

## Process & verification

12. **The analytic DPS / HP·DPS proxy is a smoke-detector, not a scale.**
    Single-target DPS *understates* AoE+CC casters (no AoE multiply, no CC value) and
    auto-carries with uncounted procs/steroids. Use it to catch a piece sitting wildly
    off-budget (it caught Mournhollow at ~147k). The real gate is the V.33 ±10% HP·DPS proxy
    + `tools/simulation/stat_edge.py` teamfight sims.

13. **"power" is reserved.** `scaling.power(T,L) = 1.5^((T-1)/2 + (L-1))` is the abstract
    power scalar. The survivability×damage worth proxy is **HP·DPS** — never call it "power."

14. **Determinism is non-negotiable (V.2/V.14).** Every "every Nth" / "chance" / ramp uses a
    deterministic cadence counter (like `crit_counter`), never RNG — sims must stay
    byte-identical.

15. **When reshuffling axis assignments, preserve the *destination cell multiset*.**
    The stat×playstyle grid marginals are the contract, not which piece sits where. Reassign
    freely to honor Callings as long as the multiset of target cells is unchanged — the grid
    still lands exactly. (Both T.36a kings and T.36b distribution were corrected this way with
    zero grid impact.)
