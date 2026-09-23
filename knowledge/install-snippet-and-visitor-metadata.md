---
id: install-snippet-and-visitor-metadata
title: Install snippet and visitor metadata
tags: [install, snippet, metadata, sdk, app]
---

# Install snippet and visitor metadata

Guides render inside a host application through an install snippet embedded in that app. Two things can be wrong independently:

- **The snippet isn't installed or isn't firing.** No guide of any kind can appear, regardless of segment or publish status. Signals: no recent events from the app, or `snippet_installed: false`. This is a code/deploy issue in the host app, not a guide configuration issue.
- **The snippet is installed and sending events, but not sending a specific metadata field.** Guides and segments both still work, but any segment rule that depends on the missing field will never match. This is a configuration issue in what the host app's SDK call sends per visitor, not a guide or segment issue.

Always check both independently: a healthy `last_event_at` (recent) tells you the snippet is alive, but says nothing about which metadata fields are included in those events. Compare a segment's rule fields against the app's `metadata_fields_received` list directly.

Metadata field changes typically happen when engineering updates the SDK initialization call (e.g. during a release) and don't realize a field consumed by a segment rule was dropped or renamed. This is invisible from the guide editor — nothing about the guide or segment looks misconfigured.
