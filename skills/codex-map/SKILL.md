---
name: codex-map
description: Open or restore the live Codex activity map in a pane beside the current chat when the user requests the work map or agent visualization.
---

Use the bundled read-only local map service. Resolve the plugin root two directories above this skill directory. Run `python3 <plugin-root>/scripts/start.py --session <current-chat-id>` using the actual current chat ID from session context. If the ID is unavailable, omit `--session` and explain that the latest local session is selected.

Open the returned URL using the available `open_in_codex` tool with `placement: "right"` and a browser target. Reuse an existing map tab when available. A queued result does not prove the pane is visible. Verify the API contains the intended session, then continue the user's work with the map running. Do not replace the user's task with simulated activity.

Trusted plugin hooks supply structured live events. Existing chats without loaded hooks fall back to session logs. Hook review belongs to Codex Settings > Hooks; never edit trust records to bypass it. This is a companion browser pane, not a modification of Codex's application binary.
