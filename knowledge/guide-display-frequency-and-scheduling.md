---
id: guide-display-frequency-and-scheduling
title: Guide display frequency and scheduling
tags: [frequency, scheduling, once, repeat, show again]
---

# Guide display frequency and scheduling

Once a guide is published and a visitor is eligible, two independent settings control how often they actually see it:

- **Display frequency** — "show once ever", "show once per session", or "show every time the trigger condition is met". Set per guide in the guide editor's Scheduling tab. A visitor who already saw a "show once ever" guide will not see it again even though they remain eligible — this is expected behavior, not a bug.
- **Active date range** — an optional start/end window for the guide. Outside that window the guide won't display even to eligible, never-shown visitors.

To make a guide display only once per visitor: open the guide's Scheduling tab and set frequency to "Once". To confirm whether a specific visitor already saw a guide, check that visitor's event history rather than assuming — "should have seen it" and "did see it" are different questions once frequency limits are in play.
