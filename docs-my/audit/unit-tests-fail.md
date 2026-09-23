# Native unit-test failures on this branch

Status of `test/run_native_tests.py` after picking up the four missing
`origin/master` source commits described in
[audit.md §1.3](audit.md). Companion to that section — read it first for why
the source and tests had diverged.

## Current result

```text
python3 test/run_native_tests.py
->  Ran 76 tests
->  FAILED (errors=2)
```

74 pass, 2 error, 0 fail. Environment: Python 3.14.7 on darwin.

Before the source pickup the suite did not run at all: `tests_native/__init__.py`
re-exports every module, so a single unresolved import
(`UNVERIFIED_CHANGE_WARNING`) masked all of it. Reaching a countable result is
itself the change.

## The 2 remaining errors — same single root cause

Both are a Python 3.14 incompatibility in the test file, not a defect in the
code under test.

```text
File "test/tests_native/test_transaction_confirmation.py", line 81, in _is_out_subscript_of
    and isinstance(node.slice, (ast.Constant, ast.Str))
AttributeError: module 'ast' has no attribute 'Str'
```

| | |
| --- | --- |
| Failing tests | `test_details_page_still_lists_every_output_unconditionally`, `test_primary_confirmation_loop_only_skips_verified_change_without_warning` |
| Both in | `tests_native.test_transaction_confirmation.TransactionConfirmationVisibilityTest` |
| Root cause | `ast.Str`, deprecated in Python 3.8, **removed in 3.12** |
| Occurrences | [test_transaction_confirmation.py:81](../../test/tests_native/test_transaction_confirmation.py#L81), [:109](../../test/tests_native/test_transaction_confirmation.py#L109) |

Both failing tests funnel through the same helper, `_is_out_subscript_of`, so
this is one bug hit twice rather than two independent failures. The second
occurrence, in `_is_str_arg`, is the same latent bug on a path that never gets
reached because line 81 raises first.

**Fix.** Drop `, ast.Str` from both tuples. `ast.Constant` is already the first
element of each, so nothing is lost. The neighbouring
`getattr(node, "value", getattr(node, "s", None))` fallbacks exist only to read
the old `ast.Str.s` attribute and become inert, harmlessly, once the class is
gone.

**Provenance.** This file arrived with `fc0e32d` and is upstream's, not this
branch's work. It is equally broken on `origin/master` under Python 3.12+, so
the fix belongs upstream rather than as a local carry.

## Two things to be aware of

### The 4 `test_embed_git_info` errors are silenced, not fixed

The import of `test_embed_git_info` was removed from
[tests_native/__init__.py](../../test/tests_native/__init__.py); the test count
dropped 80 -> 76, exactly those 4 tests.

The underlying gap stands. `test/tests_native/test_embed_git_info.py` is still
committed, but the script it drives — `tools/embed_git_info.py` — is absent
from this tree:

```text
python3 tools/embed_git_info.py /tmp/probe.py
->  can't open file '.../tools/embed_git_info.py': [Errno 2] No such file or directory
->  exit 2
```

which surfaced through the test as
`subprocess.CalledProcessError: ... returned non-zero exit status 2`.

This is the **same partial-pickup pattern** as audit.md §1.3: `tools/` is absent
at the merge base `v1.9.0` and present on `origin/master`, added there by
`e4266c1` "Fix reproducible build (#371) (#412)" — the commit that also added
`test/tests_native/test_embed_git_info.py`. The test came across with
`origin/master`'s test directory; the script it exercises did not.

Deferring it is defensible, but the file is now dormant rather than passing: a
clean run must not be read as the reproducible-build path being covered. Note
that `e4266c1` also touches `Dockerfile`, `build_firmware.sh` and
`docs/reproducible-build.md`; check those before grabbing the script alone, so
the partial pickup is not simply repeated.

### Two committed test files have never executed

`test_message_signing_display.py` and `test_signing_authorization.py` are
committed in `43e5631` "Add regression tests and points to audit", but
[tests_native/__init__.py](../../test/tests_native/__init__.py) does not import
them — it lists 7 modules, not 9. `run_native_tests.py` discovers through that
`__init__`, so neither file has ever run. The arithmetic confirms it: 76 = 80
(pre-pickup baseline) - 4 (removed `test_embed_git_info`), with nothing added.

To register them:

```python
from .test_message_signing_display import *
from .test_signing_authorization import *
```

Their pass/fail state is unknown and should not be assumed until they do run.

## Suggested order

1. Register the two unrun test files. They are this branch's own work and
   currently provide no signal at all.
2. Drop `, ast.Str` at the two sites above. Two-site edit, takes the suite to
   zero errors.
3. Decide `e4266c1` — either pick up `tools/embed_git_info.py` with the rest of
   that commit and re-register its test, or delete the dormant test file so the
   tree does not carry a test for a script it lacks.
