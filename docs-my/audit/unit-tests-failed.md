# Unit tests failed

## Native unit test failures on this branch

### Original result

```text
python3 test/run_native_tests.py
->  Ran 79 tests
->  FAILED (failures=1)
```

78 pass, 1 fail, 0 error. Environment: Python 3.14.7 on darwin.

### The 1 failure was a known, tracked finding — now fixed

`test_signing_refuses_key_absent_from_input_script`
([test_signing_authorization.py:100-153](../../test/tests_native/test_signing_authorization.py#L100-L153))
was red because the defect it targets — **F-04**, the derived-key signing
oracle — was still open. See [audit.md §F-04](audit.md) for the finding and
its action plan.

Fixed as described below. Current result:

```text
python3 test/run_native_tests.py
->  Ran 79 tests
->  OK
```

`python3 -m compileall ../src ../test` also passes clean.

## Root cause

`PSBTView.sign_input()` in `embit` (vendored via the `f469-disco` submodule)
checked that the **root** key's `sec`/`pkh` actually appears in the input's
script before signing with it:

```python
if sec in sc.data or pkh in sc.data:
    sig = root.sign(h)
```

The loop signing with **derived** keys, right below it, had no equivalent
check — it signed for any `bip32_derivation` entry whose fingerprint matched
the device, regardless of whether the resulting pubkey was part of the
input's script at all:

```python
for prv, pub in derived_keypairs:
    sig = prv.sign(h)
    inp.partial_sigs[pub] = sig.serialize() + bytes([inp_sighash])
    counter += 1
```

A host that knows a device xpub can fabricate a `bip32_derivation` entry for
any derivation path it chooses, over a completely fabricated input, and get
back a valid signature — a signing oracle, not just a missing check.

## Fixes made

### 1. `embit` — script-membership check on derived keys

**File:** `f469-disco/libs/common/embit/src/embit/psbtview.py`, in
`PSBTView.sign_input()`, the derived-key loop (around line 924-933).

Added the same `sec`/`pkh` membership check used for the root key, applied
per derived key before signing with it:

```python
for prv, pub in derived_keypairs:
    der_sec = pub.sec()
    der_pkh = hashes.hash160(der_sec)
    # same script-membership check as for the root key above -
    # a matching fingerprint alone doesn't prove this key is
    # actually part of the input's script
    if der_sec not in sc.data and der_pkh not in sc.data:
        continue
    sig = prv.sign(h)
    inp.partial_sigs[pub] = sig.serialize() + bytes([inp_sighash])
    counter += 1
```

This is the fix that actually closes F-04.

**Status: written, not yet committed.** The `embit` fork is checked out at
commit `cb6691f` ("parsing updates from `master`") in detached-HEAD state. A
local branch `fix/f-04-derived-key-signing-oracle` was created there for this
change, but the edit to `src/embit/psbtview.py` is uncommitted on top of it —
committing and pushing this branch is being done manually, not by the
assistant, at the user's request.

To find it: `f469-disco/libs/common/embit/src/embit/psbtview.py` inside this
`specter-diy` checkout. Since it's inside a nested submodule on an
uncommitted local branch, `git status`/`git diff` at the `specter-diy` or
`f469-disco` level won't show the file content — only that the submodule is
dirty. Check it directly:

```sh
cd f469-disco/libs/common/embit
git status --short   # -> M src/embit/psbtview.py
git diff              # the 7-line fix shown above
git branch --show-current  # -> fix/f-04-derived-key-signing-oracle
```

### 2. `manager.py` — removed a diagnostic that collided with the fix

**File:** [manager.py](../../src/apps/wallets/manager.py), `sign_psbtview()`.

Before the fix above, an entirely-forged single-input PSBT with a spoofed
`bip32_derivation` always produced a (wrongful) signature — that was the bug.
After the fix, such an input correctly produces zero signatures. But
`sign_psbtview()` had this diagnostic right after the signing loop:

```diff
                 sig_stream.write(b"\x00")
-        if sig_count == 0:
-            raise WalletError("We didn't add any signatures!\n\nMaybe you forgot to import the wallet?\n\nScan the wallet descriptor to import it.")
         # remove unnecessary stuff:
         with open(self.tempdir+"/sigs", "rb") as sig_stream:
             psbtv.write_to(out_stream, compress=CompressMode.PARTIAL, extra_input_streams=[sig_stream])
```

(Reconstructed from the edit made in this session, not from `git diff` — the
change landed inside the pre-existing bundled commit `ed57fab`, which mixes
in a large amount of unrelated work, so a real `git diff` against its parent
would not isolate this change cleanly.)

This fired for the newly-correct "zero signatures on an all-forged PSBT"
case, which is indistinguishable at this level from the pre-existing
"forgot to import wallet" case (both produce `wallets == {None: ...}`) — the
regression test expects `sign_psbtview()` to return normally with zero
`partial_sigs`, not raise. Removing this raise doesn't change the security
outcome either way (no signature is produced either way); it only changes
whether the device raises an exception or returns an unsigned PSBT. No other
test in the repo depends on this message.

**Status: already committed**, as part of the pre-existing local commit
`ed57fab` ("All my changes") on the current branch
(`master-from-tag-1.9.0--int`). That commit has not been pushed anywhere.

## What's still needed to make this land on GitHub CI

None of the three repos in this submodule chain (`embit` → `f469-disco` →
`specter-diy`) have been pushed. Nothing has been pushed to any existing
shared branch (`master`, `dev`, `int`, or
`master-from-tag-1.9.0--my-changes--integration`) — new branches only, to
avoid touching shared history. In dependency order:

1. **`embit`** (`f469-disco/libs/common/embit`, branch
   `fix/f-04-derived-key-signing-oracle`): commit `src/embit/psbtview.py`,
   push the branch.
   ```sh
   cd f469-disco/libs/common/embit
   git add src/embit/psbtview.py
   git commit -m "psbtview: enforce script-membership check on derived-key signing (F-04)"
   git push origin fix/f-04-derived-key-signing-oracle
   ```
2. **`f469-disco`**: create a branch, bump the `embit` gitlink to the new
   commit from step 1, commit, push.
   ```sh
   cd f469-disco
   git checkout -b fix/f-04-derived-key-signing-oracle
   git add libs/common/embit
   git commit -m "Bump embit: pull in F-04 derived-key signing fix"
   git push origin fix/f-04-derived-key-signing-oracle
   ```
3. **`specter-diy`** (this repo, branch `master-from-tag-1.9.0--int`): bump
   the `f469-disco` gitlink to the new commit from step 2, commit, push the
   whole local branch as a new remote branch.
   ```sh
   git add f469-disco
   git commit -m "Bump f469-disco: pull in F-04 derived-key signing fix"
   git push origin master-from-tag-1.9.0--int
   ```

Until step 1 and 2 are pushed, `specter-diy`'s `f469-disco` gitlink can't be
bumped to a commit that actually exists on `origin`, so the steps must run
in this order.
