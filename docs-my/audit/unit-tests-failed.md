# Unit tests failed

## Native unit test failures on this branch

### Current result

```text
python3 test/run_native_tests.py
->  Ran 79 tests
->  FAILED (failures=1)
```

78 pass, 1 fail, 0 error. Environment: Python 3.14.7 on darwin.

### The 1 remaining failure is a known, tracked finding — not a test defect

`test_signing_refuses_key_absent_from_input_script`
([test_signing_authorization.py:100-153](../../test/tests_native/test_signing_authorization.py#L100-L153))
is red because the defect it targets — **F-04**, the derived-key signing
oracle — is still open. The test is doing its job; see
[audit.md §F-04](audit.md) for the finding and its action plan. This is not
something to "fix" in the test.
