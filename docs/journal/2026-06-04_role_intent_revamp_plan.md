# 2026-06-04 — Role system revamp: intent axis + role/role_code (T.32 plan)

Planned (not yet built) the role-system revamp from GitHub issue #37. Landed a §T row
(T.32), three invariants (V.31/V.32/V.33), a §B drift entry (B.13), a full plan doc, and
a generated 648-combo classifier matrix. No production code yet — this is plan-only.

## What changed

1. **New §T.32** — role revamp scoped: 6th archetype axis `intent`, composer full-rework,
   8-role `classify_role` + `role_code`, `stat_overrides` scope/ordering fix.
2. **Plan doc** `docs/design/tasks/t32_role_intent_revamp_plan.md` — full architecture,
   authored intent-multiplier values, drift guard, test plan, SPEC deltas.
3. **Matrix fixture** `docs/design/tasks/t32_role_matrix.txt` — all 648 axis combos →
   `role_code` → `role`, generated + validated (0 role_codes map to >1 role).
4. **SPEC** `SPEC.md` — T.32 row; V.31 (intent presence), V.32 (role/role_code pure-axis
   functions), V.33 (full-compose + override scope/ordering + ±10% intent drift guard);
   B.13 (axis-count drift); D.10 role-taxonomy half resolved; Implementation Order +
   planning note.

## Why (the part SPEC compresses out)

**Issue #37 wanted `primary_role` / `secondary_role_signature`.** User overrode the naming
mid-brainstorm: `role` = coarse title, `role_code` = fine descriptor — because
"primary/secondary" wrongly implies the primary matters more, when really one is a *title*
and the other a *finer encoding* of the same thing. Good call; the field names now read as
what they are.

**Controller died on contact with "role = pure axis function."** Issue #37 + early
brainstorm wanted a `controller` role (debuff support) split from `support` (buff). But the
buff-vs-debuff signal lives in the *kit/traits* (Trickster Calling = "Debuff supports"), not
in any axis. Once the user pinned role to be derived *exclusively* from axis identity,
controller became underivable — folded into `support`. The lesson: a role taxonomy that's a
pure function of N axes can only express distinctions those axes encode. We chose to keep
roles axis-pure (auditable, deterministic, no trait coupling) and accept that debuff/buff is
a kit concern, surfaced elsewhere.

**Threat was the one un-composed stat — and that turned out to be the cleanest win.** The
audit found `threat`/`move_speed`/`ability_cost` are authored **0×** in the whole roster:
`compose_stats` puts `threat=60` in the base, no axis ever touches it, then `_build_*`
overwrites it with `d.threat` (default 60). Pure dead plumbing. Folding threat *into* the
composer (tanks pull aggro, casters sneak, utility taunts) both removes the exception and
fixes a long-standing "threat is uniformly 60" blandness — without needing a 7th axis. The
user floated a "taunt-vs-sneak" 7th axis; we rejected it because durability+intent+playstyle
already carry the signal and the 6-axis constraint is firm.

**Power-drift guard confusion resolved by naming what "power" is.** The user couldn't see how
to tell if raising threat breaks a power budget. Answer: it can't — `threat`/`move_speed`/
`mana_regen`/`crit`/`penetration` are **not** power stats. Power `P` is the HP×DPS budget;
only `max_hp/armor/resistance` (eHP) and `str/int/attack_speed` (DPS) feed it. So the intent
drift guard only watches `(dmg·AS)·√(hp·armor·res) ∈ [0.90,1.10]` and ignores everything
else. Threat is free. This reframing (which stats *are* power) is the durable insight.

**`role_code` dynamic length is safe because it's a tag-set, not a record.** Stripping
`hybrid` tokens makes the code variable-length — which would break any consumer doing
`code.split('-')[5]`. We set the contract now (nothing consumes it yet): `role_code` is a
non-positional tag-set (membership/substring), and anything needing a field reads first-class
`role`/`intent`. Omitting `hybrid` is *lossless* (absent axis = hybrid by position), so the
code stays injective — proven by the 648-row matrix.

## Decisions

- **6 axes, final**: `stat`(str/int/hybrid) · `reach`(melee/ranged) ·
  `durability`(squishy/hybrid/tanky_hp/tanky_arm) · `playstyle`(auto/hybrid/ability) ·
  `speed`(speedy/hybrid/heavy) · `intent`(damage/hybrid/utility). Renames: `primary_stat`→
  `stat`, `range_`→`reach` (drops the builtin-dodging underscore); both middles → `hybrid`
  to unify the convention. `hybrid` deliberately recurs across 4 axes.
- **8 roles**: tank · bruiser · support · mage · marksman · assassin · swashbuckler ·
  spellblade. `swashbuckler` = melee-auto (user rejected `warrior` as too generic / synonym
  of bruiser); `spellblade` = the all-hybrid generalist catch-all.
- **Intent authored from roster archetype tags** (`Tank-*`→utility, `APC/ADC-*`→damage,
  `SUP-*`→utility, `Hybrid-*`→hybrid). Not defaulted-to-hybrid — user wanted it design-driven.
- **stat_overrides**: any stat incl. premium (crit/pen), key-validated, applied
  **after tier-scale, before level-scale** so scalable overrides level-scale while
  pen/crit/threat stay flat.
- **Stats *will* shift** for damage/utility pieces — user confirmed re-baselining the sim is
  expected tuning churn, not a blocker. `hybrid`-intent pieces stay byte-identical.

## Process notes (AI collaboration)

- **Conflicts caught**:
  - *Issue text vs code vocabulary* — #37 said "add a sixth axis" implying 5 existed; t5
    design doc says "**4 orthogonal axes**"; code actually ships **5** (`speed` bolted on
    post-t5, never back-propagated). Reconciled to 6 + logged as B.13 with a V-guard so the
    count can't silently drift again.
  - *Issue naming vs user* — #37's `primary_role`/`secondary_role_signature` overridden to
    `role`/`role_code` by the user. Followed the human, not the ticket.
- **Agent errors (mine, this session)**:
  - **Arithmetic**: stated the combination space as "1944" twice (3·2·4·3·3·3 = **648**).
    Only caught when the validation script printed 648. Lesson: compute combinatorics in code,
    not in prose.
  - **Worked-example math**: wrote the utility drift example as `≈0.96`; actual `0.984`. Fixed
    in plan review before spec. Don't hand-wave numbers that a guard will later assert.
  - **SPEC insert ordering**: dropped V.31–V.33 *above* V.30 on first edit (out of numeric
    order); had to reorder. Appending invariants needs an explicit "after the highest-numbered
    one" anchor, not "near the end of §V".
  - **Near-miss naming collisions**: walked toward `bruiser` as both a durability value *and*
    a role title, and `standard`→`sturdy` before the user simplified it to `hybrid`. The user's
    "just reuse hybrid for the middle, like the other axes" was cleaner than my proposals.
- **Guardrails added**: V.31 (intent presence, CI), V.32 (role/role_code pure + non-positional),
  V.33 (full-compose + override rules + drift guard) — each doubles as an agent guardrail
  against the exact drifts that produced B.13.
- **Drift caught**: the 4-vs-5-vs-6 axis count; the dead `threat`/`move_speed`/`ability_cost`
  passthrough (authored 0× — confirmed by grepping the roster call sites, not trusting the
  field defaults).

### Prompting-strategy reflection

The high-leverage move this session was the user's repeated **"brainstorm and confirm before
implementing"** combined with my front-loading the *audit facts* (the `d.*` 0×-authored grep,
the real composer pipeline, the trait-catalog buff/debuff signal) into the brainstorm before
proposing anything. Decisions got made against verified ground truth, not against the issue's
or design-doc's claims — which is exactly the CLAUDE.md "verify, don't trust the design docs"
rule paying off in a *planning* context, not just a build one.

What worked: turning every genuine fork into an explicit either/or with a recommendation
(`AskUserQuestion` once, then inline `Confirm before I proceed` checklists). The user
overrode ~half my recommendations (naming, controller, hybrid-middle, swashbuckler) — which is
the *point*: the recommendations made the forks legible enough to be overridden cheaply.

What was low-leverage / improvable: I twice produced numbers (1944, 0.96) faster than I
verified them. The fix that's emerging across this project — push any combinatorial or
arithmetic claim into a throwaway script *before* it reaches prose. The matrix script did its
job; I should have run it the first time I needed a combo count, not after asserting one.

Evolution note: earlier entries in this repo were build/bug post-mortems. This is the first
*plan-only* milestone journaled — the discipline of writing the process notes for a plan
(before any code) surfaced the axis-count drift and the dead-field audit as first-class
findings rather than incidental discoveries during a later build. Planning-time journaling
looks worth keeping.

## Files

- `docs/design/tasks/t32_role_intent_revamp_plan.md` — new (plan).
- `docs/design/tasks/t32_role_matrix.txt` — new (generated 648-combo fixture).
- `docs/journal/2026-06-04_role_intent_revamp_plan.md` — this entry.
- `SPEC.md` — +T.32 row; +V.31/V.32/V.33; +B.13; D.10 partial-resolve; Implementation Order +
  T.32 planning note.

## Follow-ups

- `/build §T.32` — wide refactor: axis renames (`primary_stat→stat`, `range_→reach`) ripple
  through `content.py`/`encounter.py`/`formation.py`/tests; expect sim-baseline regen.
- Author `intent` on all 60 champs + 60 enemies + 6 bosses from roster archetype tags.
- Sync `t5_content_plan.md` "4 orthogonal axes" → 6 (part of B.13 fix).
- Tune intent-multiplier magnitudes against a T.25 sim sweep (first-pass values shipped).
- Decide whether `formation.classify_role` (placement) should become intent-aware.
