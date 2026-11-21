# Start this goal in Codex

The package contains:

- `CODEX_GOAL.md` - complete implementation specification and acceptance criteria
- `assets/velacare-evolution-tui-reference.png` - the user's approved TUI screenshot

From the target GitHub repository's local checkout, copy these into the repo, then start Codex from that repo.

## Codex CLI

```bash
cd /path/to/your/repository
codex -i assets/velacare-evolution-tui-reference.png \
  "Read CODEX_GOAL.md and implement the full VelaCare Evolution Engine. Treat the attached image as the required TUI design reference. Verify all acceptance criteria, especially full population snapshots for EVERY generation, and run the software and tests."
```

Current Codex CLI supports `--image` / `-i` for attaching images to the first prompt. The image should be attached explicitly, **not just linked in Markdown**.

If your Codex version supports persistent Goals (`/goal`, introduced in 0.128.0), you may also set:

```text
/goal Implement and verify CODEX_GOAL.md. Done only when the algorithm runs, the TUI matches the attached reference, and all candidates in all generations can be reconstructed from saved filesystem records.
```

## Codex desktop app

Open the local repository in Codex. Keep `CODEX_GOAL.md` and the PNG under `assets/` in the repo. Attach the PNG to your task (or drag it into the prompt) and send:

```text
Read CODEX_GOAL.md and implement it end-to-end. The attached PNG is the required VelaCare TUI design reference. The full population history of every generation must be reconstructable from disk; verify with tests. Run a real example and inspect the output before reporting completion.
```

## One-shot Codex exec (optional)

Run interactively for iterative work; `codex exec` may also accept image input in versions that support the shared `-i/--image` option. Check `codex exec --help` on your installed version before scripting.

## Notes

- All paths in the goal file use `/agentic-space` for the target SecurSpaces environment, with a local fallback for development.
- Include the screenshot in the repository so future Codex sessions can inspect it and the design requirement remains traceable.
- The screenshot's numerical values are illustrative. The implementation must always calculate real results.
