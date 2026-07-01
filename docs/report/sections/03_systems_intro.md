# Systems & Features

This chapter is the mid-level reference layer: how each subsystem and content
area works *now*, and where it lives in the code. It is assembled from the
project's **LIVING** documentation (`docs/live/`) — docs that are reconciled to
the code on every change that touches their subject and audited by the `/check`
drift tool. Where the previous chapter mapped *what exists and how it interacts*,
this one goes one level deeper into each system in turn.

The sections below cover, in order, the combat engine and its resolution
pipeline, the effect/hook/status framework that all content plugs into, the two
weather systems, enemy formation, encounter and board generation, stat scaling,
the weather API layer, save/serialization, items, and the kit-authoring
conventions — followed by the content references (rosters, abilities, traits,
augments, items) whose real data lives in code.
