Review the staged changes.

Questions:

1. Are the changes sound overall?
2. Do they improve code quality and robustness without unnecessary churn?
3. Are there real bugs or issues: correctness, security, crashes, regressions, or MicroPython incompatibilities?

Hard constraints (read-only review):

- Do NOT modify tracked files, commit, rebase, or push. Re-freezing `src` into gitignored `bin/micropython_unix` during `make test` is allowed.
- Do NOT read, open, or search inside any `*.md` files anywhere (including submodules, `docs/`, `udev/`, `shield/`, `shield-lite/`, `README.md`, or via `git show` / `git cat-file`). Exclude `*.md`, `*.txt`, and image files (`*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.webp`, `*.svg`) in all diff and search commands, e.g.:
  `git show <target> -- . ':!*.md' ':!*.txt' ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.gif' ':!*.webp' ':!*.svg'`
- Do NOT read, open, or search inside `test/` folder
- Do NOT delegate file/doc/tests reading to subagents that might bypass these exclusions.

Domain context:

- Target hardware: MicroPython 1.x on a 32-bit MCU. Small ints are 31-bit; larger ints use `mpz`; `mp_obj_get_int` raises `OverflowError` above `2^31 - 1`. Floats are single precision. Simulator is the MicroPython 1.12 unix port (`platform.simulator` is `True`).
- `embit`: located at `f469-disco/libs/common/embit/src/embit` (was an inline copy matching embit v0.8.0; now a submodule at v0.8.2 + 4 fork commits).
- Firmware versions: encoded via `version_to_str` in `bootloader/tools/core/blsection.py`; the bootloader forbids firmware downgrades.
- Host dispatch: `src/specter.py` (`process_host_request`) calls `can_process()` on every app and raises `"Not sure what app to use..."` if more than one matches.
- Submodule bumps (`bootloader`, `f469-disco`): inspect with `git -C <submodule> log --oneline <old>..<new>`, and read submodule source only to verify an API assumption.

Verification (run inside nix dev shell via Bash):

- `cd test && python3 run_native_tests.py` (CPython with stubs): expect 104 tests run with 1 expected failure (the offline PIN-guess cost test).
- `make test`: frozen-import smoke test followed by 21 MicroPython tests; all should pass. Run if the toolchain (`bin/micropython_unix`, nix) is available; state clearly if unavailable or skipped.

Output format:

1. Overall soundness verdict and brief rationale.
2. Table of findings (Severity, Location, Issue, Impact) — skip style nits.
3. Verification log: what you ran/verified vs. what you could not verify (missing toolchain, skipped checks, etc.).
