# Journal Entry Template

Journals are the **narrative / "why" layer**. SPEC.md is the contract layer (what
the invariant *is*); the journal is the story (why it exists, what we rejected,
where the agent and the code disagreed). Append `docs/journal/<YYYY-MM-DD>_<topic>.md`
after any non-trivial milestone.

Copy the skeleton below. Drop optional sections, but the **Process notes (AI
collaboration)** section is **mandatory** — see "Why the process section is required".

---

```markdown
# <YYYY-MM-DD> — <short title>

<1-3 line framing: what landed, which commits, what task/§T/§B/§V it touches.>

## What changed

<Numbered list. One item per conceptual change — even when several rode the same
commit. Cite `file.py` touch points and the commit hash.>

## Why (the part SPEC compresses out)

<The reasoning the spec can't hold: the alternatives considered and rejected, the
false assumption that caused the bug, the design philosophy. This is the whole
point of the journal — if it's only restating the diff, you haven't written the
journal yet.>

## Decisions

<Bulleted. Each decision + its rationale, especially the non-obvious ones and the
ones a future agent would plausibly get wrong.>

## Process notes (AI collaboration)   ← MANDATORY

<This repo is built with AI agents. Document the collaboration reality, not just
the code. At least one bullet from each that applies:

- **Conflicts / misalignments** — where CLAUDE.md, SPEC.md, the design docs, and
  the code disagreed. Which won, and why. (e.g. design-doc examples citing stat
  keys that don't exist; roster vocabulary drifting from a catalog.)
- **Agent errors** — wrong turns the agent (or you steering it) took: a plausible-
  but-wrong approach, a hallucinated primitive, a naming collision walked into, a
  fix that missed the root cause first time. Record it so it isn't repeated.
- **Guardrails added** — invariants/tests written specifically to stop an agent
  from making the same mistake again (an invariant doubling as an agent guardrail).
- **Drift caught** — spec-vs-code or doc-vs-code gaps found and reconciled.>

### Prompting-strategy reflection   ← MANDATORY (bonus weight)

<How did the *way you prompted / drove the agent* work out this time? What prompt
shape was high-leverage (e.g. "trace the cause and decide if an invariant should
catch recurrence" vs "just fix it")? What was low-leverage (e.g. batching too much
per commit, under-specifying scope)? How is your prompting strategy evolving across
the life of this project? This is the longitudinal record of learning to build
*with* agents — treat it as a first-class deliverable, not an afterthought.>

## Files

<Flat list of touched files + the SPEC/doc deltas.>

## Follow-ups

<Loose ends, deferred work, things to verify in a later sweep.>
```

---

## Why the process section is required

This project is an experiment in **building software collaboratively with AI
agents** (see CLAUDE.md, README). The interesting, gradeable, and reusable
knowledge is not only *what* the code does — it's *how the human + agent loop
produced it*: where the agent drifted, where the spec saved us, how the prompting
changed as the codebase grew. That signal is invisible in the diff and evaporates
fast. Capturing it every entry is what turns this repo from "a game" into "a
documented case study in vibe-coding a non-trivial system".

Rule of thumb: if a future agent reading only the code would repeat a mistake we
already made, the journal's **Process notes** section failed.
