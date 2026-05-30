"""Power simulation & balance benchmarking (T.25).

Exhaustive deterministic matchup sweeps + Bradley-Terry ratings derived from
the auto-resolve combat engine. Pure consumer of src/game/ — no UI, no API.

Sub-modules:
    matchup     — piece <-> piece-on-other-side bridges; MatchupConfig/Result; run_matchup
    tournament  — pair enumeration + sampling
    ratings     — Bradley-Terry MLE + binary win rate (per-piece attribution)
    report      — CSV writers + console summary
    runner      — argparse CLI entry point
"""
