# Submodules

## Map

- The table below is a snapshot; the gitlinks in each parent's tree are the
  source of truth for pins
- Forks live under `hardware-wallets-and-cryptography/`
- Paths are relative to this repo's root
- Drift snapshot is documented as of `2026-09-29`

| Submodule | Remote | Fork | Pin | Describe (`git describe --tags --abbrev=10`) | `--remote` target | Drift past pin | Pin reachable from | Binary |
|---|---|:-:|---|---|---|---|---|:-:|
| `bootloader` | `specter-bootloader` | ✅ | `0bdba4f798` | `v1.0.0-24-g0bdba4f798` | `dev` (`branch =`) | 0 | `dev` only | bootloader |
| `bootloader/lib/fatfs` | `fatfs` | ✅ | `8ea3980232` | `R0.14-2-g8ea3980232` | `dev` (`branch =`) | 0 | `dev`, `int`, `master` | bootloader |
| `bootloader/lib/secp256k1` | `bitcoin-core/secp256k1` | ❌ | `5e1c885efb` | — | `master` (default) | **1826** (→ `2b4a7b906f`) | `master`, 12 tags | bootloader |
| `f469-disco` | `f469-disco` | ✅ | `59aa8ef34f` | `v1.3.1-20-g59aa8ef34f` | `dev` (`branch =`) | 0 | `dev` only | firmware |
| `f469-disco/libs/common/embit` | `embit` | ✅ | `b2e606bb71` | `v0.8.2-4-gb2e606bb71` | `int` (`branch =`) | 0 | `int` only | firmware |
| `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` | `secp256k1-zkp` | ✅ | `d9560e0af7` | — | `master` (default) | **1949** (→ `037cc6d74c`) | `master`, `dev`, `int` | — |
| `f469-disco/micropython` | `micropython` | ✅ | `6bdf1b6916` | `v1.10-1185-g6bdf1b6916` | `master` (default) | 0 | `master` only | firmware |
| `f469-disco/usermods/secp256k1` | `secp256k1-embedded` | ✅ | `1c41d24e56` | — | `secp-zkp--int` (`branch =`) | 0 | `secp-zkp--int` only | firmware |
| `f469-disco/usermods/secp256k1/secp256k1` | `secp256k1-zkp` | ✅ | `d9560e0af7` | — | `master` (default) | **1949** (→ `037cc6d74c`) | `master`, `dev`, `int` | firmware |
| `f469-disco/usermods/udisplay_f469/lvgl` | `lvgl` | ✅ | `dd100e5e07` | `v6.0.2-31-gdd100e5e07` | `f469-disco--pin` (`branch =`) | 0 | `f469-disco--pin`, `master` | firmware |

> Describe values come from upstream tags left in a local clone. The forks have
> no tags, so in a fresh clone `git describe --tags` fails with "No names found".
> `bootloader/lib/secp256k1` predates upstream's first tag; `git describe
> --contains` gives `v0.2.0~173`.

> **8 remotes are forked** *(9 submodules; `secp256k1-zkp` is used twice, see below)*  
> **1 remote is external** (`bitcoin-core/secp256k1`)

> Remote `secp256k1-zkp` appears twice:
> - under `f469-disco/usermods/secp256k1`  
> - under `f469-disco/libs/common/embit/secp256k1`
>
> Both from the same fork and at the same commit `d9560e0af7`, so there is no
> version skew between the two checkouts.
>
> **Only the `usermods` copy reaches firmware; keep the two in step when bumping.**

Pins below `f469-disco/` are recorded in `f469-disco`, not here. See
`f469-disco/docs-my/submodules.md` for that repo's own view.

## What reaches the device

**Firmware**
- `make disco` (`make debug` is the same with `boot/debug`)

| Submodule | Built into | Mechanism |
|---|---|---|
| `f469-disco/micropython` | the build | `make -C f469-disco/micropython/ports/stm32` |
| `f469-disco/usermods/secp256k1` + its `secp256k1/` tree | signing usermod | `USER_C_MODULES=../../../usermods` (relative to `f469-disco/micropython/ports/stm32`) |
| `f469-disco/libs/common/embit` | frozen Python | `manifests/disco.py` → `f469-disco/manifests/disco.py` → `empty.py` + `common.py` → `embit.py` |
| `f469-disco/usermods/udisplay_f469/lvgl` | display usermod | its `micropython.mk` includes `lvgl/lvgl.mk` |
| `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` | **not built** | outside every freeze root (see note below) |

> `embit.py` walks `embit/src` and skips `embit/util` (CPython-only backends —
firmware uses the C usermod)

> `common.py` skips `embit`, so no double-freeze

> `manifests/disco.py` also freezes `src/` and `boot/main` (`debug.py`:
`boot/debug`)

**Bootloader** (separate binary, packed into `initial_firmware.bin` by
`build_firmware.sh`)

| Submodule | Built into | Mechanism |
|---|---|---|
| `bootloader/lib/secp256k1` | bootloader | `bootloader/platforms/stm32f469disco/bootloader/Makefile` |
| `bootloader/lib/fatfs` | bootloader | same `Makefile` |

**Not built note**: `f469-disco/libs/common/embit/secp256k1/secp256k1-zkp` is a
C source tree for `embit`'s own CPython ctypes build, outside every freeze root.
Its parent, `f469-disco/libs/common/embit/secp256k1/`, shares its name with the
`secp256k1` module that `embit` imports. Under CPython, with the embit repo root
on `sys.path`, `import secp256k1` would resolve that directory as an implicit
namespace package; `f469-disco/libs/common/embit/src/embit/util/secp256k1.py`
guards against that explicitly (it keys on `from micropython import const`).

## Verify pin and drift for each submodule

Reads each pin and `--remote` target from git, so it needs no edit after a pin
bump. Use it to refresh the Map's drift column:

```sh
git submodule foreach --recursive -q '
  b=$(git config -f "$toplevel/.gitmodules" "submodule.$name.branch") || \
    { git remote set-head origin -a >/dev/null; b=HEAD; }
  git fetch -q origin
  printf "%-55s pin=%.10s head=%s drift=%s dirty=%s\n" "$displaypath" "$sha1" \
    "$(git rev-parse --short=10 HEAD)" \
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

resolves the exact same trees, regardless of who owns each remote. This holds
for a clone of this branch (`-b <branch>`); the fork's default `master` still
carries the upstream URLs (`diybitcoinhardware/f469-disco`,
`cryptoadvance/specter-bootloader`). The `Makefile`
guard rules for `$(MPY_DIR)/mpy-cross/Makefile` and `$(EMBIT_INIT)`
(`f469-disco/libs/common/embit/src/embit/__init__.py`) run

```make
git submodule update --init --recursive
```

with **no `--remote`**, so a fresh checkout is initialized at the recorded
hashes. These are file targets: they run only when those files are missing.
A partly initialized tree (e.g. `micropython` and `embit` present but
`f469-disco/usermods/secp256k1` or `bootloader` missing) is not caught. `make`
does not reset a submodule that is initialized but has moved — it builds
whatever is checked out. Run the verify script before building.

**What `--remote` does.** Nothing during a normal clone or build. Only
`git submodule update --remote` reads branches: it moves a submodule to the head
of its `branch =`, or of the remote's default branch (`origin/HEAD`) when no
`branch =` is set, and checks out the new commit without staging it
(`git submodule status` shows `+`; `git add` records it). Omitting `branch =` therefore does
not opt a submodule out — it just targets the default branch. With
`--recursive`, nested submodules move too. That is the drift footgun: it
silently replaces a verified tree with an untested one (see the Map's drift
column).

A single `--remote --recursive` would swap both `secp256k1-zkp` trees —
including the one compiled into the signing usermod — and the bootloader's
`secp256k1` (1826 commits ahead). lvgl is safe only because its fork's
`f469-disco--pin` branch sits at the pin; the fork's `master` would pull
`v9.x` over the pinned `v6.0.2`.

Historically this repo was left in exactly that broken state — `f469-disco`
pinned at `db3ce3e918` with an embit submodule from a later commit layered on top
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
here or in a submodule — an already-initialized checkout keeps the old URL until
synced. Known cases: `bootloader/lib/fatfs` (was `cryptoadvance/fatfs`),
`f469-disco/usermods/secp256k1/secp256k1` (was `ElementsProject/secp256k1-zkp`)
and `f469-disco/usermods/udisplay_f469/lvgl` (was `lvgl/lvgl`).

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
  `f469-disco/libs/common/embit`, `f469-disco/micropython`,
  `f469-disco/usermods/secp256k1`) is orphaned if that branch is force-pushed
  past it. Tagging those pins in their forks would protect them. This has
  already happened once: `embit` `d418ef39d4` and `secp256k1-embedded`
  `0502cf4435` were rewritten to `b2e606bb71` and `1c41d24e56` (same trees)
  and survive only in local clones.
- **Forks with several branches** (`fatfs`: `dev`, `int`, `master`; `lvgl`:
  `f469-disco--pin`, `master`; `secp256k1-zkp`: `master`, `dev`, `int`):
  orphaned only if every containing branch is force-pushed. No fork has tags.
- **External remote** (`bitcoin-core/secp256k1` — bootloader crypto): the pin
  is contained in upstream tags, so only repository deletion (or tag removal
  plus force-push of every containing branch) can orphan it.
- If the reason for forking `micropython`, `secp256k1-embedded`, `embit`,
  `fatfs`, `lvgl` and both `secp256k1-zkp` instances was to control that
  exposure, the same argument covers `bitcoin-core/secp256k1`, the remaining
  external remote. It is declared in `bootloader/.gitmodules`, so forking it
  takes a commit there as well — as was done for `fatfs` in bootloader
  `0961f30d08`, for
  `embit/secp256k1/secp256k1-zkp` in embit `b1d42c633f`, and for
  `usermods/secp256k1/secp256k1` in secp256k1-embedded `1c41d24e56`.
