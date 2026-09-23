---
id: segments-and-eligibility
title: Segments and visitor eligibility
tags: [segment, eligibility, visitors, count, snapshot]
---

# Segments and visitor eligibility

A guide is only shown to visitors who belong to its assigned **segment** — a rule evaluated against each visitor's attributes (e.g. region, plan tier, role) and metadata sent by the host app.

## Two different visitor counts — this is the most common source of confusion

1. **Eligible visitors at publish** — a one-time snapshot shown on the guide's summary page, calculated when the guide was published. This number never updates on its own.
2. **Segment's live estimated visitor count** — recalculated on the segment record itself as visitor data changes. This is the number that reflects *current* reality.

These two numbers describing the "same" audience can legitimately disagree, and neither one is wrong — they answer different questions ("how many matched when I published" vs. "how many match right now"). When a customer quotes the publish-time number as evidence a guide should be working, the live segment count is the one that determines what actually happens today. If they differ, explain why (usually: visitor metadata changed, or the segment rule was edited) rather than treating the discrepancy as a bug.

## Why a segment can silently go to zero

The most common cause is that the segment rule depends on a visitor metadata field (e.g. `plan_tier`, `beta_opt_in`) that the host application has stopped sending. The segment rule itself doesn't change — it simply stops matching anyone, because the field it checks is no longer present on any visitor. This shows up as `estimated_visitors: 0` with no error — the segment query still runs, it just returns no matches. Cross-check the segment's rule fields against the app's currently-received metadata fields (see the install snippet doc) before assuming the segment or guide is broken.
