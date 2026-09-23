---
id: segment-rule-changes-and-staleness
title: Segment rule changes and estimate staleness
tags: [stale, recompute, rule change, freshness]
---

# Segment rule changes and estimate staleness

A segment's `estimated_visitors` count is not computed live on every read — it is recalculated on a rolling cycle (roughly every 24 hours in the current system) and cached until the next cycle.

This creates a specific, easy-to-miss failure mode: if a segment's rule is edited, the cached estimate still reflects the *old* rule until the next recompute cycle runs. A segment can therefore show `0` visitors immediately after a rule change even though the new rule would match visitors just fine once recomputed — the `0` is stale, not wrong, and not evidence the new rule is broken.

**How to tell the difference between "stale" and "actually empty":** compare the segment's `computed_at` timestamp to its `rule_updated_at` (or any noted rule change). If `computed_at` is *before* the rule change, the estimate predates it and cannot be trusted as a verdict on the current rule — the honest answer is "not yet known, will refresh within the recompute window," not "this segment is empty." If `computed_at` is *after* the rule change, the estimate does reflect the current rule.

Never state a segment is definitively empty when its estimate predates a known rule change — flag it as stale and give the customer the expected refresh window instead.
