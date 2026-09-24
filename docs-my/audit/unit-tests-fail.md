# Native unit-test failures on this branch

Status of `test/run_native_tests.py` after picking up the four missing
`origin/master` source commits described in
[audit.md §1.3](audit.md). Companion to that section — read it first for why
the source and tests had diverged.

## Current result

```text
python3 test/run_native_tests.py
->  Ran 79 tests
->  FAILED (failures=1)
```

78 pass, 1 fail, 0 error. Environment: Python 3.14.7 on darwin.

## The 1 remaining failure is a known, tracked finding — not a test defect

`test_signing_refuses_key_absent_from_input_script`
([test_signing_authorization.py:100-153](../../test/tests_native/test_signing_authorization.py#L100-L153))
is red because the defect it targets — **F-04**, the derived-key signing
oracle — is still open. The test is doing its job; see
[audit.md §F-04](audit.md) for the finding and its action plan. This is not
something to "fix" in the test.

## Resolved since the original scan

- **`ast.Str` (Python 3.12+ incompatibility)** — fixed at both sites in
  `test_transaction_confirmation.py`. No longer reproduces.
- **`test_embed_git_info`** — the dormant test (`tools/embed_git_info.py`
  never existed in this tree) was deleted in `0080ec9`, along with its
  `tests_native/__init__.py` import. No test now claims coverage of the
  reproducible-build script.
- **`test_message_signing_display.py` / `test_signing_authorization.py`** —
  both registered in [tests_native/__init__.py](../../test/tests_native/__init__.py)
  and now run on every invocation. Their F-03 and F-21 regression tests are
  green (see [audit.md §F-03](audit.md) and [audit.md §F-21](audit.md) for the
  fixes); their F-04 regression test is the one failure above.
