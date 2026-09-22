# TODO

Open items from the build/docs review, plus what surfaced while re-pinning the
`f469-disco` submodule.

**Nothing in the wallet's own code has changed yet.**

`src/` is the folder holding the Python code that runs on the device. Comparing
the commit where this review started (`753b36b`, 2026-09-16) against the latest
commit shows no differences at all inside that folder:

```sh
git diff 753b36b..HEAD -- src/    # prints nothing
```

Every commit since then touched build files, docs or submodule pins only — not
one line of wallet code. So the bug in item 1 below is still there, unfixed.

## 1. `branch_txt` is always empty — output labels lose the branch name

[`src/apps/wallets/manager.py:747-752`](../src/apps/wallets/manager.py#L747-L752)

```python
branch_txt = ""
if branch_idx == 1:
    "change "          # bare expression, discarded
elif branch_idx > 1:
    "branch %d " % branch_idx
metaout["label"] = "%s %s#%d" % (wallet.name, branch_txt, idx)
```

The `if`/`elif` bodies are bare string expressions with no assignment, so
`branch_txt` never changes from `""`. Output labels therefore never say
"change" or "branch N".

On a signing device this is a user-visible confirmation string that silently
drops information. Cosmetic rather than a signing fault, but worth fixing.

Confirmed duplicated verbatim at
[`src/apps/wallets/liquid/manager.py:553-558`](../src/apps/wallets/liquid/manager.py#L553-L558).
Fix both.

Note the label format string also leaves a double space when `branch_txt` is
empty (`"%s %s#%d"`), so fixing the assignment alone still reads
`wallet change #3`. Build the label from the parts instead.

## 2. DECISION: five submodule remotes are still external

`ElementsProject/secp256k1-zkp` (two checkouts), `bitcoin-core/secp256k1`,
`lvgl/lvgl` and `cryptoadvance/fatfs` sit outside the
`hardware-wallets-and-cryptography` org. Full map, pins and reproducibility
analysis: [submodules.md](./submodules.md).

Reproducibility itself is fine — everything is pinned by hash. The open question
is availability and supply-chain control: three of those five are the C crypto
and display libraries that end up in signing firmware, and a force-push or
deletion upstream would break fresh clones. If the reason for forking
`micropython`, `secp256k1-embedded` and `embit` was to control exactly that, the
same argument covers these. Forking the two `bootloader/lib/*` remotes means a
commit in the bootloader repo too.

Also: both `f469-disco` and `bootloader` carry `branch = dev` in the top-level
[`.gitmodules`](../.gitmodules), and both pins currently match their fork's `dev`
head. `git submodule update --remote` will drift off them the next time either
branch moves. Either drop the `branch` lines or treat them as documentation only.

## Also unverified

Two Linux lines in [`docs/development-firmware-build-simulation-testing.md`](../docs/development-firmware-build-simulation-testing.md),
untested because the review ran on MacOS:

- [line 16](../docs/development-firmware-build-simulation-testing.md#L16) — the `nix-users` group claim.
- [line 17](../docs/development-firmware-build-simulation-testing.md#L17) — `sudo apt install direnv`.
