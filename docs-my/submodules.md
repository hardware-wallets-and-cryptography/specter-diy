# Submodules

## Map

| Submodule | Remote | Fork? | Pinned commit | Describe | Branch (`branch =`) |
|-----------|--------|:-----:|---------------|----------|---------------------|
| `f469-disco/usermods/udisplay_f469/lvgl` | `lvgl/lvgl` | ❌ | `dd100e5` | `v6.0.2-31-gdd100e5e0` | — |
| `bootloader/lib/secp256k1` | `bitcoin-core/secp256k1` | ❌ | `5e1c885` | `v0.2.0~173` | — |
| `bootloader` | `hardware-wallets-and-cryptography/specter-bootloader` | ✅ | `c331570` | `v1.0.0-22-gc331570` | `dev` |
| `bootloader/lib/fatfs` | `hardware-wallets-and-cryptography/fatfs` | ✅ | `8ea3980` | `R0.14-2-g8ea3980` | `dev` |
| `f469-disco` | `hardware-wallets-and-cryptography/f469-disco` | ✅ | `46d111b` | `v1.3.1-13-g46d111b` | `dev` |
| `f469-disco/micropython` | `hardware-wallets-and-cryptography/micropython` | ✅ | `6bdf1b6` | `v1.10-1185-g6bdf1b6` | — |
| `f469-disco/libs/common/embit` | `hardware-wallets-and-cryptography/embit` | ✅ | `d418ef3` | `v0.8.2-4-gd418ef3` | `int` |
| `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` | `hardware-wallets-and-cryptography/secp256k1-zkp` | ✅ | `d9560e0` | `d9560e0a` | — |
| `f469-disco/usermods/secp256k1/secp256k1` | `hardware-wallets-and-cryptography/secp256k1-zkp` | ✅ | `d9560e0` | `d9560e0a` | — |
| `f469-disco/usermods/secp256k1` | `hardware-wallets-and-cryptography/secp256k1-embedded` | ✅ | `0502cf4` | `0502cf4` | `secp-zkp--int` |

> **8 forked / 2 external.**

> Remote `secp256k1-zkp` appears twice — under `usermods/secp256k1` and under
> `embit/secp256k1` — both from the same fork and at the same commit `d9560e0`,
> so there is no version skew between the two checkouts. **Only the `usermods`
> copy reaches firmware; keep the two in step when bumping.**

The `embit/secp256k1/` checkout is a C source tree, not a Python package. It sits
next to code that does `import secp256k1`, which under CPython would make it an
implicit namespace package; `embit/src/embit/util/secp256k1.py` guards against
that explicitly. It is outside the freeze root (`f469-disco/manifests/embit.py`
walks only `embit/src`), so it never reaches firmware.

## Reproducibility

**What is guaranteed.** Every entry above is pinned by commit hash in the
parent's tree (a gitlink), not by branch. A fresh

```sh
git clone --recursive https://github.com/hardware-wallets-and-cryptography/specter-diy.git
```

resolves the exact same trees, regardless of who owns each remote. The
`Makefile` reinforces this — it runs

```make
git submodule update --init --recursive
```

with **no `--remote`**, so a build always honours the recorded hashes.

**What the `branch =` lines do.** Nothing, during a normal clone or build. They
are consumed only by `git submodule update --remote`, which moves a submodule to
its remote branch head and stages a new gitlink. That is the drift footgun: it
silently replaces a verified tree with an untested one. Historically this repo
was left in exactly that broken state — `f469-disco` pinned at `db3ce3e` with an
embit submodule from a later commit layered on top as untracked content, which
made `make unix` fail on a frozen `embit/examples/explorer.py`.

Avoid `--remote`. To move a pin, do it explicitly:

```sh
git submodule sync --recursive
git -C <path> fetch origin <branch>
git -C <path> checkout <full-sha>
git -C <path> submodule sync --recursive
git -C <path> submodule update --init --recursive
git add <path>
```

**Verifying a checkout matches the pins.**

```sh
git submodule status --recursive
```

Every line must start with a **space**. A leading `+` means the checkout differs
from the recorded gitlink, `-` means uninitialized, `U` means conflicts. Also
check for drift inside submodules:

```sh
git -C f469-disco status --short     # expect empty
git -C bootloader   status --short   # expect empty
```

Untracked content inside a submodule is not harmless here: the manifests freeze
whole directory trees, so stray files can end up compiled into firmware or break
the build.

**What can still break reproducibility.** The pins are only as durable as the
remotes hosting them. For the two external remotes — `bitcoin-core/secp256k1`
(bootloader crypto) and `lvgl/lvgl` (display) — a force-push or repository
deletion upstream would make a fresh `--recursive` clone fail, and the pinned
objects would then survive only in existing local clones.

If the reason for forking `micropython`, `secp256k1-embedded`, `embit`, `fatfs`
and both `secp256k1-zkp` instances was to control that exposure, the same
argument covers the remaining external crypto remote, `bitcoin-core/secp256k1`.
It is declared in the bootloader repo's own `.gitmodules`, so forking it requires
a commit there as well — as was done for `fatfs` in bootloader `c331570`, for
`embit/secp256k1/secp256k1-zkp` in embit `4f1afc7`, and for
`usermods/secp256k1/secp256k1` in secp256k1-embedded `0502cf4`.

**Stale local remote (`secp256k1-zkp`).** Same issue as `fatfs` below: an
already-initialised `usermods/secp256k1/secp256k1` checkout may still have
`ElementsProject/secp256k1-zkp` as its `origin` until `git submodule sync
--recursive` is run. The pin `d9560e0` is present on the fork's `dev`, `int` and
`master`.

**Stale local remote (`fatfs`).** The `fatfs` fork is recorded in `bootloader/.gitmodules`
at the pinned commit, but an already-initialised checkout keeps the old
`cryptoadvance/fatfs` URL in its local config until synced:

```sh
git -C bootloader config submodule.lib/fatfs.url   # may still show cryptoadvance
git submodule sync --recursive
```

This does not affect the pin — `8ea3980` is present on the fork's `dev`, `int`
and `master` — only where a re-fetch goes.

**Fetching each submodule's `dev` branch by hand.** `git submodule update
--init --remote` fetches from whatever `origin` is *currently configured
inside the submodule*, not the URL in `.gitmodules` — if that local `origin`
is stale, the fetch can fail with `fatal: Unable to find refs/remotes/origin/dev
revision in submodule path '<path>'` even though `dev` exists on the correct
fork. Sync first, from the superproject root:

```sh
git submodule sync -- bootloader f469-disco
git submodule update --init --remote -- bootloader f469-disco
```

Or do it manually inside each submodule, for full control:

```sh
cd bootloader
git remote set-url origin https://github.com/hardware-wallets-and-cryptography/specter-bootloader.git
git fetch origin
git checkout dev
git pull origin dev
cd ..

cd f469-disco
git remote set-url origin https://github.com/hardware-wallets-and-cryptography/f469-disco.git
git fetch origin
git checkout dev
git pull origin dev
cd ..
```

Either way this moves the submodule to the tip of `dev`, which will show as a
modified gitlink in the superproject (`git status`) if that tip differs from
the recorded pin — commit it there to update the pin, per the `--remote`
warning above.
