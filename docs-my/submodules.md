# Submodules

## Map

| Submodule | Remote | Fork? | Pinned commit | Describe | `branch =` |
|---|---|:--:|---|---|---|
| `bootloader` | `hardware-wallets-and-cryptography/specter-bootloader` | ✅ | `c331570` | `v1.0.0-22-gc331570` | `dev` |
| `bootloader/lib/fatfs` | `hardware-wallets-and-cryptography/fatfs` | ✅ | `8ea3980` | `R0.14-2-g8ea3980` | `dev` |
| `bootloader/lib/secp256k1` | `bitcoin-core/secp256k1` | ❌ | `5e1c885` | `5e1c885` | — |
| `f469-disco` | `hardware-wallets-and-cryptography/f469-disco` | ✅ | `de1abb4` | `v1.3.1-19-gde1abb4` | `dev` |
| `f469-disco/libs/common/embit` | `hardware-wallets-and-cryptography/embit` | ✅ | `eb6104f` | `v0.8.2` | `dev` |
| `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` | `ElementsProject/secp256k1-zkp` | ❌ | `d9560e0` | `d9560e0a` | — |
| `f469-disco/micropython` | `hardware-wallets-and-cryptography/micropython` | ✅ | `6bdf1b6` | `v1.10-1185-g6bdf1b691` | — |
| `f469-disco/usermods/secp256k1` | `hardware-wallets-and-cryptography/secp256k1-embedded` | ✅ | `1e74fc3` | `1e74fc3` | `secp-zkp` |
| `f469-disco/usermods/secp256k1/secp256k1` | `ElementsProject/secp256k1-zkp` | ❌ | `d9560e0` | `d9560e0a` | — |
| `f469-disco/usermods/udisplay_f469/lvgl` | `lvgl/lvgl` | ❌ | `dd100e5` | `v6.0.2-31-gdd100e5e0` | `release/v6` |

**6 forked, 4 external.** Note `secp256k1-zkp` appears twice — once under
`usermods/secp256k1`, once under `embit/secp256k1` — both at the same commit
`d9560e0`, so there is no version skew between the two checkouts.

The `embit/secp256k1/` checkout is a C source tree, not a Python package. It sits
next to code that does `import secp256k1`, which under CPython would make it an
implicit namespace package; `embit/src/embit/util/secp256k1.py` guards against
that explicitly. It is outside the freeze root (`manifests/embit.py` walks only
`embit/src`), so it never reaches firmware.

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
remotes hosting them. For the four external remotes — `ElementsProject/secp256k1-zkp`
(×2), `bitcoin-core/secp256k1`, `lvgl/lvgl` — a force-push or repository deletion
upstream would make a fresh `--recursive` clone fail, and the pinned objects would
then survive only in existing local clones. All four are C crypto or display
sources; three reach signing or bootloader firmware (the `embit/secp256k1/` copy
is outside the freeze root).

If the reason for forking `micropython`, `secp256k1-embedded`, `embit` and
`fatfs` was to control that exposure, the same argument covers these.
`bitcoin-core/secp256k1` is declared in the bootloader repo's own `.gitmodules`,
so forking it requires a commit there as well — as was done for `fatfs` in
`c331570`.

**Stale local remote.** The `fatfs` fork is recorded in `bootloader/.gitmodules`
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
