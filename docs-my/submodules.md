# Submodules

## Map

- The table below is a single source of truth for pins
- Forks live under `hardware-wallets-and-cryptography/`
- Paths are relative to this repo's root
- Drift snapshot as of `2026-09-26`

| Submodule | Remote | Fork | Pin | Describe | `--remote` target | Drift past pin | Pin reachable from | Binary |
|---|---|:-:|---|---|---|---|---|:-:|
| `bootloader` | `specter-bootloader` | ✅ | `c331570` | `v1.0.0-22-gc331570` | `dev` (`branch =`) | 0 | `dev` only | bootloader |
| `bootloader/lib/fatfs` | `fatfs` | ✅ | `8ea3980` | `R0.14-2-g8ea3980` | `dev` (`branch =`) | 0 | `dev`, `int`, `master` | bootloader |
| `bootloader/lib/secp256k1` | `bitcoin-core/secp256k1` | ❌ | `5e1c885` | `v0.2.0~173` | `master` (default) | **1824** (→ `f14d299`) | `master`, 12 tags | bootloader |
| `f469-disco` | `f469-disco` | ✅ | `41446cc` | `v1.3.1-17-g41446cc` | `dev` (`branch =`) | 0 | `dev` only | firmware |
| `f469-disco/micropython` | `micropython` | ✅ | `6bdf1b6` | `v1.10-1185-g6bdf1b691` | `master` (default) | 0 | fork `master` | firmware |
| `f469-disco/usermods/secp256k1` | `secp256k1-embedded` | ✅ | `0502cf4` | — | `secp-zkp--int` (`branch =`) | 0 | `secp-zkp--int` only | firmware |
| `f469-disco/usermods/secp256k1/secp256k1` | `secp256k1-zkp` | ✅ | `d9560e0` | — | `master` (default) | **1949** (→ `037cc6d`) | `master`, `dev`, `int` | firmware |
| `f469-disco/usermods/udisplay_f469/lvgl` | `lvgl/lvgl` | ❌ | `dd100e5` | `v6.0.2-31-gdd100e5e0` | `master` (default) | **10204** (→ v9.x) | `master`, 33 `release/*`, 56 tags | firmware |
| `f469-disco/libs/common/embit` | `embit` | ✅ | `d418ef3` | `v0.8.2-4-gd418ef3` | `int` (`branch =`) | 0 | `int` only | firmware |
| `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` | `secp256k1-zkp` | ✅ | `d9560e0` | — | `master` (default) | **1949** (→ `037cc6d`) | `master`, `dev`, `int` | — |

> **8 forked**  
> **2 external**

> Remote `secp256k1-zkp` appears twice:
> - under `f469-disco/usermods/secp256k1`  
> - under `f469-disco/libs/common/embit/secp256k1`  
> Both from the same fork and at the same commit `d9560e0`, so there is no version skew
> between the two checkouts.  
> **Only the `usermods` copy reaches firmware; keep the two in step when bumping.**

Pins below `f469-disco/` are recorded in `f469-disco`, not here. See
`f469-disco/docs-my/submodules.md` for that repo's own view.

### What reaches the device

**Firmware** (`make disco`; `make debug` is the same with `boot/debug`):

- `f469-disco/micropython` — the build (`make -C f469-disco/micropython/ports/stm32`)
- `f469-disco/usermods/secp256k1` + its `secp256k1/` tree — compiled into the
  signing usermod (`USER_C_MODULES=f469-disco/usermods`)
- `f469-disco/usermods/udisplay_f469/lvgl` — compiled into the display usermod
  (its `micropython.mk` includes `lvgl/lvgl.mk`)
- `f469-disco/libs/common/embit` — frozen as Python. Chain:
  `manifests/disco.py` → `f469-disco/manifests/disco.py` → `empty.py` +
  `common.py` → `embit.py`. `embit.py` walks `embit/src` and skips `embit/util`
  (CPython-only backends — firmware uses the C usermod); `common.py` skips
  `embit`, so no double-freeze. `manifests/disco.py` also freezes `src/` and
  `boot/main` (`debug.py`: `boot/debug`).

**Bootloader** (separate binary, packed into `initial_firmware.bin` by
`build_firmware.sh`):

- `bootloader/lib/secp256k1` and `bootloader/lib/fatfs` — compiled by
  `bootloader/platforms/stm32f469disco/bootloader/Makefile`

**Not built**: `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp`. It is a C
source tree for `embit`'s own CPython ctypes build, outside every freeze root. It
sits next to code that does `import secp256k1`, which under CPython would make it
an implicit namespace package; `f469-disco/libs/common/embit/src/embit/util/secp256k1.py`
guards against that explicitly (it keys on `from micropython import const`).

## Verify pin and drift for each submodule

Reads each pin and `--remote` target from git, so it needs no edit after a pin
bump. Use it to refresh the Map's drift column:

```sh
git submodule foreach --recursive -q '
  b=$(git config -f "$toplevel/.gitmodules" "submodule.$name.branch") || \
    { git remote set-head origin -a >/dev/null; b=HEAD; }
  git fetch -q origin
  printf "%-55s pin=%.7s head=%s drift=%s dirty=%s\n" "$displaypath" "$sha1" \
    "$(git rev-parse --short=7 HEAD)" \
    "$(git rev-list --count "$sha1..origin/$b")" \
    "$(git status --short | wc -l | tr -d " ")"
'
```

- `head` must equal `pin`; otherwise the checkout has moved.
- `dirty` must be `0`. A parent shows `dirty` > 0 when a nested checkout has moved.
- `drift` is commits past the pin on the `--remote` target. `0` means the pin
  sits at the target's head today, not that it is protected from future pushes.
- The script fetches from each checkout's local `origin`. If that URL is stale
  (see [Local remote URLs](#reproducibility)), `drift` is measured against the
  wrong repo or fails. Sync first.

## Reproducibility

**What is guaranteed.** Every entry above is pinned by commit hash in its
parent's tree (a gitlink), not by branch. A fresh

```sh
git clone --recursive https://github.com/hardware-wallets-and-cryptography/specter-diy.git
```

resolves the exact same trees, regardless of who owns each remote. The `Makefile`
guard rules for `$(MPY_DIR)/mpy-cross/Makefile` and `$(EMBIT_INIT)`
(`f469-disco/libs/common/embit/src/embit/__init__.py`) run

```make
git submodule update --init --recursive
```

with **no `--remote`**, so a fresh checkout is initialised at the recorded
hashes. These are file targets: they run only when those files are missing.
`make` does not reset a submodule that is initialised but has moved — it builds
whatever is checked out. Run the verify script before building.

**What `--remote` does.** Nothing during a normal clone or build. Only
`git submodule update --remote` reads branches: it moves a submodule to the head
of its `branch =`, or of the remote's default branch (`origin/HEAD`) when no
`branch =` is set, and stages a new gitlink. Omitting `branch =` therefore does
not opt a submodule out — it just targets the default branch. With
`--recursive`, nested submodules move too. That is the drift footgun: it
silently replaces a verified tree with an untested one (see the Map's drift
column).

A single `--remote --recursive` would swap the display stack (lvgl `v9.x` over
the pinned `v6.0.2`), both `secp256k1-zkp` trees — including the one compiled
into the signing usermod — and the bootloader's `secp256k1` (1824 commits
ahead). Even lvgl's `release/v6` is 490 commits past `dd100e5` (`1f707f9`,
2025-08-14, vs 2019-10-29).

Historically this repo was left in exactly that broken state — `f469-disco`
pinned at `db3ce3e` with an embit submodule from a later commit layered on top
as untracked content, which made `make unix` fail on a frozen
`embit/examples/explorer.py`.

Avoid `--remote`. To move a top-level pin (`bootloader`, `f469-disco`), do it
explicitly:

```sh
git submodule sync --recursive
git -C <path> fetch origin <branch>
git -C <path> checkout <full-sha>
git -C <path> submodule sync --recursive
git -C <path> submodule update --init --recursive
git add <path>
```

A nested pin is recorded in its parent submodule's repo, not here. Bumping it
takes one commit per level: `bootloader/lib/*` and `f469-disco/micropython`,
`f469-disco/usermods/secp256k1`, `f469-disco/libs/common/embit` need two;
either `secp256k1-zkp` checkout needs three. Check first that each parent's
drift is `0`; otherwise checking out its branch also pulls in the untested
commits past its pin.

```sh
# 1. in the direct parent: move the nested pin, commit, push to its branch
git -C <parent> checkout <parent-branch>          # e.g. f469-disco/usermods/secp256k1 → secp-zkp--int
git -C <parent>/<nested> fetch origin
git -C <parent>/<nested> checkout <full-sha>
git -C <parent> add <nested>
git -C <parent> commit -m "bump <nested> to <sha>"
git -C <parent> push origin <parent-branch>

# 2. repeat step 1 one level up (e.g. in f469-disco, branch dev) until a
#    top-level submodule holds the new commit

# 3. here: move the top-level pin to that new commit
git add <top-level>
```

Both `secp256k1-zkp` checkouts are pinned to the same commit. To keep them in
step, run step 1 in both `f469-disco/usermods/secp256k1` (branch
`secp-zkp--int`) and `f469-disco/libs/common/embit` (branch `int`), stage both
in one `f469-disco` commit on `dev`, then stage `f469-disco` here.

**Verifying a checkout matches the pins**

```sh
git submodule status --recursive
```

Every line must start with a **space**. A leading `+` means the checkout differs
from the recorded gitlink, `-` means uninitialized, `U` means conflicts. This
compares against the **index**, so a staged-but-uncommitted pin also shows a
space; use `git diff --cached --submodule=short` to see pins that differ from
`HEAD`. For changes inside submodules, nested ones included, check the
verify script's `dirty` field.

Untracked content inside a submodule is not harmless here:
`f469-disco/manifests/common.py` and `f469-disco/manifests/embit.py` walk whole
directory trees and freeze every `.py` they find, so stray files can end up
compiled into firmware or break the build.

**Local remote URLs.** The URLs in `.git/config` (here and in each submodule)
should match the matching `.gitmodules`. Re-check after any `.gitmodules` edit,
here or in a submodule — an already-initialised checkout keeps the old URL until
synced. Known cases: `bootloader/lib/fatfs` (was `cryptoadvance/fatfs`) and
`f469-disco/usermods/secp256k1/secp256k1` (was `ElementsProject/secp256k1-zkp`).

```sh
git config --get-regexp '^submodule\..*\.url'
git submodule foreach --recursive 'git config --get-regexp "^submodule\..*\.url" || :'
git submodule foreach --recursive -q 'echo "$displaypath $(git remote get-url origin)"'
git submodule sync --recursive
```

This never affects a pin, only where a re-fetch goes. A stale `origin` also
breaks `git submodule update --remote` with
`fatal: Unable to find refs/remotes/origin/dev revision in submodule path '<path>'`
even though `dev` exists on the correct fork.

**What can still break reproducibility.** The pins are only as durable as the
remotes and branches hosting them. An orphaned pin makes a fresh `--recursive`
clone fail; its objects then survive only in existing local clones. None of the
pins is orphaned today (see the Map's "Pin reachable from" column).

- **Forks:** a pin reachable from only one branch (`bootloader`, `f469-disco`,
  `f469-disco/libs/common/embit`, `f469-disco/usermods/secp256k1`) is orphaned
  if that branch is force-pushed past it. Tagging those pins in their forks
  would protect them.
- **External remotes** (`bitcoin-core/secp256k1` — bootloader crypto;
  `lvgl/lvgl` — display): both pins are contained in upstream tags, so only
  repository deletion (or tag removal plus force-push of every containing
  branch) can orphan them.
- If the reason for forking `micropython`, `secp256k1-embedded`, `embit`,
  `fatfs` and both `secp256k1-zkp` instances was to control that exposure, the
  same argument covers `bitcoin-core/secp256k1`, the remaining external crypto
  remote. It is declared in `bootloader/.gitmodules`, so forking it takes a
  commit there as well — as was done for `fatfs` in bootloader `c331570`, for
  `embit/secp256k1/secp256k1-zkp` in embit `4f1afc7`, and for
  `usermods/secp256k1/secp256k1` in secp256k1-embedded `0502cf4`.
