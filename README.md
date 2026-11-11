# Codex Map

A local, read-only activity map inspired by [lot-map](https://github.com/alexeyw/lot-map). Tool calls travel between Codex and ten stations. The feed shows running, completed, and failed calls; select a station to filter it.

## Run

Requires Python 3.9+; no packages, API key, or build step.

```sh
python3 server.py
```

Open http://127.0.0.1:4318. Keep the server running while you use Codex. Choose a session from the dropdown. Use `--port 4320` to change the port, or set `CODEX_HOME` to a different Codex data directory.

## What is live

The server polls local `$CODEX_HOME/sessions` JSONL files. It reads session metadata, tool call IDs and names, completion statuses, model names, and reported token usage. It does not send prompts or tool output to the browser. This works alongside existing desktop/CLI sessions without starting another agent. Demo mode is explicitly simulated.

This is a standalone companion, not an extension injected into the Codex chat UI. Local log formats are an implementation detail and may change. Calls batched inside `functions.exec` currently appear as a single Shell call. Subagent tool calls appear when their own session is selected; a combined parent/child graph is not yet implemented. Context is the last reported total token usage divided by the reported window, not a precise live occupancy measure. Missing completion records may leave a tool marked running. Counts cover the last 250 displayed events. Session discovery lists the 100 most recently modified logs. No history is changed.

The [official App Server protocol](https://learn.chatgpt.com/docs/app-server) provides structured events for applications that own their Codex connection. This companion uses existing session logs so it can observe already-running chats.

Everything is served from loopback. No analytics, CDN assets, network services, or external dependencies.

## Codex mod / plugin

This repository now includes `.codex-plugin/plugin.json`, a local marketplace, lifecycle hooks, and the `codex-map` skill.

```sh
codex plugin marketplace add .
codex plugin add codex-map@codex-map-local
```

Restart Codex to load the new plugin. In **Settings > Hooks**, review and trust Codex Map's hooks. Trust must be granted through Codex; the installer does not bypass that review. In a chat, ask **“open my Codex map”** or invoke `$codex-map`. The skill starts the local service and opens a session-bound narrow browser pane on the right. A SessionStart hook asks the agent to open that pane when supported; this is agent-mediated and is not a native UI injection or guaranteed pane API.

Hooks observe tool/model request lifecycles, messages, compaction, and subagent starts/stops. They store names, IDs, timestamps and error flags under `$CODEX_HOME/codex-map/events/`; prompts, arguments and tool output are excluded. Hooks remain advisory and return successfully on visualization errors. Local event metadata persists until removed by the user. Hosted tools or specialized paths that do not emit hooks are not comprehensively covered.

Existing chats continue using the log fallback until resumed with the plugin loaded. Hook events become authoritative once available. Batched tool calls are detailed only when the runtime emits their individual lifecycle hooks. The map's error detection is best effort. The local service starts on demand and remains running until stopped; it does not install a login daemon.

For a compact pane manually:

```sh
python3 scripts/start.py --session YOUR_CHAT_ID
```

Verification: `python3 -m unittest discover -s tests -v` and `node --check public/app.js`.
