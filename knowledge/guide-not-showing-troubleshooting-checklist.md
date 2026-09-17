---
id: guide-not-showing-troubleshooting-checklist
title: "Guide not showing: troubleshooting checklist"
tags: [troubleshooting, checklist, not showing, guide broken]
---

# Guide not showing: troubleshooting checklist

When a guide isn't appearing for visitors who should see it, the usual causes, roughly in order of frequency:

1. **Not published.** The guide is still a draft. See: guide publishing and status.
2. **Segment has no current matches.** The live segment estimate is 0 even though the publish-time snapshot was higher, usually because a metadata field the rule depends on stopped arriving. See: segments and eligibility.
3. **Install snippet not active in the target app.** No events at all from that app recently. See: install snippet and visitor metadata.
4. **Metadata field missing.** Snippet is active, but a specific field the segment rule needs isn't being sent. See: install snippet and visitor metadata.
5. **Display frequency already satisfied.** Eligible visitors already saw the guide under a "once" frequency setting. See: guide display frequency and scheduling.
6. **Active date range hasn't started or has ended.** See: guide display frequency and scheduling.

More than one of these can be true for the same guide at once (e.g. a snippet problem and an unrelated segment problem) — check each independently rather than stopping at the first plausible cause, and report every cause found, in the order a fix would need to happen (an app with no events can't be fixed by touching the segment).

If every item above checks out and the guide still isn't appearing, this is not a self-service configuration issue — escalate to support with what was already checked so they don't have to repeat it.
