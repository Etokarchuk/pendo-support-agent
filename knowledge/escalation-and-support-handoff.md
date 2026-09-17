---
id: escalation-and-support-handoff
title: Escalation and support handoff
tags: [escalation, support, ticket, handoff]
---

# Escalation and support handoff

Not every issue can be resolved through self-service diagnosis. Escalate to human support when either is true:

- Every check available (guide status, segment eligibility, install status) comes back healthy, and the guide still isn't behaving as expected — the cause is outside what account-level configuration data can explain (e.g. a rendering bug, a targeting rule edge case, a backend issue).
- A required check could not be completed (a dependency was unavailable) and there is no way to verify the relevant fact.

A useful escalation carries a **summary** of the customer's issue, the **specific checks already performed and their results**, and an explicit statement of **what remains unresolved and why**. This lets a support engineer start from "here's what's already ruled out" instead of re-asking the customer the same triage questions, and lets the customer avoid repeating themselves.

Escalating when self-service diagnosis has actually succeeded (a config issue was clearly identified and is fixable by the customer) wastes the support queue's time and delays the customer's fix — give them the specific fix instead.
