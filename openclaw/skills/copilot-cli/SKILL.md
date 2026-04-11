---
name: copilot-cli
description: "Default programming backend for this agent. Delegate coding/editing/refactor/build/test tasks to the GitHub Copilot CLI (`copilot` command) via bash. Use for: writing new features, fixing bugs, refactoring, running tests, exploring an unfamiliar codebase. Copilot is the preferred backend; fall back to Claude Code only if Copilot fails. Never run inside ~/.openclaw, /Users/clawbot/.npm-global/lib/node_modules/openclaw, or any OpenClaw state directory."
allowed-tools: ["bash"]
metadata:
  {
    "openclaw":
      {
        "emoji": "🤖",
        "requires": { "anyBins": ["copilot", "claude"] }
      }
  }
---

# Copilot CLI (primary coding backend)

This agent's **default** way to do any real coding work is to shell out to
`copilot` (GitHub Copilot CLI). Only fall back to `claude` if copilot fails
or the user explicitly asks for Claude Code.

Binary locations on this machine:

- `copilot` → `/opt/homebrew/bin/copilot` (GitHub Copilot CLI 1.0.21+)
- `claude`  → `/Users/clawbot/.npm-global/bin/claude` (Claude Code 2.1.101)

## Non-interactive one-shot (default pattern)

```bash
# Quick task — runs, does the work, exits
bash workdir:~/Documents/harnesse2e-main command:"copilot -p 'Your task here' --allow-all-tools --allow-all-paths --add-dir /Users/clawbot/Documents/harnesse2e-main"
```

Key flags:

| Flag                    | Why                                                                |
| ----------------------- | ------------------------------------------------------------------ |
| `-p, --prompt <text>`   | Non-interactive: executes prompt and exits                         |
| `--allow-all-tools`     | Required for non-interactive mode (no approval prompts)            |
| `--allow-all-paths`     | Let Copilot edit anywhere under the workspace                      |
| `--add-dir <dir>`       | Explicitly whitelist the workspace directory                       |
| `--effort <level>`      | Reasoning effort: `low`/`medium`/`high`/`xhigh` (default: medium)  |

## Background / long-running tasks

For anything longer than ~30s (builds, big refactors, running a test suite),
use background mode so the user can keep chatting while work proceeds:

```bash
bash workdir:~/Documents/harnesse2e-main background:true command:"copilot -p 'Build feature X end-to-end, run tests, report results' --allow-all-tools --allow-all-paths --add-dir /Users/clawbot/Documents/harnesse2e-main"
# Returns sessionId — track with the process tool
```

Monitor with:

```
process action:poll  sessionId:XXX
process action:log   sessionId:XXX
process action:kill  sessionId:XXX   # if needed
```

## Progress updates (critical)

When you spawn Copilot in the background, keep the user in the loop:

- Send 1 short message when you start ("kicked off `copilot -p …` in
  harnesse2e-main, sessionId Y").
- Only update again when something changes: milestone done, question
  from copilot, error, or finish.
- If you kill a session, say so immediately and why.

## Fallback to Claude Code

If `copilot` is unavailable or fails with auth / environment issues, fall
back to Claude Code:

```bash
bash workdir:~/Documents/harnesse2e-main command:"claude --permission-mode bypassPermissions --print 'Your task here'"
```

Tell the user you fell back and why — don't silently switch backends.

## ⚠️ Safety rules

1. **Never** run `copilot` or `claude` with cwd inside:
   - `~/.openclaw` (openclaw state dir — contains auth profiles, sessions)
   - `/Users/clawbot/.npm-global/lib/node_modules/openclaw` (the live openclaw install)
   - Any directory that itself contains an `openclaw.json`
2. Default workspace for this agent is
   `/Users/clawbot/Documents/harnesse2e-main`. Stay inside unless the user
   explicitly points you elsewhere.
3. Respect the user's backend choice — if they say "use claude / use codex",
   switch. `copilot` is only the _default_, not a mandate.
4. Don't hand-patch files yourself when copilot can do it. You're the
   orchestrator; copilot is the worker. Hand-editing one line for a typo
   is fine; refactoring a module is copilot's job.
5. For builds/tests that don't need LLM reasoning (e.g. `pnpm test`,
   `pytest`), just run them directly via bash — don't burn copilot tokens
   on shell execution.

## Quick sanity check

To verify copilot is working at all:

```bash
bash command:"copilot --version"
# Should print: GitHub Copilot CLI 1.0.21. (or newer)
```

If this fails, stop and tell the user — don't silently fall back.
