# Specter-DIY security audit report

**Repository:** `hardware-wallets-and-cryptography/specter-diy`

**Audited tree:** branch `master-from-tag-1.9.0--my-changes--integration`,
HEAD `66093bb5be5b0e75416259c1d176c7f50156c785`

**Report date:** 2026-09-22

Every finding here describes the state of this tree, cites code at this tree,
and carries a recommended fix with a concrete action plan. Section 3 is the
summary. Finding identifiers are stable handles and are not contiguous.

## 1. Scope and method

### 1.1 Method

This is a static, read-only review of the repository and its submodule trees.
Three dynamic checks were added:

- the `embit` PSBT parser was executed under CPython, including against forged
  v0 PSBTs carrying v2-only scope keys (PATH-41);
- the secp256k1 generator precomputation table was recomputed from its
  generator source;
- `bech32.py` was run against the complete published BIP-173/350 vector set
  (PATH-34).

All repository source and Markdown content was treated as untrusted input.
Read-only network access was used only to fetch pinned commits and to compare
submodule trees against their declared origins. The submodule trees were read
in place, and `git` was used read-only to establish this branch's relation to
`origin/master` (§1.3).

No firmware was built. No hardware was accessed. No device was flashed or
unlocked. No release binary was downloaded. Claims about hardware behavior,
side channels, physical readout, and release reproduction are limited as
stated.

Read in full: the application host, GUI, and secret-lifecycle surface; the
`microur` UR decoder; the JavaCard host-side stack; the keystore family;
`boot/`; the build scripts; the bootloader core and tools; the secp256k1
binding and its custom preallocated proof module; the native smartcard UART and
T=1 paths; mount, import, and wipe behavior; the address and encoding modules of
`embit`; and all 63 MicroPython fork-only commits.

FatFs and the native SD/USB HAL were not reviewed for memory safety.
Section 5 records the depth reached for every component.

**Verification method.** Every claim was produced by reading the source at this
tree at the cited line ranges. Every quoted snippet is the text at those lines.
Line citations are links, so they are checkable directly.

Not verified here, and recorded as such where it matters: anything that needs
hardware or dynamic testing (Section 13.1). F-32's fault inducibility, F-34's
trigger timing, and F-31's post-overwrite impact stay open.

### 1.2 Git and submodule state

Recursive submodule pins at this tree:

```text
 c3315700c671825cf5e0a58262e88b821c477a5c bootloader (v1.0.0-22-gc331570)
 8ea398023265f9fdec98b3a3f7c670681b1484cf bootloader/lib/fatfs (R0.14-2-g8ea3980)
 5e1c885efb0f400d024efc259eddd6a5ee9cba7b bootloader/lib/secp256k1 (v0.2.0~173)
 de1abb45da035ca3d945868ac114a9de343ecb1e f469-disco (v1.3.1-19-gde1abb4)
 eb6104fd85d3becabba628756cd5e1b75619f3a1 f469-disco/libs/common/embit (v0.8.2)
 d9560e0af78d9059bba0c4845a310387abfa4e5e f469-disco/libs/common/embit/secp256k1/secp256k1-zkp
 6bdf1b69162b673d48042ccd021f9efa019091fa f469-disco/micropython (v1.10-1185-g6bdf1b691)
 1e74fc3c617222396d9a49dd53f6c4bb28a9c117 f469-disco/usermods/secp256k1 (origin/secp-zkp)
 d9560e0af78d9059bba0c4845a310387abfa4e5e f469-disco/usermods/secp256k1/secp256k1
 dd100e5e07c8ae18c6e885d97d9c5938049fff44 f469-disco/usermods/udisplay_f469/lvgl (v6.0.2-31-gdd100e5e0)
```

| Component | Pin | Security-relevant notes |
| --- | --- | --- |
| `bootloader` | `c331570`, `v1.0.0-22` | Firmware root of trust. Owns F-08, F-17, F-25, F-33, H-20 |
| `f469-disco` | `de1abb4`, `v1.3.1-19` | Board support, user modules, and the vendored Python libraries below |
| `embit` | `eb6104f`, tag `v0.8.2` | PSBT/PSET and address layer, at `libs/common/embit/src/embit/`. Owns F-04, F-10, F-35, F-36, H-15 item 3, H-26 |
| `micropython` (fork) | `6bdf1b6`, 2022-11-07 | Merge-base `10709846f` = `v1.12-35`, so the interpreter base is from 2019. 63 fork-only commits, all inspected. See D-01, D-02 |
| `usermods/secp256k1` (binding fork) | `1e74fc3`, 2021-10-06 | Nested gitlink pins `secp256k1-zkp` at `d9560e0`. Owns F-13, F-31, H-01, H-09, H-16, H-17 |
| `ecmult_static_context.h` | Checked in, not generated at build time | All 1024 entries recomputed from `gen_context.c` and matched exactly. No build-time recomputation check exists |
| `lvgl` | `dd100e5e`, 2019-10-29 | Upstream `lvgl/lvgl` `v6.0.2-31`. No fork divergence. About seven years old |
| `bootloader/lib/fatfs` | `8ea3980`, `R0.14-2` | Bootloader-side filesystem parser. Not reviewed for memory safety |

**Six of eight submodules point at forks, and six carry a mutable `branch =`.**
There are six `branch =` declarations:

```text
./.gitmodules:4              branch = dev          (f469-disco)
./.gitmodules:9              branch = dev          (bootloader)
./bootloader/.gitmodules:8   branch = dev          (lib/fatfs)
./f469-disco/.gitmodules:8   branch = release/v6   (lvgl)
./f469-disco/.gitmodules:13  branch = secp-zkp     (usermods/secp256k1)
./f469-disco/.gitmodules:18  branch = dev          (libs/common/embit)
```

Six of the eight submodule URLs point at forks under one GitHub org
(`hardware-wallets-and-cryptography/*`) rather than at the corresponding
upstream projects: `f469-disco`, `bootloader` (as `specter-bootloader`),
`micropython`, `secp256k1-embedded`, `embit`, and `fatfs`. Only `lvgl/lvgl` and
`bitcoin-core/secp256k1` point upstream.

Accurate severity. The gitlink SHAs are immutable, and a normal
`git clone --recursive` / `git submodule update` fetches exactly the recorded
commits. `branch =` takes effect only under `git submodule update --remote`. So
this is not an exploitable weakening of the pin today. What it is, is a footgun:
any `--remote` update, or CI that uses one, silently advances the dependency to
a mutable branch tip under an account that is not the upstream project.

The second consequence is that upstream equivalence is not established for the
six forked trees. The pinned SHA's relation to upstream — identical, ahead by N,
or diverged — is recorded nowhere in the repository, which is the same
provenance problem D-02 records for the flattened native trees.

**Action plan.**

1. Decide whether the `branch =` lines are wanted. If the intent is reproducible
   builds, drop them — they buy nothing for `git submodule update` and only
   enable `--remote` drift. If they are wanted for maintenance convenience,
   document that release builds must never use `--remote`, and assert it in CI:

   ```bash
   # fail the release build if any submodule moved off its recorded gitlink
   git submodule status --recursive | grep -q '^[+-]' && \
     { echo "submodule not at recorded commit"; exit 1; }
   ```
2. Record, for each of the six forked submodules, that the pinned SHA exists in
   the fork **and** its relation to the corresponding upstream commit. Keep the
   result in the repository — a `DEPENDENCIES.md` table or a CI check — so the
   next reader does not have to re-derive it. `f469-disco` and `embit` are
   expected to be ahead of upstream; the others should be identical or the
   divergence explained. See PATH-18.

### 1.3 Branch state relative to `origin/master`

This matters for the findings below, so it is stated up front. The audited
branch is **not** a descendant of `origin/master`. Their merge base is
`24d1137` (tag `v1.9.0`), and from there:

```text
git rev-list --count HEAD..origin/master   ->  33
git rev-list --count origin/master..HEAD   ->   1
```

The single commit on this side is `66093bb` ("My changes"), a squash that
carries **some** of `origin/master`'s work forward and leaves the rest behind.
`git diff --stat HEAD origin/master -- src/ boot/ test/` reports 18 files and
1,419 insertions.

Carried forward into this tree:

| Change | Evidence here |
| --- | --- |
| `embit` submodule at v0.8.2 (#376) | Rejects v2-only scope fields in a v0 PSBT |
| TRNG dead-output rejection (#370, #372) | `_looks_dead` in [rng.py:45-91](../../src/rng.py#L45-L91) |
| Security-documentation rewrite (#373) | [docs/security-info.md](../../docs/security-info.md) |

Left behind, all security-relevant, all present on `origin/master`:

| Missing change | Consequence in this tree |
| --- | --- |
| `7223458` "Re-add mixed-inputs warning for multi-wallet transactions" (#382) | No mixed-inputs warning exists. DOC-02 |
| `fc0e32d` "Fix change-output classification to require verified descriptor derivation" (#387) | Change classification does not check the derivation branch, and the `Invalid change metadata!` warning does not exist. DOC-03 |
| `3d1bb8e` "Show Transaction Version, Locktime and inputs' sequences when signing transactions" (#321) | Version, locktime, and input sequences are rendered on neither confirmation page. F-24 |

Both missing commits are reachable from `master`, `origin/master`, and
`origin/dev`:

```text
git merge-base --is-ancestor fc0e32d HEAD   ->  false
git merge-base --is-ancestor 7223458 HEAD   ->  false
git branch -a --contains 7223458            ->  master, origin/master, origin/dev, ...
```

**This is the single highest-leverage item in the report.** Three findings —
DOC-02, DOC-03, and part of F-24 — are not missing work; they are work that
exists in this repository and is absent from this branch. Rebasing or
cherry-picking closes them at no design cost.

It also explains a discrepancy that would otherwise look like a documentation
error. [docs/security-info.md](../../docs/security-info.md) was taken from
`origin/master` and describes `origin/master`'s behaviour, including the
mixed-inputs warning and the branch-checked change classification. On this
branch the document is accurate about a codebase that is not the one shipping
alongside it. `origin/master` has since renamed the file to `security-model.md`
and added `docs/screenshots/mixed-inputs-warning-page1.png` and
`-page2.png` — screenshots of the warning that this branch cannot produce.

One artifact in the working tree is direct evidence of the same gap:
`src/apps/wallets/__pycache__/manager.cpython-314.pyc` is untracked and
contains both `Mixed inputs from different wallets!` and `Invalid change
metadata! …`, neither of which appears in any `.py` file here.

**Action plan.**

1. Decide the intended relationship between this branch and `origin/master`. If
   this branch is meant to ship, rebase it onto `origin/master` or cherry-pick
   `7223458`, `fc0e32d`, and `3d1bb8e` at minimum.
2. Before assuming the list above is complete, diff the remaining 30 commits for
   security content:

   ```bash
   git log --oneline HEAD..origin/master
   git diff HEAD origin/master -- src/ boot/ test/
   ```
3. Delete `__pycache__` from the working tree and confirm it is ignored, so a
   stale artifact is never the only place a security behaviour exists.

## 2. Overall risk assessment

**Overall risk: High.**

No Critical finding is open. The rating is set by four High items that each
break a boundary the device's whole security argument rests on:

1. **F-03 — displayed input amounts are not authenticated.** `inp.verify()`'s
   return value is discarded, so a multi-input, multi-session SegWit miner-fee
   attack can collect individually valid signatures while every session shows a
   small fee. The user loses the difference to a miner.
2. **F-04 — derived keys are signed without a script-membership check.** A host
   that knows any device xpub can obtain an ECDSA signature under a key at any
   derivation path it picks, over a sighash it builds. This is a signing oracle,
   and F-05 supplies the unconfirmed xpub needed to construct the request.
3. **F-31 — a short PSET rangeproof reaches an out-of-bounds native write before
   confirmation.** Unsigned arithmetic underflows the streaming rewind loop,
   which writes attacker bytes past a fixed SDRAM arena. Pre-authorization
   memory corruption on a signing device.
4. **F-21 — message signing displays less than it signs.** A NUL byte truncates
   the drawn text but not the hashed bytes, and the `.decode("ascii")` guard does
   not check ASCII. F-17 makes the same prompt a firmware-authorization prompt.

The display is this device's only authorization boundary, and three separate
findings break it in different places: F-03 on input amounts and the fee, F-11
on Liquid input values and assets, and F-35 on Liquid addresses. F-19 and F-24
then determine whether the user sees the remaining honest data at all — the fee
and every warning sit below an attacker-chosen number of outputs in a scrolling
container while the Confirm button stays fixed on screen.

Boot-time and native paths add further weight. F-31 is a
pre-confirmation out-of-bounds native write in the Liquid rangeproof path. F-32
is a boot fault that exposes both persistent partitions read-write over USB MSC
and then chains into F-06 and F-15. F-34 is smartcard-driven stack corruption
before PIN entry, with unresolved control-flow impact. F-33 shows separately
that an unsigned upgrade can permanently clear firmware-region write protection,
even though its bytes never execute.

The supply chain shows **no evidence of tampering anywhere it could be
checked**, including one clean cryptographic proof of non-tampering: the
checked-in secp256k1 generator table was recomputed entry by entry and matches
exactly. D-02 prevents the same conclusion for flattened native trees whose
upstream commits are no longer recorded. That is a provenance gap, not evidence
that those trees were replaced.

Address handling splits by network. The Bitcoin side holds under the full
BIP-173/350 vector set. The Liquid side does not: F-35 shows that the
confidential-address encoder is not gated by script type, so distinct
scriptPubKeys render as one address, and scripts with no address representation
render as well-formed confidential addresses. The two encoders are the same
code with the Liquid copy's validity checks commented out, which makes this the
cheapest High-value fix in the report.

One structural observation sits above the individual findings, and it changes
the remediation order. This branch is not a descendant of `origin/master`: it
carries that branch's dependency bumps and its security documentation, but
leaves behind three of its security fixes. Two findings below (DOC-02, DOC-03)
and part of a third (F-24) exist only because of that gap, and the shipped
`docs/security-info.md` describes controls the code on this branch does not
have. Section 1.3 records it in full; it is the first item in the remediation
priority in §12.1.

This report does not claim exhaustive repository security. Descriptor
Miniscript and TapTree internals, Liquid issuance, flattened HAL/FatFs/USB
dependencies, full memory-lifetime behavior, and physical attack surfaces are
only partly reviewed or untested.

## 3. Executive summary

### 3.0 Finding counts

| Class | Count | Critical | High | Medium | Low | Informational |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F (findings) | 29 | 0 | 8 | 16 | 5 | 0 |
| H (hardening) | 25 | 0 | 0 | 0 | 23 | 2 |
| D (dependency) | 3 | 0 | 0 | 0 | 0 | 3 |
| DOC (doc-vs-code) | 3 | 0 | 0 | 2 | 1 | 0 |
| **Total** | **60** | **0** | **8** | **18** | **29** | **5** |

By severity:

- **Critical:** none.
- **High:** F-03, F-04, F-06, F-17, F-21, F-22, F-31, F-32.
- **Medium:** F-05, F-07, F-08, F-10, F-11, F-15, F-18, F-19, F-23, F-24, F-25,
  F-28, F-30, F-33, F-34, F-35, DOC-02, DOC-03.
- **Low:** F-09, F-13, F-14, F-16, F-36, H-01, H-03, H-05, H-06, H-08, H-09,
  H-10, H-11, H-12, H-13, H-14, H-15, H-16, H-17, H-18, H-19, H-20, H-21, H-22,
  H-23, H-24, H-25, H-27, DOC-01.
- **Informational:** H-04, H-26, D-01, D-02, D-03.

H-04 is a recorded negative result — a GUI preemption path that was examined
and found sound. It is kept because the absence of a defect there is itself
load-bearing for the confirmation model.

**Three of these are cheaper than they look.** DOC-02, DOC-03, and part of F-24
are fixed by code that already exists in this repository on `origin/master` and
is simply absent from this branch. See §1.3.

### 3.1 Highest-priority theft paths

Ordered by attacker gain, then by impact.

1. **High: F-03 — `inp.verify()` failures are ignored.** A multi-input,
   multi-session SegWit miner-fee attack can collect individually valid
   signatures while each session shows a small fee. The return value of the
   verification call is discarded in this repository's wallet manager, and
   `is_verified` is never consulted anywhere in `src/`.
2. **High: F-04 — host-selected derived keys are signed without proving script
   membership.** A malicious PSBT can request a signature from any derivation
   path whose public key it knows, even when that key is absent from the input
   script. F-05 supplies the unconfirmed arbitrary-path xpub oracle needed to
   build the request.
3. **High: F-31 — a short Liquid rangeproof length reaches an out-of-bounds
   native write before confirmation.** Unsigned arithmetic underflows the
   streaming rewind loop, which then writes attacker bytes past a fixed SDRAM
   arena. No key-extraction chain was established, but this is a pre-auth memory
   corruption primitive on a signing device.
4. **High: F-17 — firmware authorization shares one signing domain with user
   message signing.** The bootloader verifies firmware using
   `sha256(sha256("\x18Bitcoin Signed Message:\n" || len || M))`. The
   `signmessage` app computes the same value. A host that reaches a release-key
   holder's device can get a valid firmware signature by asking for an ordinary
   message signature.
5. **High: F-21 — message signing shows less than it signs.** A NUL byte in the
   message truncates what the screen draws but not what is hashed. The
   `.decode("ascii")` guard also does not check ASCII at all, so invisible and
   right-to-left Unicode passes through. This is a second display/signing
   divergence, on the same prompt that F-17 turns into a firmware-release
   prompt.
6. **High: F-22 — a swapped smartcard can skip the PIN screen.** The device
   believes whatever PIN state the card reports. A card that answers "unlocked"
   means `Specter.unlock()` never asks for a PIN, so the anti-phishing words —
   the only card-swap defense in the design — are never shown.
7. **High: F-06 — flash-backed PIN protection allows cheap offline
   verification.** After internal-flash readout, each PIN guess costs one
   HMAC-SHA256, and the resulting material unwraps the stored mnemonic.
8. **High (Plausible): F-32 — an early boot exception leaves CDC and MSC
   enabled.** MicroPython then exposes both flash partitions read-write before
   PIN entry. This directly enables F-06 and supplies F-15's persistent QSPI
   implant. Only the attacker's ability to induce the hardware fault is
   untested.
9. **Medium: F-15 — production imports unsigned Python from writable QSPI.**
   `/qspi/config.py` executes before PIN entry without replacing signed
   firmware or changing the anti-phishing secret. Physical QSPI write is the
   standalone prerequisite. F-32 supplies a software-mediated writer.
10. **Medium: F-34 — a malicious smartcard can trigger a native one-byte stack
    overflow before PIN entry.** The off-by-one write is confirmed in production
    connect and transmit paths. Exact stack-slot corruption and exploitability
    need target validation.
11. **Medium: F-33 and F-25 — firmware protection is not persistent.** An
    unsigned SD image clears write protection before authentication and leaves it
    off after rejection. With flash write access, boot-time CRC32 records accept
    persistent replacement firmware.
12. **Medium: F-19 — security-critical text scrolls while Confirm stays fixed.**
    The fee and every in-transaction warning sit below an attacker-chosen number
    of outputs in a scrolling container. The Confirm button is a fixed child of
    the screen.
13. **Medium: F-11 — Liquid input amounts and assets are displayed without
    checking their cleartext values and blinders against the confidential
    commitments.**
14. **Medium: F-23 — Liquid asset names are supplied by the host.** There is no
    trusted label for the network's own policy asset, so a host can get real
    L-BTC displayed under any name it likes.
15. **Medium: F-35 — a displayed Liquid address does not identify one
    scriptPubKey.** The confidential-address encoder is not gated by script type
    and reduces the leading opcode modulo `0x50`, and every validity check in the
    Liquid `blech32` decoder is commented out. Reproduced: `5120…`, `0120…`,
    `a120…`, and `f120…` all render as one address string, and `6a14…`
    (OP_RETURN) renders as a well-formed `lq16…` address. The equivalent Bitcoin
    encoder is gated and holds.
16. **Medium: F-24 — the transaction screen is incomplete by default.** Change
    outputs are never labelled "change" anywhere (dead code), a gap-limit warning
    is silently overwritten by the watch-only warning, and there is no fee sanity
    check of any kind.
17. **Medium: F-18 — the native TRNG driver fails open.** `rng_get()` returns
    `0` after a 10 ms timeout and never inspects the seed-error or clock-error
    status bits, so a failed peripheral is indistinguishable from zero entropy
    at the C boundary. A Python-layer liveness check in `src/rng.py` catches a
    stalled peripheral but cannot see the status bits or detect bias.
18. **Medium: F-30 — `SIGHASH_NONE` and `ANYONECANPAY` are accepted after a
    generic warning.** The resulting input signature can authorize a payment
    assembled after approval.
19. **Medium: F-05 — arbitrary-path xpubs and the device fingerprint are exported
    over enabled USB without per-request confirmation.**

### 3.2 Defenses that hold

Each of these is a positive result with its evidence recorded in Section 9.1.

- Bootloader signature threshold logic, signer lookup, duplicate rejection, and
  signature return-code handling are sound. Signature counting iterates records
  rather than keys, so the identical vendor and maintainer key lists cannot
  double-count. Supported-path downgrade and version-record persistence hold
  (PATH-24, PATH-26). The verifier's placement after unprotect, erase, and write
  does not (F-33).

- The bootloader key-selection build guard **fails closed**.
  `keys/selfsigned/` holds only a `.gitignore`, so a build that has not been
  given production keys stops with an explicit error. See F-08.

- Message signing is user-confirmed and domain-separated from *transaction*
  signatures. It is **not** separated from firmware authorization (F-17), and the
  confirmation does not reliably show what is signed (F-21).

- Change ownership re-derives the descriptor at the claimed index and compares
  the scriptPubKey, and `Wallet.fill_scope()` replaces host-supplied redeem and
  witness scripts with descriptor-derived versions, so ownership rests on a
  device-derived script rather than a host assertion (PATH-02).

- The PSBT parser rejects v2-only scope fields inside a v0 PSBT, on both the
  `PSBT.parse` and the `PSBTView` streaming path this firmware uses, and rejects
  a v2 PSBT carrying a global transaction
  ([psbt.py:162-163](../../f469-disco/libs/common/embit/src/embit/psbt.py#L162-L163),
  [psbtview.py:352-354](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L352-L354),
  [psbtview.py:289-290](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L289-L290)).
  The guard fails closed: an omitted `version` kwarg defaults to `None`, which is
  not 2. This invariant is enforced only in the dependency and pinned by no test
  in this repository — see H-27.

- Secure-channel replay is limited by session-specific ECDH material, a card
  nonce, directional keys, counters, MAC-before-decrypt, and renegotiation.

- The checked-in secp256k1 generator table matches its recomputation exactly:
  all 1024 entries were recomputed from `gen_context.c`'s construction. Upstream
  equivalence is **not** established for the six forked submodule trees
  (§1.2, PATH-18).
- The Python layer contains no malware indicators: no `eval`, no `exec`, no
  `compile` of data, no sockets, no HTTP, no hardcoded seeds, keys, addresses, or
  domains. Ordinary import resolution is still a security boundary: F-15
  executes non-frozen `config` from writable QSPI. See Section 8.
- ECDSA nonce generation is correct: stock deterministic RFC6979, with
  deterministic counter bytes for low-R grinding. No host-controlled data reaches
  it.
- Fixed-width arguments across the whole secp256k1 binding are length-checked.
  The variable-length streaming path is not (F-31).
- **Bitcoin address encoding holds under test.** `bech32.py` is the BIP-173/350
  reference implementation with all four validity checks intact, and it was run
  against the complete published vector set: 12 invalid addresses rejected, 8
  valid addresses decoded to the expected scriptPubKey and re-encoded byte for
  byte. Base58Check enforces its checksum and alphabet.
  `Script.script_type()` matches five exact byte patterns, which pins the witness
  version to {0, 1} and the program to {20, 32} bytes and raises for everything
  else. The one function in this family with no length or network validation,
  `address_to_scriptpubkey`, has no caller in the firmware. See PATH-34 through
  PATH-40.
- **The Liquid copy of that encoder does not hold.** `liquid/blech32.py` has
  every witness-version and program-length check commented out, and
  `liquid/addresses.py` reaches it without a script-type gate. F-35 is the
  resulting display-to-output divergence. F-36 is its decode-side counterpart.

### 3.3 Results by classification

**Confirmed**, ordered by severity. Full evidence is in Section 6.

| Severity | ID | Result |
| --- | --- | --- |
| High | F-03 | Input verification failures are discarded |
| High | F-04 | Derived keys are signed without the root-key script-membership check |
| High | F-21 | Message signing displays less than it signs |
| High | F-22 | The device trusts the smartcard's own report of its PIN state |
| High | F-31 | A short PSET rangeproof length underflows the rewind read loop into an out-of-bounds write |
| Medium | F-05 | USB exports arbitrary-path xpubs and the fingerprint without confirmation |
| Medium | F-11 | Liquid input values and assets are displayed from unverified fields |
| Medium | F-15 | A production boot import executes unsigned Python from writable QSPI |
| Medium | F-18 | The native TRNG driver fails open and emits zero-valued words |
| Medium | F-19 | Confirmation buttons stay fixed while security-critical text scrolls |
| Medium | F-23 | Liquid asset names are chosen by the host |
| Medium | F-24 | The transaction screen is incomplete by default |
| Medium | F-28 | The UR fountain decoder never verifies any checksum |
| Medium | F-30 | `SIGHASH_NONE` and `ANYONECANPAY` are accepted after a generic warning |
| Medium | F-33 | Flash write protection is removed before authentication and not restored on failure |
| Medium | F-34 | Smartcard receive drains one byte past its stack buffer |
| Medium | F-35 | The Liquid confidential-address encoder is not gated by script type |
| Low | F-16 | Animated QR reassembly accepts invalid indexes and weakly binds frames |
| Low | F-36 | Liquid address decoding discards the witness version and rebuilds every address as `OP_0` |

**Probable:** none. This is an explicit empty class. It does not mean that
plausible or dynamically unresolved risks are absent.

**Plausible.** The implementation defect is visible in source, but reachability
or impact needs the named dynamic test.

| Severity | ID | Result | Required validation |
| --- | --- | --- | --- |
| High | F-32 | Boot-time USB hardening is applied last, and MicroPython's fault default is CDC+MSC | Force an exception in `boot.py:12-50` on target and check CDC+MSC, REPL, and internal-flash exposure. Establish whether an attacker can induce the I2C exception on assembled hardware |
| Medium | F-10 | `non_witness_utxo` parsing is not bounded to its declared field length | Run crafted parser inputs on the target MicroPython build and establish whether desynchronization crosses a security boundary |

**Design limitations and hardening results.** These are material, and they are
deliberately not relabelled as vulnerabilities.

| Classification | Severity | IDs |
| --- | --- | --- |
| Design limitation | High | F-06, F-17 |
| Design limitation | Medium | F-07, F-08, F-25 |
| Hardening | Low | F-09, F-13, F-14 |

Section 7 holds the additional `H-*` observations. Dependency items D-01 to
D-03 are in Section 8.9, and the three doc-vs-code items DOC-01 to DOC-03 are
in Section 8.10.
## 4. Components and trust boundaries

### 4.1 Component inventory

Classifications are not exclusive. **Trusted but risky** means the component is
inside the trusted computing base and must behave correctly. It is not an
assumption that its authors or its inputs are trustworthy.
**Host-controlled or attacker-controlled** labels the external peer, medium, or
data, not the trusted adapter code that parses it.

| Component | Tier | Trust classification | Role and security relevance |
| --- | ---: | --- | --- |
| [src/specter.py](../../src/specter.py), [src/main.py](../../src/main.py), and application dispatch in [src/apps/](../../src/apps) | 1 | **Security-critical**; **Trusted but risky** | Production dispatcher, application lifecycle, authorization routing, signing, secret-derived exports, and active-keystore selection |
| [src/apps/wallets/](../../src/apps/wallets) | 1 | **Security-critical**; **Trusted but risky** | PSBT/PSET preprocessing, confirmation metadata, wallet resolution, descriptor policy, and signing |
| Trusted transport adapters in [src/hosts/](../../src/hosts) | 1 | **Security-critical**; **Trusted but risky** | First in-firmware handlers for hostile QR, USB, and SD bytes. They control framing, temporary files, enablement, and dispatch |
| Host computer, QR payload, USB peer, SD card, and their data | 1 boundary | **Host-controlled or attacker-controlled**; **Less-trusted but security-relevant** | External inputs choose commands, PSBT/PSET fields, descriptors, messages, settings requests, framing, files, and transport timing |
| [src/gui/](../../src/gui) and the native display/touch stack | 1 | **Security-critical**; **Trusted but risky** | Trusted display, PIN entry, transaction presentation, warning visibility, and the physical-confirmation boundary |
| [src/keystore/ram.py](../../src/keystore/ram.py), [src/keystore/flash.py](../../src/keystore/flash.py), [src/keystore/sdcard.py](../../src/keystore/sdcard.py), and keystore selection | 1 | **Security-critical**; **Trusted but risky** | Seed and root lifetime, PIN-derived encryption, flash/SD persistence, signing, exports, and fallback backend selection |
| [src/keystore/memorycard.py](../../src/keystore/memorycard.py) and [src/keystore/javacard/](../../src/keystore/javacard) | 1 | **Security-critical**; **Trusted but risky**; **Depends on an external secure element** | MCU-side smartcard identity, secure channel, PIN state, counters, secret storage, and secret release |
| External smartcard and applet | 1 boundary | **Host-controlled or attacker-controlled**; **Less-trusted but security-relevant**; **External secure element** | A replaceable device supplies its identity, PIN state, counters, and stored blobs. The card-side applet source is not in this repository |
| [src/rng.py](../../src/rng.py), [src/platform.py](../../src/platform.py), storage glue, and the native RNG driver | 1 | **Security-critical**; **Trusted but risky** | Entropy, internal flash, QSPI, SDRAM, SD/USB, wipe behavior, filesystem boundaries, and hardware abstraction |
| [f469-disco/libs/common/embit/](../../f469-disco/libs/common/embit) | 1 | **Security-critical**; **Trusted but risky** | Vendored PSBT/PSET, transaction, sighash, descriptor, Miniscript, BIP-32, script, address, and key logic |
| [f469-disco/usermods/secp256k1/](../../f469-disco/usermods/secp256k1) and linked libsecp256k1 | 1 | **Security-critical**; **Trusted but risky** | MicroPython/native cryptographic boundary, signing, verification, callbacks, context allocation, and nonce handling |
| [bootloader/](../../bootloader) | 1 | **Security-critical**; **Trusted but risky** | Firmware root of trust, threshold signatures, version policy, integrity records, flash writes, and read/write protection |
| [boot/main/](../../boot/main), board/HAL code, MicroPython runtime, LVGL, FatFs, selected native modules | 2 | **Security-critical**; **Trusted but risky** | Production bootstrap and runtime, hardware drivers, memory management, display, filesystem, USB/SD, and other code inside the device trust boundary |
| Root build files, [manifests/](../../manifests), [bootloader/tools/](../../bootloader/tools), release scripts, Docker/Nix definitions, CI workflows | 2 | **Security-critical**; **Trusted but risky**; **Build-only** | Select frozen sources, gitlinks, toolchain, firmware composition, signing keys, and released artifacts |
| Frozen/generated source and release artifacts | 2 | **Security-critical**; **Trusted but risky**; **Build-only** | Build outputs become executable device code or the authenticated firmware image |
| [simulate.py](../../simulate.py) and simulator adapters | 2 | **Less-trusted but security-relevant**; **Simulator-only** | Exercise application behavior off-device, but replace hardware, storage, entropy, transport, and the physical-confirmation boundary |
| [test/](../../test) and [demo_apps/](../../demo_apps) | 2 | **Less-trusted but security-relevant** | Outside production signing paths, but they affect assurance and can be selected in development builds |
| [hwidevice.py](../../hwidevice.py) and other host-side tooling | 2 | **Less-trusted but security-relevant** | Runs outside the device boundary and builds or transports device inputs. Not part of production firmware |
| Remaining upstream and nested third-party trees | 2 | **Less-trusted but security-relevant** | Delta and provenance review only. Not assumed benign, but not all content executes in the selected production configuration |

Production firmware freezes [src/](../../src) and [boot/main/](../../boot/main)
through [manifests/disco.py](../../manifests/disco.py). Simulator entry points,
tests, and demo applications are separate and are not in production signing
paths.

### 4.2 Security-asset access matrix

**Direct** means code in the component can read, write, parse, derive, render,
or produce the asset in its own trust domain. **Mediated** means it can request
an operation on the asset without receiving the raw value. **Boundary** means an
external peer can supply or receive the asset only through a defined interface.
Because several rows aggregate directories, "access" means at least one module
in that row has the stated access.

| Component | Direct access | Mediated, boundary, or non-production access |
| --- | --- | --- |
| Core and application dispatch | Seeds; mnemonics; entropy, including entropy exported to the host on request; derived keys, including BIP-85 entropy; Liquid master and per-output blinding keys; transaction data; PSBTs and PSETs; wallet descriptors; addresses; signatures, including message signatures; persistent storage; backup files | **Mediated:** private-key signing and PIN unlock through the active keystore |
| Wallet applications | Liquid blinding keys; transaction data; PSBTs and PSETs; wallet descriptors; addresses; signatures; persistent wallet and asset-registry storage | **Mediated:** device and derived private keys through keystore signing and xpub APIs. A descriptor-embedded private key, if imported, is direct |
| QR, USB, and SD adapters | Opaque bytes that may hold mnemonics, entropy, derived-key exports, blinding keys, transaction data, PSBTs and PSETs, descriptors, addresses, signatures, or backup files | They frame or transport these values. They do not obtain device-held private keys, seeds, PINs, or secure-element secrets |
| Host, QR payload, USB peer, SD card | None inside the device trust boundary | **Boundary:** may supply mnemonics, transaction data, PSBTs and PSETs, descriptors, backup files, and firmware updates. May receive entropy, derived keys including BIP-85, the Liquid master blinding key, addresses, signatures, and backup files through supported export flows |
| GUI and native display/touch stack | Mnemonics; derived keys including BIP-85; Liquid master blinding key; transaction data and confirmation metadata; descriptors; addresses; signatures and message-signature requests; PINs; backup file names and displayed backup content | No direct private-key, device-secret, or secure-element access was found. It authorizes mediated use by returning the user's confirmation |
| RAM, flash, and SD keystores | Private keys; seeds; mnemonics; entropy; derived keys including BIP-85; Liquid master blinding key; transaction data; PSBTs and PSETs passed for signing; signatures; PINs; device secrets; persistent storage; backup files | Descriptors and addresses are handled by callers using keystore-derived public keys. Firmware updates are outside this boundary |
| Smartcard keystore and JavaCard stack | Private and derived keys once the mnemonic is loaded into the inherited RAM keystore; seeds; mnemonics; entropy; blinding keys; transaction data; PSBTs and PSETs passed for signing; signatures; PINs; device and secure-element secrets; persistent storage; backup files | **Mediated:** card-resident secret-blob and PIN operations cross the secure-element channel |
| External smartcard and applet | Card identity and channel private keys; seed entropy in the card secret blob; PINs; secure-element secrets; card persistent storage; secure-channel signatures | **Boundary:** the mnemonic and spending keys are rebuilt on the MCU after blob retrieval. The reviewed host code never passes the card transaction data, PSBTs/PSETs, descriptors, addresses, backups, or firmware updates |
| RNG, platform, filesystem, storage glue | Entropy; device secrets; persistent storage; backup files | **Opaque transport:** mnemonics, PSBTs and PSETs, descriptors, and firmware updates can traverse file or device APIs without this layer interpreting them |
| `embit` | Private keys; seeds; mnemonics; entropy and BIP-85 entropy; derived keys; Liquid blinding keys; transaction data; PSBTs and PSETs; descriptors; addresses; signatures | No PIN, device-secret, secure-element, persistent-storage, backup, or firmware-update access is intrinsic to the library |
| secp256k1 binding and linked library | Private keys; entropy for nonce or context operations; derived EC keys and tweaks; Liquid blinding keys, generators, and proofs; signatures | It receives digests, not full transaction data, PSBTs/PSETs, descriptors, addresses, PINs, storage, backups, or firmware updates |
| Bootloader | Signatures used for firmware authorization; persistent internal-flash contents; firmware-update data | It has no designed access to wallet private keys, seeds, mnemonics, PINs, device or secure-element secrets, backups, PSBTs/PSETs, descriptors, or addresses |
| Production bootstrap, MicroPython, LVGL, FatFs, board/HAL, native runtime | Every runtime asset can be resident in interpreter memory, rendered by LVGL, or moved through native memory and file/device APIs | Access is path-dependent. No claim is made that every subcomponent sees every asset, only that this aggregate runtime boundary can host or transport all of them |
| Build, packaging, release, CI, manifests, bootloader tools | Firmware-update data and firmware signatures; selected frozen/generated source; build filesystem | **Build-time:** release private keys are reachable only when the optional local signing tool is given a private-key file. Normal documented assembly imports externally produced signatures |
| Frozen/generated source and release artifacts | Firmware-update data, embedded public verification keys, firmware signatures | **After installation:** executable artifacts inherit the access of the components they embed. No wallet secret is expected in an honest release artifact |
| Simulator code and adapters | Simulated private keys, seeds, mnemonics, entropy, derived keys, blinding keys, transaction data, PSBTs and PSETs, descriptors, addresses, signatures, PINs, simulated storage, backup files | **Simulator-only:** these are process values and files, not production-device assets. Firmware-update handling is not part of the reviewed simulator entry point |
| Tests and demo applications | Test or demo instances of the same asset classes | **Test/demo only:** no production-device access, and no access to a deployed secure-element secret |
| Host-side HWI and tooling | Transaction data; PSBTs; descriptors; addresses; signatures returned by the device | **Boundary:** requests derived public keys and message signatures. No normal interface gives it private keys, seeds, mnemonics, PINs, or device secrets |
| Remaining third-party trees | No uniform direct access can be assigned without production reachability | Unselected source has no production-device access. Linked code inherits only the assets its reachable callers pass it |

### 4.3 Trust-boundary map

1. **QR/USB/SD to MCU.** Transport content is attacker-controlled. QR and SD
   ingestion need user action. USB is off by default but becomes bidirectional
   after opt-in.
2. **Transport to parser.** All inputs converge on
   `Specter.process_host_request` at
   [src/specter.py:606-652](../../src/specter.py#L606-L652). Applications handle
   confirmation. There is no central authorization gate.
3. **Parser to display.** Wallet managers and `embit` turn hostile
   PSBT/PSET data into confirmation metadata.
4. **Display to key use.** A positive GUI result allows keystore and native
   secp256k1 signing.
5. **MCU to smartcard.** Replaceable hardware supplies identity, PIN state,
   counters, and stored secret material.
6. **Persistent storage.** Internal flash holds the device secret and PIN state.
   QSPI holds authenticated encrypted wallet and settings state. SD can hold
   backups and hostile input. SDRAM holds temporary processing files.
7. **Firmware update.** SD/FatFS content enters the bootloader's version,
   integrity, threshold-signature, and flash-write path.
8. **Build and release.** Source, gitlinks, toolchains, manifests, and key
   selection determine the final trust root and the firmware artifacts.

### 4.4 Hostile-input data-flow map

"Gate" records the normal application path. Boot-time, fault, and parser
findings that bypass or weaken a gate are listed in the final column.

| Hostile source | Entry and normal gate | Parser or dispatcher | Sensitive operation or asset | Security result |
| --- | --- | --- | --- | --- |
| QR scanner bytes | User starts scanning after unlock | `QRHost.scan` / `process_chunk` → legacy BCUR, `microur`, or normal multipart → `Specter.process_host_request` | PSBT/PSET signing, descriptor import, message requests, mnemonic-import fallback | F-03, F-04, F-16, F-28, H-08, H-13. Confirmation is operation-specific |
| Enabled USB VCP peer | USB is off by default and enabled from the unlocked main menu | `USBHost.update` writes a fixed RAM file → `Specter.process_host_request` | Every host command, signing, xpub/fingerprint, entropy, label, wallet metadata | F-03, F-04, F-05, F-14, F-21, F-23, F-30. Boot-failure behavior is assessed separately |
| SD-card directory and file bytes | User selects a top-level `.psbt`, `.txt`, or `.json` file after unlock | `SDHost` copies the file to a fixed RAM path → central dispatch | Signing, descriptor/backup import, mnemonic fallback. The bootloader consumes upgrade files independently | F-03, F-04. No application-level execution primitive. Native FatFs is a separate boundary |
| PSBT/PSET fields | Accepted host transport and signing request | `embit` scope/view parsers → wallet manager preprocessing | Wallet identification, input/output verification, fee and change display, sighash generation, signature | F-03, F-04, F-10, F-11, F-23, F-24, F-30 |
| Descriptor, wallet name, xpub, fingerprint, derivation, address | Host command or compatibility parser. Import and address screens confirm per operation | `Wallet.parse`, `Descriptor.from_string`, ownership helpers, xpub/message apps | Wallet policy, change ownership, displayed address, arbitrary derived public keys or signatures | F-04, F-05, H-19. The reviewed descriptor ownership path re-derives scripts |
| Message bytes and requested derivation | `signmessage` command after unlock and mnemonic load | Message parser → confirmation screen → keystore message signing | Recoverable signature at a host-selected path | F-17, F-21. PATH-05 blocks reuse as a transaction signature |
| Entropy and secret-export requests | Host app dispatch or a user-selected GUI app | `getrandom`, BIP85, xpub, blinding key, backup, and wallet-export flows | Raw TRNG bytes, derived entropy, xpubs, master blinding key, mnemonic/backup material | F-05, F-14, H-03, H-11, H-21. The command table in 4.5 defines each gate |
| Smartcard responses and faults | Device-initiated APDUs before and during unlock | JavaCard applet wrappers and `SecureChannel` | Card identity, PIN state and counters, protected seed blob, backend availability | F-07, F-22, F-34, H-10, H-14, H-23. Message replay is PATH-14 |
| QSPI and internal-flash settings and ciphertext | Read at setup, unlock, or app load | AEAD/HMAC loaders, plaintext label/network loader, keystore selection | Device secret, PIN verifier, encrypted mnemonic, wallet/settings state, active network | F-06, F-15, H-12, H-14 |
| Firmware-update sections and signatures | Bootloader finds a matching root-level SD filename at boot | Section/attribute parser → compatibility and version checks → flash copy and hash → threshold verification | Firmware and bootloader flash, integrity and version records, hardware protection state | F-08, F-17, F-25, F-33 |
| GUI touch and PIN input | Physical user interaction | LVGL input and screen results | PIN-derived keys, confirmation authorization, menu-selected secret display or export | F-19, F-21, F-24, H-05, H-06, H-21 |
| Source, dependency, build, and release inputs | Contributor, build, or release-key-holder access | Gitlinks, manifests, compiler/container, generators, packaging and signing tools | The entire executable image, the embedded trust root, release signatures | F-08, F-09, F-17, D-01 to D-03. Section 8 holds the provenance and malicious-maintainer analysis |

### 4.5 Host command and message surface

The gate vocabulary is: **PIN** means normal application startup completed
`unlock()`; **KEY** means a mnemonic or root is loaded; **CONF** means a
distinct on-device confirmation screen.

Under normal startup no host channel is active before PIN entry. QR and SD menu
entries are initialized after unlock. USB is initialized at the main menu and
stays disabled until explicit opt-in. Host update loops do not dispatch while
disabled ([src/specter.py:115-132](../../src/specter.py#L115-L132),
[src/specter.py:184-188](../../src/specter.py#L184-L188),
[src/specter.py:275-279](../../src/specter.py#L275-L279),
[src/hosts/core.py:111-113](../../src/hosts/core.py#L111-L113)).

| Command or message | Channel/application | Normal gate | Confirmation and effect |
| --- | --- | --- | --- |
| `sign <psbt-or-base64>`; bare PSBT/PSET magic; `cHNi`/`cHNl`; decoded `UR:BYTES` signing payload | Wallet app over QR, enabled USB, or a selected SD file | PIN + KEY | Sighash, already-signed, wallet, and `TransactionScreen` prompts. F-03, F-04, F-30 |
| `addwallet <name>&<descriptor>` or a bare descriptor | Wallet/compatibility app | PIN + KEY | `ConfirmWalletScreen`. Persists wallet policy |
| `showaddr <type> <path> [redeem]` or `bitcoin:<address>?index=N` | Wallet app | PIN + KEY | Blocking `WalletScreen`. Verifies and displays an address |
| `listwallets` | Wallet app | PIN + KEY | No per-request confirmation. Exports public wallet metadata |
| `addasset <asset-id> <label>` | Liquid wallet app | PIN + KEY + Liquid network | Confirms a host-selected asset label. F-23 |
| `dumpassets` | Liquid wallet app | PIN + KEY | No per-request confirmation. Exports registry metadata |
| `xpub <path>` | Xpub app | PIN + KEY | No per-request confirmation. Arbitrary parsed path. F-05 |
| `fingerprint` | Xpub app | PIN + KEY | No per-request confirmation. F-05 |
| `signmessage <path> ascii:<message>` or `base64:<message>` | Message-signing app | PIN + KEY | Message and path confirmation. F-17, F-21 |
| `getrandom [length]` | Randomness app | PIN + KEY | No confirmation. Length 1-1000. F-14 |
| `getlabel` | Label app | PIN + KEY | No confirmation. Returns the device label |
| `setlabel <text>` | Label app | PIN + KEY | Explicit confirmation before persistence |
| `slip77` | Blinding-key app | PIN + KEY | Explicit warning and confirmation on the host path. Exports the master blinding private key |
| `bip39: <mnemonic>` | Backup/import app | PIN | Explicit mnemonic-import confirmation |
| Coldcard JSON or text compatibility records | Compatibility app | PIN + KEY | Converted to `addwallet` and gets its confirmation |
| Any unmatched 16-32-byte or mnemonic-like stream | Root fallback | PIN | `MnemonicPrompt` offers seed substitution. See Section 8 |
| Internal `set_mnemonic <mnemonic>` | Cross-application message, not a host command | PIN + KEY | The root application confirms before replacing the seed |

Smartcard messages are device-initiated rather than host commands. The plaintext
APDUs are `SELECT`, `GET_PUBKEY`, `OPEN_EE`, `OPEN_SE`, `SECURE_MSG`, and
`CLOSE`. The secure channel carries `ECHO`, `SECURE_RANDOM`, `PIN_STATUS`,
`UNLOCK`, `LOCK`, `CHANGE_PIN`, `SET_PIN`, `GET_SECRET`, and `SET_SECRET`
([applet.py](../../src/keystore/javacard/applets/applet.py),
[securechannel.py](../../src/keystore/javacard/applets/securechannel.py),
[secureapplet.py](../../src/keystore/javacard/applets/secureapplet.py),
[memorycard.py](../../src/keystore/javacard/applets/memorycard.py)).

### 4.6 Secret-lifetime matrix

"Destroy" describes explicit software action. It is not a claim that garbage
collection or power loss erased physical memory.

| Value | Create or import | Copy or transform | Persistent storage | Display, serialize, export | Cache and destruction |
| --- | --- | --- | --- | --- | --- |
| BIP-39 mnemonic | `helpers.gen_mnemonic`, or explicit and fallback import flows | Normalized into `RAMKeyStore.mnemonic`. Converted to a seed, and to entropy bytes for smartcard storage | AEAD-encrypted under `enc_secret` in flash or SD; smartcard secret blob; optional plaintext SD backup | Mnemonic and backup screens, QR export | Keystore attribute. No deterministic zeroization. Lock does not prove physical erasure |
| BIP-39 seed | `bip39.mnemonic_to_seed(mnemonic, passphrase)` | Immediately derives the root and the SLIP77 master | No designed persistent seed file | No direct export found | GC-managed local. No explicit wipe |
| Root and derived private keys | `HDKey.from_seed`; child derivation for sign, xpub, and BIP85 | Root derives identity, wallet, signing, and exported child material | The root is rebuilt after unlock rather than serialized as a raw xprv | The root is not exported. Derived BIP85 xprv/WIF may be deliberately displayed | `RAMKeyStore.root` and child objects are GC-managed. No explicit wipe |
| Identity key | Hardened child of the root | Default AEAD/HMAC key material | Not directly persisted | No direct export found | Keystore attribute. No explicit wipe |
| SLIP77 master and output blinding keys | Derived from the seed; output keys derive from scripts | Used to rewind and build Liquid commitments and descriptors | May be embedded in an encrypted persisted Liquid descriptor | A dedicated WIF/QR screen and wallet export deliberately disclose the master key | Keystore attribute and derived objects. No explicit wipe |
| Device secret | 32 random bytes generated when missing | Derives user, settings, PIN, smartcard, and SD identifiers and keys | Plaintext internal-flash file | No normal export found | `self.secret` and its derived cache. Erased only by platform wipe, not by ordinary lock |
| User PIN and verifier | Touchscreen input | HMAC verifier, `pin_secret`, or card-side SHA-256 command value | HMAC verifier in authenticated PIN state. The card tracks its own state | Password-mode input only | Python strings and a verifier attribute. No zeroization |
| `pin_secret` and `enc_secret` | Derived from the device secret plus PIN; a random data key | `pin_secret` wraps `enc_secret`; `enc_secret` encrypts mnemonic backups and storage | The wrapped `enc_secret` persists. `pin_secret` does not | No display or export | Keystore attributes. No explicit wipe |
| Entropy pool and raw TRNG output | A public constant initial pool plus TRNG and touch feeds | SHA-512 state update. Requests above 64 bytes return raw TRNG output | Not designed to persist | `getrandom` exports up to 1000 bytes. BIP85 exports derived entropy | Module-global pool. No reset and no health state |
| Secure-channel session material | Ephemeral ECDH plus a card nonce derive directional AES and MAC keys | AES-CBC and truncated-HMAC channel state with a counter | Not designed to persist | Not exposed by any normal UI or host command | Channel attributes. Close clears card key state but does not zero every derived key |
| ECDSA and Schnorr nonces | Deterministic native signing, or the auxiliary-randomness path | Used only inside native signing | Not persisted | Never intentionally serialized | Native lifetime. No Python-level wipe |
| Liquid blinders and proof nonces | Deterministic `txseed` derivation and host/PSET values | Written to scopes and consumed by proof and commitment code | Temporary filled PSET in the SDRAM ramdisk | Returned in the signed PSET, as the protocol requires | Python objects and temp files. Best-effort cleanup on the next command |
| PSBT/PSET and transaction buffers | Host stream copied into fixed temporary files | Parsed into scopes, metadata, sighashes, filled and signed files, QR fragments | SDRAM ramdisk during processing. Optional selected SD source or output | Signed container returned over QR, USB, or SD | Best-effort tempdir and transport cleanup. Immutable parser objects and stale SDRAM remnants are not wiped |
| Backup material | Mnemonic or encrypted keystore serialization | AEAD encryption, filename construction, QR or SD formatting | User-selected SD files, including optional plaintext mnemonic export | Displayed or written only in user-invoked backup flows | Python buffers and FAT metadata. Deletion does not scrub directory entries or RAM copies |
## 5. Coverage

Each row uses one review depth: Shallow, Moderate, or Deep. A component is split
into several rows when different parts reached different depth. "Files inspected"
records what was actually read, not the wider directory that owns it.

| Component | Tier | Files/directories inspected | Security relevance | Depth | Evidence produced | Open questions | Recommended dynamic tests |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| Application core and dispatcher | 1 | `src/specter.py`, `src/main.py`, `src/helpers.py`, every module under `src/apps/` | Routes all host requests, confirmations, signing, secret exports, and keystore selection | Deep | Host convergence, absence of a central authorization gate, per-application confirmation inventory, mnemonic-import fallback | Lower parser, GUI, runtime, and hardware layers are separate rows | Regression-test every host prefix against its expected confirmation and privilege boundary |
| Bitcoin wallet and signing application | 1 | `src/apps/wallets/manager.py`, `src/apps/wallets/wallet.py`, Bitcoin signing and display paths | Turns hostile PSBT data into wallet ownership, display metadata, confirmation, and signatures | Deep | F-03, F-04, F-24, F-30, and the reviewed descriptor ownership path | Advanced Miniscript/TapTree policies and unread embit internals are separate rows | Reproduce F-03, F-04 and F-30 on target. Compare displayed metadata with the exact sighash source |
| Liquid wallet and signing application | 1 | Liquid manager input/output metadata, asset registry, host commands, display paths, native proof call sites | Turns hostile PSET data and asset metadata into Liquid display and signatures | Moderate | F-11, F-23, F-30, F-31, H-03, and Bitcoin/Liquid manager separation | Issuance, reissuance, and the remaining PSET internals | Exercise mismatched commitments, issuance fields, asset labels, all Liquid sighash modes, and F-31 on target |
| Application USB and SD adapters | 1 | `src/hosts/usb.py`, `src/hosts/sd.py`, central dispatch in `src/specter.py` | First firmware handlers for hostile USB lines and selected SD files | Deep | F-05 reachability, no application-level execution primitive, fixed RAM-file dispatch | FatFs, mount behavior, and native USB/SD drivers are separate rows | Fuzz filenames, file contents, framing, interruption, and oversized input on target |
| Application QR and multipart decoders | 1 | The whole `src/hosts/qr.py` state machine, legacy BCUR dispatch, and the whole `f469-disco/libs/common/microur/` decoder | Reassembles attacker-controlled frames before privileged dispatch | Deep | F-16, F-28, H-08, H-13, and a state-machine inventory | External scanner firmware and target transport timing | Fuzz mixed streams, indexes, counts, checksums, bytewords, oversized sequences, discarded CBOR lengths, and scanner timing |
| Native filesystem and transport layer | 2 | Python-facing platform calls only; selected build configuration | FatFs, mount, QSPI, SD, and USB code process hostile media below Python | Shallow | Boundary identified. No native memory-safety conclusion | FatFs parser, mount handling, QSPI behavior, native SD/USB drivers, DMA and interrupt paths | Target fuzzing with malformed filesystems, descriptors, transfer lengths, removal, and reset |
| Transaction and message GUI | 1 | `src/gui/screens/transaction.py`, page/button layout, warning, xpub, descriptor, and message-confirmation paths | Trusted display and final human authorization boundary | Moderate | F-19, F-21, F-24, H-05, H-06 | Exact LVGL rendering and input timing on target | Photograph and instrument long or malformed messages and 3/10/50-output transactions. Test NUL, bidi, scrolling, and confirmation timing |
| PIN, popup, and QR GUI paths | 1 | `src/gui/async_gui.py`, `screens/input.py`, `components/qrcode.py`, screen/decorator event paths, relevant LVGL input code | PIN entry, screen replacement, QR rendering, and input state can authorize or expose secret use | Deep | H-04, H-18, H-19, and bounded background-screen callback liveness | Touch-controller behavior below LVGL and physical RAM remnants | Test controller-level event injection, PIN rendering and clearing, and secret QR output in every production and debug terminal configuration |
| RAM, flash, and SD keystores | 1 | `src/keystore/ram.py`, `flash.py`, `sdcard.py`, selection and backup paths | Holds roots, mnemonics, the device secret, PIN-derived material, backups, and signing capability | Deep | F-06, H-11, H-14, and no deterministic secret zeroization | RAM/SDRAM remnants, physical flash readout, rollback, fault injection, side channels | Induce read/write failures. Measure remnants. Test rollback, deletion recovery, PIN timing, and RDP bypass |
| Smartcard keystore and channel stack | 1 | `src/keystore/memorycard.py`, the whole JavaCard host stack, native `usermods/scard` UART/connection/T=1 receive paths | Delegates identity, PIN state, counters, protected seed storage, and native framing across an external boundary | Deep | F-07, F-22, F-34, H-10, H-14, H-23, replay defenses, and bounded T=1 buffers except F-34 | External applet source, real-card PIN enforcement, interposition, exact F-34 stack effect | Emulate unlocked and substituted cards. Fuzz ATR/T=1 timing, PPS, replay, errors, counter rollback, removal, and malicious blobs |
| External smartcard applet | 1 | No card-side source is present. Only the host protocol and the observed contract were inspectable | Card-resident identity, PIN attempt counter, channel keys, and secret release are security-critical | Shallow | Repository-boundary gap recorded | Whether deployed applet behavior matches any reviewable source | Obtain and audit the applet source. Verify build and provenance. Run card substitution and fault tests |
| Entropy and randomness path | 1 | `src/rng.py`, `src/helpers.py`, STM32 `rng_get`, the `os.urandom` path, signing nonce call sites | Generates mnemonic entropy and supplies cryptographic random material | Moderate | F-14, F-18, and a verified deterministic RFC6979 path | Real TRNG fault frequency, source health, touch entropy, side channels | Inject stuck, zero, and error TRNG states and check fail-closed seed generation. Measure the touch contribution |
| `embit` PSBT/PSET signing core | 1 | `psbt.py`, `psbtview.py`, the relevant sighash and `sign_input` paths, upstream delta | Parses hostile signing containers and picks the exact transaction digest | Deep | F-03, F-04, F-10, F-11, and the v0/v2 scope-field version guard (PATH-41) | Target MicroPython behavior and the unreviewed parser families below | Differentially fuzz scope and global data, declared lengths, duplicates, versions, and field order |
| `embit` address construction and encoding | 1 | `script.py`, `base58.py`, `bech32.py`, `networks.py`, `liquid/blech32.py`, `liquid/addresses.py`, `liquid/networks.py` in full; address call sites in `src/apps/` and `src/gui/screens/transaction.py` | Determines whether the address the user approves matches the scriptPubKey that is signed | Deep | F-35, F-36, H-25, H-26, PATH-34 to PATH-40, and the full BIP-173/350 vector set executed against `bech32.py` | Taproot output-key tweaking and Miniscript/TapTree construction feed this layer and are covered in the row below | Run the BIP-350 vector set and a Liquid script-type matrix (OP_RETURN, bare multisig, non-standard leading bytes, non-v0 witness versions) as on-target regressions |
| `embit` descriptor, policy, and derived-secret internals | 1 | Selected `descriptor.py`, ownership, derivation, and BIP32 depth paths | Determines multisig policy, derivation, BIP85, and SLIP77 behavior | Shallow | The reviewed ownership path, and the H-15 path-depth item | `transaction.py`, `bip85.py`, `slip77.py`, full Miniscript and TapTree behavior | Malformed descriptors and scripts, deep recursion, derived-secret isolation tests |
| secp256k1 core binding call paths | 1 | `mpy/libsecp256k1.c` in full; `libsecp256k1-config.h`, `ext_callbacks.c`, `secp256k1_build.c`, `micropython.mk` | Native boundary handling private keys, signatures, points, and fixed-size attacker data | Deep | F-13 reachability, F-14, H-01, H-09, H-17, PATH-04, PATH-20 | Fault and side-channel behavior. Timing distinguishability of secret-dependent proof failures | Enforce the context-size bound. Force GC exhaustion against each allocation path. Fuzz fixed-size arguments and time secret-dependent failures |
| secp256k1 proof and extended binding paths | 1 | `mpy/config/rangeproof_preallocated/` in full; all rangeproof, surjectionproof, generator, Pedersen, Schnorr, and preallocated entry points; direct Liquid call sites | Proof code accepts hostile native inputs | Deep | F-31, H-16, H-17, PATH-20, PATH-21, verified arena ordering and rewind-message bounds | SDRAM contents above `0xC03EE000`, FMC aliasing, and upstream borromean/surjection/generator internals assumed correct | Execute F-31 with a short proof field. Verify H-16 with the project compiler. Fuzz proof offsets, lengths, generators, and allocation failure |
| Bootloader signature authorization | 1 | Signature threshold and counting loop, key sets, build guard, signed-message construction, host signing tools | Establishes the firmware root of trust at upgrade time | Deep | F-08, F-17, and verified duplicate, known-key, threshold, and return-code handling | Deployed key configuration and release-key operation. The surrounding pre-auth erase/write sequence is F-33 | Mutate signer order, duplicates, unknown and bad signatures, image bytes, and configured key sets |
| Bootloader persistence, downgrade, and recovery | 1 | `bootloader.c`, `bl_section.c`, `bl_integrity_check.c`, `bl_kats.c`, `bl_util.c`, `startup_mailbox.c`, `startup.c`, flash and option-byte `bl_syscalls.c`, linker maps, platform Makefiles, tools | Controls rollback, boot-time integrity, recovery, flash selection, and hardware protection state | Deep | F-25, F-33, H-20, PATH-23 to PATH-29 | Hardware confirmation of option-byte state, power-cut timing, forged-record behavior | Fuzz records and mailbox. Power-cut each erase step. Attempt downgrade and record replacement. Read option bytes before and after a rejected upgrade |
| Production runtime and platform glue | 2 | `boot/main/`, mount/CWD/import resolution, storage partitioning, wipe, RNG, native smartcard transport and T=1, manifest and freeze selection, board and build configuration | MicroPython, HAL, storage, display, USB, and native user modules run inside the trusted boundary | Moderate | F-15, F-18, F-32, F-34, H-22 to H-24, and exact-number, import, and storage behavior | Full FatFs, STM32 HAL/USB/SDMMC memory safety, general interpreter content, hardware timing and remanence | Exercise boot faults, QSPI implants, wipe recovery, malicious smartcards, malformed filesystems and USB, reset, and memory remnants |
| Build, packaging, release, and CI | 2 | `Dockerfile`, `build_firmware.sh`, root and bootloader Makefiles, packaging tools, manifests, Nix and shell definitions, workflows | Selects source, toolchain, trust roots, signatures, and released artifacts | Deep | F-08, F-09, and static deterministic-build evidence | Official release provenance and empirical reproducibility | Run two clean cross-machine builds, import published signatures, and compare every release artifact hash |
| Frozen/generated source and release artifacts | 2 | Manifest and generator inputs. The checked-in secp256k1 table was recomputed | Generated executable code and opaque release images can diverge from reviewed source | Moderate | All 1024 generator table entries matched. Deterministic inputs identified | No official release binary was obtained or compared | Recompute generated files during the build and compare clean builds with the official signed binaries |
| Project security and build documentation | 2 | `docs/security-info.md` in full, build and reproducibility docs, bootloader docs | Defines the user-facing threat model and the release/security claims | Moderate | The claim-by-claim security-model differential in Section 8.10, including DOC-01 and DOC-02 | Some hardware claims are not statically attestable | Validate deployed option bytes, scanner firmware, and the published release procedure against hardware and artifacts |
| Dependency provenance | 2 | Recursive gitlinks, declared origins, upstream resolution, embit per-file hashes, the LVGL relation, generator-table construction | Detects substitution, mutable pins, unexplained forks, and opaque signing-path constants | Deep | All gitlinks resolve. embit and the generator table match. The LVGL relation is resolved. D-01 divergence measured | Official artifact provenance | Repeat provenance and generated-table checks automatically in CI |
| Dependency content and known-issue exposure | 2 | All 63 MicroPython fork-only commits; the whole native secp binding and custom proof module; selected LVGL, FatFs, embit, microur, smartcard, storage, and build dependencies | Dependencies run in-process with keys or parse hostile data | Moderate | D-01 to D-03, F-31, F-34, H-16, H-17, H-22, H-23 | Flattened HAL/FatFs/USB trees lack upstream SHAs. Systematic upstream-advisory and backport review is incomplete | Restore provenance. Review advisories and backports. Fuzz native dependency boundaries on target |
| Simulator | 2 | `simulate.py`, simulator manifest, platform, and GUI entry points, production-selection checks | Replaces entropy, storage, hardware, transport, and physical confirmation, and can mislead assurance | Moderate | The simulator is excluded from the production freeze path. Target-only H-16 ABI behavior identified | Full security-regression parity and target equivalence | Run every portable regression vector in the simulator, then repeat hardware-dependent results on target |
| HWI, tests, and demo applications | 2 | Production manifest separation only | Host tooling builds hostile requests. Tests and demos affect assurance and may enter development builds | Shallow | Not found in production signing paths | `hwidevice.py`, `test/`, and `demo_apps/` were not read | Measure coverage of every finding and confirm that no demo or test module enters a release manifest |

No named Tier 1 top-level area is completely untouched. That does not mean full
coverage: several security-critical subsystems were reviewed only shallowly, or
not at all. The limits in Sections 9, 10, and 13.3 are part of the security
result.

## 6. Findings

Findings are ordered by severity: High, then Medium and Low. Within a severity
level they are ordered by identifier. Identifiers are stable handles and are not
contiguous.

Each finding starts with a classification block, then evidence, an attack trace,
why existing checks do not stop it, and a recommended fix with a concrete action
plan.

---

### F-03: Input verification failures are discarded

**Status:** Confirmed · **Severity:** High · **Confidence:** High

- **Affected component:** Bitcoin previous-transaction verification, fee
  display, and SegWit signing.
- **Files and code regions:**
  [manager.py:648-699](../../src/apps/wallets/manager.py#L648-L699), in
  particular [manager.py:653-655](../../src/apps/wallets/manager.py#L653-L655);
  [psbt.py:271-299](../../f469-disco/libs/common/embit/src/embit/psbt.py#L271-L299).
- **Functions and modules:** Wallet-manager PSBT preprocessing,
  `InputScope.verify`.
- **Attacker capability:** Supply a multi-input SegWit PSBT and cause more than
  one signing attempt.
- **Prerequisites:** Inputs controlled by the victim, and user approval of each
  displayed attempt.
- **Default reachability:** Every Bitcoin signing flow that accepts missing
  previous transactions.
- **Impact on funds:** Individually valid signatures can be combined into a
  transaction that pays an arbitrarily large miner fee.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Every input amount that contributes to the
  displayed fee must be authenticated before signing.
- **Owning codebase:** This repository and `embit`.

**Evidence**

The manager calls `inp.verify(ignore_missing=True)` and ignores its return
value. Missing `non_witness_utxo` data returns `False`, and
`InputScope.is_verified` is never enforced or shown to the user. This conflicts
with the adjacent `embit` warning that hardware wallets must verify previous
transactions to prevent the SegWit miner-fee attack.

`is_verified` has **zero** references anywhere in `src/`, so the API `embit`
provides for exactly this purpose is never consulted.

**Attack trace**

BIP143 commits to the amount of the input being signed, not to every input's
amount. For a two-input transaction an attacker can:

1. present input A honestly and understate B, getting a valid signature for A
   while the displayed fee stays small;
2. present B honestly and understate A, getting a valid signature for B;
3. combine both signatures with the real input amounts.

Each signature is valid for its own honestly priced input, and both commit to
the same prevouts, sequences, and outputs.

Two things make this easier than a first reading suggests:

- The per-input values that would expose the lie are drawn **only on the details
  page** of `TransactionScreen`, and that page is hidden by default unless a
  custom sighash, an unknown Liquid value, or an issuance is present
  ([transaction.py:16-27](../../src/gui/screens/transaction.py#L16-L27)). A user
  following the default flow never sees the amount that was lied about.
- There is **no compensating fee control at all** — no absolute threshold, no
  sat/vB rate, no percentage warning — and `meta["warnings"]` is never populated
  on the Bitcoin path. See F-24.

**Why existing checks do not prevent it**

Committing to the amount of the currently signed input does not authenticate the
other inputs whose false amounts drive the fee display.

**Code at this tree**

[manager.py:654](../../src/apps/wallets/manager.py#L654):

```python
# verify, do not require non_witness_utxo if witness_utxo is set
inp.verify(ignore_missing=True)
```

The return value is discarded. `grep -rn "is_verified" src/` returns **zero**
hits, so the `embit` API built for exactly this purpose is never consulted, even
though `InputScope.verify` sets `self._verified` at
[psbt.py:297-299](../../f469-disco/libs/common/embit/src/embit/psbt.py#L297-L299).
The Liquid manager makes the identical call at
[liquid/manager.py:294](../../src/apps/wallets/liquid/manager.py#L294).
Per-input values are drawn only on `page2`
([transaction.py:87-112](../../src/gui/screens/transaction.py#L87-L112)), and
`meta["warnings"]` is never populated on the Bitcoin path.

**Recommended fix**

Treat `verify()` returning `False` as fatal. If support for unverified amounts
must stay, show an unavoidable per-input warning and never present a computed
fee as verified. Add the F-24 fee sanity check as defense in depth.

**Action plan**

1. In [manager.py:648-699](../../src/apps/wallets/manager.py#L648-L699), capture
   and act on the result:

   ```python
   verified = inp.verify(ignore_missing=True)
   if not verified:
       metainp["warning"] = "Input amount is NOT verified - previous transaction missing!"
       meta.setdefault("warnings", []).append(
           "Input %d amount is unverified. The displayed fee may be wrong." % i
       )
       unverified_inputs += 1
   ```
2. Set `meta["fee_verified"] = (unverified_inputs == 0)` and have
   [transaction.py:68-79](../../src/gui/screens/transaction.py#L68-L79) render
   `Fee: ~N satoshi (UNVERIFIED)` in `style_warning` when it is False.
3. Preferred, if no wallet depends on unverified amounts: make it fatal —
   `raise WalletError("Missing non_witness_utxo for input %d" % i)`.
4. Add the F-24 fee sanity check as the compensating control.

---

### F-04: Derived keys are signed without the root-key script-membership check

**Status:** Confirmed · **Severity:** High · **Confidence:** High for the defect
and its reachability; Medium for a completed theft chain, which depends on what
else the target key signs.

- **Affected component:** PSBT key derivation and input signing.
- **Files and code regions:**
  [psbtview.py:787-824](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L787-L824),
  [psbtview.py:854-871](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L854-L871);
  [manager.py:373-386](../../src/apps/wallets/manager.py#L373-L386),
  [manager.py:785-792](../../src/apps/wallets/manager.py#L785-L792);
  [ram.py:77-78](../../src/keystore/ram.py#L77-L78).
- **Functions and modules:** `PSBTView.sign_input`, wallet-manager signing,
  `RAMKeyStore.sign_input`.
- **Attacker capability:** Know a device xpub and supply matching BIP32
  derivation metadata in a PSBT.
- **Prerequisites:** The device is unlocked, and the hostile PSBT is accepted
  after the generic "Unknown wallet in inputs!" warning.
- **Default reachability:** Every PSBT input is passed to keystore signing, even
  when no wallet resolves.
- **Impact on funds:** A host that knows any device xpub can get an ECDSA
  signature, under a key at **any host-chosen derivation path**, over the sighash
  of a transaction the host fully builds. The host does not need to own a UTXO;
  the input can be fabricated. This is a signing oracle, not just a missing
  check.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** A derived private key must sign only when its
  public key is authorized by the input script or by an explicit wallet policy.
- **Owning codebase:** `embit` plus this repository.

**Evidence**

The root-key branch enforces membership
([psbtview.py:857-862](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L857-L862)):

```python
# check if root is included in the script
if sec in sc.data or pkh in sc.data:
    sig = root.sign(h)
```

The derived-key loop immediately below has no equivalent test
([psbtview.py:863-867](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L863-L867)):

```python
for prv, pub in derived_keypairs:
    sig = prv.sign(h)
    inp.partial_sigs[pub] = sig.serialize() + bytes([inp_sighash])
    counter += 1
```

The only gates on `derived_keypairs`
([psbtview.py:787-824](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L787-L824))
are a matching 4-byte device fingerprint, which is host-supplied, and
`hdkey.xonly() == pub.xonly()`, which the attacker satisfies by computing `pub`
themselves from a known xpub for the path they chose.
[ram.py:77-78](../../src/keystore/ram.py#L77-L78) passes `self.root`, the master
key, so the path is unconstrained.
[manager.py:792](../../src/apps/wallets/manager.py#L792) calls
`keystore.sign_input` for every input, whether or not a wallet resolved.

The guard also compares **x-only** keys:

```python
if hdkey.xonly() != pub.xonly():
    raise PSBTError("Derivation path doesn't look right")
```

That comparison is used even for non-Taproot inputs, where the parity byte
matters. A supplied `pub` with the opposite parity still passes, and the
signature is then filed under the attacker's `pub` in `partial_sigs`. No key
material leaks, because the signature is made with the correctly derived private
key, but it is a second instance of the same laxity in the same function.
`sec()` equality is the correct comparison.

**Attack trace**

Supply derivation metadata matching a known xpub for an arbitrary path, and
approve an unknown-wallet transaction with a fabricated input.

**Why existing checks do not prevent it**

The transaction screen *is* shown. The problem is what it shows: a transaction
spending inputs the user does not own, after the generic "Unknown wallet in
inputs!" prompt. The natural reading is "this is not my money, approving is
harmless". It is not. Approving yields a signature from the user's key at a path
the attacker picked. Fingerprint and x-only checks prove derivability, not
authorization by the input script. F-05 supplies the xpub that makes the
derivation records constructible, and F-19 governs whether the surrounding
warnings are on screen at all.

**Code at this tree**

[psbtview.py:857-867](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L857-L867):

```python
# check if root is included in the script
if sec in sc.data or pkh in sc.data:
    sig = root.sign(h)
    inp.partial_sigs[rootpub] = sig.serialize() + bytes([inp_sighash])
    counter += 1
for prv, pub in derived_keypairs:          # <-- no equivalent test
    sig = prv.sign(h)
    inp.partial_sigs[pub] = sig.serialize() + bytes([inp_sighash])
    counter += 1
```

`derived_keypairs` is an `OrderedDict` for determinism, which does not
constrain membership. The x-only comparison is at
[psbtview.py:820-821](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L820-L821).
[ram.py:77-78](../../src/keystore/ram.py#L77-L78) passes `self.root`, and
[manager.py:786](../../src/apps/wallets/manager.py#L786) calls
`self.keystore.sign_input(...)` for every input regardless of whether a wallet
resolved.

**Recommended fix**

Apply the same public-key or public-key-hash membership test to every derived
key. Do not call keystore signing for an input unless a known wallet or an
explicitly supported standalone script policy resolved. Compare full SEC keys,
not x-only keys, outside Taproot.

**Action plan**

1. In `PSBTView.sign_input`, gate the derived loop the same way as the root:

   ```python
   for prv, pub in derived_keypairs:
       psec = pub.sec()
       ppkh = hashes.hash160(psec)
       if psec not in sc.data and ppkh not in sc.data:
           continue
       sig = prv.sign(h)
       inp.partial_sigs[pub] = sig.serialize() + bytes([inp_sighash])
       counter += 1
   ```
2. Replace the x-only comparison with a full SEC comparison outside Taproot:

   ```python
   if inp.is_taproot:
       ok = hdkey.xonly() == pub.xonly()
   else:
       ok = hdkey.sec() == pub.sec()
   if not ok:
       raise PSBTError("Derivation path doesn't look right")
   ```
3. In [manager.py:779-786](../../src/apps/wallets/manager.py#L779-L786), skip
   `keystore.sign_input` when no wallet resolved for that input, rather than
   relying on the generic "Unknown wallet in inputs!" prompt.
4. This is an upstream `embit` defect reproduced verbatim. Route items 1 and 2
   through coordinated disclosure to the `embit` maintainers; item 3 is ours.

---

### F-06: Flash-backed PIN protection allows one-HMAC-per-guess offline brute force

**Status:** Design limitation · **Severity:** High · **Confidence:** High,
conditional on internal-flash read access.

- **Affected component:** `FlashKeyStore` and `SDKeyStore` persistence.
- **Files and code regions:**
  [flash.py:109-150](../../src/keystore/flash.py#L109-L150),
  [flash.py:157-188](../../src/keystore/flash.py#L157-L188),
  [flash.py:238-243](../../src/keystore/flash.py#L238-L243);
  [ram.py:130-163](../../src/keystore/ram.py#L130-L163);
  [sdcard.py:86-87](../../src/keystore/sdcard.py#L86-L87),
  [sdcard.py:124](../../src/keystore/sdcard.py#L124);
  [input.py:208-300](../../src/gui/screens/input.py#L208-L300).
- **Functions and modules:** `FlashKeyStore`, `SDKeyStore`, PIN setup and
  unlock paths.
- **Attacker capability:** Read internal flash.
- **Prerequisites:** An RDP1 bypass, an installation without the secure
  bootloader, or equivalent physical read access.
- **Default reachability:** Applies to mnemonics stored by `FlashKeyStore` or
  `SDKeyStore`.
- **Impact on funds:** Offline PIN recovery decrypts the stored mnemonic.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic per PIN guess.
- **Security property violated:** Stored seed confidentiality must resist
  offline PIN guessing after media readout.
- **Owning codebase:** This repository.

**Evidence**

- The 32-byte device secret is stored in cleartext in `/flash/keystore/secret`.
- The PIN verifier is one `HMAC-SHA256(tagged_hash("pin", secret), pin)` per
  guess.
- `pin_secret = tagged_hash("pin", secret + pin)` unwraps `enc_secret`, which
  then decrypts the persisted mnemonic.
- There is no memory-hard KDF and no enforced minimum PIN length.
- The attempt counter sits in the same flash trust domain, so it cannot
  constrain an offline attacker. It can also be forged or rolled back after read
  and write access.
- The bootloader configuration uses RDP1 rather than RDP2.

`docs/security-info.md` states the correct version of this twice and an
incorrect version once, claiming that the HMAC prevents offline brute force from
flash contents. It does not, because the key to that HMAC is itself flash
contents. See DOC-01.

Authenticated QSPI wallet and settings blobs hold no monotonic counter. An
attacker with QSPI access can replay a valid older blob and suppress gap-limit
warnings. That does not forge wallet ownership and does not recover the seed. A
separate fail-closed path wipes on flash-write failure during unlock; its
behavior under hardware faults is untested.

**Attack trace**

Dump flash. Read the device secret and the verifier. Brute-force the numeric PIN
offline. Derive `pin_secret`, decrypt `enc_secret`, then decrypt the mnemonic
blob.

**Why existing checks do not prevent it**

The attempt counter shares the readable-flash trust domain, and the PIN
derivation is not memory-hard.

**Code at this tree**

[flash.py:126-128](../../src/keystore/flash.py#L126-L128):

```python
key = tagged_hash("pin", self.secret)
pin_hmac = hmac.new(key=key, msg=pin.encode(), digestmod="sha256").digest()
```

[flash.py:139](../../src/keystore/flash.py#L139) derives
`pin_secret = tagged_hash("pin", self.secret + pin.encode())`. The device secret
is read in cleartext from `/flash/keystore/secret` at
[ram.py:130-138](../../src/keystore/ram.py#L130-L138). There is no memory-hard
KDF and no minimum PIN length, and RDP2 is compiled out in the bootloader —
see F-08.

**Recommended fix**

Use a memory-hard PIN KDF. Enforce a minimum PIN length. Bind rollback-sensitive
state to a protected monotonic value where the hardware allows it. Provide a
production configuration with stronger hardware-backed readout protection.

**Action plan**

1. Replace the single HMAC with a memory-hard KDF. MicroPython on this board has
   no scrypt/argon2, so the practical option is a PBKDF2-SHA256 wrapper with a
   high, tuned iteration count plus a stored per-device salt:

   ```python
   # flash.py
   PIN_KDF_ITERS = 200_000   # tune against the F469 budget, target ~1s
   def _pin_kdf(self, pin: str) -> bytes:
       return hashlib.pbkdf2_hmac("sha256", pin.encode(),
                                  tagged_hash("pin-salt", self.secret),
                                  self.PIN_KDF_ITERS, 32)
   ```

   Use it for both `self.pin` (verifier) and `self.pin_secret`. Version the
   on-flash record so existing devices migrate on next successful unlock.
2. Enforce a minimum PIN length in
   [input.py:208-300](../../src/gui/screens/input.py#L208-L300) — the PIN screen
   currently imposes none.
3. Keep the RDP1 limitation documented next to the storage guarantees in
   [docs/security-info.md](../../docs/security-info.md). It already covers this
   at [security-info.md:139-148](../../docs/security-info.md#L139-L148), but a
   later bullet in the same document contradicts it — see DOC-01.

---

### F-17: Firmware authorization and user message signing share one signing domain

**Status:** Design limitation · **Severity:** High · **Confidence:** High

- **Affected component:** Bootloader signature verification and the
  message-signing app.
- **Files and code regions:**
  [bl_signature.c:22-25](../../bootloader/core/bl_signature.c#L22-L25),
  [bl_signature.c:146-158](../../bootloader/core/bl_signature.c#L146-L158);
  [bl_section.c:391-434](../../bootloader/core/bl_section.c#L391-L434);
  [bootloader-spec.md:176-210](../../bootloader/doc/bootloader-spec.md#L176-L210);
  [signmessage.py:94-105](../../src/apps/signmessage/signmessage.py#L94-L105).
- **Functions and modules:** Bootloader signature hashing and verification,
  `blsect_make_signature_message`, `MessageApp.sign_message`.
- **Attacker capability:** Reach a release-key holder's device with a chosen
  message, over an enabled USB VCP or a QR the holder scans.
- **Prerequisites:** The key holder signs the message. Two of the four release
  keys must be obtained this way to reach `main_fw_sig_threshold = 2`.
- **Default reachability:** The generic message-signing app accepts the same
  Bech32 message format the documented release process uses.
- **Impact on funds:** A firmware image the maintainers did not intend to ship
  becomes installable on every device that trusts those keys, and such firmware
  can steal all wallet secrets.
- **Physical access required:** No.
- **Malicious host required:** Yes, a maintainer's.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** Yes.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic after two user approvals.
- **Security property violated:** Firmware authorization signatures must be
  domain-separated from generic user-message signatures and must communicate
  release intent.
- **Owning codebase:** This repository and the bootloader submodule.

**Evidence**

The bootloader authenticates firmware with the Bitcoin signed-message
construction:

```c
#define BITCOIN_SIG_PREFIX ("\x18" "Bitcoin Signed Message:\n")
...
sha256_Update(&context, BITCOIN_SIG_PREFIX, sizeof(BITCOIN_SIG_PREFIX) - 1U);
sha256_Update(&context, len_byte, sizeof(len_byte));
sha256_Update(&context, message, message_len);
/* digest_in, then a second SHA-256 over digest_in */
secp256k1_ecdsa_verify(verify_ctx, &sig_obj, digest, &pubkey_obj);
```

The message-signing app computes the same value:

```python
msghash = sha256(sha256(
    b"\x18Bitcoin Signed Message:\n" + compact.to_bytes(len(msg)) + msg
).digest()).digest()
```

Same prefix, same length encoding, same double SHA-256, same curve, and no extra
domain separator on either side.

The authorized message is printable text, not opaque binary.
`blsect_make_signature_message` builds `hrp` from brief section names and
versions (`"b1.22.134rc5-2.0.1-"`), builds `data` from a 5-bit mapping of
SHA-256 over the concatenated section digests, then Bech32-encodes both. Length
is capped at 252 bytes by `message_len <= VARINT_MAX_ONE_BYTE`.

The bootloader specification states the intent plainly: "The Bech32 message as
an intermediate product allows delegation of the step 5 to an air-gapped device,
like Specter itself."

**Attack trace**

Build a malicious upgrade file. Compute its Bech32 signature message. Present it
to a release-key holder's device as an ordinary `signmessage` request at the
release key's path. The device prompts, showing the path and the Bech32 string.
On approval it returns a signature that is, by construction, a valid firmware
signature. Repeat with a second key holder.

**Why existing checks do not prevent it**

The confirmation shows the derivation path and the message. The `hrp` part
discloses section names and versions, so a careful signer can confirm **which
version** they authorize. The `data` part is 52 Bech32 characters of a hash.
Nothing on screen says which binary those characters commit to, and nothing
distinguishes a firmware authorization from an ordinary message. The
confirmation authenticates intent about a version number, never about content.

F-21 shows that this same prompt can be made to display less than it signs, and
H-06 shows its result is compared with `is False` rather than truthiness. To be
precise: **F-21 does not by itself produce a firmware signature.** The NUL trick
hides the tail of a message, so the bytes actually signed are
`prefix || NUL || tail`, which is not the Bech32 message `M` the bootloader
needs, and `M` is Bech32 so it cannot contain a NUL. The narrower point still
matters: the residual defense above rests on the assumption that what the screen
shows is what gets signed, and F-21 shows that assumption does not hold in
general on this screen.

**Code at this tree**

[bl_signature.c:148-149](../../bootloader/core/bl_signature.c#L148-L149):

```c
sha256_Update(&context, (const uint8_t*)BITCOIN_SIG_PREFIX,
              sizeof(BITCOIN_SIG_PREFIX) - 1U);
```

[signmessage.py:93-97](../../src/apps/signmessage/signmessage.py#L93-L97):

```python
msghash = sha256(sha256(
    b"\x18Bitcoin Signed Message:\n" + compact.to_bytes(len(msg)) + msg
).digest()).digest()
```

Same prefix, same length encoding, same double SHA-256, no domain separator on
either side. The message app accepts any derivation path with no allowlist.

**Recommended fix**

1. Give firmware authorization its own tagged hash or prefix, so a signature
   from the generic message app cannot be a firmware signature. This is the real
   fix, and it needs a coordinated bootloader and firmware change.
2. Until that lands, sign releases on a key and a device that never run the
   generic message app, and constrain release keys to a derivation path the
   message app refuses.
3. Have the message app recognize the bootloader `hrp` grammar and show an
   explicit "this authorizes a firmware release" screen.

**Action plan**

1. **Real fix (coordinated bootloader + firmware change):** give firmware
   authorization its own prefix in `bl_signature.c`, e.g.
   `#define SPECTER_FW_SIG_PREFIX ("\x1eSpecter Firmware Authorization:\n")`, and
   bump the upgrade-file format version so old bootloaders reject new files and
   vice versa. Update
   [bootloader/tools/upgrade-generator.py](../../bootloader/tools/upgrade-generator.py)
   `message` output at the same time.
2. **Interim, no firmware change required:** in
   [signmessage.py](../../src/apps/signmessage/signmessage.py), refuse to sign
   any message whose Bech32 HRP matches the bootloader grammar
   (`^b\d+\.\d+\.\d+`), or refuse paths under the release-key branch. Document
   the release-key derivation path and constrain it.
3. Have the message app detect the bootloader `hrp` grammar and show an explicit
   "This authorizes a FIRMWARE RELEASE" screen rather than the generic message
   prompt.

---

### F-21: Message signing displays less than it signs

**Status:** Confirmed · **Severity:** High · **Confidence:** High for the
decode and hashing behavior, which is all directly in source. Medium for the
LVGL truncation step, which is standard `strlen` behavior but should be
confirmed on device.

- **Affected component:** The `message` app and the GUI text path.
- **Files and code regions:**
  [signmessage.py:43-51](../../src/apps/signmessage/signmessage.py#L43-L51),
  [signmessage.py:54-75](../../src/apps/signmessage/signmessage.py#L54-L75),
  [signmessage.py:78-85](../../src/apps/signmessage/signmessage.py#L78-L85),
  [signmessage.py:92-105](../../src/apps/signmessage/signmessage.py#L92-L105);
  [prompt.py:16-18](../../src/gui/screens/prompt.py#L16-L18);
  [common.py:122-137](../../src/gui/common.py#L122-L137);
  [ram.py:79-85](../../src/keystore/ram.py#L79-L85);
  `py/objstr.c:157,1881-1891` and `py/unicode.c:177-203` in the pinned
  `micropython` fork; `lv_label.c` in the pinned LVGL.
- **Functions and modules:** `MessageApp.process_host_command`,
  `MessageApp.sign_message`, `bytes_decode`, `utf8_check`,
  `lv_label_set_text`.
- **Attacker capability:** A host that can send one `signmessage` command.
- **Prerequisites:** The user approves one message-signing prompt.
- **Default reachability:** QR and SD by default. USB after the user enables it.
- **Impact on funds:** The user's key signs text they were never shown. Direct
  fund loss depends on what the signature is used for, but this is a
  display/signing divergence on a signing primitive, and F-17 makes that
  primitive a firmware-authorization primitive as well.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** The trusted display must show every byte a
  signing operation authorizes.
- **Owning codebase:** This repository. The decode semantics come from upstream
  MicroPython, but relying on `.decode("ascii")` for validation is this
  project's choice.

**Evidence, in four steps**

1. The app accepts arbitrary binary. `base64:` payloads are decoded with no
   length cap and no byte-value restriction.
2. The "ASCII" guard does not guard ASCII. MicroPython's `bytes.decode`
   **throws the encoding argument away** — `objstr.c:157` literally says
   `// TODO: validate 2nd/3rd args` — and substitutes utf-8. The only check that
   runs is `utf8_check()`.
3. `utf8_check()` **accepts `0x00`**. `unicode.c:196` only rejects a `>= 0x80`
   byte with no lead byte. So a message with an embedded NUL decodes fine and the
   hex-fallback branch never runs.
4. The resulting string goes to `lv.label.set_text()`, which takes a
   `const char *` and measures it with `strlen`. **Everything after the first NUL
   is not drawn.** `sign_message()` then hashes the full byte string.

**Attack trace**

```text
payload = b"I authorise nothing.\x00" + b"<arbitrary attacker text>"
host sends:  signmessage m/44h/0h/0h/0/0 base64:<b64(payload)>

screen shows:   Message:
                __________________________________
                I authorise nothing.
                __________________________________
device signs:   dSHA256("\x18Bitcoin Signed Message:\n" || compact(len) || payload)
```

**Three smaller problems on the same screen**

- Because the encoding argument is ignored, all valid UTF-8 passes, including
  U+202E RIGHT-TO-LEFT OVERRIDE, zero-width characters, and homoglyphs.
- The frame lines are plain underscores inside the same label, so an attacker can
  forge extra `__________` separators and a fake trailing block.
- The message sits in a scrolling `lv.page` while Confirm is a fixed child of
  the screen, so a long message can be approved unread. That is F-19.

**The derivation path is unbounded and the signature is recoverable**

`signmessage` accepts any BIP-32 path, hardened or not, on any coin type, with
no allowlist and no depth limit
([signmessage.py:43-51](../../src/apps/signmessage/signmessage.py#L43-L51)). A
supplied fingerprint prefix is checked against the device, but nothing bounds the
path. The returned signature is **recoverable**
([ram.py:79-85](../../src/keystore/ram.py#L79-L85) `sign_recoverable`, returning
`base64(flag || compact_sig)`), so the host can recover the **public key at the
requested path** from it. One confirmation therefore leaks the pubkey at any path
the attacker names, which is a wallet-structure and address-clustering oracle
outside the xpub-export flow of F-05. The path *is* displayed in the prompt
title, so this is bounded by user attention rather than by code.

The address shown alongside is derived from `derivation_path[0]` only. `84h`
gives p2wpkh, `49h` gives p2sh-p2wpkh, and everything else falls through to
p2pkh ([signmessage.py:78-85](../../src/apps/signmessage/signmessage.py#L78-L85)).
For `m/86h` (Taproot) the device displays a **legacy p2pkh address** that has
nothing to do with the key's real usage.

**Why existing checks do not prevent it**

The only content check is a decode that does not check what its own argument
says it checks. There is no length cap, no control-character filter, and no NUL
rejection anywhere on this path.

**Code at this tree**

[signmessage.py:59-68](../../src/apps/signmessage/signmessage.py#L59-L68):

```python
try:
    msg = "Message:\n\n"
    msg += "__________________________________\n"
    msg += message.decode("ascii")
    msg += "\n__________________________________"
except:
    msg = "Hex message:\n\n%s" % hexlify(message).decode()
```

No NUL rejection, no control-character filter, no length cap. `base64:` decoding
at [signmessage.py:57](../../src/apps/signmessage/signmessage.py#L57) is
unbounded. In the pinned MicroPython fork, `objstr.c` discards the encoding
argument to `.decode()` and `unicode.c`'s `utf8_check()` accepts NUL, which is
why the `.decode("ascii")` guard does not reject non-ASCII input. The derivation
path is unbounded
([signmessage.py:43-51](../../src/apps/signmessage/signmessage.py#L43-L51)), the
signature is recoverable
([ram.py:83-88](../../src/keystore/ram.py#L83-L88)), and the address mapping
falls through to p2pkh for `m/86h`
([signmessage.py:78-83](../../src/apps/signmessage/signmessage.py#L78-L83)).

**Recommended fix**

Reject any byte outside printable ASCII plus `\n`, or show hex unconditionally
for anything else. Cap the message length. Require the user to scroll to the end
before Confirm becomes pressable. Bound the derivation path, or at least warn
when it lies outside the paths of any wallet the device knows. Fix the
address-type mapping, or omit the address.

**Action plan**

1. Validate bytes explicitly instead of relying on `.decode("ascii")`:

   ```python
   MAX_MSG_LEN = 512
   if len(message) > MAX_MSG_LEN:
       raise AppError("Message too long (%d > %d bytes)" % (len(message), MAX_MSG_LEN))
   printable = all(0x20 <= b <= 0x7E or b == 0x0A for b in message)
   if printable:
       msg = "Message:\n\n__________________________________\n" \
             + message.decode() + "\n__________________________________"
   else:
       msg = "Hex message:\n\n%s" % hexlify(message).decode()
   ```

   This closes the NUL truncation, the U+202E and homoglyph variants, and the
   forged `__________` separator in one change.
2. Move the frame lines out of the message label into their own labels so they
   cannot be forged.
3. Bound the derivation path (see H-15 item 3) and warn when it lies outside any
   known wallet's paths.
4. Fix the address mapping: add `86h → p2tr`, or drop the address line for
   unrecognized purposes rather than showing a misleading p2pkh address.
5. Gate Confirm on scroll-to-end — see F-19.

---

### F-22: The device trusts the smartcard's own report of its PIN state

**Status:** Confirmed · **Severity:** High · **Confidence:** High

- **Affected component:** `MemoryCard` keystore and `SecureApplet`.
- **Files and code regions:**
  [secureapplet.py:48-80](../../src/keystore/javacard/applets/secureapplet.py#L48-L80),
  [secureapplet.py:105-119](../../src/keystore/javacard/applets/secureapplet.py#L105-L119);
  [memorycard.py:85-130](../../src/keystore/memorycard.py#L85-L130);
  [ram.py:264-315](../../src/keystore/ram.py#L264-L315);
  [specter.py:564-574](../../src/specter.py#L564-L574).
- **Functions and modules:** `SecureApplet.get_pin_status`,
  `SecureApplet.unlock`, `MemoryCard.is_locked`, `RAMKeyStore.unlock`.
- **Attacker capability:** Swap the smartcard, or emulate one.
- **Prerequisites:** Brief physical access to the card slot, and the smartcard
  keystore is selected.
- **Default reachability:** Applies whenever card-reported state controls
  smartcard unlock.
- **Impact on funds:** The device can be made to boot with no PIN prompt and to
  load an attacker-chosen seed. Funds later sent to addresses it generates go to
  the attacker.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** PIN enforcement and card identity must not
  rest only on assertions made by the untrusted card.
- **Owning codebase:** This repository.

**Evidence**

Every PIN-policy decision is a byte the card sent. There is no attestation of
that state and no device-side counter to cross-check it.

```python
# secureapplet.py
def get_pin_status(self):
    status = self.sc.request(self.PIN_STATUS)
    (self._pin_attempts_left, self._pin_attempts_max, self._pin_status) = list(status)

def unlock(self, pin):
    if not self.is_locked:      # card-reported
        return                  # PIN never sent, never checked
    ...

# ram.py
async def unlock(self):
    if not self.is_pin_set: ...
    while self.is_locked:       # card-reported
        pin = await self.get_pin(); self._unlock(pin)
```

Consequences:

1. A card reporting `PIN_UNLOCKED` (2) makes `is_locked` False, so the
   `while self.is_locked` loop never runs. **The device boots straight to the
   main menu with no PIN prompt.** `SecureApplet.unlock()` short-circuits the
   same way.
2. Because no PIN screen is drawn, the anti-phishing words are never shown.
   Those words are the only card-swap defense in the design.
3. A card reporting `pin_attempts_left == pin_attempts_max` suppresses the "You
   only have N of M attempts" warning at
   [ram.py:264-274](../../src/keystore/ram.py#L264-L274).
4. Combined with F-07, the same card can serve an attacker-chosen `entropy`
   blob. The "plaintext" format uses the public constant `b"\xcc" * 32`, so the
   attacker does not even need the device's own secret to build a blob the device
   accepts.

**Attack trace**

Emulate a card that returns `PIN_UNLOCKED`, skip the PIN loop, and serve the
constant-key attacker seed described in F-07.

**Why existing checks do not prevent it**

The device has no independent PIN-state or card-identity check before it decides
whether to prompt. The residual mitigation is that loading the key from the card
is still a manual menu action ("Load key from smartcard"). That is a UI step, not
a cryptographic control.

**Code at this tree**

[secureapplet.py:48-51](../../src/keystore/javacard/applets/secureapplet.py#L48-L51)
takes the whole PIN policy from a card response:

```python
def get_pin_status(self):
    status = self.sc.request(self.PIN_STATUS)
    (self._pin_attempts_left, self._pin_attempts_max, self._pin_status) = list(status)
```

[secureapplet.py:77-80](../../src/keystore/javacard/applets/secureapplet.py#L77-L80)
derives `is_locked` from `self._pin_status`,
[secureapplet.py:105-106](../../src/keystore/javacard/applets/secureapplet.py#L105-L106)
short-circuits `unlock()` on it, and
[memorycard.py:101-102](../../src/keystore/memorycard.py#L101-L102) forwards it
straight through into `RAMKeyStore.unlock`'s `while self.is_locked` loop. No
device-side PIN-attempt counter exists anywhere in `src/keystore/`.

**Recommended fix**

Pin the card identity, as F-07 recommends. Keep a device-side monotonic
PIN-attempt counter in flash as a cross-check. Always require PIN entry at boot,
whatever the card claims. Do not accept a constant-key blob from a card that was
not previously paired.

**Action plan**

1. Always prompt for a PIN at boot when a smartcard keystore is selected,
   regardless of what the card reports. In `RAMKeyStore.unlock`, replace
   `while self.is_locked` with a first-iteration-unconditional loop for
   card-backed keystores.
2. Add a device-side monotonic PIN-attempt counter in `/flash/keystore/` and
   cross-check it against `_pin_attempts_left`; treat a disagreement as a
   card-swap and hard-fail.
3. Pin the card public key at pairing — see F-07, which is the prerequisite for
   this being meaningful.
4. Require confirmation of the resulting wallet fingerprint after each "Load key
   from smartcard".

---

### F-31: A short PSET rangeproof length underflows the rewind read loop into an out-of-bounds write

**Status:** Confirmed · **Severity:** High · **Confidence:** High

- **Affected component:** Native secp256k1 MicroPython binding, streaming
  rangeproof rewind entry point.
- **Files and code regions:**
  [libsecp256k1.c:1818-1844](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1818-L1844);
  [liquid/wallet.py:56-82](../../src/apps/wallets/liquid/wallet.py#L56-L82);
  [liquid/manager.py:311-333](../../src/apps/wallets/liquid/manager.py#L311-L333),
  [liquid/manager.py:489-495](../../src/apps/wallets/liquid/manager.py#L489-L495);
  [stream.c:59-68](../../f469-disco/micropython/py/stream.c#L59-L68);
  [platform.py:148-154](../../src/platform.py#L148-L154);
  [sdram.c:10-11](../../f469-disco/usermods/sdram/sdram.c#L10-L11).
- **Functions and modules:** `usecp256k1_rangeproof_rewind_from`,
  `LWallet.fill_pset_scope`, `LiquidWalletManager.preprocess_psbt`,
  `mp_stream_rw`.
- **Attacker capability:** Supply a PSET over USB, SD, or QR to a device that
  holds a registered Liquid blinded wallet.
- **Prerequisites:** A blinded Liquid wallet is registered, and one attributed
  PSET scope omits its cleartext asset, value, and blinders, so `wallet.py:62`
  does not short-circuit.
- **Default reachability:** Reachable during PSET preprocessing, before any
  confirmation screen.
- **Impact on funds:** No key-disclosure or unauthorized-signing chain was
  shown. The established result is attacker-chosen bytes written for an
  attacker-chosen length beyond a fixed, known SDRAM arena on a signing device,
  before authorization.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Attacker-declared lengths must be validated
  before they bound a native write, and writes into a preallocated arena must
  stay inside that arena.
- **Owning codebase:** The `secp256k1-embedded` binding fork, plus the
  unvalidated call site in this repository.

**Evidence**

The binding reads the host-derived proof length and computes:

```c
size_t prooflen = (size_t)get_uint64(args[1]);
intptr_t memoff = (prooflen / 4 + 1) * 4;
if (memlen < memoff) { /* raise */ }
while (l < (prooflen - 64)) {
    mp_stream_read_exactly(stream, (byte *)(memptr + l), 64, &err);
    if (err) { /* raise */ }
    l += 64;
}
```

For `prooflen` 0, 5, and 63 the unsigned loop bounds are `0xFFFFFFC0`,
`0xFFFFFFC5`, and `0xFFFFFFFF` on the 32-bit target. The `memlen < memoff`
comparison passes for a five-byte proof, because `memoff` is only eight; it does
not bound the write loop. EOF also does not stop the loop, because `mp_stream_rw`
returns a short read with `errcode = 0`.

The destination is fixed and known. `platform.get_preallocated_ram()` returns
the SDRAM arena at `0xC02EE000` with size `0x100000`.
`LWallet.fill_pset_scope` reads the CompactSize rangeproof length straight from
the PSET stream and calls the native function with no minimum and no arena
bound. Both the input and the output rangeproof paths run while confirmation
metadata is being built.

**Attack trace**

Put a five-byte rangeproof value in an attributed Liquid input or output scope.
Omit the cleartext fields that bypass rewind. Append chosen bytes. Execution
reaches `rangeproof_rewind_from(stream, 5, 0xC02EE000, 0x100000, ...)`, `5 - 64`
wraps, and the trailing bytes are streamed past the arena.

**Impact constraint**

This is a sequential write into a fixed SDRAM region, not an arbitrary-address
write. This review did not establish what lies above `0xC03EE000` at runtime, how
the FMC aperture aliases beyond populated SDRAM, or a complete path from the
overwrite to seed disclosure or unauthorized signing. Those limits keep the
result at High rather than Critical.

**Why existing checks do not prevent it**

The existing guard validates only the scratch offset. The Python caller does not
bound the CompactSize value. MicroPython reports EOF from `mp_stream_rw` with
`errcode = 0`, so the native `if (err)` escape does not stop the loop.

**Code at this tree**

[libsecp256k1.c:1818-1839](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1818-L1839):

```c
size_t prooflen = (size_t)get_uint64(args[1]);
intptr_t memptr = (intptr_t)get_uint64(args[2]);
intptr_t memlen = (intptr_t)get_uint64(args[3]);
intptr_t memoff = (prooflen / 4 + 1)*4;
size_t l = 0;
if(memlen < memoff){ mp_raise_ValueError("Not enough memory for proof."); }
int err = 0;
while(l < (prooflen - 64)){                       // unsigned underflow for prooflen < 64
    mp_stream_read_exactly(stream, (byte*)(memptr+l), 64, &err);
    if(err){ mp_raise_ValueError("Failed to read from stream"); }
    l += 64;
}
```

The Python caller at
[liquid/wallet.py:65-80](../../src/apps/wallets/liquid/wallet.py#L65-L80) reads
the CompactSize straight from the PSET stream and passes it with no minimum and
no arena bound.

**Recommended fix**

Enforce both a protocol minimum and the real arena maximum before crossing the
native boundary. Use addition-based bounds that are checked for overflow. Treat
a short stream read as failure regardless of `errcode`. Validate the rangeproof
length in `fill_pset_scope`.

**Action plan**

1. Native, in `usecp256k1_rangeproof_rewind_from`:

   ```c
   if(prooflen < 65 || prooflen > (size_t)memlen){
       mp_raise_ValueError("Invalid proof length");
       return mp_const_none;
   }
   while(l + 64 <= prooflen){                     /* addition-based, no underflow */
       size_t got = mp_stream_read_exactly(stream, (byte*)(memptr+l), 64, &err);
       if(err || got != 64){ mp_raise_ValueError("Failed to read from stream"); }
       l += 64;
   }
   ```

   Treat a short read as failure regardless of `errcode` — `mp_stream_rw`
   reports EOF with `errcode == 0`
   ([stream.c:59-68](../../f469-disco/micropython/py/stream.c#L59-L68)).
2. Python, in `LWallet.fill_pset_scope`, validate before crossing the boundary:

   ```python
   l = compact.read_from(stream)
   if l < 65 or l > memlen:
       raise RewindError("Invalid rangeproof length %d" % l)
   ```
3. Fix the ABI mismatch in the same module **first** — see H-16 — or the arena
   bound the native check relies on is itself garbage.

---

### F-32: Boot-time USB hardening is applied last, and MicroPython's fault default is CDC+MSC

**Status:** Plausible · **Severity:** High · **Confidence:** Medium

- **Affected component:** Production boot sequence and USB device
  configuration.
- **Files and code regions:**
  [boot.py:15-59](../../boot/main/boot.py#L15-L59);
  [main.c:686,746-757,774-787](../../f469-disco/micropython/ports/stm32/main.c#L746-L757);
  [usb.c:205,233-300,624-627](../../f469-disco/micropython/ports/stm32/usb.c#L624-L627);
  [storage.c:141-154](../../f469-disco/micropython/ports/stm32/storage.c#L141-L154),
  [storage.c:186-214](../../f469-disco/micropython/ports/stm32/storage.c#L186-L214);
  `mpconfigboard_common.h:314-315`; `src/platform.py`; `src/hosts/usb.py`.
- **Functions and modules:** Frozen `boot.py` top level,
  `platform.enable_usb`, `platform.set_usb_mode`, `stm32_main`, `flash_error`,
  `pyb_usb_vcp_init0`, `pyb_usb_dev_init`.
- **Attacker capability:** Induce an exception after the power hold is
  established but before frozen `boot.py` disables USB, then attach USB.
- **Prerequisites:** A real peripheral fault must raise during
  `boot.py:15-56`. The I2C battery-gauge calls at lines 19-23 are the identified
  candidate, but fault inducibility is untested.
- **Default reachability:** Not reachable on a normal boot. Reachable before PIN
  entry and wallet initialization whenever the early boot exception occurs.
- **Impact on funds:** MSC exposes internal flash and QSPI read-write. That
  enables F-06 offline mnemonic recovery and supplies F-15's persistent
  unsigned-code write primitive. CDC receives stdout and tracebacks. An
  interactive REPL additionally requires `main.py` to terminate.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Probabilistic. The software fail-open
  chain is deterministic, but attacker-triggerable hardware exception
  reachability is unproven.
- **Security property violated:** Security defaults must be established before
  fallible initialization, and boot faults must fail closed.
- **Owning codebase:** This repository's boot and platform integration.
  MicroPython's default is behavior the integration must override.

**Evidence**

- Before `boot.py` runs, `pyb_usb_vcp_init0()` installs USB VCP into dupterm and
  attaches it to the REPL
  ([usb.c:624-627](../../f469-disco/micropython/ports/stm32/usb.c#L624-L627)).
- The port runs frozen `boot.py`. On exception, `flash_error(4)` blinks and
  returns, so startup continues
  ([main.c:746-757](../../f469-disco/micropython/ports/stm32/main.c#L746-L757)).
- If `pyb.usb_mode(None)` at [boot.py:57-59](../../boot/main/boot.py#L57-L59)
  was skipped, the port's default branch initializes `USBD_MODE_CDC_MSC`
  ([main.c:774-787](../../f469-disco/micropython/ports/stm32/main.c#L774-L787)).
- This board enables USB and MSC. The default logical unit serves a synthesized
  MBR whose two partitions map internal flash and QSPI read-write
  ([storage.c:141-154](../../f469-disco/micropython/ports/stm32/storage.c#L141-L154),
  [storage.c:186-214](../../f469-disco/micropython/ports/stm32/storage.c#L186-L214)).
  `pyb_usb_dev_init` does not clear the earlier dupterm object.

The software behavior is established in source. The only open link is a fault
that makes one of the early peripheral statements raise on real hardware. The
battery-gauge I2C setup is the realistic candidate; no device test was
performed. The weaker "a wiped filesystem removes `boot.py`" variant is blocked,
because the script is frozen.

**Attack trace**

Force an I2C exception during `boot.py:19-23`. Attach USB. Read the keystore
secret and PIN record through MSC for F-06. Write `/qspi/config.py`. Reboot
normally to get persistent pre-PIN code execution through F-15.

**Impact detail**

MSC yields the flash-resident device secret and PIN verifier. That removes the
RDP prerequisite from F-06: PIN guesses can be checked offline, then `pin_secret`
unwraps `enc_secret` and the persisted mnemonic. QSPI write access supplies
F-15's missing prerequisite, so a `config.py` implant persists across normal
boots. Dupterm stays attached, so CDC receives stdout and tracebacks. An
interactive prompt is not unconditional, because the normal GUI `main.py` loop
does not return.

**Why existing checks do not prevent it**

Application host gating happens later and controls only `USBHost`. The
MicroPython port has already exposed CDC and MSC. `platform.enable_usb` does not
clear dupterm, and the safer `set_usb_mode` helper has no callers.

**Code at this tree**

In [boot/main/boot.py](../../boot/main/boot.py) the ordering is power hold
(lines 13-14) → I2C init and battery-gauge write (lines 19-23) → LEDs →
`pyb.ExtInt(...)` (line 49) → and only then, at lines 57-59:

```python
pyb.usb_mode(None)
os.dupterm(None,0)
os.dupterm(None,1)
```

The inert `sys.path` cleanup at lines 7-10 is the subject of F-15. In the
pinned MicroPython fork, `flash_error(4)` returns rather than halting, the USB
fault default is `USBD_MODE_CDC_MSC`, and the MSC partition map is read-write.

**Recommended fix**

Disable USB and both dupterm slots in the first lines of `boot.py`. Establish
USB-off and terminal-detached state before any I2C, display, pin, interrupt, or
filesystem work. Make peripheral setup fail closed. Enforce terminal detachment
inside the function that enables USB. Do not rely on later application host state
to secure a port-owned USB device.

**Action plan**

1. Move the three USB-off lines to the very top of `boot.py`, above the power
   hold:

   ```python
   # boot.py -- first three statements, before anything fallible
   import pyb, os
   pyb.usb_mode(None)
   os.dupterm(None, 0)
   os.dupterm(None, 1)
   ```
2. Wrap the fallible peripheral setup (I2C, ExtInt) so a raise cannot leave the
   device in a less-secure state than it started:

   ```python
   try:
       i2c = pyb.I2C(1); i2c.init()
       if 112 in i2c.scan():
           i2c.mem_write(0b00010000, 112, 0)
   except Exception:
       i2c = None          # continue with USB already off
   ```
3. Make `platform.enable_usb` clear both dupterm slots itself, so no caller can
   enable USB and leave the REPL attached.
4. Longer term: patch the fork so `flash_error()` halts instead of returning for
   the frozen-`boot.py` failure case.

---

### F-05: USB exports arbitrary-path xpubs and the fingerprint without confirmation

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Xpub and fingerprint host-command handling.
- **Files and code regions:**
  [xpubs.py:257-278](../../src/apps/xpubs/xpubs.py#L257-L278);
  [specter.py:606-652](../../src/specter.py#L606-L652);
  [usb.py:66-89](../../src/hosts/usb.py#L66-L89),
  [usb.py:151-182](../../src/hosts/usb.py#L151-L182);
  [manager.py:238-240](../../src/apps/wallets/manager.py#L238-L240).
- **Functions and modules:** Xpub app `process_host_command`, USB dispatch, the
  wallet-list host command.
- **Attacker capability:** Control a host connected to an enabled USB VCP.
- **Prerequisites:** USB enabled, device unlocked, and a key loaded.
- **Default reachability:** USB is off by default. Export is unconditional after
  the user opts in and unlocks the session.
- **Impact on funds:** Permanent wallet privacy loss, including derivable
  addresses, balances, transaction history, and account linkage. A master xpub
  combined with any leaked non-hardened child private key can recover ancestor
  private keys. The xpub also helps build the derivation metadata F-04 needs.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Secret-derived wallet metadata exports must be
  scoped and explicitly authorized by the user.
- **Owning codebase:** This repository.

**Evidence**

The handler checks only whether the keystore is locked, accepts any parsed path
including `m`, and returns the xpub without calling `show_screen`. `show_screen`
is a parameter of that handler and is never used. The `fingerprint` command works
the same way. `LIST_WALLETS` also returns wallet names with no confirmation.

**Attack trace**

Enable USB, unlock the device, send `xpub m` or `fingerprint`, and receive the
result with no confirmation screen.

**Why existing checks do not prevent it**

The only gate is session unlock. The host-request handler has no per-export
authorization.

**Code at this tree**

In [xpubs.py:257-277](../../src/apps/xpubs/xpubs.py#L257-L277), `show_screen` is
a parameter and is never called:

```python
async def process_host_command(self, stream, show_screen):
    if self.keystore.is_locked:
        raise AppError("Device is locked")
    prefix = self.get_prefix(stream)
    if prefix == b"fingerprint":
        return BytesIO(hexlify(self.keystore.fingerprint)), {}
    elif prefix == b"xpub":
        ...
        xpub = self.keystore.get_xpub(bip32.path_to_str(path))
        return BytesIO(xpub.to_base58(NETWORKS[self.network]["xpub"]).encode()), {}
```

`LIST_WALLETS` at
[manager.py:238-240](../../src/apps/wallets/manager.py#L238-L240) is likewise
unconfirmed.

**Recommended fix**

Route host-requested xpub and fingerprint exports through the existing xpub
confirmation flow, and show the requested derivation and the resulting
fingerprint. Consider whether wallet-name enumeration also needs a prompt or an
interface-level opt-in.

**Action plan**

1. Route both exports through a prompt, reusing the existing confirmation style:

   ```python
   elif prefix == b"xpub":
       path = bip32.parse_path(stream.read().strip().decode())
       xpub = self.keystore.get_xpub(bip32.path_to_str(path))
       if not await show_screen(Prompt(
               "Export public key?",
               "Path: %s\n\nFingerprint: %s" % (
                   bip32.path_to_str(path),
                   hexlify(self.keystore.fingerprint).decode()))):
           return
       return BytesIO(xpub.to_base58(NETWORKS[self.network]["xpub"]).encode()), {}
   ```
2. Same for `fingerprint`.
3. Decide explicitly whether `LIST_WALLETS` needs a prompt or an interface-level
   opt-in; it currently enumerates wallet names to any host.
4. Bound the path depth here too — this handler is the reachable entry point for
   H-15 item 3.

---

### F-07: Smartcard identity is trust-on-first-use, and public-constant blobs lack origin authentication

**Status:** Design limitation · **Severity:** Medium · **Confidence:** High for
the trust defect and for practical exploitation.

- **Affected component:** JavaCard secure channel and `MemoryCard` keystore.
- **Files and code regions:**
  [securechannel.py:52-58](../../src/keystore/javacard/applets/securechannel.py#L52-L58),
  [securechannel.py:68-144](../../src/keystore/javacard/applets/securechannel.py#L68-L144),
  [securechannel.py:197-201](../../src/keystore/javacard/applets/securechannel.py#L197-L201);
  [secureapplet.py:48-80](../../src/keystore/javacard/applets/secureapplet.py#L48-L80);
  [memorycard.py:66-86](../../src/keystore/memorycard.py#L66-L86),
  [memorycard.py:112-130](../../src/keystore/memorycard.py#L112-L130),
  [memorycard.py:171-203](../../src/keystore/memorycard.py#L171-L203),
  [memorycard.py:279-292](../../src/keystore/memorycard.py#L279-L292),
  [memorycard.py:355-357](../../src/keystore/memorycard.py#L355-L357).
- **Functions and modules:** `SecureChannel`, `SecureApplet`, `MemoryCard`.
- **Attacker capability:** Substitute or emulate a card, or actively interpose on
  the card interface.
- **Prerequisites:** Physical access to the card or the interface, and the
  smartcard keystore is selected.
- **Default reachability:** Applies whenever the smartcard keystore is selected.
- **Impact on funds:** A substituted card can claim to be unlocked and supply an
  attacker-selected seed, so future receive addresses can belong to the attacker.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** External secure-element identity and seed
  origin must be authenticated independently of the element.
- **Owning codebase:** This repository. The external card applet implementation
  is not present for review.

**Evidence**

The secure channel gets the card's static public key from the card, then
verifies later card signatures with that same, unpinned key. Closing the channel
discards it. That proves possession of a key, but not card identity or
continuity. PIN state and remaining attempts are also asserted by the untrusted
card.

The supported "plaintext" blob format is AEAD-authenticated using the public
constant `b"\xcc" * 32`. Calling the mode plaintext addresses confidentiality,
but not integrity or origin authentication. A substituted card can build a
structurally valid, attacker-chosen entropy blob.

**Attack trace**

An emulator presents its own key, reports `PIN_UNLOCKED`, and returns a
correctly encoded constant-key blob containing attacker entropy. The device
accepts the internally valid session and blob.

**Existing protections that remain**

Fresh host ephemeral material, a card nonce, separate directional keys, message
counters, MAC-before-decrypt, and renegotiation limit replay. Card removal falls
back to `SDKeyStore`, but the backend identity, color, and anti-phishing words
change, and the flash backend cannot decrypt the card seed. So the fallback is
visible and does not itself leak card secrets.

**Why existing checks do not prevent it**

The secure channel proves possession of the card-supplied key, not continuity
with a previously trusted card.

The user-visible mitigation also does not always hold. Identity changes are
visible only when a PIN screen is drawn:

- The anti-phishing words come from `get_auth_word`, which is only ever called
  from `PinScreen` ([ram.py:292-306](../../src/keystore/ram.py#L292-L306)). No
  PIN screen means no words.
- Whether a PIN screen appears is decided by a byte the **card** sends. See
  F-22. A hostile card that reports `PIN_UNLOCKED` makes `RAMKeyStore.unlock`'s
  `while self.is_locked` loop skip, so the user is never asked for a PIN and never
  sees any words to compare.

There is also a **destructive** variant on the same fallback. On a
smartcard-primary device that never set a flash PIN, removing the card selects
`SDKeyStore`, whose `is_pin_set` is False, so `unlock()` goes straight to
`setup_pin()`. An attacker holding only the device is invited to **choose a PIN
with no authentication**. `_set_pin`
([flash.py:167-182](../../src/keystore/flash.py#L167-L182)) then finds
`self.enc_secret is None` and overwrites `/flash/keystore/enc_secret` with a
fresh random key, permanently destroying any seed the user had stored on flash or
SD. See H-14.

**Code at this tree**

[securechannel.py:52-58](../../src/keystore/javacard/applets/securechannel.py#L52-L58)
fetches `card_pubkey` from the card and never pins it;
[securechannel.py:201](../../src/keystore/javacard/applets/securechannel.py#L201)
discards it on close. The public-constant blob format is at
[memorycard.py:171](../../src/keystore/memorycard.py#L171) and
[memorycard.py:185](../../src/keystore/memorycard.py#L185):

```python
res = aead_encrypt(b"\xcc"*32, self.MAGIC + fingerprint, r)
...
key = b"\xcc"*32
```

The anti-phishing words come only from `PinScreen`, and whether a PIN screen is
drawn at all is decided by the card (F-22). The destructive no-PIN fallback is
at [flash.py:173-186](../../src/keystore/flash.py#L173-L186) (H-14).

**Recommended fix**

Pin the card public key at pairing and hard-fail on mismatch. Always require PIN
entry at boot, whatever state the card claims. Require confirmation of the
resulting wallet fingerprint after each card load. Remove the public-constant
blob format, or put it behind an explicit per-load integrity warning.

**Action plan**

1. Pin the card key at first pairing, stored AEAD-encrypted under the device
   secret:

   ```python
   # memorycard.py
   def _check_card_identity(self):
       sec = secp256k1.ec_pubkey_serialize(self.applet.card_pubkey)
       known = self._load_paired_card_pubkey()      # from /flash/keystore/card_pub
       if known is None:
           self._save_paired_card_pubkey(sec)       # TOFU, but recorded
       elif known != sec:
           raise KeyStoreError("Smartcard identity changed! Card may have been swapped.")
   ```

   Call it from `MemoryCard.init` before any PIN decision.
2. Remove the `b"\xcc"*32` blob format, or gate it behind a per-load "this seed
   is unauthenticated" prompt.
3. Always require PIN entry at boot (F-22), so the anti-phishing words are
   always shown.
4. Confirm the resulting wallet fingerprint after each card load.

---

### F-08: Bootloader key selection is unrecorded in build output, and RDP1 is the default

**Status:** Design limitation · **Severity:** Medium · **Confidence:** High

The RDP1 default drives the Medium rating. Unrecorded key selection alone is Low
build hardening, and the key-selection guard fails closed.

- **Affected component:** Bootloader build configuration and STM32 flash
  protection.
- **Files and code regions:**
  [build_firmware.sh:14-16](../../build_firmware.sh#L14-L16);
  [bootloader/Makefile:18-20](../../bootloader/Makefile#L18-L20),
  [bootloader/Makefile:34-37](../../bootloader/Makefile#L34-L37);
  [bl_syscalls.c:744-758](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L744-L758).
- **Functions and modules:** Bootloader build targets, key-directory selection,
  option-byte configuration.
- **Attacker capability:** Influence the locally installed build keys.
  Separately, obtain physical readout under RDP1.
- **Prerequisites:** Practical RDP1 extraction for the seed impact, or a
  compromised release build environment for the key-selection impact.
- **Default reachability:** The supplied release script enables RDP1 and uses
  the manually populated `selfsigned` key directory.
- **Impact on funds:** RDP1 readout is the prerequisite that makes F-06
  practical. Unrecorded build keys prevent artifact-level confirmation of the
  firmware trust root.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic once the prerequisite access
  exists.
- **Security property violated:** Release artifacts should identify their trust
  root, and production storage protection should match the claimed physical
  threat model.
- **Owning codebase:** This repository and the bootloader submodule.

**Evidence**

[bootloader/Makefile](../../bootloader/Makefile) defaults `KEYS ?= selfsigned`.
[build_firmware.sh](../../build_firmware.sh) invokes:

```sh
make stm32f469disco READ_PROTECTION=1 WRITE_PROTECTION=1
```

without overriding `KEYS`. Production keys are selected by a manual copy:

```sh
cp bootloader/keys/production/pubkeys.c bootloader/keys/selfsigned/
```

Omitting that copy is not silent. At this bootloader checkout,
`keys/selfsigned/` holds only a `.gitignore` whose single line is `pubkeys.c`:

```text
$ git ls-tree -r HEAD keys/
100644 ... keys/production/pubkeys.c
100644 ... keys/selfsigned/.gitignore
100644 ... keys/test/pubkeys.c
```

There is no `keys/selfsigned/pubkeys.c` in a fresh clone, and the Makefile guard

```make
@test -f keys/$(KEYS)/pubkeys.c || (echo ERROR: ... ; exit 1;)
```

stops the build with an explicit error. The build fails closed rather than
producing a self-signed trust root.

What remains is narrower:

1. The selected key set is not recorded in the build output, so one completed
   build cannot be distinguished from another by inspecting its artifacts.
2. Production keys are installed by overwriting a directory named `selfsigned`
   instead of by passing `KEYS=production`. The naming is misleading, and the
   step lives in documentation rather than in the build system.
3. RDP2 is intentionally compiled out. This is the part of F-08 that carries
   real weight, because it is the precondition for F-06.

**Key-management observation**

`bootloader/keys/production/pubkeys.c` defines `vendor_pubkey_list` and
`maintainer_pubkey_list` as **byte-identical**: the same four keys in the same
order, with `bootloader_sig_threshold = 2` and `main_fw_sig_threshold = 2`.
Bootloader upgrades check vendor keys alone; firmware upgrades check vendor plus
maintainer ([bootloader.c:1007-1009](../../bootloader/core/bootloader.c#L1007-L1009)).
With identical lists both reduce to the same 2-of-4, so the role separation the
data structure expresses gives no defense in depth. Compromising any two of those
four keys authorizes both images.

Signature counting was checked specifically for this. The loop in
[bl_signature.c:225-247](../../bootloader/core/bl_signature.c#L225-L247) iterates
signature *records*, and `find_pubkey` returns the first match, so a key present
in both lists cannot double-count. The threshold is real. Only the separation is
not.

A related validation gap: the bound at
[bootloader.c:247-248](../../bootloader/core/bootloader.c#L247-L248) is
`vendor_n_keys + maintainer_n_keys` = 8, which counts key *slots* rather than
*distinct* keys. A threshold of 5 to 8 would validate and then be permanently
unsatisfiable. That is not the current configuration.

**Positive evidence preserved**

The signature-verification logic rejects duplicate signature records, validates
record sizing, resolves fingerprints against compiled-in keys, rejects invalid
signatures for known keys, counts only valid signatures, enforces threshold
bounds, checks all relevant secp256k1 return codes, and separates production and
test key definitions. The documented flow verifies firmware after copying it into
internal flash, which limits removable-media TOCTOU. The defect is key selection
and physical protection, not the threshold-verification algorithm.

**Attack trace**

Read protected flash through a practical RDP1 bypass and continue with F-06.
Build provenance has no artifact-verifiable key-set record.

**Why existing checks do not prevent it**

The key guard fails closed but does not record key identity, and RDP1 is
intentionally weaker than irreversible RDP2.

**Code at this tree**

[bootloader/Makefile:20](../../bootloader/Makefile#L20) has
`KEYS ?= selfsigned`, and
[build_firmware.sh:21](../../build_firmware.sh#L21) calls
`make stm32f469disco READ_PROTECTION=1 WRITE_PROTECTION=1` without
`KEYS=production`. The fail-closed guard at
[bootloader/Makefile:35](../../bootloader/Makefile#L35) is intact. RDP2 is
compiled out at
[bl_syscalls.c:750-753](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L750-L753):

```c
// RDP Level 2 is intentionally disabled. If misused may brick your board!
```

`vendor_pubkey_list` and `maintainer_pubkey_list` in
[bootloader/keys/production/pubkeys.c](../../bootloader/keys/production/pubkeys.c)
are **byte-identical** — the same four keys (k9ert, Mike, Stepan, Backup m/99h)
in the same order, with `bootloader_sig_threshold = 2` and
`main_fw_sig_threshold = 2`. The nominal vendor/maintainer role separation
therefore gives no defense in depth.

Partial mitigation, not a fix:
[tools/introspect-binary.py](../../bootloader/tools/introspect-binary.py) and
[tools/parse_pubkeys.py](../../bootloader/tools/parse_pubkeys.py) can verify a
signed binary against a `pubkeys.c`. These read the **source** file, so they do
not let a finished artifact carry evidence of its own trust root.

**Recommended fix**

Select the production key directory through `KEYS=production` for release
targets instead of overwriting `selfsigned`. Record the selected key-set
fingerprints in build metadata, so a finished artifact carries evidence of its
own trust root. Separate the vendor and maintainer key sets so the two roles mean
something. Keep the RDP1 limitation documented next to the storage guarantees.

**Action plan**

1. `build_firmware.sh`: pass `KEYS=production` explicitly instead of relying on
   a manual `cp` into a directory named `selfsigned`.
2. Record the key set in the artifact. Emit a `keyset.txt` next to the release
   binaries containing the SHA-256 fingerprint of each compiled-in key —
   `parse_pubkeys.get_pubkey_info` already computes exactly this, so wiring it
   into `build_firmware.sh` is a few lines.
3. Make the vendor and maintainer lists genuinely distinct, so 2-of-4 on
   firmware is not the same 2-of-4 as on the bootloader.
4. Tighten the bound at
   [bootloader.c:247-248](../../bootloader/core/bootloader.c#L247-L248) to count
   *distinct* keys rather than key slots.
5. Document the RDP1 limitation next to the storage guarantees. RDP2 being
   irreversible is a legitimate reason not to enable it by default, but it
   should be stated where F-06's threat model is described.

---

### F-10: `non_witness_utxo` parsing is not bounded to its declared field length

**Status:** Plausible · **Severity:** Medium · **Confidence:** High for the
desynchronization; Medium for the security impact.

- **Affected component:** `embit` input-scope parsing and PSBT
  normalization.
- **Files and code regions:**
  [psbt.py:153-165](../../f469-disco/libs/common/embit/src/embit/psbt.py#L153-L165),
  [psbt.py:307-322](../../f469-disco/libs/common/embit/src/embit/psbt.py#L307-L322);
  [transaction.py:111-143](../../f469-disco/libs/common/embit/src/embit/transaction.py#L111-L143);
  [psbtview.py:308-342](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L308-L342),
  [psbtview.py:420-441](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L420-L441);
  [manager.py:708-718](../../src/apps/wallets/manager.py#L708-L718).
- **Functions and modules:** `InputScope.read_value`, transaction
  deserialization, `PSBTView` scope scanning, wallet-manager normalization.
- **Attacker capability:** Supply a PSBT with a malformed declared
  `non_witness_utxo` field length.
- **Prerequisites:** An accepted signing request that contains
  `non_witness_utxo`.
- **Default reachability:** Any Bitcoin `sign` command carrying that field.
- **Impact on funds:** Two parser passes can see different key sets over
  identical bytes. That breaks parser determinism and can break display/signing
  equivalence. No direct theft primitive was completed.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic parser difference.
- **Security property violated:** Every parsing and normalization pass must
  enforce identical field boundaries and canonical scope contents.
- **Owning codebase:** `embit`.

**Evidence**

`InputScope.read_value` reads the declared compact length, but parses the
embedded transaction directly from the parent stream. It neither wraps the value
in a bounded reader nor requires exact consumption. Independent `PSBTView`
scanners honor the declared length.

A targeted check smuggled a `PSBT_IN_SIGHASH_TYPE` value inside the declared
`non_witness_utxo` length:

```text
InputScope pass      -> sighash_type = 0x81
length-honoring scan -> key 0x03 not found in scope
```

The wallet manager copies the raw declared-length blob and also serializes the
desynchronized scope into the normalized file. The shown variant later appears to
fail closed on a duplicate-key error, so theft is not claimed.

**Attack trace**

Smuggle a sighash record inside the declared UTXO length, so `InputScope` sees it
but the length-honoring scan does not.

**Why existing checks do not prevent it**

No bounded substream and no exact-consumption check ties embedded transaction
parsing to the PSBT field boundary.

**Code at this tree**

[psbt.py:307-322](../../f469-disco/libs/common/embit/src/embit/psbt.py#L307-L322):

```python
if k[0] == 0x00:
    if len(k) != 1:
        raise PSBTError("Invalid non-witness utxo key")
    elif self.non_witness_utxo is not None:
        raise PSBTError("Duplicated utxo value")
    else:
        l = compact.read_from(stream)        # <-- read, then never used
        if self.compress and self.txid and self.vout is not None:
            txout, txhash = self.TX_CLS.read_vout(stream, self.vout)
            ...
        else:
            tx = self.TX_CLS.read_from(stream)
    return
```

`l` is discarded. The embedded transaction is parsed directly from the parent
stream, so no bounded substream and no exact-consumption check tie it to the
declared field boundary. Independent `PSBTView` scanners do honor the declared
length, which is what makes the two views disagree.

**Recommended fix**

Parse through a length-bounded stream and require exact consumption of the
declared field value. Add differential tests that require all parser and scanner
passes to produce the same scope boundaries and key set.

**Action plan**

1. Parse through a bounded reader and require exact consumption:

   ```python
   l = compact.read_from(stream)
   start = stream.tell()
   if self.compress and self.txid and self.vout is not None:
       txout, txhash = self.TX_CLS.read_vout(stream, self.vout)
       self._txhash, self._utxo = txhash, txout
   else:
       self.non_witness_utxo = self.TX_CLS.read_from(stream)
   consumed = stream.tell() - start
   if consumed != l:
       raise PSBTError("non_witness_utxo length mismatch: declared %d, consumed %d"
                       % (l, consumed))
   ```

   `read_vout` may legitimately stop early; in that case seek to `start + l` and
   verify the seek lands inside the scope rather than requiring exact
   consumption for that branch.
2. Add a differential test asserting `InputScope` and the length-honoring
   `PSBTView` scanner see the same key set over identical bytes.
3. This is an upstream `embit` defect. Route it through coordinated disclosure
   together with F-04 (§12.2).

---

### F-11: Liquid input values and assets are displayed from unverified fields

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Liquid PSET input unblinding and display.
- **Files and code regions:**
  [liquid/wallet.py:59-65](../../src/apps/wallets/liquid/wallet.py#L59-L65);
  [liquid/manager.py:258](../../src/apps/wallets/liquid/manager.py#L258),
  [liquid/manager.py:354-383](../../src/apps/wallets/liquid/manager.py#L354-L383);
  [liquid/pset.py:80-109](../../f469-disco/libs/common/embit/src/embit/liquid/pset.py#L80-L109),
  [liquid/pset.py:165-174](../../f469-disco/libs/common/embit/src/embit/liquid/pset.py#L165-L174).
- **Functions and modules:** `LWallet.fill_pset_scope`, Liquid manager metadata
  generation, `LInputScope.unblind`.
- **Attacker capability:** Supply a malicious PSET through a host transport.
- **Prerequisites:** The device is configured for a Liquid network, and the user
  approves.
- **Default reachability:** Every Liquid PSET signing flow with host-supplied
  cleartext input metadata.
- **Impact on funds:** Displayed input totals and asset labels can be falsified
  while signatures stay valid for the real confidential commitments. Loss
  requires the user to rely on the false input summary instead of checking the
  output list.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Displayed Liquid amounts and assets must be
  verified against the confidential commitments being signed.
- **Owning codebase:** This repository and `embit`.

**Evidence**

Host-controlled proprietary fields populate `value`, `asset`,
`value_blinding_factor`, and `asset_blinding_factor`.
`LWallet.fill_pset_scope` returns early when all four are present, despite a
comment saying the commitments should be verified. `LInputScope.unblind` contains
generator and Pedersen commitment checks, but no call site for it was found in
the PSET signing flow. Display metadata uses the unverified values directly.

The host can also supply `blinding_seed`, which seeds generated output blinders
and rangeproof nonces. No extra secret disclosure was shown, because the host
already knows the plaintext output amounts it supplied.

**Attack trace**

Present a confidential input that really holds 10 L-BTC while claiming 0.1
L-BTC. The device displays 0.1 and signs against the real commitments.

**Why existing checks do not prevent it**

Output commitments are verified, but that does not authenticate input cleartext
metadata. Previous-transaction verification proves transaction identity, not the
relationship between claimed values or blinders and the commitments.

**Code at this tree**

At [liquid/wallet.py:62-64](../../src/apps/wallets/liquid/wallet.py#L62-L64) the
comment describes a verification that does not happen:

```python
if None not in [scope.asset, scope.value, scope.asset_blinding_factor, scope.value_blinding_factor]:
    # verify that asset and value blinding factors lead to value and asset commitments
    return True
```

`grep -rn "unblind" src/` finds no call site for `LInputScope.unblind` in the
PSET signing flow. Display metadata uses the host-supplied values directly at
[liquid/manager.py:375-380](../../src/apps/wallets/liquid/manager.py#L375-L380).

**Recommended fix**

Recompute and compare the asset generator and the Pedersen commitment from the
supplied asset, value, and blinders. Treat missing or mismatching values as
unknown and unblinded, and do not compute a trusted input summary from them.

**Action plan**

1. Implement the check the comment promises, before the early return:

   ```python
   if None not in [scope.asset, scope.value, scope.asset_blinding_factor,
                   scope.value_blinding_factor]:
       gen = secp256k1.generator_generate_blinded(scope.asset, scope.asset_blinding_factor)
       if secp256k1.generator_serialize(gen) != vout.asset:
           raise WalletError("Asset commitment does not match claimed asset")
       commit = secp256k1.pedersen_commit(scope.value_blinding_factor, scope.value, gen)
       if secp256k1.pedersen_commitment_serialize(commit) != vout.value:
           raise WalletError("Value commitment does not match claimed value")
       return True
   ```
2. If the check cannot be performed (missing blinders), set `scope.value = -1`
   so the screen renders `???` — `TransactionScreen` already handles that
   sentinel at
   [transaction.py:98](../../src/gui/screens/transaction.py#L98) — and exclude
   the input from any computed total.
3. Do not compute or display a fee when any input amount is unverified.

---

### F-15: A production boot import executes unsigned Python from writable QSPI

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Production MicroPython module search and the external
  QSPI trust boundary.
- **Files and code regions:**
  [boot.py:7-10](../../boot/main/boot.py#L7-L10),
  [boot.py:62](../../boot/main/boot.py#L62);
  [platform.py:9-12](../../src/platform.py#L9-L12);
  [main.c:696-741](../../f469-disco/micropython/ports/stm32/main.c#L696-L741),
  also `main.c:300,660-661`;
  [builtinimport.c:59-67](../../f469-disco/micropython/py/builtinimport.c#L59-L67).
- **Functions and modules:** Boot-time `sys.path` sanitization, `platform`
  module initialization, `init_flash_fs_part`, MicroPython import resolution.
- **Attacker capability:** Write a Python or MPY file to the root of external
  QSPI or internal flash.
- **Prerequisites:** Physical QSPI or flash programming, or another file-write
  primitive. F-32 supplies read-write MSC access to both partitions if its boot
  fault occurs.
- **Default reachability:** The non-frozen `import config` runs on every
  production boot, before PIN entry.
- **Impact on funds:** Persistent pre-PIN arbitrary Python runs inside the signed
  firmware trust boundary. It can read seeds and keys after unlock, change
  display or signing behavior, or exfiltrate secrets, while the genuine firmware
  and the anti-phishing device secret stay intact.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic once the attacker can write
  `config.py` or `config.mpy`.
- **Security property violated:** Signed firmware must not load unauthenticated
  executable code from attacker-writable persistent storage.
- **Owning codebase:** This repository plus the pinned MicroPython fork.

**Evidence**

The fork mounts `/flash`, then `/qspi`. Each mount helper changes the current
working directory, so CWD ends at `/qspi`. It builds:

```text
["", "/qspi", "/qspi/lib", "/flash", "/flash/lib"]
```

The intended cleanup does nothing:

```python
for p in sys.path:
    if "qspi" in sys.path:
        sys.path.remove(p)
```

The membership test looks for the exact element `"qspi"`, which is not present,
so nothing is removed. Even removing `/qspi` alone would not close the path,
because the empty element resolves relative to CWD.

Frozen `boot.py` imports frozen `platform.py`, whose top level runs:

```python
try:
    import config
except:
    import config_default as config
```

No `config.py` exists in the repository or in the frozen manifest. So
MicroPython's importer probes the VFS and executes `/qspi/config.py` before PIN
entry. The authenticated settings loaders are not involved.

**Attack trace**

Write `/qspi/config.py` and reboot normally. It executes when frozen `boot.py`
imports frozen `platform.py`, before PIN entry. The implant persists without
replacing firmware or changing the device secret.

**Scope constraints**

A normal host command cannot choose a filename in the QSPI root, and SD is not
mounted into `sys.path` in the production build. Frozen `boot.py`, frozen
`main.py`, and built-in modules cannot be shadowed. The missing piece is a write
primitive: physical flash access, or another vulnerability. F-32's read-write MSC
state supplies it and turns this into a persistent chain.

**Why existing checks do not prevent it**

QSPI user-file HMAC helpers are bypassed by the language import machinery. The
empty `sys.path` entry also resolves against QSPI. Secure boot authenticates
internal firmware, not external modules.

**Code at this tree**

[boot.py:7-10](../../boot/main/boot.py#L7-L10) is inert:

```python
for p in sys.path:
    if "qspi" in sys.path:     # tests for the exact element "qspi", never present
        sys.path.remove(p)
```

[platform.py:9-12](../../src/platform.py#L9-L12) runs the unauthenticated
import at module top level:

```python
try:
    import config
except:
    import config_default as config
```

`find . -name config.py` outside `f469-disco/` and `.git/` returns nothing, and
`config` is not in the frozen manifest, so the importer probes the VFS. The
pinned MicroPython fork sets CWD to `/qspi` and keeps the `""` `sys.path`
entry, which is what makes that probe reach writable storage.

**Recommended fix**

Replace path mutation with a frozen/native allowlist. Remove the `""` entry.
Move CWD to RAM or another non-persistent location before imports. Make the
`config` choice a frozen build-time setting or authenticated data rather than
executable Python. Test that every production import resolves only to frozen or
native code.

**Action plan**

1. Remove the executable-import escape hatch. Freeze a `config.py` into the
   manifest so the VFS is never probed, or replace the mechanism with
   authenticated data:

   ```python
   # platform.py
   try:
       import config            # frozen only
   except ImportError:
       import config_default as config
   ```

   and add `config.py` to [manifests/](../../manifests/) so the frozen module
   always wins. Note the bare `except:` must become `except ImportError:` or a
   syntax error in a planted `/qspi/config.py` would still be swallowed.
2. Fix the `sys.path` sanitization and drop the `""` entry:

   ```python
   sys.path[:] = [p for p in sys.path if p and "qspi" not in p]
   ```
3. Chdir to a non-persistent location before any import runs.
4. Add a boot-time assertion that every security-relevant module resolved to a
   frozen path (`__file__` absent on frozen modules is a usable signal).

---

### F-18: The native TRNG driver fails open and emits zero-valued words

**Status:** Confirmed · **Severity:** Medium. The seed impact becomes High only
if the failure persists while the software entropy pool holds no
attacker-unknown input. · **Confidence:** High for the fail-open behavior, which
is static. Medium for the seed-recovery chain, which also depends on fault
persistence and on whether the attacker knows the accumulated pool state.

- **Affected component:** STM32 random-number peripheral driver, `os.urandom`,
  and application entropy pooling.
- **Files and code regions:**
  [rng.c:33-55](../../f469-disco/micropython/ports/stm32/rng.c#L33-L55)
  (`rng_get`) and `ports/stm32/moduos.c:97-110` (`os_urandom`) in the pinned
  `micropython` fork; [rng.py:7](../../src/rng.py#L7),
  [rng.py:45-116](../../src/rng.py#L45-L116);
  [decorators.py:6-18](../../src/gui/decorators.py#L6-L18).
- **Functions and modules:** `rng_get`, `os_urandom`, `get_random_bytes`,
  `feed_touch`.
- **Attacker capability:** None is needed for a spontaneous peripheral fault. An
  active attack additionally needs the ability to induce a clock, seed, or
  liveness fault.
- **Prerequisites for seed recovery:** The failure must persist across the TRNG
  reads used for mnemonic generation, and the software entropy pool must hold no
  input unknown to the attacker. The pool starts from a public constant, but
  touch events feed CPU timing and coordinates into it.
- **Default reachability:** `MICROPY_HW_ENABLE_RNG` is `(1)` for
  `STM32F469DISC`, so this is the real path. `os.urandom` is the only hardware
  entropy source for `src/rng.py`, which feeds mnemonic generation, the software
  pool, and Liquid blinding nonces.
- **Impact on funds:** If the TRNG failure persists and the pool state is fully
  known, mnemonic generation is deterministic and an attacker can reproduce every
  derived key. A transient failure does not erase pool entropy: if even one touch
  event contributed timing or coordinates unknown to the attacker, this review
  does not establish seed recovery. The final mnemonic entropy is a SHA-512
  derived value, not an all-zero byte string.
- **Physical access required:** Unknown.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Fault occurrence is probabilistic. Output
  is deterministic once the fault and the pool state are fixed.
- **Security property violated:** Entropy-source failure must be detected, and
  seed generation must fail closed.
- **Owning codebase:** The pinned `micropython` fork, and this repository for
  the missing health check above it.

**Evidence**

```c
uint32_t start = HAL_GetTick();
while (!(RNG->SR & RNG_SR_DRDY)) {
    if (HAL_GetTick() - start >= RNG_TIMEOUT_MS) {   /* 10 ms */
        return 0;
    }
}
return RNG->DR;
```

Two defects. First, on timeout the function returns `0` and reports no error to
any caller. Second, it never inspects `RNG->SR` `SECS` (seed error) or `CECS`
(clock error). The STM32F4 reference manual requires both to be checked; a seed
error means the entropy source has failed and `DR` must not be used.

`os_urandom` then consumes one 32-bit TRNG word per output **byte**, discarding
24 bits each time, with no status the Python layer can inspect:

```c
for (int i = 0; i < n; i++) {
    vstr.buf[i] = rng_get();
}
```

**Attack trace**

Force every mnemonic-generation RNG read to time out from a known initial pool,
then reproduce the resulting mnemonic entropy.

**Why existing checks do not prevent it**

There is one compensating control, and it sits above the defect rather than at
it. [src/rng.py](../../src/rng.py) carries a Python-layer liveness check:
[rng.py:18-21](../../src/rng.py#L18-L21) defines `RNGError(BaseError)`, and
[rng.py:45-91](../../src/rng.py#L45-L91) defines `_looks_dead(data)`, which
rejects a buffer where any single byte value covers more than half of it
(n ≥ 8), or where the distinct-value count is below half the expected count for
healthy output. The threshold is computed in fixed point
(`_expected_distinct`), so it is identical on MicroPython single-precision and
CPython double-precision builds. It gates the only entry point at
[rng.py:96-108](../../src/rng.py#L96-L108):

```python
def get_random_bytes(nbytes):
    global entropy_pool
    d = get_trng_bytes(nbytes)
    if _looks_dead(d):
        raise RNGError("TRNG returned no entropy")
    feed(d)
```

Every seed- and key-generating caller goes through it:
[helpers.py:24](../../src/helpers.py#L24) (mnemonic),
[ram.py:158](../../src/keystore/ram.py#L158) and
[flash.py:148,183](../../src/keystore/flash.py#L148) (device/enc secrets),
[securechannel.py:82](../../src/keystore/javacard/applets/securechannel.py#L82).
16 unit tests in
[test/tests_native/test_rng.py](../../test/tests_native/test_rng.py) cover the
partial-stall, majority-stall, low-variety, short-buffer, and >64-byte paths.

What that check cannot do is see the peripheral. It is a statistical inference
over output bytes, so it catches a stalled or mostly-stalled source and nothing
else: a biased-but-varied source, a seed error reported only in `SECS`, and a
clock error reported only in `CECS` all pass it. There is no Python-visible
health API to consult instead — `grep -n "SECS\|CECS" rng.c` returns nothing.

Two paths bypass the check, both assessed as non-security-critical:
`get_random_bytes(1)` at [input.py:233](../../src/gui/screens/input.py#L233)
skips it (`n < 4`), which is intentional and documented in the docstring; and
[platform.py:271](../../src/platform.py#L271) calls `os.urandom` directly, but
only to overwrite flash blocks during wipe.

The software pool does not close the gap either. It starts from the constant
`b"7" * 64` ([rng.py:7](../../src/rng.py#L7)), holds no TRNG health state, and
requests above 64 bytes bypass it entirely. For mnemonic-sized requests it does
preserve earlier touch-derived entropy, which can prevent straightforward seed
reproduction when that state is unknown to the attacker.

**Recommended fix**

Make `rng_get()` signal failure instead of returning `0`. Check `SECS` and
`CECS`. Consume full 32-bit words. Expose a Python-visible health and liveness
check. Refuse to generate a mnemonic if it fails.

**Action plan**

1. Fix the driver in the fork. `rng_get()` should signal failure rather than
   return `0`:

   ```c
   // ports/stm32/rng.c
   uint32_t rng_get(void) {
       ...
       while (!(RNG->SR & RNG_SR_DRDY)) {
           if (HAL_GetTick() - start >= RNG_TIMEOUT_MS) {
               rng_last_error = RNG_ERR_TIMEOUT;
               return 0;
           }
       }
       if (RNG->SR & (RNG_SR_SECS | RNG_SR_CECS)) {
           rng_last_error = RNG_ERR_SEED_OR_CLOCK;
           return 0;
       }
       return RNG->DR;
   }
   ```

   Have `os_urandom` raise `OSError` when `rng_last_error` is set, and consume
   full 32-bit words rather than one word per byte.
2. Expose `pyb.rng_health()` so `src/rng.py` can check the peripheral directly
   instead of inferring from output statistics.
3. Replace the constant pool seed `b"7" * 64`
   ([rng.py:7](../../src/rng.py#L7)) with a health-checked hardware seed at boot
   — see F-14.
4. Keep `_looks_dead` after the driver is fixed. It is cheap, and it is the only
   check that survives a driver that reports success while producing garbage.

---

### F-19: Confirmation buttons stay fixed while security-critical text scrolls

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High. This is
layout, not rendering, so it does not depend on target LVGL behavior.

- **Affected component:** GUI confirmation layer.
- **Files and code regions:**
  [prompt.py:16-30](../../src/gui/screens/prompt.py#L16-L30);
  [common.py:140-159](../../src/gui/common.py#L140-L159);
  [transaction.py:60-85](../../src/gui/screens/transaction.py#L60-L85);
  [manager.py:764](../../src/apps/wallets/manager.py#L764),
  [manager.py:766](../../src/apps/wallets/manager.py#L766).
- **Functions and modules:** `Prompt`, the fixed confirmation buttons,
  `TransactionScreen`.
- **Attacker capability:** Choose the number of outputs in a PSBT, or the length
  of a message.
- **Prerequisites:** The user approves without scrolling through all
  security-critical content.
- **Default reachability:** Every transaction and message confirmation.
- **Impact on funds:** Any conclusion that rests on the user seeing the fee, the
  gap-limit warning, or the watch-only warning does not hold.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic layout effect.
- **Security property violated:** Security-critical confirmation text must be
  visible, or reviewed, before approval is possible.
- **Owning codebase:** This repository.

**Evidence**

`Prompt` puts the message inside a scrolling `lv.page` and attaches the button
pair to the **screen**:

```python
self.page = lv.page(self)
self.page.set_size(480, 600)
self.message = add_label(message, scr=self.page)
(self.cancel_button, self.confirm_button) = add_button_pair(..., scr=self)
```

`add_button` places buttons at a fixed `y=700` on a 480x800 display. Confirm is
therefore reachable and enabled no matter how much of the content the user has
seen.

`TransactionScreen` appends into that same container in this order: outputs
(lines 68-74), then the fee (76-88), then the aggregated warning block (90-94).
The vertical position of the fee and of every warning is a function of the
attacker-chosen output count. Each non-change output consumes roughly 180-200 px
— a 28 pt value line, an optional label, a wrapped address at three lines of
28 pt mono, plus 30 px and 10 px margins — against a visible page height of about
640 px. Three outputs fill the viewport. Ten push the fee and every warning well
below it. The per-output gap-limit and watch-only warnings sit in the same
container.

**What this does not affect**

"Unknown wallet in inputs!"
([manager.py:378-386](../../src/apps/wallets/manager.py#L378-L386)), the
already-signed warning (`manager.py:338-348`), and the sighash prompt are
separate blocking `Prompt` screens shown before the transaction screen. Those
cannot be scrolled away, although their own body text has the same fixed-button
property.

**Attack trace**

Supply enough outputs or text to push the fee and warnings below the viewport,
then obtain approval without scrolling.

**Why existing checks do not prevent it**

There is no scroll-to-end gate, no pagination limit, and no fixed warning region
controlling the button.

**Code at this tree**

In [prompt.py:16-30](../../src/gui/screens/prompt.py#L16-L30) the message goes
into a scrolling page while the buttons attach to the screen:

```python
self.page = lv.page(self)
self.page.set_size(480, 600)
self.message = add_label(message, scr=self.page)
...
(self.cancel_button, self.confirm_button) = add_button_pair(..., scr=self)
```

`TransactionScreen` appends outputs, then the fee
([transaction.py:68-79](../../src/gui/screens/transaction.py#L68-L79)), then
warnings ([transaction.py:81-85](../../src/gui/screens/transaction.py#L81-L85))
into the same `self.page`, so the fee's vertical position is a function of the
attacker-chosen output count. No scroll-to-end gate exists anywhere in
`src/gui/`.

**Recommended fix**

Render the fee and the warning block outside the scrolling container, or disable
Confirm until the container has been scrolled to the end. Cap or paginate the
output list.

**Action plan**

1. Cheapest effective change: move the fee and the aggregated warning block out
   of `self.page` and into fixed screen-level labels above the button pair, so
   they cannot be scrolled off.
2. Stronger: disable Confirm until the page has been scrolled to the end.

   ```python
   # prompt.py
   def _on_scroll(self, obj, event):
       if event == lv.EVENT.VALUE_CHANGED:
           at_end = (self.page.get_scrl().get_y() + self.page.get_scrl().get_height()
                     <= self.page.get_height() + 4)
           if at_end:
               self.confirm_button.set_state(lv.btn.STATE.REL)
   ```

   Start the button in `lv.btn.STATE.INA` when the content overflows the
   viewport.
3. Cap or paginate the output list on the default page, and render
   `"%d change outputs not shown" % num_change_outputs` — the counter already
   exists at
   [transaction.py:60-66](../../src/gui/screens/transaction.py#L60-L66) and is
   discarded (see F-24).

---

### F-23: Liquid asset names are chosen by the host

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

Impact can be high for a user who holds both valuable and worthless assets, but
the required earlier label approval and the later transaction approval keep this
at Medium.

- **Affected component:** `LWalletManager` asset registry and transaction
  display.
- **Files and code regions:**
  [liquid/manager.py:37](../../src/apps/wallets/liquid/manager.py#L37),
  [liquid/manager.py:129-141](../../src/apps/wallets/liquid/manager.py#L129-L141),
  [liquid/manager.py:162-190](../../src/apps/wallets/liquid/manager.py#L162-L190),
  [liquid/manager.py:583-593](../../src/apps/wallets/liquid/manager.py#L583-L593);
  [transaction.py:98-99](../../src/gui/screens/transaction.py#L98-L99),
  [transaction.py:125-126](../../src/gui/screens/transaction.py#L125-L126),
  [transaction.py:167-189](../../src/gui/screens/transaction.py#L167-L189).
- **Functions and modules:** `LWalletManager` asset import, persistence,
  lookup, and display metadata.
- **Attacker capability:** A host on any enabled channel.
- **Prerequisites:** A Liquid network is selected, and the user approved one
  "Import asset?" prompt at some earlier point. It need not be during the target
  transaction.
- **Default reachability:** Available on configured Liquid networks.
- **Impact on funds:** The user approves a transfer of real value believing it is
  something worthless.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Security-critical asset identity must be
  anchored in trusted network data, not in replaceable host labels.
- **Owning codebase:** This repository.

**Evidence**

`addasset` is a host command. One prompt, then the label is stored and used
forever:

```python
if cmd == ADD_ASSET:
    hexasset, assetlbl = arr
    if await show_screen(Prompt("Import asset?",
            "Asset:\n\n"+format_addr(hexasset, letters=8, words=2)+"\n\nLabel: "+assetlbl)):
        asset = bytes(reversed(unhexlify(hexasset)))
        self.assets[asset] = assetlbl
        self.save_assets()

def asset_label(self, asset):
    if asset in self.assets: return self.assets[asset]     # attacker string
    h = hexlify(bytes(reversed(asset))).decode()
    return "L-"+h[:4]+"..."+h[-4:]
```

There is **no built-in table of known asset IDs**. Not even the network's policy
asset (L-BTC or tL-BTC) has a trusted name. Unlabelled, it renders as an
eight-hex-character fragment such as `L-6f02...4d61`. The only thing that turns
an asset ID into a readable name is an entry the host asked for.

**Attack trace**

1. The host sends `addasset <real L-BTC asset id> TestToken`. The prompt shows a
   64-hex-character blob. A user cannot recognize the L-BTC asset ID by eye and
   has nothing to compare it against. They approve.
2. Later the host presents a PSET spending real L-BTC. The screen renders
   `10.00000000 TestToken to <addr>`.
3. The user approves.

The inverse also works: label a worthless asset "L-BTC".

**Aggravating factor**

`check_unknown_assets` actively asks the user to label assets **during** the
signing confirmation, which trains them to attach names to hex blobs at the
moment they can least verify them. The label is then persisted. Separately,
`dumpassets` returns the whole registry to the host with no confirmation. That is
low sensitivity, but it fingerprints which assets the user touches.

**Existing mitigations**

The import prompt does show the full asset ID, and the registry is stored
AEAD-encrypted under `keystore.userkey`, so it cannot be tampered with at rest.

**Why existing checks do not prevent it**

The import prompt shows only a raw identifier the user cannot readily
authenticate, and no reserved policy-asset mapping exists.

**Code at this tree**

[liquid/manager.py:129-139](../../src/apps/wallets/liquid/manager.py#L129-L139)
stores a host-supplied label after one prompt, and
[liquid/manager.py:580-589](../../src/apps/wallets/liquid/manager.py#L580-L589)
returns it unconditionally:

```python
def asset_label(self, asset):
    if asset is None:
        return "L-???"
    if isinstance(asset, str):
        return asset
    if asset in self.assets:
        return self.assets[asset]
    h = hexlify(bytes(reversed(asset))).decode()
    return "L-"+h[:4]+"..."+h[-4:]
```

There is no built-in table of known asset IDs —
`grep -rn "policy_asset\|L-BTC" src/apps/wallets/liquid/` finds no reserved
mapping. `DUMP_ASSETS` at
[liquid/manager.py:140-141](../../src/apps/wallets/liquid/manager.py#L140-L141)
returns the whole registry with no confirmation.

**Recommended fix**

Hard-code the policy asset ID per Liquid network and render it with a reserved,
non-overridable name. Refuse host labels that collide with reserved names. Always
show the first and last bytes of the raw asset ID next to any label, so a name
can never fully replace identity. Restrict labels to a short printable-ASCII set.

**Action plan**

1. Add the policy asset per network to
   [liquid/networks.py](../../f469-disco/libs/common/embit/src/embit/liquid/networks.py)
   or to a local constant, and make it non-overridable:

   ```python
   RESERVED_ASSETS = {
       "liquidv1":  (unhexlify("6f0279e9ed041c3d710a9f57d0c02928416460c4b722ae3457a11eec381c526d")[::-1], "L-BTC"),
       "liquidtestnet": (..., "tL-BTC"),
   }
   def asset_label(self, asset):
       reserved = RESERVED_ASSETS.get(self.network)
       if reserved and asset == reserved[0]:
           return reserved[1]
       ...
   ```
2. Reject host labels that collide with a reserved name in the `ADD_ASSET`
   handler.
3. Always render the first and last bytes of the raw asset ID next to any
   label, so a name can never fully replace identity:
   `"%s (%s…%s)" % (label, h[:4], h[-4:])`.
4. Restrict labels to short printable ASCII, and drop `check_unknown_assets`'
   habit of asking for labels during the signing confirmation.

---

### F-24: The transaction screen is incomplete by default

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High. Points 1
and 2 are trivially verifiable, and point 1 is dead Python.

- **Affected component:** PSBT display metadata and `TransactionScreen`.
- **Files and code regions:**
  [manager.py:747-771](../../src/apps/wallets/manager.py#L747-L771);
  [transaction.py:16-27](../../src/gui/screens/transaction.py#L16-L27),
  [transaction.py:60-85](../../src/gui/screens/transaction.py#L60-L85).
- **Functions and modules:** Wallet-manager output metadata,
  `TransactionScreen`.
- **Attacker capability:** Supply a transaction whose safety depends on hidden
  change, hidden warnings, or fee context.
- **Prerequisites:** The user follows the default confirmation view.
- **Default reachability:** Every ordinary Bitcoin transaction confirmation.
- **Impact on funds:** Point 3 is the missing compensating control for F-03.
  Points 1 and 2 make the change chain effectively invisible.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** The default trusted display must present
  enough recipient, change, warning, and fee information for informed approval.
- **Owning codebase:** This repository.

This is three defects in the same screen. Together they mean the default
confirmation view does not carry enough information to judge the transaction.

**1. Change is never labelled "change" anywhere.** The code that would do it is
dead:

```python
branch_txt = ""
if branch_idx == 1:
    "change "                       # bare expression, discarded
elif branch_idx > 1:
    "branch %d " % branch_idx       # bare expression, discarded
metaout["label"] = "%s %s#%d" % (wallet.name, branch_txt, idx)
```

`branch_txt` is always empty. A change output and a receive-branch output of the
same wallet both render as `MyWallet #7`. Nothing on either page separates
branch 0 from branch 1 from branch 3 of a multi-branch descriptor. The resulting
label also has a double space, which makes it easy to spot.

**2. A gap-limit warning is silently overwritten:**

```python
if allowed_idx <= idx:
    metaout["warning"] = "Derivation index is by %d larger than ..." % ...
if wallet.is_watchonly:
    metaout["warning"] = "Watch-only wallet!"        # overwrites
```

`metaout["warning"]` is a single string, not a list. For a watch-only wallet the
signal that a host is steering funds far outside the wallet's known range is
thrown away and replaced by a much less important notice.

**3. There is no fee sanity check of any kind.** `meta["fee"]` is computed and
rendered, but there is no absolute threshold, no sat/vB rate, no percentage
threshold, no warning styling, and `meta["warnings"]` is never populated on the
Bitcoin path. `if fee:` also means a fee of exactly zero renders no fee row
(that part is H-05), and a **negative** fee — reachable through F-03 — renders
as an ordinary `Fee: -N satoshi (-M%)` with no warning.

Fields that appear **only** on the hidden details page for an ordinary
transaction are the number of inputs, every input value and label, and every
change output. `enable_inputs` opens that page by default only for custom
sighashes, unknown Liquid values, or issuance. Transaction version, locktime, and
input sequence are not rendered on either page.

**Attack trace**

Present far-gap watch-only change, or an extreme fee. The default screen omits or
overwrites the relevant context.

**Why existing checks do not prevent it**

Critical fields are hidden on a details page or never generated, and warnings use
a single replaceable string.

**Code at this tree**

**1. Dead `branch_txt`** —
[manager.py:746-752](../../src/apps/wallets/manager.py#L746-L752) holds the bare
discarded expressions.

**2. Overwritten warning** —
[manager.py:757-760](../../src/apps/wallets/manager.py#L757-L760) overwrites the
gap-limit warning with the watch-only warning.

**3. No fee sanity check** —
[transaction.py:68](../../src/gui/screens/transaction.py#L68) is
`if meta.get("fee"):`, so a zero fee renders no row (H-05) and a negative fee
renders as an ordinary line. `grep -rn 'meta\["warnings"\]' src/apps/wallets/manager.py`
returns nothing, so `meta["warnings"]` is never populated on the Bitcoin path,
and the `if "warnings" in meta` block at
[transaction.py:81-85](../../src/gui/screens/transaction.py#L81-L85) is dead for
Bitcoin. `num_change_outputs` at
[transaction.py:60-66](../../src/gui/screens/transaction.py#L60-L66) is computed
and discarded.

**Recommended fix**

Fix `branch_txt`. Make `warning` a list. Add absolute and percentage fee
thresholds into `meta["warnings"]`. Show input values, transaction version,
locktime, and sequence on the default page, or at least an "N change outputs not
shown" line — the counter for it, `num_change_outputs`, is already computed and
then discarded.

**Action plan**

1. Fix the dead code:

   ```python
   branch_txt = ""
   if branch_idx == 1:
       branch_txt = "change "
   elif branch_idx > 1:
       branch_txt = "branch %d " % branch_idx
   metaout["label"] = "%s %s#%d" % (wallet.name, branch_txt, idx)
   ```
2. Make `warning` a list and render all of them:

   ```python
   warnings = metaout.setdefault("warnings", [])
   if allowed_idx <= idx:
       warnings.append("Derivation index is by %d larger than last known used index %d!" % ...)
   if wallet.is_watchonly:
       warnings.append("Watch-only wallet!")
   ```

   Update both render sites in `transaction.py` to iterate.
3. Populate `meta["warnings"]` with fee thresholds in `preprocess_psbt`:

   ```python
   meta["fee"] = fee
   send_amount = sum(o["value"] for o in meta["outputs"] if not o["change"])
   if fee < 0:
       meta.setdefault("warnings", []).append("NEGATIVE FEE - this transaction is invalid!")
   elif send_amount > 0 and fee * 100 > send_amount * 10:
       meta.setdefault("warnings", []).append(
           "Fee is %.1f%% of the amount sent!" % (fee * 100 / send_amount))
   elif fee > 1_000_000:
       meta.setdefault("warnings", []).append("Fee is over 0.01 BTC!")
   ```
4. Change `if meta.get("fee"):` to `if "fee" in meta:` so a zero fee renders
   (H-05).
5. Render `"%d change outputs not shown" % num_change_outputs` on the default
   page.
6. This item is also a prerequisite for DOC-02: `meta["warnings"]` must be
   populated on the Bitcoin path before any documented warning can be true.

---

### F-25: Boot-time firmware integrity is only a CRC32

**Status:** Design limitation · **Severity:** Medium · **Confidence:** High

Impact becomes high when flash write protection is absent or bypassed, but the
flash-write prerequisite keeps this at Medium.

- **Affected component:** Bootloader persistent firmware integrity
  verification.
- **Files and code regions:**
  [bl_integrity_check.h:40-77](../../bootloader/core/bl_integrity_check.h#L40-L77);
  [bl_integrity_check.c:64-129](../../bootloader/core/bl_integrity_check.c#L64-L129);
  [bootloader.c:1206-1216](../../bootloader/core/bootloader.c#L1206-L1216),
  [bootloader.c:1229-1266](../../bootloader/core/bootloader.c#L1229-L1266),
  [bootloader.c:1271-1277](../../bootloader/core/bootloader.c#L1271-L1277);
  `bootloader/platforms/stm32f469disco/startup/startup.c:209-244`.
- **Functions and modules:** Integrity-check records, `icr_validate`,
  `icr_verify_main`, upgrade copy and startup verification.
- **Attacker capability:** Obtain an arbitrary flash-write primitive through
  physical access or prior code execution.
- **Prerequisites:** Bypass, disable, or remove STM32 write protection. F-33
  supplies that prerequisite for the targeted region after an unsigned SD upgrade
  attempt, and a factory-flashed device has not yet established WRP for these
  regions.
- **Default reachability:** Every boot validates only CRC records, once an
  upgrade has established them.
- **Impact on funds:** An attacker with flash write can install persistent
  key-stealing firmware and recompute accepted integrity records.
- **Physical access required:** Unknown.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** Yes.
- **Deterministic or probabilistic:** Deterministic once flash write is
  available.
- **Security property violated:** Firmware authenticity established during
  upgrade must stay cryptographically enforced at every boot.
- **Owning codebase:** The bootloader submodule and platform integration.

**Evidence**

The integrity check record holds `pl_crc` and `struct_crc` and nothing else.
`icr_validate()` checks the magic value, the struct revision, and a CRC32 of the
record. `icr_verify_main()` recomputes a CRC32 over the flash payload. No
signature, no MAC, and no key is involved at boot.

ECDSA runs exactly once, in the SD-card upgrade path:

```text
erase_flash(...)
copy_sections(file, ...)          # unverified firmware written to flash
hash_flash_sections(...)
verify_multisig(...)              # ECDSA, AFTER the write
if (!verify) { alert; return false; }
create_icrs(...)                  # CRC records written only on success
```

One positive follows from this order. Because the hash is taken **from flash
after copying**, the bytes that are signed are exactly the bytes that will
execute. So signed data and executed data cannot differ on the upgrade path.
That is better than verifying a file and then copying it.

The negative is that anyone with a flash-write primitive — SWD/JTAG, a debug
interface, or code execution in running firmware — can install arbitrary firmware
and recompute accepted CRC32 records. The option-byte barrier is weaker than the
build flag suggests:

1. `WRITE_PROTECTION=1` makes `blsys_init()` protect only the start-up sector on
   every boot. The firmware and bootloader target region is protected only after
   a successful upgrade.
2. Clearing that target protection before authentication, and skipping its
   restore on every failure, is independently exploitable as F-33.
3. `make-initial-firmware.py` emits an image but cannot program option bytes. So
   a factory-flashed device that has never completed an SD upgrade has RDP1 but
   no established WRP for the main-firmware region or the bootloader copies.

The official release build does pass `READ_PROTECTION=1 WRITE_PROTECTION=1`, and
read protection is reasserted on boot. The flag does not itself program WRP into
a newly flashed device.

**Interrupted or rejected upgrade**

Unverified bytes copied to flash receive no integrity record, so the boot path
refuses to execute them (PATH-23). A power cut and an authentication failure both
fail closed for immediate execution. A rejected signature still leaves WRP
cleared, which is F-33, so the hardware barrier is persistently downgraded.

**Attack trace**

Write arbitrary firmware directly to flash, recompute the payload and record
CRCs, and boot it.

**Why existing checks do not prevent it**

ECDSA is used only during the SD upgrade flow. Boot accepts recomputable unkeyed
CRCs.

**Code at this tree**

[bl_integrity_check.h:47-63](../../bootloader/core/bl_integrity_check.h#L47-L63)
defines the record with only `pl_crc` and `struct_crc`. There is no signature,
MAC, or key at boot. ECDSA runs exactly once, in the SD upgrade path at
[bootloader.c:1254-1256](../../bootloader/core/bootloader.c#L1254-L1256), after
the copy to flash — which is the one positive here: the signed bytes are the
executed bytes.

**Recommended fix**

Verify a signature at boot, or at minimum a keyed MAC over a device-held key,
instead of a CRC. Make write protection unconditional for release builds rather
than an `#ifdef`, and make WRP a boot-time invariant that is reasserted on every
start and every upgrade exit.

**Action plan**

1. Verify at boot rather than CRC. Cheapest version that keeps boot time
   acceptable: add a keyed MAC field to `bl_integrity_check_rec_t`, computed over
   the payload under a device-unique key derived at first boot and stored in the
   key-storage sector the fork already reserves. Bump `struct_rev` so old records
   are rejected.
2. If full ECDSA at boot is affordable on this MCU, prefer it — the signature is
   already present in the upgrade file and could be retained alongside the
   payload.
3. Make write protection unconditional for release builds instead of
   `#ifdef WRITE_PROTECTION`, and reassert WRP as a boot-time invariant in
   `blsys_init()` for the firmware and bootloader regions, not only the start-up
   sector.
4. Have `make-initial-firmware.py` document that a factory-flashed device has
   RDP1 but no WRP until the first successful upgrade.

---

### F-28: The UR fountain decoder never verifies any checksum

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** `microur` multipart UR/BCUR2 decoding, reached from
  `ur:crypto-psbt`.
- **Files and code regions:**
  [decoder.py:45-79](../../f469-disco/libs/common/microur/decoder.py#L45-L79),
  [decoder.py:104-122](../../f469-disco/libs/common/microur/decoder.py#L104-L122);
  [util/ur.py:53-73](../../f469-disco/libs/common/microur/util/ur.py#L53-L73);
  [util/bytewords.py:56-99](../../f469-disco/libs/common/microur/util/bytewords.py#L56-L99);
  [qr.py:404-415](../../src/hosts/qr.py#L404-L415).
- **Functions and modules:** Multipart decoder `read_part`, `_reduce`,
  `_combine`, and the bytewords decode path.
- **Attacker capability:** Supply or alter multipart UR QR frames.
- **Prerequisites:** The user scans a multipart `ur:crypto-psbt` stream.
- **Default reachability:** The default QR signing flow for multipart UR
  payloads.
- **Impact on funds:** Corrupted or spliced payloads reach the PSBT parser with
  no UR-level integrity. Independent theft still needs a downstream exploit.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Multipart transport data must be authenticated
  against both per-part and message-level checksums before dispatch.
- **Owning codebase:** `f469-disco/libs/common/microur`, consumed by this
  repository.

**Evidence**

The UR format has two integrity mechanisms. **Neither is enforced on the
multi-part path.**

1. **Per-part bytewords CRC.** `stream_decode_check()` verifies it, and it *is*
   used for the single-part case (`decoder.py:52`,
   `bytewords.decode_check(stream.read())`). The multi-part path goes through
   `decode_write()` → `decodeinto()`, which contains **no CRC check at all**.
   The docstring in `stream_decode_check` still says "TODO: Checksum is currently
   ignored", although it is in fact checked there, which shows the checking was an
   afterthought.
2. **Message-level CRC32**, the `checksum` field in the UR header. `read_part`
   stores it and asserts that every later part declares the *same* value, but
   `_combine()` reassembles and returns the message **without ever computing
   CRC32 over the result and comparing**.

So the assembled message reaches the PSBT parser with no end-to-end integrity.
Because the fountain decoder XORs parts together (`_reduce`), one bad part
corrupts every part derived from it. The cross-part `checksum` equality check is
no protection against a deliberate attacker, who simply reads the checksum off
the legitimate stream and reuses it.

The mitigating factor is that the result is still displayed before signing.
Related lower-severity items: all of this validation is written with bare
`assert` (H-13), and the bytewords decoder does no range validation on its input
characters (H-08).

**Attack trace**

Alter a fountain part while reusing the declared checksum. The combined corrupted
message is returned without verification.

**Why existing checks do not prevent it**

Cross-part checksum equality compares attacker-supplied declarations, and bare
assertions do not authenticate the result.

**Code at this tree**

[decoder.py](../../f469-disco/libs/common/microur/decoder.py) stores the header
checksum and only compares declarations across parts:

```text
decoder.py:51  data = bytewords.decode_check(stream.read())   # single-part only
decoder.py:67  self.checksum = self.checksum or checksum
decoder.py:68  assert self.checksum == checksum               # declaration vs declaration
```

`grep -n "crc32" decoder.py` returns nothing, so `_combine()` returns the
reassembled message without computing CRC32 over it. The multi-part path goes
through `decode_write()` → `decodeinto()`, which has no CRC check.

**Recommended fix**

Compute CRC32 over the output of `_combine()` and compare it with
`self.checksum`; raise on mismatch. Use `stream_decode_check` on the multi-part
path too.

**Action plan**

1. Verify the message-level CRC32 in `_combine()`:

   ```python
   # decoder.py, at the end of _combine()
   import binascii
   crc = binascii.crc32(result) & 0xFFFFFFFF
   if crc != self.checksum:
       raise URError("UR message checksum mismatch: got %08x, declared %08x"
                     % (crc, self.checksum))
   ```

   For the streaming case, accumulate the CRC32 incrementally rather than
   buffering.
2. Use `stream_decode_check` on the multi-part path so the per-part bytewords
   CRC is also enforced, and remove the stale "TODO: Checksum is currently
   ignored" docstring.
3. Apply H-08 (bytewords range validation) and H-13 (`assert` → `raise`) in the
   same change; all three protect the same parser.

---

### F-30: `SIGHASH_NONE` and `ANYONECANPAY` are accepted after a generic warning

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Bitcoin and Liquid sighash confirmation and signing.
- **Files and code regions:**
  [manager.py:36-44](../../src/apps/wallets/manager.py#L36-L44),
  [manager.py:378-419](../../src/apps/wallets/manager.py#L378-L419),
  [manager.py:774-795](../../src/apps/wallets/manager.py#L774-L795);
  [liquid/manager.py:19-29](../../src/apps/wallets/liquid/manager.py#L19-L29),
  [liquid/manager.py:44](../../src/apps/wallets/liquid/manager.py#L44).
- **Functions and modules:** Sighash-name initialization, the custom-sighash
  prompt, per-input signing.
- **Attacker capability:** Supply a PSBT or PSET that declares a dangerous
  non-default sighash.
- **Prerequisites:** The user presses "Proceed anyway" on one warning screen.
- **Default reachability:** Every signing request can declare one of the accepted
  custom sighash combinations.
- **Impact on funds:** A signature made with `NONE | ANYONECANPAY` commits to
  essentially nothing except the one input. It is a blank cheque: the attacker
  can embed that input in any transaction, with any outputs, at any later time.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** The device must not authorize signatures that
  surrender transaction outputs without an explicit, understandable policy.
- **Owning codebase:** This repository.

**Evidence**

All six combinations are built into the accepted set, and the "proceed" branch
signs with whatever the PSBT asked for:

```python
SIGHASH_NAMES = {ALL: "ALL", NONE: "NONE", SINGLE: "SINGLE"}
for sh in list(SIGHASH_NAMES):
    SIGHASH_NAMES[sh | SIGHASH.ANYONECANPAY] = SIGHASH_NAMES[sh] + " | ANYONECANPAY"

confirm = await show_screen(Prompt("Warning!",
    "\nCustom SIGHASH flags are used!\n\n" + "\n".join(custom_sighashes),
    confirm_text="Proceed anyway", cancel_text=canceltxt))
if confirm:
    return None          # sign with whatever the PSBT asked for
```

and then, per input:

```python
inp_sighash = sighash or inp.sighash_type or self.DEFAULT_SIGHASH
```

The warning text says only "Custom SIGHASH flags are used!" and lists the flag
name. It does not state the consequence, and the affirmative button is "Proceed
anyway". Nothing distinguishes `SINGLE`, which is merely unusual, from
`NONE | ANYONECANPAY`, which surrenders the input unconditionally.

The Liquid manager inherits the same handling over a **larger** flag space,
because it adds a `| RANGEPROOF` variant of each
([liquid/manager.py:19-29](../../src/apps/wallets/liquid/manager.py#L19-L29)),
with `DEFAULT_SIGHASH = ALL | RANGEPROOF`.

An availability note, not a security issue: `SIGHASH_DEFAULT` (`0x00`, Taproot)
is absent from `SIGHASH_NAMES`, so a Taproot PSBT declaring `sighash_type = 0` is
rejected with "Unknown sighash type: 0!" at
[manager.py:385-388](../../src/apps/wallets/manager.py#L385-L388).

**Attack trace**

Request `NONE | ANYONECANPAY`, obtain approval, then transplant the signed input
into any later transaction.

**Why existing checks do not prevent it**

The warning names the flag but does not explain that outputs are uncommitted, and
no policy rejects the dangerous modes.

**Code at this tree**

[manager.py:37-44](../../src/apps/wallets/manager.py#L37-L44) builds all six
combinations into the accepted set.
[manager.py:417-422](../../src/apps/wallets/manager.py#L417-L422) shows
`"\nCustom SIGHASH flags are used!\n\n"` with `confirm_text="Proceed anyway"`
and returns `None` on confirm, and
[manager.py:778](../../src/apps/wallets/manager.py#L778) does
`inp_sighash = sighash or inp.sighash_type or self.DEFAULT_SIGHASH`. The Liquid
manager adds a `| RANGEPROOF` variant of each at
[liquid/manager.py:19-29](../../src/apps/wallets/liquid/manager.py#L19-L29).

**Recommended fix**

Refuse `NONE` and `NONE | ANYONECANPAY` outright. For `SINGLE`, verify that a
matching output index exists. Make the warning describe what the flag gives away,
and make Cancel the affirmative button.

**Action plan**

1. Refuse the blank-cheque modes outright:

   ```python
   FORBIDDEN_SIGHASHES = (SIGHASH.NONE, SIGHASH.NONE | SIGHASH.ANYONECANPAY)
   ...
   if inp.sighash_type in FORBIDDEN_SIGHASHES:
       raise WalletError(
           "This transaction asks for SIGHASH_NONE, which would let anyone "
           "redirect the funds. Refusing to sign.")
   ```

   Apply in both `preprocess_psbt` and the Liquid override, accounting for the
   `| RANGEPROOF` variants.
2. For `SINGLE`, verify a matching output index exists before offering the
   prompt.
3. Rewrite the warning to state the consequence, and swap the button roles so
   Cancel is the affirmative action:

   ```python
   Prompt("DANGER", "\nInput %d asks to sign with %s.\n\n"
                    "This does NOT commit to the outputs. Anyone holding this "
                    "signature can spend the input into any transaction.\n"
          % (i, name),
          confirm_text="Cancel", cancel_text="I understand, sign anyway")
   ```
4. Separately, add `SIGHASH.DEFAULT` (`0x00`) to `SIGHASH_NAMES` so Taproot
   PSBTs are not rejected with "Unknown sighash type: 0!" — availability, not
   security.

---

### F-33: Flash write protection is removed before authentication and not restored on failure

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Bootloader SD upgrade sequencing and STM32
  option-byte write protection.
- **Files and code regions:**
  [bootloader.c:827-853](../../bootloader/core/bootloader.c#L827-L853),
  [bootloader.c:1231-1277](../../bootloader/core/bootloader.c#L1231-L1277),
  [bootloader.c:1445-1454](../../bootloader/core/bootloader.c#L1445-L1454);
  [bl_syscalls.c:598-629](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L598-L629),
  [bl_syscalls.c:711-742](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L711-L742),
  [bl_syscalls.c:874-888](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L874-L888);
  [gui.h:27-60](../../bootloader/platforms/stm32f469disco/bootloader/gui.h#L27-L60).
- **Functions and modules:** `do_upgrade_with_file`,
  `set_write_protection_state`, `bootloader_run_initialized`,
  `blsys_flash_write_protect`, `flash_set_write_protection_state`,
  `blsys_alert`.
- **Attacker capability:** Insert a malicious SD card and power on. No signing
  key and no prior code execution is required.
- **Prerequisites:** The device has completed a signed SD upgrade, so WRP is set
  for the affected sectors.
- **Default reachability:** The default and only SD upgrade path automatically
  processes a root-level `specter_upgrade*.bin` with no PIN and no confirmation.
- **Impact on funds:** No direct loss. The deterministic result is permanent
  clearing of WRP for the target region plus destruction of installed firmware,
  which supplies the flash-write prerequisite F-25 needs.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Hardware protection removed for an operation
  must be restored if authorization fails, and unauthenticated input must not
  permanently weaken the device.
- **Owning codebase:** The bootloader submodule and STM32 platform integration.

**Evidence and ordering**

| Code region | Operation | Authenticated? |
| --- | --- | --- |
| `bootloader.c:1226` | Verify payload CRCs | No; attacker-computable |
| `bootloader.c:1231-1234` | Clear WRP option bytes | No |
| `bootloader.c:1237-1244` | Erase and write flash | No |
| `bootloader.c:1248-1251` | Hash bytes back from flash | No |
| `bootloader.c:1255-1263` | Verify multisignature | First authenticity check |
| `bootloader.c:1266-1269` | Create integrity records | Success only |
| `bootloader.c:1271-1277` | Restore WRP | Success only, and compile-time gated |

`set_write_protection_state(..., false)` at
[bootloader.c:1231-1234](../../bootloader/core/bootloader.c#L1231-L1234) has no
`#ifdef`. The restore at
[bootloader.c:1271-1277](../../bootloader/core/bootloader.c#L1271-L1277) is both
success-only and inside `#ifdef WRITE_PROTECTION`. Failures at erase, copy, hash,
signature verification, or integrity-record creation all bypass it.

The change is persistent option-byte programming.
`set_write_protection_state()` calls `blsys_flash_write_protect()`
([bl_syscalls.c:711-742](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L711-L742)),
which commits through `HAL_FLASHEx_OBProgram` and `HAL_FLASH_OB_Launch`
([bl_syscalls.c:598-629](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L598-L629)).
The signature-failure alert is terminal and waits for power-down, so it cannot
fall through to the restore. The bootloader GUI has no input or confirmation API,
and the failure screen does not disclose the resulting WRP state.

**Attack trace**

Build CRC-correct `main` and `sign` sections with the expected platform and base
address, but with zero recognized signature records. Put the file at
`/specter_upgrade_x.bin`. On power-up, metadata, compatibility, version, and
payload-CRC checks pass. WRP is cleared. Attacker bytes replace the firmware. The
signature count is zero. The device halts with WRP still cleared.

PATH-23 explains why those unverified bytes do not execute by themselves. The
security impact is the permanent removal of the hardware control that F-25 relies
on.

**Why existing checks do not prevent it**

Pre-write checks cover only attacker-computable structure, CRC, platform, and
address fields. Authenticity is checked after unprotect, erase, and write, with
no cleanup path and no boot-time WRP reassertion for the firmware and bootloader
regions.

**Code at this tree**

[bootloader.c:1230-1234](../../bootloader/core/bootloader.c#L1230-L1234) clears
WRP before anything is verified:

```c
// Remove write protection from needed sections of the flash memory
if (!set_write_protection_state(&bl_ctx.file_metadata, p_args->loaded_from, false)) {
  fatal_error("Error while removing write protection");
}
```

Then erase (1237), copy (1242), hash (1247), and only at
[bootloader.c:1254-1263](../../bootloader/core/bootloader.c#L1254-L1263) does
`verify_multisig` run — whose failure branch does `return false` **without**
restoring WRP. The restore at
[bootloader.c:1271-1277](../../bootloader/core/bootloader.c#L1271-L1277) is
reachable only on the success path.

**Recommended fix**

Make WRP a boot-time invariant, not a success side effect. Reapply it in a
mandatory cleanup path and before every normal boot. Prefer verification before
destructive writes, or require explicit physical authorization for the
erase-and-copy stage. Report protection state on failure.

**Action plan**

1. Restore WRP on every exit from `do_upgrade_with_file`. Simplest correct
   shape:

   ```c
   bool ok = false;
   /* ... unprotect, erase, copy, hash ... */
   if (verify_multisig(...)) {
       if (!create_icrs(...)) { fatal_error("..."); }
       ok = true;
   } else {
       (void)blsys_alert(bl_alert_error, "Signature Error", err_text, BL_FOREVER, 0U);
   }
   #ifdef WRITE_PROTECTION
   if (!set_write_protection_state(&bl_ctx.file_metadata, p_args->loaded_from, true)) {
       fatal_error("Error while applying write protection");
   }
   #endif
   return ok;
   ```

   Audit every other early `return` and `fatal_error` between the unprotect and
   the restore for the same problem.
2. Better: verify the file's signature **before** touching WRP, then verify
   again from flash after the copy. The first check costs one extra hash pass and
   removes the attacker's ability to clear WRP with an unsigned card at all. The
   second preserves the "signed bytes are executed bytes" property F-25 notes as
   a positive.
3. Reassert WRP for the firmware and bootloader regions in `blsys_init()` on
   every boot, so a device that was left unprotected recovers at next power-on.

---

### F-34: Smartcard receive drains one byte past its stack buffer

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High

- **Affected component:** Native smartcard UART transport used by the JavaCard
  keystore.
- **Files and code regions:**
  [scard_io.c:333-347](../../f469-disco/usermods/scard/ports/stm32/scard_io.c#L333-L347);
  [connection.c:36](../../f469-disco/usermods/scard/connection.c#L36),
  [connection.c:656-661](../../f469-disco/usermods/scard/connection.c#L656-L661),
  [connection.c:854-859](../../f469-disco/usermods/scard/connection.c#L854-L859),
  [connection.c:978](../../f469-disco/usermods/scard/connection.c#L978);
  [memorycard.py:51-59](../../src/keystore/memorycard.py#L51-L59).
- **Functions and modules:** `scard_rx_readinto`, `wait_connect_blocking`,
  `wait_response_blocking`, `CardConnection.transmit`,
  `MemoryCard.is_available`.
- **Attacker capability:** Attach a malicious or substituted smartcard that
  controls UART2 response timing and bytes.
- **Prerequisites:** At least 33 bytes must be queued when one blocking receive
  drains the UART ring. Practical frequency and exact stack layout need target
  validation.
- **Default reachability:** Production smartcard connect and transmit paths,
  including pre-PIN keystore availability detection.
- **Impact on funds:** One attacker-chosen byte is written past a 32-byte stack
  array, and the overlong length causes a matching one-byte over-read. Memory
  corruption is confirmed. Control-flow hijack and key extraction are not.
- **Physical access required:** Yes.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Probabilistic, because the card must
  accumulate 33 queued bytes before a blocking drain.
- **Security property violated:** A replaceable secure-element peer must not
  write beyond native receive buffers before authentication.
- **Owning codebase:** The `diybitcoinhardware/f469-disco` smartcard user
  module.

**Evidence**

```c
size_t scard_rx_readinto(scard_handle_t handle, uint8_t *buf, size_t nbytes) {
    size_t bytes_read = 0;
    uint8_t *p_data = buf;
    while (bytes_read <= nbytes && uart_rx_any(handle->uart_obj)) {
        *p_data++ = uart_rx_char(handle->uart_obj);
        ++bytes_read;
    }
    return bytes_read;
}
```

At `bytes_read == nbytes` the loop runs once more. Both
`wait_connect_blocking()` and `wait_response_blocking()` allocate
`uint8_t rx_buf[32]`, pass `sizeof(rx_buf)`, and then forward the returned
`n_bytes` to the T=1 protocol
([connection.c:656-661](../../f469-disco/usermods/scard/connection.c#L656-L661),
[connection.c:854-859](../../f469-disco/usermods/scard/connection.c#L854-L859)).
The result is one out-of-bounds stack write followed by a one-byte over-read.

These are live production paths. The connection defaults to blocking mode, and
`MemoryCard.is_available()` connects during keystore selection before PIN entry.
A hostile card can retry indefinitely.

Trigger timing is not guaranteed. The 270-byte UART ring must hold at least 33
bytes at one drain, while the normal event loop often wakes after one or two
bytes. A roughly 35 ms MCU stall at 9600 baud is enough and can coincide with
protocol callbacks or garbage collection, but this was not measured.

The exact overwritten stack slot depends on the release compiler and its
optimization level. No control-flow or key-disclosure chain is claimed. That
uncertainty constrains severity without changing the confirmed memory-safety
defect.

**Attack trace**

Present a hostile card. Repeatedly stream at least 33 bytes while the MCU is
delayed in protocol or Python processing. Trigger the connect or response receive
loop so byte 33 overwrites the stack byte next to `rx_buf`.

**Why existing checks do not prevent it**

The native loop's capacity comparison is off by one, both callers trust the
returned length, and the target build has no stack protector.

**Code at this tree**

[scard_io.c:333-345](../../f469-disco/usermods/scard/ports/stm32/scard_io.c#L333-L345)
has `while(bytes_read <= nbytes && ...)`. Both callers allocate
`uint8_t rx_buf[32]` and forward the returned count unchecked
([connection.c:656-661](../../f469-disco/usermods/scard/connection.c#L656-L661),
[connection.c:854-859](../../f469-disco/usermods/scard/connection.c#L854-L859)).
[memorycard.py:51-59](../../src/keystore/memorycard.py#L51-L59) reaches this
before PIN entry via `is_available()`.

**Recommended fix**

Change the loop condition to `< nbytes`. Reject any returned size above the
supplied buffer at both callers. Restore compiler warnings (H-22). Fuzz ATR and
T=1 timing with a smartcard emulator under the release toolchain.

**Action plan**

1. One-character fix in the loop condition:

   ```c
   while(bytes_read < nbytes && uart_rx_any(handle->uart_obj)) {
   ```
2. Defense in depth at both callers:

   ```c
   size_t n_bytes = scard_rx_readinto(handle, rx_buf, sizeof(rx_buf));
   if (n_bytes > sizeof(rx_buf)) {
       /* cannot happen after the loop fix; fail closed if it does */
       return SCARD_ERR_INTERNAL;
   }
   ```
3. Restore `-Wall` (H-22) and fuzz ATR/T=1 timing with a card emulator under the
   release toolchain — this defect and H-23 are both in classes
   `-Wall -Werror` would surface.

---

### F-35: The Liquid confidential-address encoder is not gated by script type

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High for the
encoding defect and both reproduced display failures; Low for an independent
theft chain.

- **Affected component:** Liquid confidential-address generation and output
  display.
- **Files and code regions:**
  [liquid/addresses.py:19-30](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L19-L30);
  [liquid/blech32.py:112-124](../../f469-disco/libs/common/embit/src/embit/liquid/blech32.py#L112-L124),
  [liquid/blech32.py:127-132](../../f469-disco/libs/common/embit/src/embit/liquid/blech32.py#L127-L132);
  [liquid/manager.py:64-76](../../src/apps/wallets/liquid/manager.py#L64-L76),
  [liquid/manager.py:545](../../src/apps/wallets/liquid/manager.py#L545).
- **Functions and modules:** `addresses.address`, `blech32.decode`,
  `blech32.encode`, `LWalletManager.get_address`.
- **Attacker capability:** Supply a malicious PSET through a host transport.
- **Prerequisites:** The device is configured for a Liquid network, and the
  output carries a `\xfc\x04pset\x06` or `\xfc\x08elements\x06` blinding-pubkey
  record so that `LWalletManager.get_address` takes the confidential branch.
- **Default reachability:** Every Liquid PSET output that carries a blinding
  pubkey and whose scriptPubKey is not p2sh takes the affected branch. The
  misleading result occurs whenever that scriptPubKey is not one of the five
  canonical types.
- **Impact on funds:** The device renders a well-formed confidential address for
  a scriptPubKey that has no address representation, and renders several distinct
  scriptPubKeys as one identical address. So an approved payment can commit to a
  script the user never saw.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** The displayed address must correspond
  one-to-one with the scriptPubKey being signed.
- **Owning codebase:** `embit` (`liquid/addresses.py` and
  `liquid/blech32.py`), with the unguarded call site in this repository.

**Root cause: two defects that cancel each other's protection**

The first is in `addresses.address`. The Bitcoin encoder, `Script.address`
([script.py:15-38](../../f469-disco/libs/common/embit/src/embit/script.py#L15-L38)), first
calls `Script.script_type()` and raises `ValueError` when the script is not one
of the five canonical types. The Liquid encoder does not: it special-cases `p2sh`
and then treats *everything else* as a witness program.

```python
# addresses.py:19-30
else:
    data = script.data
    ver = data[0]
    # FIXME: should be one of OP_N
    if ver > 0:
        ver = ver % 0x50
    ...
    return blech32.encode(network["blech32"], ver, blinding_key.sec() + data[2:])
```

`ver = data[0] % 0x50` is a lossy map. Four different leading bytes — `0x01`,
`0x51`, `0xa1`, `0xf1` — all reduce to witness version 1, and the rest of the
address is built from `data[2:]` with the length byte discarded. Nothing recovers
the original first byte.

The second defect is that the round-trip guard which would have caught this is
inert. `blech32.encode` re-decodes its own output and returns `None` if the
decode fails. But every check in `blech32.decode` is commented out:

```python
# blech32.py:112-124
def decode(hrp, addr):
    """Decode a segwit address."""
    hrpgot, data = bech32_decode(addr)
    if hrpgot != hrp:
        return (None, None)
    decoded = convertbits(data[1:], 5, 8, False)
    # if decoded is None or len(decoded) < 2 or len(decoded) > 40:
    #     return (None, None)
    # if data[0] > 16:
    #     return (None, None)
    # if data[0] == 0 and len(decoded) != 20 and len(decoded) != 32:
    #     return (None, None)
    return (data[0], decoded)
```

The strict `bech32.decode` used on the Bitcoin path
([bech32.py:121-137](../../f469-disco/libs/common/embit/src/embit/bech32.py#L121-L137))
keeps all four checks, so `bech32.encode` really does fail closed. `blech32` does
not, which is why the confidential branch is the reachable one.

**Attack trace**

Run against the vendored modules with a fixed 33-byte blinding pubkey `02` +
`11`×32 and the `liquidv1` network:

```
spk 5120…  script_type=p2tr  -> lq1pqgg3zyg…9q4zct3sxg6rvwp68slmqn394jzud3c
spk 0120…  script_type=None  -> lq1pqgg3zyg…9q4zct3sxg6rvwp68slmqn394jzud3c
spk a120…  script_type=None  -> lq1pqgg3zyg…9q4zct3sxg6rvwp68slmqn394jzud3c
spk f120…  script_type=None  -> lq1pqgg3zyg…9q4zct3sxg6rvwp68slmqn394jzud3c
  >>> four distinct scriptPubKeys, one address string

6a14<20B>   (OP_RETURN)      -> lq16qgg3zyg…zxtearrsedgz
0002aabb    (OP_0 <2 bytes>) -> lq1qqgg3zyg…r24mxu3pee3hwhgv
0029<41B>   (41-byte prog.)  -> lq1qqgg3zyg…jq3th20newd9
```

The same three scripts on the *unconfidential* Liquid branch, which uses the
strict `bech32.encode`, return `None`. That confirms the disabled `blech32`
validation is what makes the confidential branch permissive.

**Why existing checks do not prevent it**

- `LOutputScope.verify`
  ([liquid/pset.py:273-321](../../f469-disco/libs/common/embit/src/embit/liquid/pset.py#L273-L321))
  verifies asset generators and Pedersen commitments. It never looks at
  `script_pubkey`.
- The Bitcoin manager wraps address generation in `try/except` and falls back to
  hex ([manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99)). The Liquid
  override calls `liquid_address` *before* that fallback is reachable
  ([liquid/manager.py:70-74](../../src/apps/wallets/liquid/manager.py#L70-L74)),
  so the guarded path is bypassed exactly when the address is confidential.
- `Descriptor.owns` is no defense here: the affected output is a destination, not
  change, so no ownership comparison runs on it.
- Nothing in the display layer distinguishes a rendered address from a hex
  fallback. `show_output`
  ([transaction.py:167-196](../../src/gui/screens/transaction.py#L167-L196))
  formats whatever string it is given.

**Exploitability limits**

The colliding partners `0120…`, `a120…`, and `f120…` are non-standard
scriptPubKeys. `a120<32B>` is `OP_GREATERTHAN` followed by a 32-byte push, which
evaluates true for any two-item scriptSig and is therefore anyone-can-spend.
`f120…` is an invalid opcode and burns. In all of these cases the transaction is
non-standard, so relay is refused by default policy and inclusion needs
cooperation from the Liquid functionary federation. Direct theft is therefore
**plausible, not demonstrated**, and it is not claimed here.

The OP_RETURN variant *is* standard and relayable, and it produces guaranteed
burn of the output value after the user approved a screen showing an
address-shaped string. Its rendered form begins `lq16` rather than `lq1q` or
`lq1p`, which a careful comparison catches.

Medium reflects that combination: the display-to-output correspondence property
is definitively broken, while every full theft chain carries an extra unproven
condition.

**Code at this tree**

[liquid/addresses.py:19-30](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L19-L30)
has the `ver = ver % 0x50` reduction with the `FIXME` intact, and the round-trip
guard is inert because
[blech32.py:112-124](../../f469-disco/libs/common/embit/src/embit/liquid/blech32.py#L112-L124)
has all four validation checks commented out. The strict `bech32.decode` used on
the Bitcoin path retains them, which is why only the confidential branch is
permissive. The unguarded call site is
[liquid/manager.py:70-74](../../src/apps/wallets/liquid/manager.py#L70-L74),
which calls `liquid_address` before the Bitcoin manager's `try/except` hex
fallback at [manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99) is
reachable.

**Recommended fix**

1. Restore the four commented-out checks in `blech32.decode`. They cost nothing
   and re-arm the round-trip guard in `blech32.encode`.
2. Gate `addresses.address` on `Script.script_type()` the way `Script.address`
   does, and raise for anything else instead of reducing `data[0]` modulo `0x50`.
3. Replace `ver = data[0] % 0x50` with an explicit OP_N decode that accepts only
   `0x00` and `0x51`–`0x60`, which resolves the existing `FIXME`.
4. Route `LWalletManager.get_address` through the same exception guard as the
   Bitcoin manager, and label hex fallbacks on screen as "unrecognized output
   script" instead of showing bare hex where an address normally appears.

**Action plan**

1. Uncomment the four checks in `blech32.decode`:

   ```python
   decoded = convertbits(data[1:], 5, 8, False)
   if decoded is None or len(decoded) < 2 or len(decoded) > 40:
       return (None, None)
   if data[0] > 16:
       return (None, None)
   if data[0] == 0 and len(decoded) != 20 and len(decoded) != 32:
       return (None, None)
   return (data[0], decoded)
   ```

   Note the confidential payload is `blinding_key.sec() + program`, so the
   length bounds must account for the 33-byte prefix on the blech32 side.
2. Gate `addresses.address` on script type and decode OP_N explicitly, resolving
   the `FIXME`:

   ```python
   st = script.script_type()
   if st not in ("p2wpkh", "p2wsh", "p2tr"):
       raise ValueError("Unsupported script type for Liquid address: %s" % st)
   op = script.data[0]
   if op == 0x00:
       ver = 0
   elif 0x51 <= op <= 0x60:
       ver = op - 0x50
   else:
       raise ValueError("Invalid witness version opcode")
   ```
3. Wrap `LWalletManager.get_address` in the same `try/except` the Bitcoin
   manager uses, and label the hex fallback on screen as "UNRECOGNIZED OUTPUT
   SCRIPT" rather than rendering bare hex where an address normally appears.
   This also fixes H-25.

---

### F-09: The ARM compiler archive is pinned with a legacy MD5 digest

**Status:** Hardening · **Severity:** Low · **Confidence:** High for the
legacy-digest observation, and High that no practical substitution follows from
ordinary MD5 collision attacks alone.

- **Affected component:** Docker firmware build.
- **Files and code regions:** [Dockerfile:8-11](../../Dockerfile#L8-L11).
- **Functions and modules:** The ARM toolchain download and verification build
  layer.
- **Attacker capability:** Control the compiler download path and produce a
  second preimage for the already fixed MD5 digest, or influence which digest is
  pinned before this Dockerfile is trusted.
- **Prerequisites:** A practical fixed-target second preimage, or prior control
  of the reviewed build input.
- **Default reachability:** Every Docker firmware build downloads and checks
  this archive.
- **Impact on funds:** A malicious compiler could backdoor firmware with no
  matching source change. The fixed digest materially narrows that scenario.
- **Physical access required:** No.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** Yes.
- **Deterministic or probabilistic:** The computational attack was not shown.
  Deterministic if a malicious archive matching the pin is accepted.
- **Security property violated:** Executable build inputs should use modern,
  independently verifiable integrity pins.
- **Owning codebase:** This repository's build configuration and the external
  toolchain distributor.

**Evidence**

The Dockerfile downloads the ARM toolchain and checks a hard-coded, pre-existing
MD5 digest. MD5 is deprecated and inappropriate for new executable build-input
pins, but this construction is not directly vulnerable to the chosen-prefix
collision attacks usually cited against MD5. Substituting an arbitrary malicious
archive requires a second preimage for the existing digest, and ordinary
practical MD5 collision techniques do not provide one. An attacker who can also
modify the Dockerfile or its pinned digest already controls a reviewed build
input and does not need to attack MD5.

Nearby controls are stronger: the Docker base image is digest-pinned, and
bootloader Python requirements are SHA-256 hash-pinned. The compiler check is an
inconsistent assurance and maintenance weakness, not a demonstrated artifact
substitution vulnerability.

**Attack trace**

No practical proof of concept. Substitution requires an archive matching the
already fixed digest.

**Why existing checks do not prevent it**

The fixed MD5 check is legacy assurance debt. It does block arbitrary
collision-only substitution.

**Code at this tree**

[Dockerfile:12-15](../../Dockerfile#L12-L15) pins the MD5 digest
`2b9eeccc33470f9d3cda26983b9d2dc6`, and the Docker path is the documented
deterministic build
([docs/deterministic-firmware-build.md](../../docs/deterministic-firmware-build.md)).

A parallel Nix dev-shell path exists ([flake.nix](../../flake.nix),
`pkgs.buildPackages.gcc-arm-embedded-9`, pinned through `flake.lock` narHashes)
and avoids MD5 — but it is a dev shell, not the release build, so it does not
cover this. The inconsistency is internal to the release build: the base image
is digest-pinned and Python requirements use `--require-hashes`, while the
compiler that produces the firmware is pinned with MD5.

**Recommended fix**

Verify the archive using the publisher-provided SHA-256 or stronger digest and an
immutable release URL. Prefer authenticated, reproducible toolchain inputs.

**Action plan**

1. Replace the MD5 pin with SHA-256 and an immutable URL:

   ```dockerfile
   RUN curl -sSfL -o arm-toolchain.tar.bz2 "<immutable-release-url>" && \
       echo "<sha256>  arm-toolchain.tar.bz2" | sha256sum --check - && \
       tar xf arm-toolchain.tar.bz2 -C /opt && rm arm-toolchain.tar.bz2
   ```

   ARM publishes SHA-256 for the 9-2020-q2 archives; record where the digest
   came from in a comment.
2. Or make the Nix flake the release build path, so the toolchain comes from a
   content-addressed store with a `flake.lock` narHash, and retire the
   Dockerfile's independent download.

---

### F-13: libsecp256k1 error and illegal callbacks return instead of failing closed

**Status:** Hardening · **Severity:** Low · **Confidence:** High

- **Affected component:** Native secp256k1 MicroPython binding, library callback
  configuration.
- **Files and code regions:**
  [ext_callbacks.c:1-2](../../f469-disco/usermods/secp256k1/mpy/config/ext_callbacks.c#L1-L2);
  [libsecp256k1.c:23-24](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L23-L24);
  `secp256k1/src/util.h` (`checked_malloc`).
- **Functions and modules:** `secp256k1_default_illegal_callback_fn`,
  `secp256k1_default_error_callback_fn`, `checked_malloc`.
- **Attacker capability:** None established. No hostile input reaches a returning
  callback in this tree.
- **Prerequisites:** A future reachable path must allocate through a
  callback-reporting allocator and then misuse the failed result.
- **Default reachability:** Not reachable. The surjection allocation is entered
  only from binding paths whose Specter call sites are commented out.
- **Impact on funds:** None established.
- **Physical access required:** No.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Not applicable.
- **Security property violated:** Cryptographic internal errors and allocation
  failures should terminate safely rather than return invalid state to native
  callers.
- **Owning codebase:** The `secp256k1-embedded` binding fork.

**Evidence**

Both callbacks are empty:

```c
void secp256k1_default_illegal_callback_fn(const char* str, void* data){}
void secp256k1_default_error_callback_fn(const char* str, void* data){}
```

So `checked_malloc` can report out of memory to a callback that returns, and then
hand `NULL` back to its caller. The bootloader's equivalent callbacks invoke
`blsys_fatal_error`, so fail-closed handling is available in this project.

The concrete unchecked `gc_alloc` sinks exist only in the unreachable
surjection-proof list branch (H-17, PATH-20). Application call sites for that
branch are commented out
([liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454)).
This is integration debt, not a live vulnerability.

**Attack trace**

None. No current input reaches a returning callback.

**Why existing checks do not prevent it**

The callbacks neither abort nor raise, although `ARG_CHECK` returns failure and
the reviewed callers raise.

**Code at this tree**

[ext_callbacks.c](../../f469-disco/usermods/secp256k1/mpy/config/ext_callbacks.c)
is two empty function bodies. Not currently reachable: the surjection-proof list
branches are the only unchecked `gc_alloc` sinks, and their Specter call sites
are commented out at
[liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454).

**Recommended fix**

Route both callbacks to a hard fault, a secure reset, or an equivalent
fail-closed handler, and assert that they cannot return.

**Action plan**

Match what the bootloader already does with `blsys_fatal_error`:

```c
#include "py/runtime.h"
void secp256k1_default_illegal_callback_fn(const char* str, void* data){
    (void)data;
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("secp256k1 illegal argument"));
    for(;;){}   /* unreachable; assert the callback cannot return */
}
void secp256k1_default_error_callback_fn(const char* str, void* data){
    (void)data;
    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("secp256k1 internal error"));
    for(;;){}
}
```

Verify the NLR jump is valid at every call site; if any callback can fire
outside a MicroPython NLR context, use a hard reset there instead.

---

### F-14: Entropy hardening gaps and unconfirmed raw-TRNG export

**Status:** Hardening · **Severity:** Low · **Confidence:** High for software
behavior. Hardware impact unresolved.

- **Affected component:** Entropy collection, randomness export, and signing
  side-channel hardening.
- **Files and code regions:**
  [rng.py:7](../../src/rng.py#L7), [rng.py:96-116](../../src/rng.py#L96-L116);
  [getrandom.py:36-42](../../src/apps/getrandom.py#L36-L42);
  [apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11);
  [libsecp256k1.c](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c)
  context initialization and Schnorr signing.
- **Functions and modules:** `get_random_bytes`, the `getrandom` host command,
  secp256k1 context initialization and Schnorr signing.
- **Attacker capability:** Send a `getrandom` command. Physical observation is
  required for the side-channel concerns.
- **Prerequisites:** The device runs the production `getrandom` app. Requests
  above 64 bytes bypass the software pool.
- **Default reachability:** The app is in the production manifest and accepts up
  to 1000 bytes.
- **Impact on funds:** No key-recovery path was shown. Raw entropy-source output
  and missing randomization reduce assurance and physical-attack resistance.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Export behavior is deterministic.
  Side-channel consequences are probabilistic and untested.
- **Security property violated:** Entropy-source output should be health-checked,
  and deliberate secret-derived exports should require explicit authorization.
- **Owning codebase:** This repository and its native crypto integration.

**Evidence**

- The software pool starts as the constant `b"7" * 64`
  ([rng.py:7](../../src/rng.py#L7)).
- Requests above 64 bytes return fresh `os.urandom` output directly and bypass
  the pool ([rng.py:103-104](../../src/rng.py#L103-L104)). They are
  liveness-checked by `_looks_dead`, but returned raw.
- The production `getrandom` app returns up to 1000 bytes to a host with no
  confirmation. Above 64 bytes it exposes raw measurements from the
  security-critical entropy source.
- `getrandom` and `label` are listed in the production manifest
  ([apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11)) while their own
  docstrings describe them as "Demo of a single-file app extending Specter
  functionality". So two example applications are part of the shipped host
  command surface. `getrandom` is the one that matters here. The general point is
  that the production app list was not curated against the demo set.
- The inspected Python path never calls `secp256k1_context_randomize`.
- Schnorr signing supplies no BIP340 auxiliary randomness.

**Positive evidence preserved**

Every ordinary RNG request gets fresh `os.urandom` bytes and mixes local data
into the pool. Host data is never fed into the pool. ECDSA uses deterministic
RFC6979, and low-R retries use deterministic counter-based extra data while
checking nonce-function results. No direct attacker control of ECDSA nonces was
found.

**Impact**

A stuck or short-reading hardware RNG produces undetected zero-valued words.
F-18 confirms the fail-open layer below this code. On a fresh device, output
becomes predictable only if the software pool has not already received
attacker-unknown input such as touch timing and coordinates. A transient failure
does not erase entropy already in the pool. Missing context randomization and
missing auxiliary randomness reduce resistance to physical side-channel and fault
attacks. Unconfirmed random export may reveal entropy-source behavior. This
static review did not establish remote key recovery.

**Attack trace**

Request more than 64 bytes with `getrandom` and receive raw hardware-source
measurements with no prompt.

**Why existing checks do not prevent it**

The host handler never calls confirmation, and the pool is bypassed for large
requests.

**Code at this tree**

- [getrandom.py:36-42](../../src/apps/getrandom.py#L36-L42) returns up to 1000
  bytes to a host with no confirmation; `show_fn` is a parameter and is never
  called.
- `getrandom` and `label` are in the production manifest
  ([apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11)) despite their
  "Demo of a single-file app" docstrings.
- `grep -rn "context_randomize" src/` returns nothing.
- Schnorr signing supplies no BIP340 auxiliary randomness.
- A liveness check does exist above the driver
  ([rng.py:45-91](../../src/rng.py#L45-L91), enforced for every request of 4
  bytes or more), which is why this item is Low rather than Medium. Its limits
  are in F-18.

**Recommended fix**

Seed the pool from hardware at boot only after health and liveness checks. Route
all sizes through the pool. Fail on short reads. Confirm host randomness exports
and show the requested byte count. Randomize the secp256k1 context. Consider
auxiliary randomness for Schnorr signing.

**Action plan**

1. Seed the pool from health-checked hardware at boot instead of a constant:

   ```python
   # rng.py
   entropy_pool = b"7" * 64          # replaced at boot
   def seed_pool():
       d = get_trng_bytes(64)
       if _looks_dead(d):
           raise RNGError("TRNG failed at boot")
       feed(d)
   ```

   Call from `main.py` before any key material is generated.
2. Route all sizes through the pool — remove the `if nbytes > 64: return d`
   shortcut and generate in 64-byte chunks from the pool.
3. Confirm `getrandom` exports:

   ```python
   if not await show_fn(Prompt("Send entropy to host?",
           "The host is requesting %d bytes of entropy from the device TRNG."
           % num_bytes)):
       return
   ```
4. Curate the production app list — drop `getrandom` unless it has a use case,
   or re-document it as a supported feature rather than a demo.
5. Call `secp256k1.context_randomize` at boot and after each unlock, and pass
   auxiliary randomness to Schnorr signing.

---

### F-16: Animated QR reassembly accepts invalid indexes and weakly binds frames

**Status:** Confirmed · **Severity:** Low · **Confidence:** High for parser
behavior; Low for independent theft impact.

- **Affected component:** Legacy animated QR and BCUR decoding.
- **Files and code regions:**
  [qr.py:417-487](../../src/hosts/qr.py#L417-L487),
  [qr.py:489-561](../../src/hosts/qr.py#L489-L561), and the wallet-manager BCUR
  decode path.
- **Functions and modules:** QR `parse_prefix`, legacy multipart reassembly,
  BCUR decode dispatch.
- **Attacker capability:** Supply malicious or interleaved animated QR frames.
- **Prerequisites:** The user scans a legacy multipart QR stream.
- **Default reachability:** Reachable through enabled QR ingestion.
- **Impact on funds:** Payload confusion can amplify another parser or display
  exploit. No independent theft primitive was shown.
- **Physical access required:** No.
- **Malicious host required:** Yes.
- **Malicious SD/QR/USB input required:** Yes.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Multipart frames must have valid indexes and
  must be cryptographically bound to one payload.
- **Owning codebase:** This repository.

**Evidence**

- `parse_prefix` rejects `m < 0` but not `m < 1`, so `p0ofN` produces `m = 0` and
  writes to `parts[-1]`, which aliases the final part. The callers do
  `fname = "%s/p%d.txt" % (self.path, m - 1)` — a file literally named
  `p-1.txt` — and `self.parts[m - 1] = fname`, which is `self.parts[-1]`, the
  **last** slot. So `p0ofN` and `pNofN` alias each other.
- `n == 0` gives `self.parts = []` and an `IndexError` **after**
  `self.animated = True` has already been set, which leaves the decoder in an
  inconsistent state that a bare `except:` then swallows. The correct guard is
  `if m < 1 or n < 1 or n < m`.
- Legacy `pMofN` reassembly binds a session only by the part count `N`, so frames
  from two payloads with the same `N` can be mixed.
- Numeric formatting of the part filename prevents path traversal. The outcome is
  malformed or misordered input, not code execution.
- The BCUR path has stronger per-part checks, but the assembled shared hash is
  skipped rather than verified in the wallet-manager decode path.

The BCUR2/UR path is weaker still: neither of the format's two integrity
mechanisms is enforced on the multi-part path. That is F-28.

**Attack trace**

Send `p0ofN`, or interleave equal-length streams so parts alias or combine before
dispatch.

**Why existing checks do not prevent it**

Numeric filenames prevent traversal but do not validate `m >= 1` and do not bind
all frames to one payload. An attacker who controls the transport can already
choose the full payload, and decoded content still reaches parsing and
confirmation. So this is not an independent theft primitive, but it makes payload
confusion easier, and it would amplify any display/signing divergence that
lands on the same transport.

**Code at this tree**

[qr.py:552-561](../../src/hosts/qr.py#L552-L561):

```python
def parse_prefix(self, prefix: bytes):
    print(prefix)
    if not prefix.startswith(b"p") or b"of" not in prefix:
        raise HostError("Invalid prefix, should be in pMofN format")
    m, n = prefix[1:].split(b"of")
    m = int(m); n = int(n)
    if n < m or m < 0 or n < 0:      # m < 0, not m < 1; n < 0, not n < 1
        raise HostError("Invalid prefix")
    return m, n
```

So `p0ofN` yields `m = 0`, `self.parts[m - 1]` aliases `self.parts[-1]`, and
`n == 0` gives an empty `self.parts` with `self.animated` already set. Session
binding is only by part count `N`. The `print(prefix)` on line 553 is a second
instance of H-18.

**Recommended fix**

Reject `m < 1`. Bind all frames to a payload or session identifier rather than
only `N`. Verify the final BCUR shared hash before dispatch. Apply the UR-level
fixes from F-28 at the same time.

**Action plan**

1. Correct the guard:

   ```python
   if m < 1 or n < 1 or n < m:
       raise HostError("Invalid prefix")
   ```
2. Set `self.animated = True` only after `self.parts` has been successfully
   sized, so a raise cannot leave the decoder half-initialized for the bare
   `except:` to swallow.
3. Bind frames to a session: hash the first frame's payload prefix and require
   every later frame to carry the same `(N, session_id)`, rather than only `N`.
4. Verify the assembled BCUR shared hash in the wallet-manager decode path
   before dispatch, and apply F-28's UR-level fixes at the same time.
5. Remove the `print(prefix)`.

---

### F-36: Liquid address decoding discards the witness version and rebuilds every address as `OP_0`

**Status:** Confirmed · **Severity:** Low · **Confidence:** High

- **Affected component:** Liquid address verification (`showaddr` and the
  `bitcoin:` / `index=` verify-address command).
- **Files and code regions:**
  [liquid/addresses.py:41-53](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L41-L53),
  [liquid/addresses.py:82-91](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L82-L91);
  [liquid/manager.py:98-123](../../src/apps/wallets/liquid/manager.py#L98-L123).
- **Functions and modules:** `addresses.addr_decode`,
  `addresses.to_unconfidential`, `LWalletManager.find_wallet_from_address`.
- **Attacker capability:** None required. The defect is triggered by the device's
  own address, not by attacker input.
- **Prerequisites:** A Liquid wallet whose descriptor produces a non-v0
  scriptPubKey, that is, a `tr(...)` taproot descriptor, which
  `LWalletManager.parse_wallet` accepts because it only rejects legacy
  descriptors.
- **Default reachability:** Every address-verification comparison for a Liquid
  taproot wallet.
- **Impact on funds:** No direct loss. Address verification, itself a security
  feature, silently compares against a wrong address, so a genuine address is
  reported as not owned by the device.
- **Physical access required:** No.
- **Malicious host required:** No.
- **Malicious SD/QR/USB input required:** No.
- **Malicious firmware update required:** No.
- **Prior compromise required:** No.
- **Deterministic or probabilistic:** Deterministic.
- **Security property violated:** Decoding an address must reconstruct the exact
  scriptPubKey it encodes.
- **Owning codebase:** `embit` (`liquid/addresses.py`).

**Evidence**

Both segwit branches of `addr_decode` capture the witness version and then throw
it away:

```python
# addresses.py:44-53
ver, data = blech32.decode(hrp, addr)
data = bytes(data)
pub = ec.PublicKey.parse(data[:33])
pubhash = data[33:]
sc = script.Script(b"\x00" + bytes([len(pubhash)]) + pubhash)   # ver unused
...
ver, data = bech32.decode(hrp, addr)
pub = None
sc = script.Script(b"\x00" + bytes([len(data)]) + bytes(data))   # ver unused
```

For v0 addresses — p2wpkh and p2wsh, which is what every Liquid wallet the
firmware creates today produces — the hardcoded `\x00` happens to be correct, and
the reconstruction was verified exact for both. For any other witness version it
is wrong, and `to_unconfidential` then returns a valid-looking but different
address:

```
original scriptPubKey : 5120000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
addr_decode returns   : 0020000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f  (p2wsh)
to_unconfidential(v1) : ex1qqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0s7vq8tc
correct answer        : ex1pqqqsyqcyq5rqwzqfpg9scrgwpugpzysnzs23v9ccrydpk8qarc0s5mqwny
```

**Why existing checks do not prevent it**

`find_wallet_from_address` compares `addr in [a, unconf_a]`. A wrong `unconf_a`
simply fails to match, and the loop falls through to `WalletError`. So the error
surfaces as "can't find wallet owning address" rather than as a decoding bug.

The consequence is bounded: a wrong `unconf_a` cannot cause a *false* match
against a host-supplied string the host did not already know, and the screen that
follows re-derives the address from the device's own descriptor rather than
echoing the host's. The user therefore never sees a wrong address; they see a
failed verification for an address the device does own. That still matters,
because address verification is what a user relies on to confirm a receive
address, and it is silently unsound for a descriptor type the firmware accepts.

**Code at this tree**

At
[liquid/addresses.py:41-53](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L41-L53),
`ver` is bound and then never used in either branch.
`find_wallet_from_address` at
[liquid/manager.py:98-123](../../src/apps/wallets/liquid/manager.py#L98-L123)
compares `addr in [a, unconf_a]`, so a non-v0 Liquid wallet fails verification
silently.

**Recommended fix**

Use the decoded witness version to rebuild the script
(`bytes([ver + 0x50 if ver else 0, len(prog)]) + prog`), and reject versions and
program lengths outside the BIP-350 ranges. Fixing `blech32.decode` per F-35 is a
prerequisite: without those checks `addr_decode` will also accept versions above
16 and programs outside 2-40 bytes.

**Action plan**

1. Use the decoded version in both branches:

   ```python
   def _wit_script(ver, prog):
       if ver == 0 and len(prog) not in (20, 32):
           raise ValueError("Invalid v0 witness program length")
       if not (0 <= ver <= 16) or not (2 <= len(prog) <= 40):
           raise ValueError("Invalid witness version or program length")
       op = 0x00 if ver == 0 else 0x50 + ver
       return script.Script(bytes([op, len(prog)]) + bytes(prog))
   ```

   Call it as `sc = _wit_script(ver, pubhash)` and `sc = _wit_script(ver, data)`.
2. Fix `blech32.decode` first (F-35) — without those checks `addr_decode` will
   also accept versions above 16 and programs outside 2–40 bytes, so
   `_wit_script` becomes the only guard.
3. Add a round-trip test: for each supported Liquid descriptor type, assert
   `addr_decode(address(spk, bkey))[0].data == spk.data`.

## 7. Additional security-relevant behavior and hardening items

These are items that are real but do not on their own constitute an exploitable
vulnerability: latent defects, missing defense in depth, and one recorded
negative result. They are ordered by identifier.

| ID | Status | Severity | Confidence | Owning codebase |
| --- | --- | --- | --- | --- |
| H-01 | Hardening | Low | High | `secp256k1-embedded` binding fork |
| H-03 | Design limitation | Low | High | This repository |
| H-04 | No defect found | Informational | High | This repository plus pinned LVGL behavior |
| H-05 | Hardening | Low | High | This repository |
| H-06 | Hardening | Low | Medium | This repository |
| H-08 | Hardening | Low | High | Bundled `microur` |
| H-09 | Hardening | Low | High | `secp256k1-embedded` binding fork |
| H-10 | Hardening | Low | High | This repository |
| H-11 | Hardening | Low | High | This repository |
| H-12 | Hardening | Low | High | This repository |
| H-13 | Hardening | Low | High | Bundled `microur` plus this repository's build integration |
| H-14 | Hardening | Low | High | This repository |
| H-15 | Hardening | Low | High | This repository, bundled `microur`, and the `embit` submodule by item |
| H-16 | Hardening | Low | High | `secp256k1-embedded` binding fork |
| H-17 | Hardening | Low | High | `secp256k1-embedded` binding fork |
| H-18 | Hardening | Low | High | This repository |
| H-19 | Hardening | Low | High | This repository |
| H-20 | Hardening | Low | High | Bootloader submodule STM32 start-up code |
| H-21 | Design limitation | Low | High | This repository |
| H-22 | Hardening | Low | High | Pinned MicroPython fork |
| H-23 | Hardening | Low | High | `f469-disco` smartcard user module |
| H-24 | Design limitation | Low | High | This repository |
| H-25 | Hardening | Low | High | `embit` submodule plus this repository's unguarded call site |
| H-26 | Hardening | Informational | High | `embit` submodule (not reachable from this firmware) |
| H-27 | Hardening | Low | High | This repository |

### H-01: Adequate secp256k1 context size is hard-coded without a guard

[libsecp256k1.c:27-38](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L27-L38)
hard-codes `PREALLOCATED_CTX_SIZE` to 880 and holds a `FIXME` instead of
comparing it with `secp256k1_context_preallocated_size()`. For the pinned
configuration, `USE_ECMULT_STATIC_PRECOMPUTATION` makes the generator-context
allocation zero, and `ECMULT_WINDOW_SIZE=4` makes the multiplication-context
allocation 512 bytes. With the aligned context structure that needs about 704
bytes on 32-bit ARM and about 736 bytes in the simulator. The 880-byte buffer is
therefore adequate today, and there is no current overflow.

The fragility is still security-relevant. Dropping static generator
precomputation would add roughly 65,536 bytes, `manual_alloc`'s `VERIFY_CHECK` is
compiled out without `VERIFY`, and `maybe_init_ctx()` never compares the required
size. The native build also disables warnings-as-errors. A build-time or
boot-time assertion should replace the hard-coded assumption.

**Action.** Add a boot-time check in `maybe_init_ctx()`:

```c
size_t need = secp256k1_context_preallocated_size(SECP256K1_CONTEXT_SIGN |
                                                  SECP256K1_CONTEXT_VERIFY);
if (need > PREALLOCATED_CTX_SIZE) {
    mp_raise_ValueError("secp256k1 context buffer too small");
}
```

Plus a compile-time `_Static_assert` where the configuration is known.

### H-03: Liquid wallet export includes the master blinding private key

A user-triggered Liquid wallet export embeds the master SLIP77 blinding private
key in the descriptor with no warning. The dedicated blinding-key app warns only
on its host-command path, and its GUI path is likewise unwarned (H-21). So no
in-product GUI export presents this key with an adequate consent step. This
allows unblinding and privacy loss, but it does not grant Bitcoin or Liquid
spending authority. The export stays user-triggered rather than an unconditional
host leak.

**Code at this tree.** The Liquid default descriptor embeds the SLIP77 key at
[liquid/manager.py:203](../../src/apps/wallets/liquid/manager.py#L203):

```python
desc = "blinded(slip77(%s),%s)" % (self.keystore.slip77_key, desc)
```

`Wallet.export_menu` at
[wallet.py:66-95](../../src/apps/wallets/wallet.py#L66-L95) serializes
`self.descriptor.branch(0)` into a QR or an SD JSON file with no warning about
the private key it contains.

**Action.** In `export_menu`, detect a `slip77(` private key in the serialized
descriptor and require an explicit prompt before export, reusing the wording
from the host path in
[blindingkeys/app.py](../../src/apps/blindingkeys/app.py). Offer a "public-only"
export variant that substitutes the blinding *public* key.

### H-04: GUI popup preemption cannot retarget a confirmation press

LVGL delivers `RELEASED` to the `act_obj` captured at press time. Screen
destruction resets that active object, and `Screen.result()` resets its waiting
state on entry
([async_gui.py:46-60](../../src/gui/async_gui.py#L46-L60),
[decorators.py:32-41](../../src/gui/decorators.py#L32-L41),
[screen.py:53-57](../../src/gui/screens/screen.py#L53-L57)). An in-flight release
stays bound to the original button or is dropped. It is never retargeted to a
newly displayed confirmation button, so no authorization bypass follows.

Residual risk: a retained background screen can complete its own coroutine under
a popup, and H-06's `is False` comparisons remain fragile. Touch-controller
behavior below LVGL was not tested.

**Code at this tree.** The mechanism is at
[async_gui.py:46-60](../../src/gui/async_gui.py#L46-L60),
[decorators.py:32-41](../../src/gui/decorators.py#L32-L41), and
[screen.py:53-57](../../src/gui/screens/screen.py#L53-L57). No authorization
bypass. The residual risks named above are tracked as H-06.

### H-05: A fee of exactly zero is not displayed

[transaction.py:68](../../src/gui/screens/transaction.py#L68) and
[transaction.py:151](../../src/gui/screens/transaction.py#L151) both guard the
fee row with `if meta.get("fee"):`. `0` is falsy, so a fee of exactly zero
renders no fee row on either page. The screen is silent rather than showing
"Fee: 0". A genuine zero fee is therefore indistinguishable from a transaction
whose fee the screen simply chose not to draw, and any future defect that lets
an attacker drive the displayed fee to exactly zero removes the row rather than
showing an implausible number.

**Action.** Change both to `if "fee" in meta:`. Fix together with F-24 item 4.

### H-06: Confirmation results are compared by identity rather than truthiness

Several confirmation call sites test `if res is False` rather than `if not res`,
so a `None` return proceeds as though the user had confirmed:
[signmessage.py:74](../../src/apps/signmessage/signmessage.py#L74),
[label.py:41](../../src/apps/label.py#L41),
[flash.py:235](../../src/keystore/flash.py#L235),
[sdcard.py:81](../../src/keystore/sdcard.py#L81). No path was found that makes
`show_screen` return `None` today, so this is a latent fail-open pattern rather
than a live defect. It does sit on the message-signing confirmation, which F-17
turns into the firmware-authorization confirmation.

**Code at this tree.** `grep -rn "is False" src/` returns exactly the four
sites listed, plus one correct one:

```text
src/keystore/flash.py:235               if res is False:
src/keystore/sdcard.py:81               if res is False:
src/apps/label.py:41                    if res is False:
src/apps/signmessage/signmessage.py:74  if res is False:
src/hosts/usb.py:78                     if res is None or res is False:   # correct
```

**Action.** Replace the four with `if not res:`.

### H-08: Bytewords decoding does no range validation on input characters

[bytewords.py:44-46](../../f469-disco/libs/common/microur/util/bytewords.py#L44-L46),
[bytewords.py:56-99](../../f469-disco/libs/common/microur/util/bytewords.py#L56-L99):

```python
def _minus_aA(b):
    return (b-65) if b < 97 else (b-97)      # ord('A')=65, ord('a')=97

chunk = bytes([LOOKUP_TABLE[buf[1]*ALPHABET_LEN + buf[0]]])
```

`_minus_aA` never checks its range. Any byte below `'A'` — a digit, punctuation,
a control character — returns a **negative** value. The computed index into the
676-entry `LOOKUP_TABLE` then spans roughly -2619 to 5130:

- indices in -676..-1 wrap through Python negative indexing and **silently decode
  to a different byte**;
- indices outside that range raise `IndexError`;
- a table entry of -1 raises `ValueError`.

So different QR strings can decode to the same bytes, and non-alphabetic garbage
can decode "successfully". With F-28 removing the CRC check, nothing downstream
catches it.

**Code at this tree.**
[bytewords.py:44-46](../../f469-disco/libs/common/microur/util/bytewords.py#L44-L46)
has `_minus_aA` with no range check, and the `LOOKUP_TABLE` index at
[bytewords.py:56-99](../../f469-disco/libs/common/microur/util/bytewords.py#L56-L99)
is unguarded.

**Action.**

```python
def _minus_aA(b):
    if 65 <= b <= 90:
        return b - 65
    if 97 <= b <= 122:
        return b - 97
    raise ValueError("Invalid byteword character: %d" % b)
...
idx = buf[1] * ALPHABET_LEN + buf[0]
entry = LOOKUP_TABLE[idx]        # idx now provably in 0..675
if entry < 0:
    raise ValueError("Invalid byteword pair")
```

### H-09: Two bugs in the exported `nonce_function_default` wrapper

[libsecp256k1.c:328-343](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L328-L343):

```c
if(args[2] != mp_const_none){
    mp_buffer_info_t algbuf;
    mp_get_buffer_raise(args[0], &algbuf, MP_BUFFER_READ);   // args[0], not args[2]
    algo16 = algbuf.buf;
}
if(n_args > 3 && args[3]!=mp_const_none){
    mp_buffer_info_t databuf;
    if (!mp_get_buffer(args[3], &databuf, MP_BUFFER_READ)) {
        data = (void*) args[3];        // raw mp_obj_t used as a byte pointer
    }else{ data = (void*) databuf.buf; }
}
```

1. `algo16` is taken from `args[0]`, the message, rather than `args[2]`. So any
   caller passing a custom algorithm tag silently gets the wrong domain
   separation.
2. When `args[3]` is not buffer-compatible, the code casts the `mp_obj_t`
   **itself** to a pointer and hands it to
   `secp256k1_nonce_function_default`, which does
   `memcpy(keydata + 64, data, 32)`. For a small int or a qstr that is a tagged
   value, not a readable address, so this is a wild pointer dereference. For a
   heap object it silently mixes 32 bytes of adjacent GC heap into a nonce
   derivation.

This is not currently reachable: there is no caller in `src/` or in `embit`. It is
a latent memory-safety bug in a security-critical binding.

The actual signing nonce path is correct and separate. `embit/ec.py:216-230`
`PrivateKey.sign()` calls `secp256k1.ecdsa_sign(msg_hash, secret)`, which reaches
`secp256k1_ecdsa_sign(ctx, &sig, msg, sec, NULL, NULL)`, stock deterministic
RFC6979. The low-R grinding loop passes `counter.to_bytes(32,"little")` as
RFC6979 extra entropy, which is standard BIP-62 / Bitcoin Core behavior, and caps
at 200 attempts. No host-controlled data reaches nonce derivation.

**Code at this tree.**
[libsecp256k1.c:328-343](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L328-L343)
reads `algo16` from `args[0]` and casts a non-buffer `args[3]` to a raw
pointer. Not reachable — no caller in `src/` or `embit`.

**Action.**

```c
if(args[2] != mp_const_none){
    mp_buffer_info_t algbuf;
    mp_get_buffer_raise(args[2], &algbuf, MP_BUFFER_READ);   /* was args[0] */
    if(algbuf.len != 16){ mp_raise_ValueError("algo16 must be 16 bytes"); }
    algo16 = algbuf.buf;
}
if(n_args > 3 && args[3] != mp_const_none){
    mp_buffer_info_t databuf;
    mp_get_buffer_raise(args[3], &databuf, MP_BUFFER_READ);  /* raise, never cast */
    if(databuf.len != 32){ mp_raise_ValueError("data must be 32 bytes"); }
    data = databuf.buf;
}
```

### H-10: The secure-channel IV is not advanced or reset after a failed round trip

[securechannel.py:178-190](../../src/keystore/javacard/applets/securechannel.py#L178-L190):

```python
def request(self, data):
    if self.iv >= 2**16 or not self.is_open: self.open()
    ct = self.encrypt(data)                       # AES-CBC, iv = self.iv
    res = self.applet.request(self.SECURE_MSG + encode(ct))
    plaintext = self.decrypt(res)                 # raises on bad MAC/padding
    self.iv += 1                                  # only on success
```

If `decrypt()` raises — bad MAC, bad padding, an error injected by the card, or a
card pulled mid-transaction — `self.iv` is not incremented and `is_open` is not
cleared. The next request encrypts a **different** plaintext with the **same**
key and the **same** IV. Under CBC that reveals whether the two plaintexts share
a 16-byte prefix. Command plaintexts are structured (`\x03\x01` || sha256(pin),
`\x05\x00`, and so on), so the leak is a prefix-equality oracle on PIN hashes for
an attacker who can both induce the failure and observe the line.

Cross-counter replay is blocked, because the MAC covers `iv || ct`.

**Code at this tree.** In
[securechannel.py:180-195](../../src/keystore/javacard/applets/securechannel.py#L180-L195),
`self.iv += 1` is on line 192, after `self.decrypt(res)` on line 191, so a raise
leaves both `iv` and `is_open` untouched.

**Action.**

```python
def request(self, data):
    if self.iv >= 2 ** 16 or not self.is_open:
        self.open()
    ct = self.encrypt(data)
    try:
        res = self.applet.request(self.SECURE_MSG + encode(ct))
        plaintext = self.decrypt(res)
    except Exception:
        self.is_open = False      # force renegotiation, never reuse this IV
        raise
    self.iv += 1
    ...
```

### H-11: The mnemonic backup filename defaults to the first BIP-39 word

[ram.py:400-405](../../src/keystore/ram.py#L400-L405),
[flash.py:222-243](../../src/keystore/flash.py#L222-L243),
[sdcard.py:66](../../src/keystore/sdcard.py#L66):

```python
fname = "%s.txt" % self.mnemonic.split()[0]                       # plaintext export
filename = await self.get_input(suggestion=self.mnemonic.split()[0])  # encrypted save
```

For the plaintext export the file content is the whole mnemonic anyway, so the
name adds nothing. The real issue is the **encrypted** save path: the payload is
AEAD-encrypted, but the default suggested filename is the first BIP-39 word in
cleartext, so the file lands on the SD card as, for example,
`specterdiy<id>.abandon`. A user who accepts the suggestion, which is the path of
least resistance, publishes word 1 of their seed in the FAT directory entry of a
removable card. FAT directory entries also survive deletion; `os.remove` does not
scrub them.

**Code at this tree.** Three sites:

```text
src/keystore/flash.py:223   filename = await self.get_input(suggestion=self.mnemonic.split()[0])
src/keystore/sdcard.py:66   filename = await self.get_input(suggestion=self.mnemonic.split()[0])
src/keystore/ram.py:402     fname = "%s.txt" % self.mnemonic.split()[0]
```

**Action.** Default to the fingerprint:
`suggestion=hexlify(self.fingerprint).decode()`. The encrypted-save path
(`flash.py:223`, `sdcard.py:66`) is the one that matters — it currently
publishes seed word 1 in a FAT directory entry on removable media.

### H-12: The network file is unauthenticated and is read before unlock

[specter.py:121-127](../../src/specter.py#L121-L127),
[specter.py:405-411](../../src/specter.py#L405-L411). `load_network` reads
`/flash/network` with a bare `open(..., "r")` rather than through `load_aead`, so
it is neither encrypted nor authenticated, unlike every other setting. It is read
during `setup()` **before** `await self.unlock()`.

```python
def set_network(self, net):
    if net not in NETWORKS:
        net = 'main'          # silent fallback to MAINNET on garbage input
```

Anyone who can write internal flash can change the active network. Impact is
bounded, because the network name is shown in the GUI and address prefixes change
visibly. It is still unauthenticated security-relevant state whose failure mode
defaults to mainnet.

**Code at this tree.**
[specter.py:405-411](../../src/specter.py#L405-L411) uses a bare `open()`, and
[specter.py:393-395](../../src/specter.py#L393-L395) silently falls back to
mainnet on garbage input.

**Action.** Route through `load_aead`/`save_aead` under `keystore.settings_key`
like every other setting, and move the read after `unlock()`. If a pre-unlock
network hint is genuinely needed, treat it as untrusted display state and
re-derive the authoritative value after unlock.

### H-13: All UR cross-part validation is written with bare `assert`

Every consistency check in the `microur` decoder is an `assert`: `ur_type`,
`seq_num`, `seq_len`, `msg_len`, `checksum`, `payload_len`, the `readinto` length
in `_reduce`, the CBOR header tag, and the one CRC check that does exist
([decoder.py:46-70](../../f469-disco/libs/common/microur/decoder.py#L46-L70),
[util/ur.py:11-20](../../f469-disco/libs/common/microur/util/ur.py#L11-L20),
[util/ur.py:31-51](../../f469-disco/libs/common/microur/util/ur.py#L31-L51),
[util/cbor.py](../../f469-disco/libs/common/microur/util/cbor.py),
[util/bytewords.py:62-90](../../f469-disco/libs/common/microur/util/bytewords.py#L62-L90)).

The current build does **not** strip them. `MPY_CROSS_FLAGS` is only
`-march=armv7m` (`f469-disco/micropython/ports/stm32/Makefile:142`), and no `-O`
flag is passed to `mpy-cross` anywhere in the Makefile, `build_firmware.sh`, the
Dockerfile, or the manifests. So `mpy-cross` opt_level stays 0, `__debug__` is
True, and the asserts are compiled in. Note that `COPT += -Os -DNDEBUG` in the
same Makefile affects C `assert()`, not Python asserts.

The finding is fragility. The entire hostile-input validation layer of the
device's largest host-facing parser is one build flag (`mpy-cross -O`) away from
disappearing silently, and no test would catch it. That makes it one of the better
hiding places in this codebase for a malicious maintainer.

**Code at this tree.** `grep -n "assert" decoder.py` returns 12 hits covering
`ur_type`, `seq_num`, `seq_len`, `msg_len`, `checksum`, `payload_len`, the
`readinto` length, and the part-set completeness check. The build does not
currently strip them:
[ports/stm32/Makefile:142](../../f469-disco/micropython/ports/stm32/Makefile#L142)
sets `MPY_CROSS_FLAGS = -march=armv7m` only, and `grep -rn "mpy-cross" Makefile
build_firmware.sh` shows no `-O` flag anywhere.

**Action.** Convert every security-relevant `assert` in `microur` to an explicit
`raise URError(...)`, and add a boot-time tripwire so the invariant cannot
silently regress:

```python
# main.py, early
if not __debug__:
    raise RuntimeError("Firmware built with asserts stripped - refusing to run")
```

### H-14: Keystore backend naming and a destructive no-PIN fallback

Two related storage-layer notes.

1. **A seed stored on the SD card is labelled "Internal storage".**
   `SDKeyStore.NAME = "Internal storage"`
   ([sdcard.py:22](../../src/keystore/sdcard.py#L22)), and that `NAME` is what
   the PIN screen subtitle renders (`ram.py:311-313`). A user whose seed is on
   the SD card sees "using internal storage" at every unlock.
2. **Backend fallback is visible but not announced, and one variant is
   destructive.** `Specter.select_keystore`
   ([specter.py:97-113](../../src/specter.py#L97-L113)) takes the first backend
   whose `is_available()` is True. `MemoryCard.is_available()` wraps the whole
   connect, select, and open-channel sequence in `try/except: return False`, so
   any card fault, absence, or comms error silently selects `SDKeyStore`. On a
   smartcard-primary device that never set a flash PIN, `is_pin_set` is then
   False and `unlock()` goes straight to `setup_pin()`. An attacker holding only
   the device is invited to **choose a PIN with no authentication**. `_set_pin`
   then finds `enc_secret is None` and overwrites `/flash/keystore/enc_secret`
   with a fresh random key, permanently destroying any seed previously stored on
   flash or SD. See also F-07 and F-22.

**Code at this tree.**
[sdcard.py:21](../../src/keystore/sdcard.py#L21) has
`NAME = "Internal storage"`, identical to
[flash.py:29](../../src/keystore/flash.py#L29). `Specter.select_keystore` at
[specter.py:97-113](../../src/specter.py#L97-L113) takes the first available
backend, `MemoryCard.is_available()` swallows every fault, and `_set_pin` at
[flash.py:182-186](../../src/keystore/flash.py#L182-L186) overwrites
`enc_secret` with fresh randomness when it finds `None`.

**Action.**

1. Rename: `SDKeyStore.NAME = "SD card"`.
2. Before `setup_pin()` on a device that has a smartcard-era `enc_secret` or any
   stored seed, require an explicit destructive-action confirmation:

   ```python
   if self.has_stored_seed() and self.enc_secret is None:
       if not await show_screen(Prompt(
               "WARNING",
               "Setting a new PIN here will PERMANENTLY DESTROY the seed "
               "stored on this device. Continue?")):
           raise KeyStoreError("Aborted")
   ```
3. Announce backend fallback on screen rather than switching silently.

### H-15: Three small robustness items

Grouped because none justifies its own finding, but each is worth a line.

**1. The PIN HMAC is fed a `str` in one place and `bytes` in the other.**

```python
# src/keystore/flash.py:169-171  (_set_pin)
self.pin = hmac.new(key=key, msg=pin,          digestmod="sha256").digest()
# src/keystore/flash.py:126-127  (_unlock)
pin_hmac = hmac.new(key=key, msg=pin.encode(), digestmod="sha256").digest()
```

`pin` must be a `str`, because both functions call `pin.encode()` elsewhere. So
`_set_pin` passes a `str` into `hmac` while `_unlock` passes `bytes`. This only
works if the frozen MicroPython `hmac`/`hashlib` accepts a `str` and encodes it
the same way `.encode()` does. It is not a vulnerability today, because
`_set_pin` calls `_unlock` at the end, so a mismatch would fail loudly on the
first PIN setup. It is exactly the kind of latent encoding inconsistency that
becomes a PIN bypass if the underlying `hmac` implementation ever changes its
`str` handling. Make both sides pass `bytes`.

**2. UR `seq_len` is unbounded, so one QR frame can exhaust RAM or wedge the
UI.** [util/ur.py:9-25](../../f469-disco/libs/common/microur/util/ur.py#L9-L25)
parses `seq_len` from the human-readable part with no upper bound. Only
`MAX_HRP_LEN` of 30 characters limits it, so roughly seven digits. Downstream,
`choose_degree` builds `RandomSampler([1.0/i for i in range(1, seq_len+1)])`, a
list of up to about 10^7 floats, and both `part_sets_is_complete` and `progress`
iterate `range(seq_len)`. `progress` is called from the GUI refresh loop, so the
cost is `O(seq_len × |part_sets|)` per frame. This is availability only, with no
path to funds. Clamp `seq_len` to something sane, for example 1000.

**3. `bip32.parse_path` imposes no depth limit.**
[bip32.py:292-299](../../f469-disco/libs/common/embit/src/embit/bip32.py#L292-L299) accepts
a path of any length, and `keystore.get_xpub(path)` then performs one HMAC-SHA512
per level. A host sending `xpub m/0/0/0/...` with 10^5 levels wedges the device
for minutes. Serialization is safe: `bip32.py:85` `bytes([self.depth])` raises for
depth > 255, so there is **no** one-byte depth wraparound producing a forged
"master" xpub. But all the work happens before that raise. Cap the depth at around
10. Reachable through F-05, which needs no confirmation.

Item 1 belongs to this repository, item 2 to bundled `microur`, and item 3 to
the `embit` submodule.

**Code at this tree.**

1. [flash.py:178](../../src/keystore/flash.py#L178) passes a `str`, while
   [flash.py:128](../../src/keystore/flash.py#L128) passes `bytes`.
2. [util/ur.py:9-25](../../f469-disco/libs/common/microur/util/ur.py#L9-L25)
   parses `seq_len` with no upper bound.
3. [bip32.py:292-299](../../f469-disco/libs/common/embit/src/embit/bip32.py#L292-L299)
   returns `[_parse_der_item(e) for e in arr]` with no cap.

**Action.**

1. `self.pin = hmac.new(key=key, msg=pin.encode(), digestmod="sha256").digest()`.
2. `if seq_len < 1 or seq_len > 1000: raise URError("Invalid seq_len")`.
3. Cap depth in `parse_path`:

   ```python
   MAX_DERIVATION_DEPTH = 10
   if len(arr) > MAX_DERIVATION_DEPTH:
       raise ValueError("Derivation path too deep: %d" % len(arr))
   ```

   Reachable through F-05, which needs no confirmation, so enforce it in
   [xpubs.py](../../src/apps/xpubs/xpubs.py) too rather than relying on the
   dependency.

### H-16: The rangeproof rewind arena bound uses an ABI-mismatched length

The declaration and the definition of
`secp256k1_rangeproof_rewind_preallocated` disagree on the final parameter. The
header uses `uint64_t allocated_len`, and `rangeproof_preallocated_impl.h` uses
`intptr_t allocated_len`
([rangeproof_preallocated.h:9-13](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated.h#L9-L13),
[rangeproof_preallocated_impl.h:491-495](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated_impl.h#L491-L495)).
The files compile in separate translation units, so the compiler does not
diagnose the mismatch.

On 32-bit AAPCS the caller writes the aligned 64-bit value at stack offsets 48-55
while the callee reads a 32-bit value at offset 44. Targeted ARM code generation
confirmed that the callee reads uninitialized stack residue as the arena bound.
The simulator does not expose the defect, because both types are eight bytes
there.

This broken check is not currently an overflow. The fixed arena carve-outs total
about 33.5 KiB against the 1 MiB SDRAM arena, independent of hostile input. A
wrong bound can fail closed as `RewindError`, or pass for the wrong reason, but
it cannot make the current fixed carve-outs exceed the real arena.

**Code at this tree.**
[rangeproof_preallocated.h:9-13](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated.h#L9-L13)
declares `uint64_t allocated_len`;
[rangeproof_preallocated_impl.h:491-495](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated_impl.h#L491-L495)
defines `intptr_t allocated_len`. Separate translation units, so no diagnostic.

**Action.** Use one type (`size_t`) in both, `#include` the public declaration
in the translation unit that compiles the definition so the compiler can
diagnose future drift, and restore warnings-as-errors for this user module. Fix
this **before** F-31, since F-31's proposed arena bound relies on this parameter
being read correctly.

### H-17: Unreachable surjection-proof copy loops scale their index twice

Three list-copy branches allocate `n_inputs * element_size` bytes and then add
`i * element_size` to an already typed pointer before `memcpy`
([libsecp256k1.c:1300-1304](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1300-L1304),
with equivalent code at `:1376-1380` and `:1438-1442`). The compiler scales
again: a 32-byte tag at `i=1` is written about 1 KiB past a 64-byte two-element
allocation, and the 64-byte generator variant writes about 4 KiB past its
allocation. The allocation is also unchecked, and non-buffer objects are cast to
`mp_obj_list_t` with no type guard.

PATH-20 establishes that production code never enters these branches: in-tree
callers pass joined `bytes`, and the list-argument call sites are commented out.

**Code at this tree.**
[libsecp256k1.c:1300-1304](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1300-L1304)
and the equivalent code at `:1376-1380` and `:1438-1442` add
`i * element_size` to an already typed pointer. Not reachable — the
list-argument call sites are commented out at
[liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454).

**Action.** Change `ptr + i * element_size` to `ptr + i`, check the `gc_alloc`
result before use, and validate the argument is actually a list before casting
to `mp_obj_list_t`.

### H-18: Every QR payload is printed to stdout unconditionally

`QRCode._set_text` ends with a bare `print(text)`
([qrcode.py:290-296](../../src/gui/components/qrcode.py#L290-L296)), while a
nearby diagnostic is correctly simulator-gated. So every QR payload reaches
stdout, including mnemonic and SeedQR exports, BIP85 mnemonics, xprvs, WIF keys,
entropy, and the SLIP77 master blinding private key.

On a correctly booted production image the sink is inert: this board has no UART
REPL, and `boot.py` clears both dupterm slots. It becomes live in the debug image
and in F-32's boot-failure state, where the CDC REPL stays attached.

**Code at this tree.**
[qrcode.py:290-292](../../src/gui/components/qrcode.py#L290-L292), plus a second
instance at [qr.py:553](../../src/hosts/qr.py#L553) (`print(prefix)`).

**Action.** Delete both, or gate them:

```python
if platform.simulator:
    print(text)
```

### H-19: Host-supplied wallet names reach a recolor-enabled label

The descriptor half of an `addwallet <name>&<descriptor>` payload has its
checksum suffix removed, but the host-controlled name does not
([wallet.py:294-308](../../src/apps/wallets/wallet.py#L294-L308)). That name is
persisted and later concatenated into `WalletScreen.title`, which enables LVGL
recolor markup
([screens.py:19-24](../../src/apps/wallets/screens.py#L19-L24)). The
address-verification screen is reachable from both `VERIFY_ADDRESS` and
`showaddr`.

The impact is bounded to recoloring or hiding wallet-name title text. The address
itself uses a non-recolored message label, LVGL's parser only copies a complete
six-character color parameter it has already traversed, and the initial import
screen displays the name without recolor.

**Code at this tree.**
[wallet.py:294-302](../../src/apps/wallets/wallet.py#L294-L302) strips the
checksum from the descriptor half only:

```python
name = "Untitled"
if "&" in desc:
    arr = desc.split("&")
    desc = arr[-1]
    name = "&".join(arr[:-1])      # host-controlled, unsanitized
```

`desc.split("#")[0]` on line 308 sanitizes the descriptor, not the name.

**Action.**

```python
def _sanitize_name(name):
    name = "".join(c for c in name if 0x20 <= ord(c) <= 0x7E and c != "#")
    return name[:32] or "Untitled"
...
w.name = _sanitize_name(name)
```

Or render the edit glyph in a separate styled label so the title does not need
recolor enabled at all.

### H-20: Two fail-closed start-up-code robustness defects

Both defects are in the reset-path code that selects a bootloader copy. Neither
is reachable without pre-existing flash write, and both end in a halt rather than
attacker-controlled execution.

**Out-of-bounds version read.** If neither bootloader copy has a valid integrity
record, `selected` stays `-1`, but the fallback loop evaluates `version[selected]`
([startup.c:209-244](../../bootloader/platforms/stm32f469disco/startup/startup.c#L209-L244)).
The following integrity re-check fails for the same invalid records and the device
reaches its normal fatal "no bootloader" path, so no attacker-controlled value or
authorization result depends on the read. Guard `selected >= 0` before the loop.

**Unbounded start-up flash syscalls.** The start-up implementations of
`blsys_flash_read` and `blsys_flash_crc32` use raw addresses without the
`check_flash_area()` guard present in the bootloader implementations
([startup.c:47-61](../../bootloader/platforms/stm32f469disco/startup/startup.c#L47-L61),
[bl_syscalls.c:396-402](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L396-L402)).
An already forged integrity record can make CRC verification walk past flash and
bus-fault, but forging that record already requires F-25's flash-write
prerequisite.

**Code at this tree.** The out-of-bounds `version[selected]` read is at
[startup.c:209-244](../../bootloader/platforms/stm32f469disco/startup/startup.c#L209-L244)
and the unguarded `blsys_flash_read`/`blsys_flash_crc32` at
[startup.c:47-61](../../bootloader/platforms/stm32f469disco/startup/startup.c#L47-L61).
Both end in a halt, not attacker-controlled execution.

**Action.**

1. `if (selected < 0) { fatal_error("No valid bootloader copy"); }` before the
   fallback loop.
2. Add `check_flash_area()` to the start-up flash syscalls, matching
   [bl_syscalls.c:396-402](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L396-L402),
   and bound `pl_size` against the selected section in shared integrity code.

### H-21: The GUI blinding-key export displays the private key without confirmation

Selecting "Blinding key" from the main menu immediately renders the SLIP77 master
blinding private key as text and QR, with no `Prompt`, warning, cancel path, or
PIN re-entry
([blindingkeys/app.py:31-36](../../src/apps/blindingkeys/app.py#L31-L36),
[qralert.py:18-21](../../src/gui/screens/qralert.py#L18-L21)). The menu label
signals intent but does not tell the user that a private key, and its unblinding
and privacy consequences, will be exposed before it happens. The same app's host
path does provide an explicit warning and confirmation.

Severity is Low, because this key grants unblinding and privacy loss rather than
spending authority, and the GUI path requires physical use of an unlocked device.
H-18 records the additional stdout sink.

**Code at this tree.**
[blindingkeys/app.py:31-36](../../src/apps/blindingkeys/app.py#L31-L36) renders
the key immediately:

```python
async def menu(self, show_screen, show_all=False):
    await show_screen(QRAlert("Standard SLIP-77 blinding key",
            self.keystore.slip77_key.wif(NETWORKS[self.network]),
            note="Blinding private key allows your software wallet\nto track your balance."))
    return False
```

No `Prompt`, no warning, no cancel path, no PIN re-entry — in contrast to the
same app's host path, which does prompt.

**Action.** Gate the GUI path on the same prompt the host path uses, and require
PIN re-entry before display, matching how mnemonic display is handled.

### H-22: The STM32 fork removed `-Wall` while keeping `-Werror`

Fork commit `0184de6c3` ("Enable secp256k1") removed `-Wall` from the STM32
`CFLAGS` while keeping `-Wpointer-arith -Werror`
([ports/stm32/Makefile:93](../../f469-disco/micropython/ports/stm32/Makefile#L93)).
This silently disables warning classes across the interpreter, the STM32 HAL, and
all user C modules. H-23's operator-precedence defect is exactly the
`-Wparentheses` class that `-Wall -Werror` would have rejected.

**Code at this tree.**
[ports/stm32/Makefile:93](../../f469-disco/micropython/ports/stm32/Makefile#L93):

```make
CFLAGS = $(INC) -Wpointer-arith -Werror -std=gnu99 -nostdlib $(CFLAGS_MOD) $(CFLAGS_EXTRA)
```

No `-Wall`, no `-Wextra`.

**Action.** Restore `-Wall` (ideally `-Wextra`) and work through the resulting
diagnostics under the release compiler. Expect H-23 (`-Wparentheses`) and
possibly F-34 to surface immediately. Stage it: add `-Wall -Wno-error=...` for
the noisy categories first, then tighten. This is build-assurance debt rather
than a separate exploitation primitive.

### H-23: Smartcard PPS checksum validation accepts 255 of 256 values

The T=1 PPS response condition omits parentheses:

```c
0U == buf[pps_ppss] ^ buf[pps_pps0] ^ buf[pps_pck]
```

Equality binds before XOR, and the preceding checks force the first two bytes to
`0xFF` and `0x01`, so the expression accepts every PCK byte except `0x01` instead
of accepting only the correct `0xFE`
([t1_protocol.c:1020-1030](../../f469-disco/usermods/scard/t1_protocol/t1_protocol.c#L1020-L1030)).
A hostile or corrupted card can therefore advance protocol negotiation with an
invalid checksum. No memory-safety, secret-release, or funds path was shown from
the negotiated state.

**Code at this tree.**
[t1_protocol.c:1020-1030](../../f469-disco/usermods/scard/t1_protocol/t1_protocol.c#L1020-L1030)
holds the unparenthesized expression.

**Action.**

```c
0U == (buf[pps_ppss] ^ buf[pps_pps0] ^ buf[pps_pck])
```

Add positive and negative PPS test vectors so this cannot regress.

### H-24: Device wipe unlinks QSPI files but does not erase their blocks

`platform.wipe()` documents internal flash at blocks 256-447 and QSPI at
448-33215, recursively unlinks `/flash` and `/qspi`, then overwrites only
`range(256, 450)` ([platform.py:249-273](../../src/platform.py#L249-L273)). That
erases internal flash plus two QSPI blocks, and leaves 32,766 QSPI blocks
physically recoverable. FatFs unlink and reformat do not scrub their contents.

Most security-sensitive QSPI state is authenticated and usually encrypted under
keys derived from the internal-flash secret, which wipe does destroy. Residual
plaintext still includes labels, file names, sizes, existence, and other
metadata. No mnemonic recovery path was shown from QSPI alone.

**Code at this tree.** At
[platform.py:263-274](../../src/platform.py#L263-L274), internal flash (blocks
256-447) plus two QSPI blocks are erased; 32,766 QSPI blocks are left.

**Action.** Either erase the full external device —

```python
for i in range(256, 33216):
    f.writeblocks(i, os.urandom(block_size))
    gc.collect()
```

with a progress screen, since this will take a while — or document and test an
explicit cryptographic-erasure model that states plaintext QSPI metadata
(labels, file names, sizes, existence) is intentionally retained.

### H-25: A Liquid p2pkh output aborts the confirmation screen with an uncaught `IndexError`

The `ver = data[0] % 0x50` reduction described in F-35 is not only lossy; for
some leading bytes it produces a value outside the 32-entry Bech32 alphabet. A
p2pkh scriptPubKey starts `0x76`, and `0x76 % 0x50 = 38`, so `bech32_encode`'s
`CHARSET[d]` lookup raises `IndexError: string index out of range`
([blech32.py:64-67](../../f469-disco/libs/common/embit/src/embit/liquid/blech32.py#L64-L67),
[addresses.py:19-30](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L19-L30)).
Reproduced on both the confidential and unconfidential Liquid branches.

Unlike the Bitcoin manager, which wraps address generation in `try/except` and
falls back to hex ([manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99)),
the Liquid override calls `liquid_address` unguarded
([liquid/manager.py:70-74](../../src/apps/wallets/liquid/manager.py#L70-L74)), so
the exception propagates out of `preprocess_psbt`. It is caught only by the
top-level handler in `src/specter.py:87-93`, which shows an error popup. The
consequence is a host-triggerable abort of the Liquid signing flow: no
memory-safety effect, no unauthorized signature, and no device reset. It is the
same missing `script_type()` gate as F-35, and the same change fixes it.

Same root cause as F-35, on both the encoder and the call site.

**Action.** Fixed by F-35's `script_type()` gate. Additionally wrap
`LWalletManager.get_address` in the Bitcoin manager's `try/except` so any future
encoder exception degrades to a labelled hex fallback rather than aborting
`preprocess_psbt`.

### H-26: `address_to_scriptpubkey` validates neither payload length nor network, and is unreachable here

`base58.decode_check`
([base58.py:69-79](../../f469-disco/libs/common/embit/src/embit/base58.py#L69-L79))
validates the four-byte double-SHA256 checksum and the alphabet, both confirmed
against corrupted, truncated, out-of-alphabet, and empty inputs. It does not
validate the *length* of what remains, and its only address-shaped consumer does
not either. `address_to_scriptpubkey`
([script.py:174-195](../../f469-disco/libs/common/embit/src/embit/script.py#L174-L195))
emits a hardcoded `\x14` push opcode regardless:

```
hash160 field 19 B -> scriptpubkey 24 B (push opcode says 20)  script_type=None
hash160 field 20 B -> scriptpubkey 25 B                        script_type=p2pkh
hash160 field 21 B -> scriptpubkey 26 B (push opcode says 20)  script_type=None
hash160 field 32 B -> scriptpubkey 37 B (push opcode says 20)  script_type=None
```

Two further defects in the same function: it iterates `NETWORKS.values()` and
accepts any network's version byte, with no network parameter to constrain it, so
a testnet `p2pkh` address decodes without complaint. And when the version byte
matches no network at all, it falls off the end of the loop and returns `None`
silently rather than raising, because the bare `except:` on line 184 is entered
only when `decode_check` itself fails.

None of this is reachable in this firmware. `Script.from_address` and
`address_to_scriptpubkey` have no caller in `src/`, `boot/`, or the rest of the
`embit` tree; the device converts descriptors to scripts, never address strings
to scripts. See PATH-37. It is kept here as an upstream hardening item, because
the code ships on the device and is one import away from becoming reachable.

**Code at this tree.**
[script.py:174-195](../../f469-disco/libs/common/embit/src/embit/script.py#L174-L195)
emits a hardcoded `\x14` push regardless of payload length, iterates
`NETWORKS.values()` with no network parameter, and falls off the end of the loop
returning `None` rather than raising. The bech32 branch *does* validate `ver`
and length (lines 188-191) — only the base58 branch is unvalidated. Not
reachable from this firmware.

**Action.** Upstream hardening only:

```python
def address_to_scriptpubkey(addr, network=None):
    nets = [network] if network else list(NETWORKS.values())
    try:
        data = base58.decode_check(addr)
    except Exception:
        ...  # bech32 branch
    else:
        if len(data) != 21:
            raise EmbitError("Invalid base58 address payload length")
        prefix = data[:1]
        for net in nets:
            if prefix == net["p2pkh"]:
                return Script(b"\x76\xa9\x14" + data[1:] + b"\x88\xac")
            elif prefix == net["p2sh"]:
                return Script(b"\xa9\x14" + data[1:] + b"\x87")
        raise EmbitError("Unknown address version byte")
```

Also replace the bare `except:` on line 184 so a base58 failure is
distinguishable from a bech32 address.

### H-27: The displayed-scope-to-signed-output invariant is enforced only in the dependency

The property that makes the confirmation screen meaningful — that the `(value,
script_pubkey)` the device *displays* for an output is the one the signature
*commits to* — is currently enforced in exactly one place: `embit`'s refusal of
v2-only scope fields inside a v0 PSBT
([psbt.py:162-163](../../f469-disco/libs/common/embit/src/embit/psbt.py#L162-L163),
[psbtview.py:352-354](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L352-L354)).

This repository does not check the invariant itself. The wallet manager builds
confirmation metadata from scope data
([manager.py:721-768](../../src/apps/wallets/manager.py#L721-L768)) and never
compares it against the global transaction output that `PSBTView.vout` will
hash. `grep -rn "script_pubkey" src/apps/wallets/manager.py` returns only the
two address-rendering sites at
[manager.py:96-99](../../src/apps/wallets/manager.py#L96-L99).

Nor is the dependency's behaviour pinned by a test here.
`grep -rln 'PSBTv2\|V2_FIELDS' test/ src/` returns nothing, so a submodule bump
that regressed the guard would not fail any test in this repository.

Two consequences, neither exploitable today:

1. The device's central display invariant is owned by an upstream project, and
   this tree tracks that project through a mutable-branch fork pin (§1.2).
2. There is no defense in depth. Any *future* parser defect that lets scope data
   diverge from the global transaction — not only the version-field class —
   reaches the confirmation screen unchecked.

**Action plan**

1. Add the equality check in code this project owns. In
   [manager.py:721-768](../../src/apps/wallets/manager.py#L721-L768), for each
   output index `i`:

   ```python
   gout = psbt.vout(i)                      # authoritative global tx output
   if out.value != gout.value or out.script_pubkey.data != gout.script_pubkey.data:
       raise WalletError("Output %d differs from the transaction being signed" % i)
   ```

   Make the mismatch fatal rather than normalizing it away.
2. Add the same check on the input side: every scope txid, vout, and sequence
   must equal the matching global transaction input.
3. Add regression tests that pin the rejection. Craft v0 PSBTs carrying each
   v2-only key (`0x03`, `0x04` on outputs; `0x0e`, `0x0f`, `0x10` on inputs) in
   several field orders, including duplicate `0x0f` records and over-long values
   for `0x0f` and `0x10`, and assert rejection before confirmation. The existing
   `test/tests_native/test_change_security.py` is the natural home.
4. Add an end-to-end test that compares displayed metadata with the signed
   transaction, including outputs classified as change.

## 8. Assessment by security domain

### 8.1 Malware and backdoor assessment

A sweep across `src/`, `boot/`, `embit`, `microur`, and `bcur.py` looked for
`eval`, `exec`, `compile`, `__import__`, `importlib`, reflection, `subprocess`,
`os.system`, `popen`, sockets, `urllib`, `requests`, `http`, and hardcoded key,
seed, mnemonic, or address constants. No malicious payload and no covert network
primitive exists in the reviewed Python source. That negative does **not** mean
Python loading is closed: ordinary `import config` resolves executable code from
writable QSPI before PIN entry (F-15).

Every static-indicator hit is accounted for:

- `src/helpers.py:110,118-119` `load_apps()`: `__import__(module)` then
  `__import__("apps.<name>")`, where `<name>` comes from `apps.__all__`
  ([apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11)), a static literal
  list of nine frozen modules. The argument is never attacker-influenced and the
  modules are frozen into the image, not loaded from the filesystem. Benign.
- `src/hosts/qr.py:458` `getattr(self.manager, "keystore", None)`: a presence
  check with a literal name. Benign.
- `descriptor/*.py` `.compile()` is miniscript-to-Script compilation, unrelated
  to Python `compile()`. Benign.
- Every other hit is a URL inside a comment.

There is no network code on the device at all: no socket, no TCP/IP stack in the
disco manifest, no Wi-Fi, and no Bluetooth hardware. The only egress channels are
USB VCP, the QR display, and the SD card, all audited above as deliberate
channels.

The constants sweep found exactly **one** security-relevant magic value:
`b"\xcc" * 32` in
[memorycard.py:168-171](../../src/keystore/memorycard.py#L168-L171) and
[memorycard.py:184-186](../../src/keystore/memorycard.py#L184-L186), the
documented "plaintext" smartcard storage key. It is classified suspicious but
explained; see F-07 and F-22. There are no hardcoded addresses, xpubs, seeds,
mnemonics, domains, or IPs. `ec.NUMS_PUBKEY` is the standard BIP-341
nothing-up-my-sleeve point, and it is correctly surfaced to the user as "NUMS
key: Nobody knows private key".

Simulator-only behavior does not bypass production keystore or signing
protections. Debug-build separation is real but not cryptographic.
`boot/debug/boot.py` has the three lines that disable USB and the REPL commented
out, so a debug image is an unauthenticated MicroPython shell over USB with full
access to the keystore, and `pyb.main("hardwaretest.py")` redirects boot. The
separation is correct as far as it goes: a distinct manifest, a distinct output
name (`bin/debug.bin` versus `bin/specter-diy.bin`), and no reference in
`build_firmware.sh`. But **nothing cryptographic** distinguishes the two images: a
debug image signed with the vendor keys is an otherwise legitimate image. Its
version tag (`0100900001`, v1.9.0-rc1) is lower than main's (`0100900099`,
v1.9.0), and the version floor rejects it through the supported upgrade path
(PATH-26).

Upstream comparison found no substituted or tampered dependency anywhere it could
be checked. The one blob that could hide a cryptographic backdoor with no
reviewable source — the secp256k1 generator table on the signing path — was
recomputed entry by entry and matches exactly.

The build and dependency chain can still hide changes that a superficial review
would miss. Ranked, the best places are:

1. `MPY_CROSS_FLAGS += -O`, where one flag silently deletes every assert-based
   hostile-input check in the UR decoder (H-13);
2. module search and CWD changes that route a normal import to writable storage
   (F-15);
3. warning-flag removal that lets native defects compile silently (H-22);
4. provenance-free flattened MicroPython dependency trees (D-02).

Those gaps prevent a strong conclusion that a clean source tree must produce a
trustworthy release binary.

History review covered all 63 MicroPython fork-only commits and the
security-sensitive regions of project history. It found no deliberate backdoor and
no reverted upstream check, but it did find security changes filed under
unrelated subjects: `0184de6c3` ("Enable secp256k1") removed `-Wall`, and the QSPI
CWD and import behavior that enables F-15 was introduced as platform work.

At this release tree there is no CI workflow, no `CODEOWNERS`, and no
in-repository security policy. Many tags are lightweight, and commit `gpgsig`
presence could not be turned into a trusted-signer conclusion in this
environment.

### 8.2 Cryptographic assessment

- ECDSA uses deterministic RFC6979. Low-R retries vary deterministic extra data
  and check the native nonce-function result.
- Message signatures are domain-separated from transaction signatures, but they
  share a domain with firmware authorization (F-17).
- No direct hostile control of ECDSA nonces was found.
- The generator precomputation table compiled into the signing path was
  recomputed and verified exact.
- The hardware RNG driver fails open (F-18). Context randomization, Schnorr
  auxiliary randomness, and fail-closed secp256k1 callbacks still need
  improvement or target validation.
- The native binding's fixed-width inputs are length-checked. The
  variable-length streaming rewind path is not: F-31 is a pre-confirmation
  out-of-bounds write. H-16 and H-17 are non-live hardening defects in the same
  area.
- The custom preallocated rangeproof implementation and its arena carve-outs were
  read in full. Target SDRAM adjacency and timing/side-channel behavior remain
  dynamic questions.

### 8.3 Private-key and secret-memory assessment

No normal host command returns the root private key, the mnemonic, the identity
key, a child private key, or a signing nonce. Mnemonic display and BIP85 are
GUI-only. The SLIP77 host command is explicitly warned and confirmed (PATH-07).
The GUI path immediately displays the same master blinding private key with no
consent screen (H-21), and H-03 covers wallet descriptor export.

At-rest seed confidentiality can fail after internal-flash readout, through F-06.
Smartcard-origin seed integrity can fail through F-07. Static inspection did not
establish RAM remnants after shutdown, SDRAM erase behavior, PIN or signing
timing, power analysis, or fault injection.

`lock()` is authorization state, not erasure. All three keystore families leave
the mnemonic, root, SLIP77 key, identity key, device secret, `pin_secret`, and
`enc_secret` as live instance attributes. Host and menu gating makes post-lock
signing unreachable (PATH-22), but a locked running process still contains
decrypted key material. Only wipe or reboot ends that process lifetime.

### 8.4 Transaction-signing assessment

The Bitcoin display/signing boundary is broken in two places, neither of them a
parser override. F-03 breaks it in the value-destruction direction: an input
amount that was never authenticated drives the displayed fee, and the loss is
paid to a miner. F-04 breaks signing authorization itself: a derived key signs
without any proof that its public key is in the input script.

The scope the device displays is the scope the global transaction carries —
`embit` rejects v2-only scope fields in a v0 PSBT — but that invariant lives
entirely in the dependency and is pinned by no test here (H-27). Descriptor
change ownership re-derives and compares scripts and is sound as long as the
scope it compares is authentic (PATH-02).

A user can also approve a descriptor that contains an attacker key. The descriptor
confirmation identifies device, external, and NUMS keys, but it cannot protect a
user who ignores the displayed policy. That is a user-confirmation limit, not a
parser bypass.

Message signing is confirmed and domain-separated from *transaction* signatures,
so a Bitcoin Signed Message signature cannot be reused as a transaction
signature. The 25-byte constant prefix occupies exactly the region a BIP-143
preimage uses for `nVersion` plus the first 21 bytes of `hashPrevouts`, and that
a legacy sighash preimage uses for `nVersion`, the input count, and the first 20
bytes of the first outpoint txid. Forcing either to equal
`"coin Signed Message:\n"` needs roughly a 2^168 preimage on double-SHA256 or on
a real txid. The length prefix is applied to the exact bytes that are hashed, so
no length-extension or ambiguity trick is available.

Message signing is **not** separated from firmware authorization: the bootloader
uses the identical construction, so the same primitive that signs a user message
signs a firmware release (F-17). The confirmation itself is unreliable: a NUL byte
in the message truncates the screen but not the signature (F-21). The derivation
path is unbounded and fully host-controlled, and the returned signature is
**recoverable**, so one confirmation also leaks the public key at any path the
attacker names.

Xpub and fingerprint export lack confirmation (F-05), and `getrandom` returns up
to 1000 bytes with no confirmation (F-14). `addwallet`, `setlabel`, `slip77`, and
`bip39:` mnemonic import require confirmation. Several confirmation sites compare
the result with `is False` rather than truthiness (H-06). Liquid input display
integrity is broken by F-11, and Liquid asset naming by F-23. The default Bitcoin
confirmation view is itself incomplete (F-24).

On the **address** half of display-to-output correspondence the two networks
diverge. On Bitcoin the correspondence holds inside the encoder: the displayed
string is derived from the parsed `script_pubkey` and from nothing else, no PSBT
record carries an address, and the encoding is deterministic and gated by exact
script-type matching (PATH-39, PATH-35, PATH-34). What breaks the correspondence
on Bitcoin is not the encoder but F-24 and F-19, which govern whether the
string is on screen at the moment of confirmation. The encoder itself is
sound.

On Liquid the encoder breaks it. F-35 makes the mapping from scriptPubKey to
confidential address neither injective nor total, so an address the user verified
character by character does not identify the script being signed. Address
*verification* (`showaddr` and the `index=` command) is sound in the way that
matters most — the host cannot cause an address it chose to be presented as the
device's own, because the comparison is against a device-derived value (PATH-38) —
but it only ever checks branch 0, and its Liquid unconfidential half is unsound
for non-v0 descriptors (F-36).

There is also a **mnemonic-import fallback**. When no app claims a host stream,
`process_host_request` falls through to `maybe_import_mnemonic`
([specter.py:577-604](../../src/specter.py#L577-L604),
[specter.py:606-634](../../src/specter.py#L606-L634)), which offers to make
attacker-supplied bytes the device's active seed. It **is** confirmed — a
`MnemonicPrompt` is shown — so this is not an unconfirmed import. The problem is
that it is a *fallback*, reached by accident on data the device could not
classify, and the "binary" branch accepts any 16-32 byte blob. That is the shape
of a seed-substitution phishing attack. The menu already has an explicit "Import
recovery phrase" entry, and host streams should not be interpreted as mnemonics
outside it.

### 8.5 Parser assessment

The most consequential parser root cause is accepting PSBT v2-only fields in v0
scopes. The unbounded `non_witness_utxo` value parse causes cross-pass
desynchronization. Legacy animated QR accepts invalid indexes and weakly binds
frames. The UR side adds a second parser weakness: the fountain decoder never
verifies any checksum (F-28), the bytewords decoder silently maps
out-of-alphabet characters to wrong bytes (H-08), and all of that validation is
written with bare `assert` (H-13). No reviewed parser defect independently
establishes code execution.

One parser that **holds** is descriptor handling. `Descriptor.owns()`
([descriptor.py:204-233](../../f469-disco/libs/common/embit/src/embit/descriptor/descriptor.py#L204-L233))
re-derives the descriptor at the claimed index and compares the resulting
scriptPubKey against the scope's. `Wallet.fill_scope`
([wallet.py:206-226](../../src/apps/wallets/wallet.py#L206-L226)) then
**overwrites** `witness_script` and `redeem_script` with the device-derived
versions, so the scripts that get signed come from the device's own descriptor,
not the host's. `Wallet.get_descriptor` bounds both the branch index and the
derivation index (`0 <= idx < 0x80000000`). `Wallet.from_descriptor` strips
everything after the first `#`, so the descriptor half cannot carry LVGL recolor
markup. The separate host-supplied wallet name is not sanitized and reaches a
recolor-enabled title, which is H-19. This ownership mechanism is sound, and its
one structural dependency is that the scope it compares against is authentic —
which is the invariant H-27 covers. This is not a conclusion about the full
descriptor, script, Miniscript, or TapTree parser surface.

A second parser that **holds** is Bitcoin address encoding. `bech32.py` is the
BIP-173/350 reference implementation with all four validity checks intact, and it
was run against the full published vector set: 12 invalid addresses rejected, 8
valid addresses decoded to the expected scriptPubKey and re-encoded
(PATH-34). `base58.py` enforces the checksum and the alphabet (PATH-36).
`Script.script_type()` matches five exact byte patterns and lengths, which pins
the witness version to {0, 1} and the program to {20, 32} bytes and raises for
everything else (PATH-35). `address_to_scriptpubkey`, the one function in this
family that does no length or network validation, has no caller in the firmware
(PATH-37, H-26).

The Liquid copy of that encoder does **not** hold. `liquid/blech32.py` is the
same reference file with every witness-version and program-length check commented
out, and `liquid/addresses.py` reaches it without a `script_type()` gate,
reducing the leading opcode modulo `0x50`. The result is F-35: four distinct
scriptPubKeys render as one confidential address, and OP_RETURN and
invalid-length v0 programs render as well-formed addresses. F-36 is the
decode-side counterpart, and H-25 is the `IndexError` that the same reduction
produces for a Liquid p2pkh output.

Descriptor Miniscript and TapTree recursion and allocation, BIP39/BIP32/SLIP39
internals, QR encoding, BCUR multipart internals, native SD/FatFs handling, and
much of the scanner configuration state machine were not deeply reviewed.

### 8.6 Firmware, bootloader, and secure-element assessment

The bootloader signature logic holds. Duplicate signature records are rejected. A
bad signature from a **known** key hard-fails the whole file rather than being
skipped. Signatures from unknown keys are skipped without incrementing the count.
Bootloader upgrades accept only vendor keys, while firmware upgrades accept vendor
plus maintainer. An un-configured key set fails closed. `create_verify_ctx()` also
checks `req_size <= BLSIG_ECDSA_BUF_SIZE` before using its static buffer, which is
the check the MicroPython usermod omits (H-01).

F-08 does not contradict that. The documented release procedure does install the
production key set, but it does so through a manual copy. Omitting the copy fails
closed. The remaining issue is that a completed build does not record which key
set it used, so its trust root cannot be confirmed from the artifact itself.

F-25 adds a separate result: **boot-time integrity is a CRC32**, not a
signature. ECDSA runs only during an SD-card upgrade. The upgrade order is good —
the hash is taken from flash after copying, so signed bytes equal executed bytes —
but persistence of that guarantee depends on STM32 write protection. The release
build enables the feature, a factory image does not establish region WRP, and
F-33 clears existing WRP before authentication without restoring it on failure.

Version comparison, version-check-record persistence, section and attribute
parsing, integrity records, the startup mailbox, flash maps, known-answer tests,
and every interrupted-update exit were traced. Supported-path downgrade is
blocked (PATH-24, PATH-26), and the surrounding unauthenticated erase-and-write
sequence produced F-33. Hardware option-byte behavior remains to be confirmed on
target.

Secure-channel relay and replay defenses are present in the reviewed code, but
card identity is not pinned (F-07), the device believes the card's own account of
its PIN state (F-22), and the card-side applet is absent from this repository, so
the applet running on a user's card cannot be confirmed to match any source here.
Below that host protocol, a malicious card reaches the native one-byte stack
overflow in F-34 and the broken PPS checksum in H-23. RDP1 resistance, exact F-34
target stack effects, and external applet PIN enforcement need hardware or applet
review.

### 8.7 Build and supply-chain assessment

Submodule gitlinks are immutable and match the reviewed checkouts, so a normal
recursive clone or `git submodule update` gets exactly the code reviewed here.
Against that, six `branch =` declarations exist and six of eight submodule URLs
point at forks rather than upstream projects. That is not an exploitable
weakening of the pin, but it enables `--remote` drift and leaves upstream
equivalence unestablished for those six trees. See §1.2.

Material gaps and hardening items:

- MD5-only compiler verification (F-09);
- bootloader key selection recorded nowhere in the build output, and RDP1 as the
  documented default (F-08);
- a MicroPython base branched in 2019 (D-01), flattened native dependencies with
  no recoverable upstream pins (D-02), a release-tool `cryptography` pin from
  2021 (D-03), and an LVGL pin from 2019;
- `branch =` declarations and fork URLs across the recursive submodule
  configuration, with no CI assertion that release builds avoid `--remote`
  (§1.2);
- no CI workflow, `CODEOWNERS`, or release-attestation mechanism at this tree;
- no empirical reproducibility check: two clean Docker builds were not compared
  with each other or with any official release binary.

### 8.8 Physical-attack assessment

This review cannot settle physical security. The highest-impact chains are
internal-flash readout into offline PIN recovery, direct QSPI writes into F-15, an
inducible boot fault exposing both partitions through F-32, smartcard
substitution and native corruption (F-34), entropy and nonce side channels, and
RAM/SDRAM remanence. RDP1 bypass feasibility, I2C fault inducibility, option-byte
behavior, malicious-card timing, and post-wipe QSPI recovery on the deployed
board remain unresolved.

### 8.9 Dependency assessment

Outer dependency pins and identified vendored trees show no substitution. The
interpreter fork delta is reviewed. The remaining provenance gap is inside that
fork, where flattened native third-party trees lack recoverable upstream commit
IDs (D-02), alongside the obsolete release-tool dependency in D-03.

#### D-01: MicroPython is a 2019 base with 63 fork-only commits

**Status:** Hardening · **Severity:** Informational · **Confidence:** High ·
**Owning codebase:** The pinned `micropython` fork.

The pinned fork at `6bdf1b6` (2022-11-07) has merge-base `10709846f` with
upstream `micropython/micropython`, which `git describe` resolves as
`v1.12-35-g10709846f`. MicroPython v1.12 was released in December 2019. There are
exactly 63 fork-only commits, all inspected by subject and diff.

Security-relevant changes include:

```text
Reserve sector 1 for key storage on STM32F469
Add support of two partitions in internal Flash memory
Support of a dual bootloader
Enable smart card driver, UART2 on STM32F469DISC
STM32F469DISC: hardware QSPI support for external Flash memory
set chdir to use boot and main from qspi
Enable secp256k1
flatten all submodules
```

The consequences are concrete rather than opaque. The QSPI CWD and path change is
one half of F-15. The STM32 build removed `-Wall` (H-22). Flash partitioning
defines the wipe boundary in H-24. Smartcard support reaches F-34 and H-23.
Deterministic-build patches sort generated inputs and fix version and date
strings, as intended. No fork-only commit reverts an upstream security check.

The remaining assurance issue is age, not unread local history. Interpreter,
filesystem, USB, crypto, and parser fixes made upstream since the v1.12-era base
are absent unless separately backported.

**State at this tree.** `f469-disco/micropython` is pinned at
`6bdf1b69162b673d48042ccd021f9efa019091fa` (2022-11-07), `git describe` →
`v1.10-1185-g6bdf1b691`, merge-base `10709846f` (`v1.12-35`, December 2019).
There is no rebase and no backport ledger in the tree. The submodule URL points
at a fork under `hardware-wallets-and-cryptography/` — see §1.2.

**Action.** Rebase onto a current MicroPython, or maintain an explicit backport
and advisory ledger under `docs-my/` and require security review for each
fork-only change. Start by triaging upstream interpreter, VFS, USB, and
`objstr`/`unicode` fixes since v1.12 — the last of those is directly relevant to
F-21.

#### D-02: Flattened MicroPython third-party trees have no recoverable upstream pins

**Status:** Hardening · **Severity:** Informational · **Confidence:** High ·
**Owning codebase:** The pinned `micropython` fork.

Fork commits `9a19f4960`, `5c9be573d`, `27a43e027`, and `3bffc1579` removed ten
submodule pins, added roughly 8.6 million lines in-tree, and left an empty
`.gitmodules`. Security-relevant flattened trees include `lib/stm32lib`,
`lib/tinyusb`, `lib/mbedtls`, and `lib/lwip`. Most retain no upstream commit
identifier.

The limitation is inside the pinned MicroPython tree: native SDMMC, USB, QSPI,
crypto, and network code cannot be reproduced or diffed against an identified
upstream revision.

**State at this tree.** `lib/stm32lib`, `lib/tinyusb`, `lib/mbedtls`, and
`lib/lwip` are in-tree with an empty `.gitmodules` and no upstream commit
identifiers.

**Action.** Record a source URL and commit SHA for every flattened tree in a
manifest file, or restore the submodules. Then add a CI job that re-verifies
each vendored tree against its recorded revision.

#### D-03: Release tooling pins an obsolete `cryptography` package

**Status:** Hardening · **Severity:** Informational · **Confidence:** High ·
**Owning codebase:** The bootloader tools dependency lock consumed by this
repository.

[bootloader/tools/requirements.txt:92](../../bootloader/tools/requirements.txt#L92)
pins `cryptography==3.4.8`, hash-locked, and the Dockerfile installs that lock
with `--require-hashes` before running upgrade assembly and signature tools.
3.4.8 dates from August 2021 and predates several published advisories in
`cryptography` and its bundled OpenSSL.

No untrusted input reaching a vulnerable API in this release flow was shown, so
this is dependency exposure rather than a product vulnerability.

**Action.** Regenerate the hash-locked requirements against a current
`cryptography`, verify `upgrade-generator.py`, `make-initial-firmware.py`, and
the new `introspect-binary.py` against it, and add a scheduled advisory check
(`pip-audit` in CI) so the pin does not silently age again.

### 8.10 Security-model discrepancies

This subsection compares [docs/security-info.md](../../docs/security-info.md),
the repository's user-facing security statement, against the implementation.
Each independently testable clause is one `SM-xx` claim.

- **Confirmed** means the implementation enforces or implements the claim.
- **Qualified** means the mechanism exists but the claim omits a material
  condition.
- **Contradicted** means the code provides a counterexample.

Hardware properties outside the source are marked as such rather than inferred.

Result: **23 Confirmed, 12 Qualified, 7 Contradicted** across 42 claims. The
document is markedly more accurate and more self-critical than most such
documents — it names its own PIN off-by-one, its lack of key stretching, and
its unencrypted device secret.

Four of the seven contradictions are concentrated in one section,
"Transaction verification", and they share a single cause that is not a
documentation error: **the document was carried over from `origin/master` and
describes `origin/master`'s wallet manager, while this branch carries the older
one** (§1.3). SM-34, SM-35, SM-37, and SM-38 are all that gap. They are
recorded as DOC-02 and DOC-03, and the cheapest fix for both is a cherry-pick,
not a rewrite. DOC-01 is a genuine documentation defect and is present on
`origin/master` as well.

| ID | Documented claim | Result | Implementation comparison |
| --- | --- | --- | --- |
| SM-01 | The host only sees public data and signatures; keys never leave the device; all critical information — receive addresses, amounts, change outputs — is shown on the device screen for verification ([L11-14](../../docs/security-info.md#L11-L14)). | Qualified | No private-key or mnemonic egress path exists on the host interface. The second half overstates the display: unwarned change outputs are omitted from the default transaction page and no page labels an output "change" (F-24), the fee and every warning sit below an attacker-chosen number of outputs in a scrolling container (F-19), and displayed input amounts are not authenticated (F-03). |
| SM-02 | A thief with the locked device faces secrets encrypted under a key derived from the PIN and a unique internal secret, with the PIN rate-limited so on-device brute force is impractical ([L15-18](../../docs/security-info.md#L15-L18)). | Confirmed for the on-device case | `FlashKeyStore` derives `pin_secret = tagged_hash("pin", secret + pin)` ([flash.py:139](../../src/keystore/flash.py#L139)) and the persistent counter stops online guessing ([flash.py:114-125](../../src/keystore/flash.py#L114-L125)). The offline case is out of this claim's scope and the document states it correctly elsewhere — see SM-19 and F-06. |
| SM-03 | Anti-phishing words change if the internal secret is gone, revealing device replacement or unauthorized reflashing ([L19-22](../../docs/security-info.md#L19-L22)). | Qualified | The derivation is sound ([ram.py:165-175](../../src/keystore/ram.py#L165-L175)), and in smartcard mode it also binds the card public key ([memorycard.py:66-86](../../src/keystore/memorycard.py#L66-L86)). Detection requires the PIN screen to be drawn at all. A substituted card that reports `PIN_UNLOCKED` suppresses it entirely, so the words are never shown and the check never happens (F-22). |
| SM-04 | After the initial installation the bootloader only accepts firmware signed by the release keys ([L23-25](../../docs/security-info.md#L23-L25)). | Qualified | Threshold verification, signer lookup, duplicate rejection, and return-code handling are sound (PATH-13, PATH-23), and signed bytes are the executed bytes (PATH-28). Three conditions the claim omits: an unsigned image still clears write protection and erases firmware before its signatures are checked (F-33); boot-time integrity is an unkeyed CRC32, so a flash-write primitive installs replacement firmware with a recomputed record (F-25); and firmware authorization shares its signing domain with user message signing, so a release-key holder's device can be induced to produce a valid firmware signature (F-17). |
| SM-05 | Physical attacks with lab equipment against the main MCU are out of scope; use smartcard mode or temporary-seed mode if that threat matters ([L29-33](../../docs/security-info.md#L29-L33)). | Confirmed | Accurate scoping, and consistent with F-06's prerequisite. The recommendation is the right mitigation for the threat as stated. |
| SM-06 | The QR scanner's own firmware is out of scope; the scanner forwards decoded data that the main MCU treats as untrusted ([L37-40](../../docs/security-info.md#L37-L40)). | Confirmed | The MCU configures an external scanner and receives decoded payload bytes over UART ([qr.py:13-27](../../src/hosts/qr.py#L13-L27), [qr.py:110-120](../../src/hosts/qr.py#L110-L120)). No image-processing path exists in firmware. Scanner firmware is not in the repository. |
| SM-07 | The display is controlled by the application MCU ([L44](../../docs/security-info.md#L44)). | Confirmed | Production startup imports and initializes the native display module before the application ([src/main.py:13](../../src/main.py#L13), [src/main.py:21-22](../../src/main.py#L21-L22)); the STM32 user module drives the LCD through LVGL. |
| SM-08 | QSPI wallet files — descriptors, wallet metadata, settings — are encrypted and authenticated (AES-CBC + HMAC-SHA256, encrypt-then-MAC) with a key derived from the seed at `m/0x1D'`, so a flash dump reveals neither xpubs nor wallet structure, and tampering is detected on load ([L46-51](../../docs/security-info.md#L46-L51)). | Qualified | The construction is as described: `aead_encrypt` derives separate AES and HMAC keys by tagged hash and MACs the ciphertext ([helpers.py:69-105](../../src/helpers.py#L69-L105)), and `idkey` is `root.child(0x1D, hardened=True)` ([ram.py:72](../../src/keystore/ram.py#L72)). Three omissions. **Settings are not keyed from the seed** — `settings_key` is `tagged_hash("settings key", self.secret)` ([ram.py:152-153](../../src/keystore/ram.py#L152-L153)), the device secret, which is itself cleartext in flash, so anyone who dumps flash can read and forge channel settings without the seed. **The device label is plaintext** ([label.py:49-60](../../src/apps/label.py#L49-L60)). And there is **no rollback protection**: an authenticated older blob replays cleanly, which can suppress a gap-limit warning. |
| SM-09 | QR image processing runs on a separate scanner module; USB and SD are managed by the main MCU; USB is off by default ([L53-56](../../docs/security-info.md#L53-L56)). | Confirmed | [usb.py:22](../../src/hosts/usb.py#L22) is `self.settings = { "enabled": False }`. SD is mounted through `pyb.SDCard` ([platform.py:42-101](../../src/platform.py#L42-L101)). Once USB is enabled it is not an authorization boundary — see F-05. |
| SM-10 | The bootloader verifies ECDSA signatures **after** copying the payload to internal flash, reading data back from flash rather than from the removable SD card ([L70-74](../../docs/security-info.md#L70-L74)). | Confirmed | Copy at [bootloader.c:1242](../../bootloader/core/bootloader.c#L1242), verification at [bootloader.c:1254-1256](../../bootloader/core/bootloader.c#L1254-L1256). This closes the media-swap attack (PATH-28). The same ordering is what makes F-33 possible, and the document does not mention that side of it. |
| SM-11 | Multisignature with configurable thresholds is supported, with a key hierarchy: vendor keys sign the bootloader and the main firmware, maintainer keys sign the main firmware only ([L75-78](../../docs/security-info.md#L75-L78)). | Qualified | The threshold mechanism is implemented correctly and counts records rather than keys (PATH-13). In the shipped configuration the hierarchy is nominal: `vendor_pubkey_list` and `maintainer_pubkey_list` in [bootloader/keys/production/pubkeys.c](../../bootloader/keys/production/pubkeys.c) are byte-identical — the same four keys in the same order — so vendor/maintainer separation provides no defense in depth (F-08). |
| SM-12 | Downgrades are prohibited by a version-check record holding the latest version ever programmed, for bootloader and main firmware ([L79-81](../../docs/security-info.md#L79-L81)). | Confirmed for the supported path | `check_versions` compares against the maximum of the current integrity record and either version-check record, and the erase sequence keeps at least one copy across every power-cut point (PATH-24, PATH-26). A direct flash write bypasses the record entirely (F-25), which is a different attack, not a downgrade through the supported path. |
| SM-13 | A non-upgradable start-up code integrity-checks both bootloader copies on every boot and runs the newest intact one; the main firmware's integrity record is verified on every normal boot ([L82-86](../../docs/security-info.md#L82-L86)). | Qualified | The mechanism is present and behaves as described. The claim's weight depends on what "integrity-check" means: the record holds only `pl_crc` and `struct_crc` ([bl_integrity_check.h:47-63](../../bootloader/core/bl_integrity_check.h#L47-L63)) with no key, signature, or MAC. It detects corruption, not substitution — an attacker who can write flash recomputes it (F-25). |
| SM-14 | The initial installation is the trust-critical step: verify the PGP signature of `sha256.signed.txt`, verify the image hash, flash from a trusted computer ([L88-97](../../docs/security-info.md#L88-L97)). | Confirmed as a description | Accurate, and correctly identified as the trust anchor. The repository provides no mechanism that checks any of it. Related build-side gaps: the compiler archive is MD5-pinned (F-09) and the release tooling lock is from 2021 (D-03). |
| SM-15 | The bootloader can be built with RDP Level 1 (blocks external readout; a JTAG erase also destroys the internal secret and is therefore visible), RDP Level 2 (blocked by default, requires a manual source change), and write protection over the start-up, bootloader, and main-firmware sectors ([L106-119](../../docs/security-info.md#L106-L119)). | Qualified | The RDP statements are accurate, including that RDP2 is deliberately compiled out ([bl_syscalls.c:750-753](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L750-L753)). The write-protection statement omits two conditions: WRP is a side effect of a *successful SD upgrade* and is not programmed by the image generator, so a factory-flashed device that never completed an upgrade has no WRP on those regions (limit L-1); and an unsigned upgrade clears WRP before authentication and does not restore it on rejection (F-33). |
| SM-16 | Removing the protection afterwards always wipes the entire flash, including the internal secret ([L121-123](../../docs/security-info.md#L121-L123)). | Confirmed, not statically attestable | This is STM32 option-byte behaviour, documented in the bootloader README. No repository artifact can attest the option bytes actually programmed on a shipped device. |
| SM-17 | A unique secret is generated on first boot and stored unencrypted at `/flash/keystore/secret`; its confidentiality relies entirely on readout protection; it drives the anti-phishing words ([L127-133](../../docs/security-info.md#L127-L133)). | Confirmed, with regeneration semantics | [ram.py:130-163](../../src/keystore/ram.py#L130-L163) writes and reads the secret with a bare `open()`. Note it is regenerated whenever the file is missing or unreadable, not only on literal first boot — so an erasure or a read failure silently produces new anti-phishing words. |
| SM-18 | The PIN together with the unique secret generates the decryption key, so bypassing the PIN screen still fails decryption ([L135-137](../../docs/security-info.md#L135-L137)). | Qualified | True for flash and SD storage ([flash.py:139](../../src/keystore/flash.py#L139), [sdcard.py:86-91](../../src/keystore/sdcard.py#L86-L91)). In smartcard mode, lock state is a card assertion: a hostile card can report `PIN_UNLOCKED`, skip the screen, and supply an attacker-chosen portable blob (F-22, F-07). That does not decrypt genuine ciphertext, but it does let a PIN-screen bypass change the active spending keys. |
| SM-19 | The unencrypted secret is the weak point: an attacker who reads internal flash obtains the secret and the PIN file, enabling offline brute force at full speed and cloning of the anti-phishing words; RDP blocks this ([L139-148](../../docs/security-info.md#L139-L148)). | Confirmed | This is an accurate statement of F-06, including the cloning consequence. It is also what makes SM-21 self-contradictory. |
| SM-20 | At most 10 PIN attempts, then the device wipes; the counter is decremented and persisted *before* the PIN is checked, so there are effectively 9 verification attempts and a correct PIN on the 10th still wipes ([L152-157](../../docs/security-info.md#L152-L157)). | Confirmed exactly | [flash.py:114-125](../../src/keystore/flash.py#L114-L125) decrements, calls `save_state()`, then wipes on `<= 0` before computing the HMAC at [flash.py:126-128](../../src/keystore/flash.py#L126-L128). The documentation describes its own off-by-one accurately, including the fail-safe direction. |
| SM-21 | The PIN check is an HMAC keyed with the internal secret, so the PIN cannot be brute-forced offline from flash contents alone ([L158-159](../../docs/security-info.md#L158-L159)). | **Contradicted** | The key to that HMAC is itself flash contents. See DOC-01. |
| SM-22 | The PIN state file is authenticated, and tampering with it triggers a wipe ([L160-161](../../docs/security-info.md#L160-L161)). | Confirmed | `save_state` writes through `save_aead` keyed with the device secret ([flash.py:161-170](../../src/keystore/flash.py#L161-L170)), and `_unlock` wraps state handling in a `try` that converts any exception into `CriticalErrorWipeImmediately` ([flash.py:114-125](../../src/keystore/flash.py#L114-L125)). |
| SM-23 | The wipe erases the MCU's internal flash and does not erase the smartcard; a card holding an encrypted secret becomes permanently inaccessible because the card-encryption key derived from the destroyed device secret is gone ([L162-167](../../docs/security-info.md#L162-L167)). | Qualified | Both statements hold. The omission is QSPI: [platform.py:263-274](../../src/platform.py#L263-L274) erases internal flash blocks 256-447 and two QSPI blocks, leaving 32,766 QSPI blocks unerased (H-24). A reader of this bullet would reasonably conclude that a wipe removes device-side data; it removes the keys, not the blocks. |
| SM-24 | There is no key stretching — deriving keys from the PIN costs a single SHA-256 — and no time-based delay; the persistent fail-closed counter is the only rate limit and cannot be reset by power-cycling ([L171-179](../../docs/security-info.md#L171-L179)). | Confirmed in substance | Accurate and correctly reasoned. One imprecision with no security consequence: the derivation is `tagged_hash` plus HMAC-SHA256, so a handful of SHA-256 compressions rather than literally one. The offline-speed conclusion is unaffected. |
| SM-25 | Choose a PIN of 8 or more digits, because offline brute force is the realistic worst case ([L181-184](../../docs/security-info.md#L181-L184)). | Confirmed as advice | Correct, and the right conclusion from SM-19. No minimum PIN length is enforced anywhere in `src/keystore/` — the advice is the only control (F-06). |
| SM-26 | Temporary seed mode stores no private keys; the phrase lives only in RAM. Non-secret data still persists, and wallet data is encrypted with a key derived from the seed at `m/0x1D'`, so it stays unreadable until the phrase is re-entered, but its presence is visible ([L190-197](../../docs/security-info.md#L190-L197)). | Confirmed | `FlashKeyStore` starts amnesic ([flash.py:18-25](../../src/keystore/flash.py#L18-L25)); loading a mnemonic builds the root in RAM ([ram.py:54-72](../../src/keystore/ram.py#L54-L72)). The caveat about persisting descriptors and their xpubs is accurate and is the kind of disclosure the old model omitted. See SM-08 for the settings exception. |
| SM-27 | Smartcard mode: the secret lives on a PIN-protected card and reaches RAM only when unlocked; the card enforces the attempt limit in hardware and bricks when exhausted; communication runs over an encrypted secure channel; anti-phishing words derive from both the device secret and the card public key, so a swap of either is detected; the secret may be stored encrypted or as portable plaintext ([L198-211](../../docs/security-info.md#L198-L211)). | Qualified, materially | The channel is real and replay-resistant (PATH-14), and the word derivation does bind the card key ([memorycard.py:66-86](../../src/keystore/memorycard.py#L66-L86)). Three conditions are omitted, and each defeats the detection this bullet promises. Card identity is trust-on-first-use and never pinned ([securechannel.py:52-58](../../src/keystore/javacard/applets/securechannel.py#L52-L58)), so "you detect if the card was swapped" holds only against a card that cooperates. The device takes the PIN state from the card's own answer ([secureapplet.py:48-51](../../src/keystore/javacard/applets/secureapplet.py#L48-L51)), so "the card enforces the attempt limit" is a statement about an honest card (F-22). And the "portable plaintext" format is encrypted under the public constant `b"\xcc"*32` ([memorycard.py:171](../../src/keystore/memorycard.py#L171), [memorycard.py:185](../../src/keystore/memorycard.py#L185)), which authenticates nothing about its origin (F-07). |
| SM-28 | Internal flash mode stores the mnemonic encrypted and authenticated (AES-CBC + HMAC-SHA256, encrypt-then-MAC) under a key derived from the PIN and the device secret, protected by the attempt limit — but it is a software-only barrier and a sufficiently equipped physical attacker should be assumed able to extract flash, at which point security reduces to PIN entropy ([L212-223](../../docs/security-info.md#L212-L223)). | Confirmed | Implementation matches ([flash.py:174-186](../../src/keystore/flash.py#L174-L186)), and the caveat is an accurate statement of F-06 including its conclusion. |
| SM-29 | The BIP-39 passphrase is never stored on the device or the smartcard; only the mnemonic is saved ([L235-237](../../docs/security-info.md#L235-L237)). | Confirmed | `set_mnemonic(mnemonic, password)` passes the passphrase straight into `bip39.mnemonic_to_seed` ([ram.py:54-65](../../src/keystore/ram.py#L54-L65)) and keeps no attribute for it. `grep -rn "passphrase" src/keystore/` returns nothing. |
| SM-30 | Entropy sources are the MCU TRNG and the touchscreen, the latter contributing position and the moment of touch in 180 MHz ticks ([L253-256](../../docs/security-info.md#L253-L256)). | Confirmed | Decorated `PRESSING` events add `ticks_cpu()` and the low eight bits of each coordinate to the pool ([decorators.py:6-18](../../src/gui/decorators.py#L6-L18)). |
| SM-31 | All entropy is hashed together in a SHA-512 pool, and the resulting entropy is "always at least as good as the best individual source"; the microphones are not used ([L258-261](../../docs/security-info.md#L258-L261)). | Contradicted as an absolute claim | The microphone statement is correct — no acquisition path exists. The "always at least as good" claim does not hold as stated: the pool begins at the public constant `b"7" * 64` ([rng.py:7](../../src/rng.py#L7)), and requests above 64 bytes return raw TRNG output and bypass the pool in their returned value ([rng.py:103-104](../../src/rng.py#L103-L104)). The document also does not mention that the native driver fails open (F-18), though the Python liveness check above it partially covers that. |
| SM-32 | Specter holds HD private keys in descriptor wallets, supports miniscript, separates wallets per network across Mainnet/Testnet/Regtest/Signet, and Liquid support "exists in the codebase but is not actively maintained" ([L265-273](../../docs/security-info.md#L265-L273)). | Confirmed | Wallet state is rooted under fingerprint and network ([manager.py:72-90](../../src/apps/wallets/manager.py#L72-L90)) and imports reject cross-network descriptor keys ([manager.py:529-539](../../src/apps/wallets/manager.py#L529-L539)). The Liquid caveat is accurate and welcome. It is a maintenance statement, not a reachability statement: Liquid code is in the production build and owns F-11, F-23, F-31, F-35, F-36, and H-25. |
| SM-33 | Before signing, the device lists every input with the name of the wallet it belongs to and its amount; unknown-wallet inputs are shown as "Unknown wallet" and trigger an explicit warning ([L279-283](../../docs/security-info.md#L279-L283)). | Qualified | `confirm_transaction_final` builds a title listing each wallet and amount ([manager.py:356-368](../../src/apps/wallets/manager.py#L356-L368)), and `confirm_wallets` warns whenever the map contains `None` ([manager.py:370-382](../../src/apps/wallets/manager.py#L370-L382)). But per-input values are drawn only on the hidden details page ([transaction.py:87-112](../../src/gui/screens/transaction.py#L87-L112)), which is not opened by default for an ordinary transaction, so "lists every input … and its amount" is not true of the screen a user actually sees (F-24). |
| SM-34 | A transaction spending inputs from more than one wallet group triggers an explicit mixed-inputs warning at the top of the confirmation, visible without scrolling, mitigating the multisig/mixed-input change-address attack class ([L284-291](../../docs/security-info.md#L284-L291)). | **Contradicted** | No such warning exists. See DOC-02. |
| SM-35 | Change outputs show the name of the wallet they are sent to ([L292](../../docs/security-info.md#L292)). | Contradicted for the default view | `metaout["label"]` does carry the wallet name ([manager.py:744-752](../../src/apps/wallets/manager.py#L744-L752)) and the details page renders it. But unwarned change is skipped entirely on page 1 ([transaction.py:60-66](../../src/gui/screens/transaction.py#L60-L66)), and the expressions that would add `"change "` to the label are bare discarded strings, so no page identifies an output as change at all (F-24). |
| SM-36 | To use a multisig or miniscript wallet you must first import its descriptor; "the device only signs for wallets it knows" ([L293-295](../../docs/security-info.md#L293-L295)). | **Contradicted** | [manager.py:786](../../src/apps/wallets/manager.py#L786) calls `self.keystore.sign_input(...)` for every input whether or not a wallet resolved, and the derived-key branch signs with no proof that the derived public key appears in the input script (F-04). Import is the intended path, not an enforced one. |
| SM-37 | Change is verified automatically only when there is one unambiguous spending wallet, its descriptor has exactly two branches, the output derivation resolves to branch-list position 1, and the device re-derives the exact output script from that branch and index ([L297-303](../../docs/security-info.md#L297-L303)). | **Contradicted**; the code is weaker than the text | The change flag is `(wallet is not None and len(wallets) == 1 and wallet in wallets)` ([manager.py:737-738](../../src/apps/wallets/manager.py#L737-L738)). The one-unambiguous-wallet condition and descriptor-based script re-derivation via `fill_scope` are real (PATH-02). The **two-branch requirement and the branch-position-1 requirement are not in the code**: `branch_idx` is read afterwards only to build a label and a gap-limit warning ([manager.py:753-759](../../src/apps/wallets/manager.py#L753-L759)). See DOC-03. |
| SM-38 | If a branch-1 wallet change claim does not match, the output stays visible and the device displays `Invalid change metadata! Host claimed this output as wallet change, but it does not match your wallet. Verify the destination.` ([L306-312](../../docs/security-info.md#L306-L312)). | **Contradicted** | `grep -rn "Invalid change metadata" src/` matches no source file. See DOC-03. |
| SM-39 | The device cannot check the recipient of an unverified output, so always verify the address, amounts, and fees on the device screen; the screen is the trusted output channel and the host is not ([L314-317](../../docs/security-info.md#L314-L317)). | Confirmed | This is the correct framing and the correct instruction. Its precondition is that the relevant text is on screen when Confirm becomes pressable, which F-19 and F-24 do not guarantee. |
| SM-40 | QR is the default channel; USB is off by default; SD backups written by the device are encrypted and device-specific, while explicit exports — plain mnemonic `.txt`, BIP-85 keys, xpub files — are unencrypted ([L321-334](../../docs/security-info.md#L321-L334)). | Confirmed | Accurate on all three, including the distinction between device-written backups and user-chosen exports. One detail the bullet omits: the backup filename defaults to the first word of the mnemonic ([flash.py:223](../../src/keystore/flash.py#L223), [sdcard.py:66](../../src/keystore/sdcard.py#L66), [ram.py:402](../../src/keystore/ram.py#L402)), so a word of the recovery phrase appears in cleartext in a directory listing (H-11). |
| SM-41 | The firmware has not undergone an external security audit, and RAM is not explicitly scrubbed on shutdown ([L343-348](../../docs/security-info.md#L343-L348)). | Confirmed | No zeroization of any secret exists anywhere in `src/`; secrets are immutable Python `str`/`bytes` under a garbage collector (§9.3). The disclosure is accurate. |
| SM-42 | Transaction warnings are implemented in several places rather than one pipeline, covering unknown wallets, mixed-wallet inputs, non-`SIGHASH_ALL` flags, already-signed transactions, and gap-limit overruns; consolidating them is open work ([L354-361](../../docs/security-info.md#L354-L361)). | Qualified | The self-assessment that the checks are scattered is accurate and is exactly the right diagnosis. Two items in the list are wrong: there is no mixed-wallet warning at all (DOC-02), and the gap-limit warning is written to `metaout["warning"]` and then silently overwritten by the watch-only warning two lines later ([manager.py:757-760](../../src/apps/wallets/manager.py#L757-L760)), so it never reaches the screen for a watch-only wallet (F-24). The proposed consolidation would fix the overwrite. |

**What the document does not model.** The reverse comparison — current behavior
with no corresponding claim:

- Intentional secret-derived egress interfaces are not described as a class:
  arbitrary-path xpubs and the fingerprint with **no** confirmation (F-05), up
  to 1000 bytes of raw entropy with **no** confirmation (F-14), a message
  signature at any derivation path (F-21), the SLIP-77 master blinding key over
  the host interface and, without any prompt at all, in the GUI (H-03, H-21).
- QSPI is described as a data store, not as an executable-code source. Ordinary
  `import config` resolves and runs unauthenticated Python from writable QSPI
  before PIN entry (F-15).
- Native memory safety below the Python layer is not modeled: a malicious
  smartcard reaches a one-byte stack overflow before PIN entry (F-34), and a
  short PSET rangeproof reaches an out-of-bounds write before confirmation
  (F-31).
- Animated-QR reassembly and UR fountain decoding are not described. Neither
  authenticates the assembled message (F-16, F-28, H-08, H-13).
- The Liquid trust model is named as unmaintained but not characterized:
  unverified displayed values (F-11), host-chosen asset names (F-23), and an
  address encoder that does not identify one scriptPubKey (F-35, F-36).
- The dependency posture is not described: a 2019 MicroPython base (D-01),
  flattened native trees with no upstream pins (D-02), and six submodules
  tracking forks with mutable `branch =` declarations (§1.2).

This differential creates no new finding identifier beyond the three DOC items
below; the code failures it exposes are captured in Sections 6 and 7.

#### DOC-01: `security-info.md` contradicts itself on offline PIN brute force

**Status:** Confirmed · **Severity:** Low · **Confidence:** High ·
**Owning codebase:** This repository's documentation

[security-info.md:158-159](../../docs/security-info.md#L158-L159) states a
safety property that is false:

> - The PIN check is an HMAC keyed with the internal secret, so the PIN
>   cannot be brute-forced offline from flash contents alone.

The internal secret **is** flash contents. It is stored in cleartext at
`/flash/keystore/secret` and read with a bare `open()` at
[ram.py:130-138](../../src/keystore/ram.py#L130-L138). The PIN verifier
(`tagged_hash("pin", secret)` keyed HMAC,
[flash.py:126-128](../../src/keystore/flash.py#L126-L128)) and the attempt
counter live in the same readable-flash trust domain. An attacker who reads
flash has everything needed to check guesses offline. That is precisely F-06.

The same document says the opposite twice, correctly:

- [security-info.md:139-148](../../docs/security-info.md#L139-L148): "if an
  attacker manages to read the internal flash … they obtain the device secret
  together with the PIN file. That enables … brute-forcing your PIN **offline**
  at full speed."
- [security-info.md:171-176](../../docs/security-info.md#L171-L176):
  "**There is no key stretching.** … a 4-digit PIN falls in milliseconds, a
  6-digit PIN in seconds."

So the bullet is not merely imprecise; it is refuted by its own surrounding
prose. A reader who skims the "Brute-force protection is enforced on the device"
list and stops there takes away the opposite of the truth.

**Action.** Rewrite the bullet to say what the HMAC actually buys — that the PIN
is not recoverable from the PIN file *without* the device secret, which is a
statement about an attacker who has one and not the other:

```markdown
- The PIN check is an HMAC keyed with the internal secret, so the PIN file alone
  is useless without that secret. Note both live in internal flash: an attacker who
  reads flash obtains both and can brute-force offline (see above). RDP is what
  separates these two cases, not the HMAC.
```

This is a documentation fix. The underlying weakness is F-06 and needs the
memory-hard KDF proposed there.

#### DOC-02: `security-info.md` documents a mixed-inputs warning that does not exist

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High ·
**Owning codebase:** This repository's documentation, or its wallet manager,
depending on which way it is resolved

[security-info.md:284-291](../../docs/security-info.md#L284-L291) claims:

> If a transaction spends inputs from more than one wallet group, the device
> shows an explicit mixed-inputs warning at the top of the transaction
> confirmation, so it is visible without scrolling.
> This also applies when known-wallet and unknown-wallet inputs are mixed …
> The warning is particularly intended to mitigate the class of multisig/mixed-input
> change-address [attack](https://blog.trezor.io/details-of-the-multisig-change-address-issue-and-its-mitigation-6370ad73ed2a).

No such warning exists. `grep -rni "mixed" src/ --include=*.py` returns only an
unrelated comment in [rng.py:52](../../src/rng.py#L52) and a descriptor
xpub/tpub check at [manager.py:536](../../src/apps/wallets/manager.py#L536).
`confirm_wallets`
([manager.py:370-382](../../src/apps/wallets/manager.py#L370-L382)) returns
early whenever every input resolved:

```python
async def confirm_wallets(self, wallets, show_screen):
    # check if any inputs belong to unknown wallets
    if None not in wallets:
        return True                     # two known wallets -> no warning at all
```

The only use of `len(wallets)` is
[manager.py:738](../../src/apps/wallets/manager.py#L738), which *suppresses* the
change flag when more than one wallet is present — a classification behaviour,
not a warning. `confirm_transaction_final` does build a title listing each
wallet and amount, which is useful disclosure but is not the documented warning.

Three aggravating details:

1. The claim is specific. It names placement ("at the top"), scroll visibility
   ("without scrolling"), and an attack class it mitigates. A reader can
   reasonably rely on it when deciding whether to approve a multi-wallet spend.
2. "At the top … visible without scrolling" is structurally false even for the
   warnings that *do* exist. `meta["warnings"]` is rendered inside the scrolling
   `lv.page`, appended after all outputs and the fee
   ([transaction.py:81-85](../../src/gui/screens/transaction.py#L81-L85)) — that
   is F-19. And `meta["warnings"]` is never populated on the Bitcoin path at
   all, which is F-24.
3. **The warning exists in this repository, on another branch.** Commit
   `7223458` ("Re-add mixed-inputs warning for multi-wallet transactions", #382)
   is reachable from `master`, `origin/master`, and `origin/dev`, and
   `git merge-base --is-ancestor 7223458 HEAD` is false. `origin/master` also
   carries `docs/screenshots/mixed-inputs-warning-page1.png` and `-page2.png`.
   The string `Mixed inputs from different wallets!` is present in the untracked
   artifact `src/apps/wallets/__pycache__/manager.cpython-314.pyc` in this
   working tree, and in no `.py` file here. See §1.3.

**Action.**

1. **Cherry-pick `7223458`** onto this branch, or rebase the branch onto
   `origin/master`. This is the correct fix: the feature is written, reviewed,
   and merged upstream of this branch, and the document already describes it.
   Verify afterwards that the warning fires for two known wallets, not only when
   an unknown wallet is present.
2. Note that the "at the top … visible without scrolling" half of the claim
   still depends on F-19 — the warning region is inside the scrolling `lv.page`
   on this branch — and on F-24, since `meta["warnings"]` is never populated on
   the Bitcoin path here. Confirm which of those `7223458` also addresses, and
   fix the remainder.
3. If for some reason the cherry-pick is rejected, correct the document instead:
   remove the mixed-inputs paragraph and the Trezor-attack mitigation claim. A
   documented control that does not exist is worse than a documented gap.

#### DOC-03: The documented change-verification rules and warning are not in the shipped source

**Status:** Confirmed · **Severity:** Medium · **Confidence:** High ·
**Owning codebase:** This repository's documentation, or its wallet manager

[security-info.md:297-312](../../docs/security-info.md#L297-L312) describes
change verification in precise terms:

> Change is verified for you automatically only when there is one unambiguous
> spending wallet, its descriptor has exactly two branches, the output
> derivation resolves to branch-list position 1, and the device re-derives the
> exact output script from that branch and index.
> …
> If a branch-1 wallet claim does not match, the output remains visible and the
> device displays: `Invalid change metadata! Host claimed this output as wallet
> change, but it does not match your wallet. Verify the destination.`

Two parts of that are not implemented.

Both parts exist on `origin/master`, in commit `fc0e32d` ("feat: Fix
change-output classification to require verified descriptor derivation", #387),
which is not an ancestor of this branch (§1.3). So this is a missing
cherry-pick, not unwritten work.

**1. The branch conditions are absent.** The change flag is set at
[manager.py:737-738](../../src/apps/wallets/manager.py#L737-L738):

```python
metaout.update({
    "change": (wallet is not None and len(wallets) == 1 and wallet in wallets),
    ...
})
```

That is the one-unambiguous-wallet condition, and `fill_scope` / `Descriptor.owns`
supply the script re-derivation (PATH-02). There is no test for
`descriptor.num_branches == 2` and no test for `branch_idx == 1`. `branch_idx`
is fetched on the next lines and used only for the display label and the
gap-limit warning. An output owned by the sole spending wallet is classified as
change regardless of which branch it derives from, including the receive branch.

**2. The warning string does not exist.** `grep -rn "Invalid change metadata" src/`
matches no source file. It matches exactly one path in the working tree:

```text
src/apps/wallets/__pycache__/manager.cpython-314.pyc
```

That file is untracked and ignored. Its string table also contains
`Mixed inputs from different wallets!` (DOC-02). So a build of `manager.py` that
implemented both documented behaviours existed on this machine, and the source
in the tree is not it.

**Impact.** A user who reads this section believes the device flags a
host-supplied change claim that does not match. It does not: the output is
classified by the rule above, and an unwarned change output is then dropped from
the default transaction page entirely (F-24). The gap between documented and
actual behaviour points the wrong way — the document promises a check that is
missing, rather than omitting one that exists.

**Action plan**

1. **Cherry-pick `fc0e32d`**, or rebase this branch onto `origin/master`. The
   same rebase closes DOC-02. Confirmed by:

   ```bash
   git log --all --oneline -S'Invalid change metadata' -- src/apps/wallets/manager.py
   # fc0e32d feat: Fix change-output classification to require verified
   #         descriptor derivation (#387)
   git merge-base --is-ancestor fc0e32d HEAD    # false
   ```
2. If the cherry-pick is not taken, the branch conditions are small to
   reimplement — but prefer the upstream version, which has been reviewed:

   ```python
   # manager.py, replacing the change expression
   is_change = False
   if wallet is not None and len(wallets) == 1 and wallet in wallets:
       res = wallet.get_derivation(out.bip32_derivations)
       if res:
           idx, branch_idx = res
           if wallet.descriptor.num_branches == 2 and branch_idx == 1:
               is_change = True
           else:
               metaout["warning"] = (
                   "Invalid change metadata! Host claimed this output as wallet "
                   "change, but it does not match your wallet. "
                   "Verify the destination.")
   metaout["change"] = is_change
   ```

   Either way, check F-24 item 2 in the same pass: `metaout["warning"]` is a
   single string and is overwritten by the watch-only warning a few lines later,
   so the new warning disappears for watch-only wallets unless that is fixed
   too.
3. Add a regression test in
   [test/tests_native/test_change_classification.py](../../test/tests_native/test_change_classification.py),
   which already exercises this path, asserting that a receive-branch output and
   a three-branch descriptor are **not** classified as change and that the
   warning is present.
4. Remove `__pycache__` from the working tree and confirm it is ignored, so a
   stale artifact cannot again be the only place a security behaviour exists.

## 9. Properties that hold, and limits of static review

### 9.1 Security properties that hold in reviewed paths

Each entry states the evidence, why the property holds, the residual risk, and
confidence. "Blocked" means the reviewed implementation stops the path. "Not
reachable" means the path cannot be entered in the production configuration.

A property that is Blocked here is blocked in the reviewed path only. Each
entry names the specific check that enforces it, so the claim is falsifiable:
if the cited code changes, the claim must be re-established.

PATH-18 is the one entry in this set that does **not** hold — it is retained
because a provenance claim that fails is itself a result.

#### PATH-01: Ordinary transaction signing reaches confirmation — Blocked

Evidence: wallet signing metadata is prepared before `TransactionScreen` is
shown, and signing proceeds after that screen returns approval
([manager.py:611-621](../../src/apps/wallets/manager.py#L611-L621),
[manager.py:714-786](../../src/apps/wallets/manager.py#L714-L786)).
Why it holds: there is no direct host-to-keystore transaction-signing caller.
Residual risk: F-03 and F-04 show that confirmation can authorize false or
insufficient metadata even though the call is present.
Confidence: High

#### PATH-02: Descriptor ownership re-derives the claimed script — Blocked

Evidence: `Descriptor.owns()` re-derives the descriptor at the claimed index and
compares the scriptPubKey, and `Wallet.fill_scope()` replaces host-supplied
redeem and witness scripts with descriptor-derived versions
([descriptor.py:204-233](../../f469-disco/libs/common/embit/src/embit/descriptor/descriptor.py#L204-L233),
[wallet.py:167-226](../../src/apps/wallets/wallet.py#L167-L226)).
Why it holds: ownership rests on a device-derived script rather than a host
assertion, and the branch and index ranges are bounded.
Residual risk: this defends the script, not the scope it is handed — see H-27.
Full descriptor, Miniscript, TapTree, script, and address-parser safety is not
established here. The branch and two-branch conditions the documentation
describes are not implemented (DOC-03).
Confidence: High

#### PATH-03: Application SD and USB adapters do not execute input — Blocked

Evidence: SD accepts selected top-level regular files with `.psbt`, `.txt`, or
`.json` suffixes and copies bytes to a fixed RAM path
([sd.py:43-100](../../src/hosts/sd.py#L43-L100)). USB writes a line to a fixed
RAM path and forwards it to the central dispatcher
([usb.py:103-179](../../src/hosts/usb.py#L103-L179)).
Why it holds: neither adapter evaluates, imports, or executes payload bytes.
Residual risk: downstream parsers, FatFs, mount handling, and native SD/USB
driver memory safety are separate attack surfaces.
Confidence: High

#### PATH-04: Fixed-width crypto arguments are length-checked — Blocked

Evidence: the binding obtains every fixed-width argument through the MicroPython
buffer API and raises unless it is exactly the 32, 33, 64, 65, or 96 bytes the
selected native operation requires
([libsecp256k1.c](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c)).
Why it holds: no fixed-width generator, Pedersen, Schnorr, ECDSA, keypair,
x-only, rangeproof, or surjectionproof entry point can receive a short Python
buffer, and variable-length inputs carry explicit lengths.
Residual risk: none for fixed-width arguments. Variable-length processing is a
separate property and includes F-31. H-09 and H-17 are unreachable wrapper
defects.
Confidence: High

#### PATH-05: Message signatures are separated from transaction signatures — Blocked

Evidence: the message app hashes the exact Bitcoin Signed Message prefix and the
length-prefixed message bytes before signing
([signmessage.py:43-51](../../src/apps/signmessage/signmessage.py#L43-L51)).
Why it holds: making that preimage a legacy or BIP-143 transaction sighash
preimage requires roughly a 2^168 preimage, and length-prefixing covers the exact
signed bytes.
Residual risk: firmware authorization deliberately uses the same domain (F-17),
and the message display can differ from the signed bytes (F-21).
Confidence: High

#### PATH-06: BIP85 and mnemonic display have no host command — Not reachable

Evidence: the BIP85 application defines no host prefixes, so its inherited
`can_process()` result is false. Mnemonic display is likewise entered from GUI
flows rather than the central host-command dispatcher
([src/apps/bip85.py](../../src/apps/bip85.py), [src/app.py](../../src/app.py)).
[app.py:13](../../src/app.py#L13) has `prefixes = []`,
[app.py:27-30](../../src/app.py#L27-L30) defines `can_process` as
`return prefix in self.prefixes`, and `grep -n "prefixes" src/apps/bip85.py`
returns nothing, so BIP-85 inherits the empty list.
Why it holds: hostile QR, SD, and USB streams cannot directly dispatch those
GUI-only export operations.
Residual risk: the user can deliberately invoke them, and BIP85 internals were
not deeply reviewed.
Confidence: High

#### PATH-07: The SLIP77 host command is explicitly confirmed — Blocked

Evidence: `BlindingKeysApp.process_host_command` checks `is_locked` and requires
a positive prompt that names the privacy consequence before returning the key
([blindingkeys/app.py:38-49](../../src/apps/blindingkeys/app.py#L38-L49)).
Why it holds: the host-facing secret-egress channel cannot return the master
blinding private key without physical confirmation.
Residual risk: the GUI path displays the same key immediately after menu
selection with no consent screen or PIN re-entry (H-21), and H-03 records an
unwarned wallet-descriptor export. The key has no narrower or revocable scope.
Confidence: High

#### PATH-08: Production ECDSA nonce generation uses RFC6979 — Blocked

Evidence: `PrivateKey.sign()` reaches stock `secp256k1_ecdsa_sign` with the
default nonce function. Low-R grinding supplies deterministic counter bytes and is
capped at 200 attempts
([ec.py:218-232](../../f469-disco/libs/common/embit/src/embit/ec.py#L218-L232),
[libsecp256k1.c](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c)).
Why it holds: no host-controlled nonce seed and no alternate nonce callback
reaches the production signing call.
Residual risk: physical side channels, fault injection, absent context
randomization (F-14), and unreachable wrapper H-09.
Confidence: High

#### PATH-09: Bitcoin and Liquid managers are separated — Blocked

Evidence: the Liquid manager accepts only networks with `blech32`, the Bitcoin
manager uses the Bitcoin network table, and wallet storage is namespaced by
fingerprint and network
([manager.py](../../src/apps/wallets/manager.py),
[liquid/manager.py:19-44](../../src/apps/wallets/liquid/manager.py#L19-L44)).
Why it holds: application dispatch and persisted wallets do not silently cross
the Bitcoin/Liquid network boundary.
Residual risk: the same root serves both. F-11, F-23, F-30, and unreviewed Liquid
proof and PSET internals remain.
Confidence: Medium

#### PATH-10: Bootloader context allocation is size-checked — Blocked

Evidence: `create_verify_ctx()` compares the requested preallocated context size
against `BLSIG_ECDSA_BUF_SIZE` before creating the verification context
([bl_signature.c](../../bootloader/core/bl_signature.c)).
Why it holds: an oversized pinned secp256k1 context fails closed rather than
writing beyond the bootloader's static buffer.
Residual risk: the application MicroPython binding omits the equivalent check
(H-01).
Confidence: High

#### PATH-11: Python eval, process, and network primitives are absent — Not reachable

Evidence: the sweep in Section 8.1 accounts for all `eval`, `exec`, `compile`,
reflection, process, socket, HTTP, and hardcoded-secret hits. `load_apps()`
imports only names from a static frozen list
([helpers.py:108-121](../../src/helpers.py#L108-L121),
[apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11)).
Why it holds: no reviewed source invokes a string-evaluation, process, or network
primitive on hostile data.
Residual risk: ordinary module import is itself an execution mechanism and is
separately exploitable through writable QSPI (F-15). Native and runtime
dependencies and the external scanner are outside this narrow negative.
Confidence: High

#### PATH-12: Reviewed security history reveals no removed check — Blocked

Evidence: history shows movement toward USB-off-by-default, removal of
development settings, gap-limit validation, watch-only warnings, and overwrite
prompts. Commit `ed77919` re-derives and compares the actual public key before
substituting a zero fingerprint.
Why it holds: no reviewed commit removed a cryptographic check, changed a
cryptographic constant suspiciously, disabled validation, or made parsing more
permissive without a compensating check.
Residual risk: all 63 MicroPython fork-only commits were reviewed, but the full
599-commit project history was searched by security-sensitive region rather than
read commit by commit. The search did find warning removal (H-22) and the
import-path chain (F-15), which shows that benign-looking platform changes stay
high-value review targets.
Confidence: Medium

#### PATH-13: Bootloader threshold-signature validation — Blocked

Evidence: the verifier rejects duplicate records, validates signer fingerprints,
hard-fails invalid signatures from known keys, skips unknown keys without
counting them, and enforces the configured threshold
([bl_signature.c:225-247](../../bootloader/core/bl_signature.c#L225-L247),
[bootloader.c:1007-1009](../../bootloader/core/bootloader.c#L1007-L1009)).
Why it holds: only distinct valid signature records associated with configured
keys contribute to authorization.
Residual risk: F-17 bypasses the intended signing ceremony, and F-33 shows that
the surrounding erase-and-write sequence runs before this verifier.
Confidence: High

#### PATH-14: Secure-channel cross-message replay is blocked — Blocked

Evidence: the host stack derives session-specific ECDH material, incorporates a
card nonce, uses directional keys and counters, authenticates before decrypting,
and renegotiates the session
([securechannel.py](../../src/keystore/javacard/applets/securechannel.py)).
Why it holds: recorded ciphertext from another direction, counter, or session
does not authenticate under the current channel state.
Residual risk: H-10 reuses an IV after a failed round trip. Card identity and PIN
state remain F-07 and F-22.
Confidence: High

#### PATH-15: Card fallback does not disclose the card seed — Blocked

Evidence: a failed `MemoryCard.is_available()` selection moves to another
backend, and the fallback path does not return the genuine card's protected secret
blob to that backend
([specter.py:97-113](../../src/specter.py#L97-L113),
[memorycard.py](../../src/keystore/memorycard.py)).
Why it holds: backend selection changes the active storage implementation rather
than extracting from an unavailable card.
Residual risk: the transition is weakly signalled and may be destructive, or may
let an attacker choose a new PIN (H-14).
Confidence: High

#### PATH-16: Submodules are pinned by immutable gitlinks — Blocked, narrowly

Evidence: every recursive submodule status matches its recorded gitlink
(`git submodule status --recursive` reports no `+`/`-` marker on any line).
Why it holds: `git clone --recursive` and `git submodule update` fetch the
recorded commit, so ordinary upstream branch movement cannot change the fetched
content without a reviewed parent-tree gitlink change.
Residual risk: this is narrower than it looks. Six `branch =` declarations
exist, so `git submodule update --remote` — or CI that uses it — silently
advances to a mutable branch tip. Six of eight URLs point at forks, so the
declared origin is not the upstream project. Malicious pinned content is still
trusted, and content review is incomplete. See §1.2.
Confidence: High for the narrow property as stated.

#### PATH-17: Satoshi display arithmetic is exact on this board — Blocked

Evidence: transaction screens format eight decimal places from integer satoshis.
The STM32F469 board sets `MICROPY_FLOAT_IMPL = double`, and the port sets
`MICROPY_LONGINT_IMPL_MPZ`
([mpconfigboard.mk](../../f469-disco/micropython/ports/stm32/boards/STM32F469DISC/mpconfigboard.mk),
[mpconfigport.h](../../f469-disco/micropython/ports/stm32/mpconfigport.h)).
Why it holds: arbitrary-size integer values and binary64 conversion retain
satoshi precision across Bitcoin's money range.
Residual risk: this does not validate asset labels, hidden fields, scrolling, or
the relationship between displayed and signed transaction objects.
Confidence: High

#### PATH-18: The `embit` tree matches its identified upstream — **Not established**

Evidence: none available in the repository. `embit` is a submodule at `eb6104f`
(tag `v0.8.2`) whose declared URL is a fork under
`hardware-wallets-and-cryptography/`, not the upstream project. Nothing in the
tree records whether that commit is identical to, ahead of, or diverged from
upstream `embit` v0.8.2.
Why it does not hold: the tag name asserts a version; the URL does not assert
provenance. A fork can carry a tag `v0.8.2` on any content.
Consequence: no provenance claim about the `embit` tree in this repository is
currently supported. That matters because `embit` owns F-04, F-10, F-35, F-36,
and H-26, and because the display-to-signed-output invariant is enforced only
there (H-27).
**Action.** Establish and record the relation:

```bash
git -C f469-disco/libs/common/embit fetch https://github.com/diybitcoinhardware/embit v0.8.2
git -C f469-disco/libs/common/embit diff FETCH_HEAD HEAD --stat
```

An empty diff settles it. A non-empty diff must be reviewed line by line,
because it is local modification to the signing library.
Confidence: High that the property is not established.

#### PATH-19: The secp256k1 generator table is canonical — Blocked

Evidence: all 1024 entries in `ecmult_static_context.h` were recomputed from
`gen_context.c` using the pinned build configuration and match exactly
([ecmult_static_context.h](../../f469-disco/usermods/secp256k1/src/ecmult_static_context.h)).
Why it holds: the opaque table on the signing path is the deterministic output of
the reviewable generator rather than a substituted point set.
Residual risk: the check is not automated in the build and does not cover other
unreviewed native code.
Confidence: High

#### PATH-20: Surjection-proof list-copy branches are not reached — Not reachable

Evidence: a buffer-compatible `bytes` argument takes the safe buffer branch
before the defective list-copy loops
([libsecp256k1.c:1256-1264](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1256-L1264),
with equivalent dispatch at `:1334-1342` and `:1416`). Every in-tree caller
passes joined `bytes`
([liquid/manager.py:420](../../src/apps/wallets/liquid/manager.py#L420)), and the
three list-argument call sites are commented out
([liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454)).
Why it holds: no PSET field is converted into a Python list of asset tags, so
hostile Liquid data cannot select the defective branch.
Residual risk: the functions stay exported. A future caller, or a re-enabled
surjection-proof flow, would make H-17 reachable.
Confidence: High

#### PATH-21: The preallocated rangeproof sign path is bounded — Blocked

Evidence: `rangeproof_sign_to` fixes `prooflen` at 5800, rejects an arena smaller
than that value, and writes with `while (l + 64 < prooflen)`
([libsecp256k1.c:1587-1592](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1587-L1592),
[libsecp256k1.c:1664-1668](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1664-L1668)).
The implementation's arena bound precedes every arena write
([rangeproof_preallocated_impl.h:43-46](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated_impl.h#L43-L46)).
Why it holds: this length is a compile-time constant and the proof message is
device-generated, so F-31's host-controlled subtractive underflow has no analogue.
The sign-side ABI also places the length consistently.
Residual risk: the comparison mixes signed and unsigned types, but the only
caller supplies the positive fixed arena size.
Confidence: High

#### PATH-22: Locked-state signing and export are unreachable — Blocked

Evidence: `Specter.lock` locks the keystore and disables every host
([specter.py:556-562](../../src/specter.py#L556-L562)), and disabled host update
loops re-check `enabled` before dispatch
([hosts/core.py:114-145](../../src/hosts/core.py#L114-L145)). Both lock call sites
immediately enter `unlock()`, which loops until the active backend is unlocked
([specter.py:232-235](../../src/specter.py#L232-L235),
[specter.py:308-311](../../src/specter.py#L308-L311)).
Why it holds: keystore signing methods do not independently check `is_locked`,
but every attacker-drivable host and menu caller is disabled until unlock. Xpub
and SLIP77 host commands also check lock state directly.
Residual risk: `lock()` is authorization state, not erasure. Mnemonic, root,
blinding key, device secret, and decrypted storage keys stay in RAM, and an
already-confirmed coroutine can create state-machine inconsistencies, although no
unconfirmed signature path was found.
Confidence: High

#### PATH-23: Unverified flash bytes never execute through the upgrade path — Blocked

Evidence: `create_icrs()` runs only after successful multisignature verification
([bootloader.c:1255-1269](../../bootloader/core/bootloader.c#L1255-L1269)), and
main firmware and bootloader selection both require a valid integrity record
([main.c:84-87](../../bootloader/platforms/stm32f469disco/bootloader/main.c#L84-L87),
[startup.c:219-232](../../bootloader/platforms/stm32f469disco/startup/startup.c#L219-L232)).
Why it holds: the record, not the flash content, is the execution gate, and it is
created only on the authenticated path.
Residual risk: F-33 shows that the same unauthenticated write window weakens WRP.
An attacker who already has F-25's direct flash-write primitive can forge the
record rather than using this upgrade path.
Confidence: High

#### PATH-24: Redundant bootloader copies cannot be collapsed or rolled back — Blocked

Evidence: `get_inactive_bl_addr()` targets the copy other than
`p_args->loaded_from`, whose value is constrained to the two compiled bases
([bootloader.c:442-472](../../bootloader/core/bootloader.c#L442-L472)).
`select_bootloader()` chooses the highest version and accepts a fallback only when
its version is equal, never lower
([startup.c:235-243](../../bootloader/platforms/stm32f469disco/startup/startup.c#L235-L243)).
Why it holds: the running copy is not an erase target, and an older valid copy
cannot satisfy the equality fallback.
Residual risk: a corrupt higher-version copy bricks rather than rolls back, and
H-20 records a fail-closed out-of-bounds read in the no-valid-copy state.
Confidence: High

#### PATH-25: The start-up mailbox offers no attacker write window — Blocked

Evidence: `bl_write_args()` and `bl_read_args()` run in the same boot with no
external code between them
([startup_mailbox.c:22-43](../../bootloader/core/startup_mailbox.c#L22-L43),
[startup.c:175](../../bootloader/platforms/stm32f469disco/startup/startup.c#L175),
[main.c:66-78](../../bootloader/platforms/stm32f469disco/bootloader/main.c#L66-L78)),
and the CRC-bypass flag is never passed.
Why it holds: argument validation accepts only the two compiled bootloader bases,
and no attacker-controlled execution can alter SRAM2 between write and read.
Residual risk: the CRC is not authentication. Persistence across a future reset,
or exposure to application firmware, would invalidate this conclusion.
Confidence: High

#### PATH-26: Anti-rollback state is monotone across interrupted updates — Blocked

Evidence: `check_versions()` compares the incoming version against the maximum of
the current integrity record and either version-check record
([bootloader.c:660-688](../../bootloader/core/bootloader.c#L660-L688)).
`erase_main_firmware_area()` computes the previous maximum before erase and
persists it in an order that leaves one copy readable at every power-cut point
([bootloader.c:758-786](../../bootloader/core/bootloader.c#L758-L786)). The
version sits inside the signed header and the Bech32 authorization message.
Why it holds: the comparison floor is the highest version ever programmed, not
merely the current image, and the floor survives every intended transition.
Residual risk: F-25's arbitrary flash write can replace the records directly.
Same-version recovery is intentionally allowed for a corrupt resident image.
Confidence: High

#### PATH-27: Upgrade parsing and signature-message construction are bounded — Blocked

Evidence: section attribute walkers bound every TLV to the fixed attribute list.
Integer and string accessors enforce their destination sizes. Metadata parsing
caps the signature payload, rejects duplicate and unknown sections, and rejects
trailing bytes
([bl_section.c:97-123](../../bootloader/core/bl_section.c#L97-L123),
[bl_section.c:225-301](../../bootloader/core/bl_section.c#L225-L301),
[bootloader.c:521-572](../../bootloader/core/bootloader.c#L521-L572)).
Why it holds: every length is checked against its containing static buffer before
use, and the section walk must consume the file exactly.
Residual risk: the worst-case Bech32 authorization string uses the entire 90-byte
bound with no headroom, so future version-format changes need a regression test.
Confidence: High

#### PATH-28: Signed and executed bytes cannot diverge through media swapping — Blocked

Evidence: the bootloader hashes the sections by reading back from flash after
copying, then verifies that digest
([bootloader.c:936-965](../../bootloader/core/bootloader.c#L936-L965),
[bl_section.c:303-335](../../bootloader/core/bl_section.c#L303-L335)).
Why it holds: replacing or rewriting the SD card can change only the bytes copied
to flash, and those exact bytes become the signed digest.
Residual risk: none for verify-versus-execute equality. The pre-verification
erase-and-write ordering has the separate F-33 impact.
Confidence: High

#### PATH-29: Signing tools and device authorization parsing agree — Blocked

Evidence: device and host tools use canonical boot-then-main section order,
disjoint firmware and bootloader HRP prefixes, and the same double-SHA256 Bitcoin
Signed Message construction
([bootloader.c:943-959](../../bootloader/core/bootloader.c#L943-L959),
[bl_section.c:344-354](../../bootloader/core/bl_section.c#L344-L354),
[bl_signature.c:144-159](../../bootloader/core/bl_signature.c#L144-L159)). The
MicroPython application contains no upgrade-file parser.
Why it holds: tool/device divergence fails signature verification, and no second
application parser can reinterpret the authorized image.
Residual risk: H-20 records a bounds-check difference in start-up flash syscalls,
but it is not a signature-message or image-authorization difference.
Confidence: High

#### PATH-30: SD-card boot-time module shadowing is not compiled in — Not reachable

Evidence: the STM32 Makefile defaults `MICROPY_HW_SDCARD_MOUNT_AT_BOOT` to zero
and passes that value as a compile definition, and the production board does not
override it. The boot code appends `/sd` paths only when that feature mounted a
card.
Why it holds: production startup never mounts SD into `sys.path`, so F-15's
boot-time import cannot resolve there.
Residual risk: QSPI and internal flash remain writable import roots, and SD still
feeds application and bootloader parsers through explicit file flows.
Confidence: High

#### PATH-31: Filesystem `boot.py` and `main.py` cannot replace frozen startup — Blocked

Evidence: `pyexec_file_if_exists()` checks `mp_frozen_stat()` before the VFS
lookup, and both production boot scripts are frozen by the manifest.
Why it holds: an attacker-created `/qspi/boot.py` or `/qspi/main.py` is never
selected over the exact frozen script.
Residual risk: F-15 uses a different, guaranteed non-frozen module (`config`).
Filesystem package directories can also shadow certain frozen top-level module
names that are probed without a matching frozen path string.
Confidence: High

#### PATH-32: Button-selected USB safe mode is absent from production — Not reachable

Evidence: `update_reset_mode()` and its call site compile only when
`!MICROPY_HW_USES_BOOTLOADER`. The production build uses the dual bootloader and
links application firmware at `0x08020000`.
Why it holds: the reset-button path that would retain a USB REPL is removed from
the release binary and stays a development-build behavior.
Residual risk: F-32 is a separate fault path in the production boot script, not
the disabled safe-mode mechanism.
Confidence: High

#### PATH-33: Exposed flash block-device operations enforce partition bounds — Blocked

Evidence: `storage_read_block`, `storage_write_block`, and their multi-block
variants validate both internal-flash and QSPI partition ranges. The MBR is
synthesized, writes to block zero are discarded, and the reserved gap is
rejected.
Why it holds: ordinary `pyb.Flash` block numbers cannot address the reserved
key-storage sector or memory outside either configured partition.
Residual risk: F-32 deliberately exposes the two valid partitions read-write over
MSC, and H-24 shows that application wipe does not scrub most valid QSPI blocks.
Confidence: High

#### PATH-34: Bech32 and Bech32m encoding matches the BIP-173/350 reference — Blocked

Evidence: `bech32.py` is the reference implementation, and all four validity
constraints are present in `decode`: witness version `> 16`, decoded length
outside 2-40, v0 length not in {20, 32}, and the variant binding
`v0 ⇔ Bech32` / `v≠0 ⇔ Bech32m`
([bech32.py:121-137](../../f469-disco/libs/common/embit/src/embit/bech32.py#L121-L137)).
On top of that, `bech32_decode` enforces the 90-character limit, mixed-case
rejection, the printable-range check, and separator position
([bech32.py:78-95](../../f469-disco/libs/common/embit/src/embit/bech32.py#L78-L95)), and
`convertbits` rejects non-canonical padding
([bech32.py:98-118](../../f469-disco/libs/common/embit/src/embit/bech32.py#L98-L118)).

Executed against the BIP-350 vector sets: all 12 invalid segwit addresses were
rejected (invalid checksum character, witness version 17, program lengths 1 and
41, v0 length 16, mixed case, over-long and non-zero padding, empty data,
Bech32m-for-v0, Bech32-for-v1, HRP mismatch). All 8 valid addresses decoded to
the expected scriptPubKey and re-encoded to the original string, covering witness
versions 0, 1, 2, and 16 and program lengths 2, 16, 20, 32, and 40 across the
`bc`, `tb`, and `bcrt` HRPs.
Why it holds: `encode` also re-decodes its own output and returns `None` on
failure ([bech32.py:140-146](../../f469-disco/libs/common/embit/src/embit/bech32.py#L140-L146)),
so the checks apply in both directions.
Residual risk: `encode` raises `IndexError` for a witness version above 31 rather
than returning `None`. That is unreachable here, because callers are gated by
`Script.script_type()` (PATH-35). The Liquid `blech32` copy of this file has the
same checks commented out; that is F-35, and this result does not extend to it.
Confidence: High

#### PATH-35: `Script.address()` constrains witness version and program length by script type — Blocked

Evidence: `Script.address` dispatches only on `Script.script_type()`, which
matches five exact byte patterns and lengths — `p2pkh` (25 bytes,
`76a914`…`88ac`), `p2sh` (23 bytes, `a914`…`87`), `p2wpkh` (22 bytes, `0014`),
`p2wsh` (34 bytes, `0020`), `p2tr` (34 bytes, `5120`) — and returns `None`
otherwise, at which point `address` raises `ValueError`
([script.py:15-38](../../f469-disco/libs/common/embit/src/embit/script.py#L15-L38),
[script.py:43-61](../../f469-disco/libs/common/embit/src/embit/script.py#L43-L61)).
Why it holds: because the two leading bytes are matched exactly, the
`ver = data[0] % 0x50` reduction can only yield 0 or 1, and `data[2:]` can only be
20 or 32 bytes. So the Bitcoin path cannot reach the collision or the
invented-address behavior of F-35. Verified: `0120…`, `a120…`, `5220…`,
`6a14…`, and `0002aabb` all raise `ValueError`, while the five canonical types
produce correct `bc1q…`, `bc1p…`, `1…`, and `3…` output. The base58 slices
`data[3:23]` and `data[2:22]` are likewise pinned to 20 bytes by the length checks
in `script_type`.
Residual risk: outputs with no address representation are shown as bare hex by
`WalletManager.get_address`
([manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99)) in the same screen
position as an address, with no "unrecognized script" label. That is a UI
weakness noted in F-35's remediation, not an encoding defect. Taproot output-key
tweaking and Miniscript/TapTree compilation are outside this result.
Confidence: High

#### PATH-36: Base58Check validates the checksum and the alphabet — Blocked

Evidence: `decode` raises `ValueError` on any character outside the
58-character alphabet, and `decode_check` recomputes
`double_sha256(b[:-4])[:4]` and raises on mismatch
([base58.py:34-79](../../f469-disco/libs/common/embit/src/embit/base58.py#L34-L79)).
Why it holds: a single corrupted trailing character, a truncated string, the
excluded characters `0OIl`, and the empty string are all rejected.
Leading-zero padding round-trips correctly, because the final character always
contributes one byte through the integer conversion.
Residual risk: the decoded payload *length* is not validated. That matters only
for `address_to_scriptpubkey`, which is unreachable here (PATH-37, H-26).
Confidence: High

#### PATH-37: `Script.from_address` and `address_to_scriptpubkey` have no caller — Not reachable

Evidence: no reference to `from_address` or `address_to_scriptpubkey` exists in
`src/`, `boot/`, or elsewhere in the vendored tree. The only occurrence is the
definition itself
([script.py:76-81](../../f469-disco/libs/common/embit/src/embit/script.py#L76-L81),
[script.py:174-195](../../f469-disco/libs/common/embit/src/embit/script.py#L174-L195)).
Why it holds: the firmware converts descriptors to scripts and scripts to address
strings, never address strings to scripts. Address verification compares two
strings rather than decoding one (PATH-38).
Residual risk: the function itself is defective — no payload-length check, a
hardcoded 20-byte push opcode, acceptance of every network's version byte with no
network parameter, and a silent `None` return for an unknown prefix. All four are
recorded in H-26, and any future caller inherits them.
Confidence: High

#### PATH-38: Address verification compares against a device-derived address — Blocked

Evidence: `find_wallet_from_address` re-derives the address from each stored
descriptor and requires string equality with the host-supplied value before any
wallet is returned, then raises `WalletError` if none matches
([manager.py:562-585](../../src/apps/wallets/manager.py#L562-L585)). The screen
that follows derives what it displays from the wallet itself
([wallets/screens.py:99-108](../../src/apps/wallets/screens.py#L99-L108),
[wallet.py:144-153](../../src/apps/wallets/wallet.py#L144-L153)). `showaddr`
applies the same rule to host-supplied paths and redeem scripts
([manager.py:444-485](../../src/apps/wallets/manager.py#L444-L485)).
Why it holds: the host cannot cause an address it chose to be displayed as
belonging to the device. It can only cause a match against an address the device
would have derived anyway. `Wallet.get_descriptor` bounds the branch index to the
descriptor's branch count and the index to `0 <= idx < 0x80000000`
([wallet.py:148-153](../../src/apps/wallets/wallet.py#L148-L153)).
Residual risk: verification only ever checks branch 0, because
`find_wallet_from_address(index=...)` calls `get_address(index, network)` with the
default `branch_index=0`, so a change address cannot be verified. The tuple that
branch returns, `(0, index)`, is also ordered inversely to the `paths` branch's
`(idx, branch_idx)`; the caller discards it, so the inconsistency is latent.
`showaddr` applies no length limit to a host-supplied redeem script before hashing
it into a p2wsh or p2sh address. F-36 makes the Liquid unconfidential half of this
comparison unsound for non-v0 descriptors.
Confidence: High

#### PATH-39: Displayed Bitcoin output addresses are derived from the parsed scriptPubKey — Blocked

Evidence: output metadata is built from `psbtout.script_pubkey` and nothing else
([manager.py:737-741](../../src/apps/wallets/manager.py#L737-L741),
[manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99)), and that string is
what reaches the confirmation label
([transaction.py:179-189](../../src/gui/screens/transaction.py#L179-L189)).
Why it holds: there is no host-supplied address field anywhere in the display
path. No PSBT record carries an address string, and no branch prefers one over the
derived value. Encoding is deterministic and gated (PATH-34, PATH-35), so a given
scriptPubKey has exactly one rendering.
Residual risk: this is a statement about the encoder and the metadata source, not
about which scriptPubKey ends up in the signed transaction. That the displayed
scope equals the signed scope rests on PATH-41, which is enforced only in the
dependency (H-27). F-24 and F-19 then govern whether the string is on screen
when the user presses Confirm, and F-03 and F-04 remain on the signing side. The
Liquid equivalent does not hold (F-35).
Confidence: High

#### PATH-40: Address network prefixes come from the configured network — Blocked

Evidence: every address-producing call passes the manager's own network
dictionary — `self.Networks[self.network]`, selected from a validated network
name — into `Script.address` or `LDescriptor.address`
([manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99),
[manager.py:447](../../src/apps/wallets/manager.py#L447),
[wallet.py:144-146](../../src/apps/wallets/wallet.py#L144-L146),
[signmessage.py:80-85](../../src/apps/signmessage/signmessage.py#L80-L85)), and
`parse_wallet` rejects a descriptor whose xpub version bytes belong to a different
network ([manager.py:529-539](../../src/apps/wallets/manager.py#L529-L539),
[wallet.py:123-137](../../src/apps/wallets/wallet.py#L123-L137)). Wallet storage is
additionally partitioned per network directory
([manager.py:80-86](../../src/apps/wallets/manager.py#L80-L86)).
Why it holds: prefixes are never taken from or inferred from host input on the
generation side, and `bech32.decode` enforces an exact HRP match rather than a
prefix match, so a mainnet address is rejected when a testnet HRP is expected.
Residual risk: the *decoding* helpers are not network-scoped.
`liquid/networks.py:76` merges the Bitcoin `NETWORKS` into the Liquid table, so
`addr_decode` accepts the HRPs `bc`, `bcrt`, `tb`, `ert`, `ex`, and `tex`
interchangeably, and `detect_network` matches with `startswith` on the first
dictionary entry that fits. That is safe for the current prefix set, which was
checked exhaustively for the three confidential HRPs `lq`, `el`, and `tlq`, but it
is order dependent, and MicroPython does not guarantee dictionary order. Adding a
network whose HRP is a prefix of another would break it silently.
Confidence: High

#### PATH-41: v2-only PSBT scope fields are rejected inside a v0 PSBT — Blocked

Evidence: `PSBTScope.read_from` declares `V2_FIELDS` per scope class and raises
`PSBTError("PSBTv2 field is not allowed in PSBTv0")` unless the parsed PSBT
version is 2
([psbt.py:162-163](../../f469-disco/libs/common/embit/src/embit/psbt.py#L162-L163)).
`PSBTView` plumbs the parsed version into every scope read, so the streaming
path this firmware actually uses is covered and not only `PSBT.parse`
([psbtview.py:352-354](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L352-L354),
[psbtview.py:364-366](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L364-L366)).
The reverse direction is closed too: a v2 PSBT carrying a global transaction is
rejected at
[psbtview.py:289-290](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L289-L290).
Why it holds: the guard fails closed. An omitted `version` kwarg defaults to
`None`, which is not 2, so a scope read that loses the version context rejects
rather than accepts. This is what keeps the displayed output scope equal to the
global transaction output that gets signed — the single most load-bearing
property on the Bitcoin signing path.
Residual risk: the property is enforced only in the dependency, no test in this
repository pins it, and `embit` is tracked through a fork pin whose upstream
relation is not established (H-27, PATH-18, §1.2). A submodule bump can retire
this entry silently.
Confidence: High for the current pin.

### 9.2 Bootloader limits

- **L-1: WRP is not established by the initial firmware image.** Firmware and
  bootloader WRP is a successful-upgrade side effect, and the image generator
  cannot program option bytes. A factory-flashed device that has not completed an
  SD upgrade has no WRP on those regions.
- **L-2: integrity-record verification does not independently bound `pl_size`.**
  The bootloader syscall layer fails closed through flash-area checks. The
  start-up syscall layer does not; H-20 records the resulting availability-only
  difference.
- **L-3: RDP2 is compiled out.** RDP1 is reasserted on every boot, while
  firmware and bootloader WRP is not. The code intended to reprotect under RDP2
  is dead.
- **L-4: KAT coverage omits CRC32 and authorization-message construction.**
  SHA-256 and secp256k1 verification have known-answer tests, but the CRC
  primitive behind every integrity and version record, and Bech32 message
  construction, do not. KATs run only when an upgrade file is present.
- **L-5: weak platform protection stubs return success.** The STM32F469 platform
  overrides them, so production is unaffected, but a new platform that omits the
  overrides would silently report read and write protection as applied.
- **L-6: several static bounds have no headroom.** The copied start-up RAM image
  ends exactly at the mailbox. The accepted bootloader payload size exceeds the
  portion copied to RAM. The upgrade report is safe only because its current
  worst-case text fits the static buffer.
- **L-7: vendor and maintainer key lists are byte-identical.** That preserves the
  real 2-of-4 threshold but gives no role separation between bootloader and
  main-firmware authorization (F-08).

### 9.3 Limits of this review

- CPython parser proofs establish parser semantics. They do not validate
  MicroPython memory behavior or target hardware timing.
- No firmware build, flash, unlock, OpenOCD, hardware RNG, smartcard, or physical
  attack was performed.
- Network access was read-only and used only for upstream comparison. No release
  artifact was downloaded. Static inspection supports a deterministic Docker
  build, but official release provenance and bit-for-bit reproduction are
  unchecked.
- **RAM remnants are not answerable statically.** Structurally, secrets are
  Python `str` and `bytes` — immutable and GC-managed: `self.mnemonic`,
  `self.root`, `self.slip77_key`, `self.idkey`, `self.secret`, `self.enc_secret`
  in `RAMKeyStore`. Nothing in the codebase zeroizes any of them, and there is no
  wipe or memset of a secret buffer anywhere in `src/`. Deterministic wiping is
  not achievable in this language and runtime, which the design implicitly
  accepts. That is a statement about the architecture, not a measurement.
- **Address construction and encoding is complete for static source.**
  `script.py`, `base58.py`, `bech32.py`, `networks.py`, `liquid/blech32.py`,
  `liquid/addresses.py`, and `liquid/networks.py` were read in full, and the
  Bitcoin encoder was executed against the complete BIP-173/350 vector set (F-35,
  F-36, H-25, H-26, PATH-34 to PATH-40). Two limits: the taproot output-key tweak
  and Miniscript/TapTree compilation that *produce* the scripts this encoder
  renders are Shallow, so a correct encoding of an incorrectly derived program is
  not ruled out. And the vector work ran off-target, so MicroPython-specific
  integer, slice, or string behavior in these files is inferred rather than
  measured.
- Liquid issuance and the remaining PSET internals were not reviewed. Recursive
  outer dependency pins are resolved, and flattened MicroPython native trees stay
  provenance-limited under D-02.
- Platform wipe behavior, RDP/WRP state reporting, SDRAM mounting, and shutdown
  remanence were not deeply reviewed.
- The application-level SD and USB adapters were read, but FatFs, filesystem
  parser behavior, mount handling below Python, and the native SD and USB drivers
  were not.
- The absence of a finding in a shallowly reviewed component is not evidence that
  the component is safe.
## 10. Testing gaps and recommended tests

### 10.1 Questions static inspection did not close

- exploit behavior of F-10 and F-31 at the target MicroPython/native boundary;
- GUI visibility, scrolling, and exact rendered text on LVGL;
- TRNG fault behavior, nonce side channels, RDP1 extraction, and RAM/SDRAM
  remanence on physical hardware;
- external JavaCard applet identity, PIN enforcement, and fault behavior;
- bootloader behavior under induced hardware conditions: option-byte state before
  and after a rejected upgrade (F-33), power cuts at each version-record erase
  step, and forged integrity or version records;
- bit-for-bit reproduction against official release artifacts.

### 10.2 Immediate regression and exploit tests

1. **The cheapest high-value test in this report (F-21).** Send
   `signmessage m/44h/0h/0h/0/0 base64:<b64("VISIBLE\x00HIDDEN")>` on hardware.
   Photograph the screen, then compare it with the bytes recoverable from the
   returned signature. One test settles a High finding.
2. Add crafted v0 PSBT tests containing each v2-only input and output key in
   every field order, and assert rejection before confirmation. Include
   **duplicate** `0x0f` records and over-long values for `0x0f` and `0x10`.
   Nothing in `test/` currently pins this rejection, so a submodule bump can
   retire it silently (H-27, PATH-41).
3. Compare displayed metadata with the exact global transaction and
   sighash source, for legacy, SegWit v0, and Taproot inputs.
4. Test change classification and ensure no real output can disappear through a
   forged scope.
5. Reproduce the two-session, two-input SegWit fee attack and verify that any
   unverified amount becomes fatal.
6. Attempt derived-key signing when the derived public key is absent from every
   applicable input script.
7. Differentially fuzz `InputScope` and `PSBTView` boundaries, starting with the
   demonstrated `non_witness_utxo` desynchronization.
8. Verify Liquid input generators and Pedersen commitments, and test mismatched
   proprietary fields.
9. Assert that a `signmessage` request whose message parses as a bootloader
   Bech32 signature message is refused, or shown with an explicit
   firmware-authorization screen (F-17).
10. Assert that `rng_get` failure propagates: stub the peripheral to time out and
    confirm that seed generation refuses. Separately verify that a known initial
    pool plus zero-valued TRNG reads produces deterministic mnemonic entropy, and
    that prior touch input changes that output (F-18).
11. Render a transaction with 3, 10, and 50 outputs and assert that the fee and
    every warning are inside the visible region at the moment Confirm becomes
    pressable (F-19).
12. Recompute `ecmult_static_context.h` during the build and fail on mismatch.
13. Emulate a smartcard that answers `PIN_UNLOCKED` to `PIN_STATUS` and returns a
    constant-key (`b"\xcc" * 32`) secret blob. Assert that the device still
    demands a PIN and refuses the blob (F-22, F-07).
14. Fuzz the UR path: parts with a corrupted bytewords CRC, mixed checksums,
    `seq_len` up to 10^6, and non-alphabetic bytewords characters. Assert that the
    assembled message is CRC-checked before dispatch (F-28, H-08).
15. Assert that `branch_txt` is non-empty for `branch_idx >= 1`, that `metaout`
    can carry more than one warning, and that a fee above an absolute or
    percentage threshold produces a visible warning (F-24).
16. Label the real L-BTC asset with `addasset` under a misleading name, then
    render a PSET spending it. Assert that the raw asset ID is still visible next
    to the label (F-23).
17. Build with `mpy-cross -O2` and assert that the UR decoder still rejects
    inconsistent parts, that is, that no security check depends on `assert`
    (H-13).
18. Have two people build this tree on different machines and compare
    `sha256(bin/specter-diy.bin)`.
19. Assert `secp256k1_context_preallocated_size() <= PREALLOCATED_CTX_SIZE` at
    build or boot time, so a future configuration change cannot invalidate the
    current bound (H-01).
20. Build a Liquid PSET with a five-byte rangeproof value and appended chosen
    bytes. Assert rejection before `rangeproof_rewind_from`, and instrument the
    target arena to prove that no byte beyond `memlen` changes (F-31).
21. Inject an exception at each statement in `boot.py:15-56`. Assert that USB
    stays disabled, that no dupterm is installed, and that neither flash
    partition is exported. On hardware, induce the I2C candidate and try the
    F-32 → F-15 `/qspi/config.py` persistence chain.
22. Run the BIP-350 address vector set and a Liquid script-type matrix as
    on-target regressions. For Bitcoin, assert that all 12 invalid and 8 valid
    vectors behave as they do off-target. For Liquid, assert that `6a14…`
    (OP_RETURN), `0002aabb`, `0029…` (41-byte program), `76a914…88ac` (p2pkh),
    and a bare multisig scriptPubKey never produce an address string, and that
    `0120…`, `a120…`, and `f120…` do not render as the same address as
    `5120…` (F-35, F-36, H-25).
23. Feed a CRC-correct, signature-invalid upgrade and assert that WRP option
    bytes are identical before and after every failure and power-cut exit (F-33).
24. Drive the smartcard UART with 32, 33, and 270 queued bytes under the release
    compiler. Assert that `scard_rx_readinto` never returns more than the supplied
    capacity, and fuzz ATR/T=1 state and timing (F-34, H-23).
25. After device wipe, image every internal and QSPI block and verify the
    documented erasure policy, including labels and filesystem metadata (H-24).
26. Render every mnemonic, BIP85, and SLIP77 QR with production, debug, and
    simulated terminal state, and assert that secret payloads never reach stdout
    (H-18, H-21). Fuzz wallet names containing recolor and control markup (H-19).

### 10.3 Target GUI, hardware, and native tests

1. Test controller-level event injection and background-screen callback liveness.
   The LVGL-level cross-screen release question is closed by H-04.
2. Test very long, newline-padded, and control-character messages, and
   transactions with many outputs, on the actual LVGL display.
3. Assert that every production import resolves to frozen or native code except
   for explicitly authenticated data. Specifically reject `/qspi/config.py`,
   empty-path and CWD resolution, and frozen-module directory shadowing (F-15).
4. Exercise F-31 and all preallocated rangeproof offsets and lengths under memory
   pressure, and map SDRAM and FMC behavior above the arena.
5. Enforce the secp256k1 context-size relation at build and boot rather than
   re-measuring it by hand.
6. Confirm that STM32 `os.urandom` reaches the hardware RNG and fails safely on
   stuck, repeated, or short output.
7. Evaluate ECDSA and Schnorr timing, power, fault, and context-randomization
   behavior.
8. Test RDP1 extraction practicality on the deployed board and MCU revision.
9. Test smartcard substitution and interposition, F-34's exact stack effect, and
   the external JavaCard applet's PIN attempt and secret-release logic.
10. Fuzz bootloader sections, records, and mailbox, and power-cut recovery on
    target. The static parser, downgrade, and KAT trace is closed by PATH-23 to
    PATH-29.
11. Measure RAM and SDRAM remnants after normal shutdown, wipe, reset, and power
    interruption.

### 10.4 Read-only dependency and release checks

Already checked: all recursive gitlinks resolve through their declared or
redirected origins; the MicroPython, LVGL, nested `secp256k1-zkp`, bootloader
library, and `embit` upstream relationships are resolved; and
[ecmult_static_context.h](../../f469-disco/usermods/secp256k1/src/ecmult_static_context.h)
was recomputed and verified.

Still to do:

1. Establish whether `embit` upstream has fixed F-04, F-10, F-35, or F-36, to
   set the embargo clock for the coordinated disclosure in §12.2. The pinned
   v0.8.2 does not fix any of them.
2. Fetch official release metadata, signatures, and binaries. Run two
   clean `linux/amd64` Docker builds from this exact tree, compare their main
   firmware, bootloader, initial-firmware, and unsigned-upgrade hashes, then
   import the published signatures in the documented order and compare the signed
   upgrade binary with the release.
3. Adopt the generator-table recomputation as a build-time assertion.
4. Restore an upstream commit identifier and a reproducible delta check for every
   flattened MicroPython native dependency (D-02).
5. Refresh the hash-locked release-tool dependencies. `cryptography` is pinned
   at 3.4.8, from August 2021; bring it to a current release and add automated
   advisory checks (D-03).
6. Establish the upstream relation for the six forked submodules and record it
   in the repository (§1.2, PATH-18). Start with `embit`, which owns the most
   findings and the PATH-41 invariant.
7. Diff the 33 commits on `origin/master` that this branch lacks, and decide
   which are security-relevant (§1.3). Three already are.

## 11. Final funds-theft analysis

The capabilities below overlap: one payload can be a malicious host request, a QR
code, a PSBT, and a transaction at the same time. Repeating the same root cause
where it is the strongest path is intentional.

**Prevented** means the reviewed implementation blocks the strongest identified
funds-theft path. **Not prevented** means a confirmed vulnerability or design
limitation leaves that path open. **Conditional** or **unresolved** identifies a
prerequisite or coverage limit that static inspection did not settle.

| Attacker capability | Strongest realistic path to funds | Does the current implementation prevent it? |
| --- | --- | --- |
| Malicious host | Send a multi-input SegWit PSBT across two sessions, understating a different input each time, and combine the individually valid signatures into a transaction with an arbitrarily large miner fee (F-03). Alternatively supply derivation metadata for a known xpub and collect a signature at a path of the attacker's choosing (F-04), or request `NONE \| ANYONECANPAY` for a reusable input signature after one generic warning (F-30). | **No — High.** All three reach confirmation over any enabled host transport, and the confirmation screen does not carry the information that would expose them: per-input values are on the hidden details page and there is no fee sanity check (F-24). USB being off by default reduces one transport's reachability but is not an authorization boundary after opt-in. |
| Malicious QR code | Encode any of the F-03, F-04, or F-30 payloads as a QR signing request. F-16 and F-28 additionally allow splicing or corrupting multipart payloads without authenticating the assembled message. | **No — High.** Scanning requires user action, but the resulting confirmation does not show enough to distinguish the hostile payload from a benign one (F-24, F-19). The QR framing defects are not needed for the signing paths; they widen payload confusion. |
| Malicious PSBT or PSET | For PSBT, F-03 inflates the fee paid to a miner and F-04 extracts a signature at a chosen path. For PSET, F-31 reaches a pre-confirmation native out-of-bounds write; F-11 and F-23 misrepresent confidential values or asset identity; F-35 renders distinct scripts as one address; F-30 yields a reusable `NONE \| ANYONECANPAY` signature. | **No.** The strongest PSBT paths are value-destroying (F-03) and a signing oracle (F-04). The strongest PSET path is confirmed memory corruption before user approval, although no key-extraction chain was established. |
| Malicious SD card | Supply a selected `.psbt` file carrying the F-03 or F-04 payload. The application-level adapter does not execute files, but it deliberately forwards their bytes to the signing flow. | **No for funds theft through signing.** File selection and confirmation are required, and neither exposes the defect. No application-level SD code-execution path was found. FatFs and native-driver memory safety are unreviewed. |
| Malicious USB device | After the user enables USB, take arbitrary-path xpubs and the master fingerprint with **no** per-request confirmation (F-05), then use them to build the F-04 derivation records and send the PSBT back over the same channel. | **No once USB is enabled.** The default-off setting reduces exposure but is not an authorization boundary after opt-in. F-05 and F-04 compose into a complete oracle over one transport. |
| Malicious, emulated, or substituted secure element | Report `PIN_UNLOCKED` and return a constant-key attacker seed (F-07, F-22), or stream card bytes into the pre-PIN native receive overflow (F-34). A card fault can also force the weaker SD backend (H-14). | **Not prevented.** PIN bypass and capture of future deposits are confirmed at the host-policy layer. F-34 adds native memory corruption with unproven control-flow impact. No path was found to extract the genuine card's existing seed. External applet behavior and target stack effects remain open. |
| Malicious firmware update | Harvest two release signatures through the generic message app (F-17). Separately, submit an unsigned but structurally valid SD image: F-33 clears WRP and destroys firmware before rejecting its signatures. With later flash write, F-25 accepts a replacement plus forged CRC records. | **No under the stated prerequisites.** The threshold verifier and the supported downgrade policy hold, but authorization-domain reuse and pre-authentication protection sequencing defeat the intended operational boundary. |
| Malicious dependency | Place seed-exfiltration or display/signing-divergence code in a dependency that executes inside the firmware trust boundary. | **No if malicious code is accepted into the pinned tree.** There is no sandbox between dependencies and wallet secrets. Outer pins, all MicroPython fork commits, and the secp binding were reviewed, but flattened HAL/USB/FatFs trees have no upstream SHA to reproduce or diff (D-02). |
| Malicious repository contributor | Hide exfiltration in trusted application or build code, or in a subtle flag or path change such as assert stripping, writable-path imports, warning removal, or provenance-free vendoring (H-13, F-15, H-22, D-02). | **No architectural prevention.** No deliberate backdoor was found, but F-15 proves a small import-path change can bypass signed-firmware expectations, and absent CI, CODEOWNERS, and release attestation weakens detection. |
| Malicious physical attacker | Read internal flash for F-06, write `/qspi/config.py` for persistent pre-PIN execution (F-15), induce F-32's USB MSC fault and chain it into both, or use a malicious smartcard (F-34). With direct flash write, install firmware and forge CRC records (F-25); F-33 can first clear WRP with an unsigned SD file. | **Conditional, and not established as prevented.** F-15 needs a QSPI writer, F-32 an inducible boot fault, F-34 timing, and F-06 and F-25 practical hardware access. Once those prerequisites hold, software controls do not restore the intended boundary. |
| Compromised build environment | Inject key-stealing code into compiler output or generated firmware, then present its opaque firmware hash to release-key holders for threshold authorization. F-08 also means the finished artifact does not record which key set established its trust root. | **Partly, but not reliably detected.** Two release signatures are still required, but F-17's signing UI does not bind approval to reviewed source or recognizable binary content. The Docker build appears deterministic by inspection, but no two clean builds and no official-release comparison were performed, so independent detection is unverified. |
| Malicious transaction | Request `NONE \| ANYONECANPAY` and later transplant the approved input signature into an arbitrary payment (F-30). Or rely on F-24 and F-19: present many outputs so the fee and every warning sit below the fold while Confirm stays pressable. | **No.** F-30 is a blank-cheque path gated only by a generic warning and user approval, and the confirmation screen does not reliably show the data that would make an unusual transaction recognizable. |
| Malicious wallet descriptor | Ask the user to import a policy in which an attacker key can satisfy the spending threshold, then steal funds deposited to that policy. After import, the ownership path re-derives the descriptor and overwrites host-supplied scripts, which prevents later script substitution (PATH-02). | **Partly.** The implementation prevents the post-import script-spoofing path and identifies device, external, and NUMS keys during confirmation. It cannot prevent theft when the user approves an attacker-spendable policy. Script and address-encoding safety is established for Bitcoin (PATH-34 to PATH-37) but not for the Liquid confidential encoder (F-35). Full Miniscript and TapTree safety is not established. |
| Malformed Bitcoin data | F-10 shows declared-length parser desynchronization in `non_witness_utxo` with unresolved target impact. Version-incompatible scope fields are rejected (PATH-41). | **Partly.** The version-consistency class is closed in the parser, though only there and with no test pinning it here (H-27). No reviewed malformed Bitcoin path independently established code execution; F-31 is the separate malformed-Liquid result. |

### 11.1 Final security questions

| Question | Assessment |
| --- | --- |
| Can a malicious host steal private keys through normal firmware interfaces? | No direct private-key or mnemonic export exists. But a host can take the **master xpub** and fingerprint with no confirmation at all (F-05), and can get a **recoverable** signature — and therefore the public key — at any derivation path with one confirmation. Privacy loss is total. No spending-authority path was found. Physical flash readout can enable seed recovery (F-06). |
| Can a host cause signing of a transaction different from what the user believes was approved? | **Yes, three ways.** F-03 is a value-destroying divergence paid to a miner: displayed input amounts are never authenticated (High). F-21 is a divergence on the message-signing prompt, where a NUL truncates what is drawn but not what is hashed (High). F-24 and F-19 are the structural version: the default screen omits input values and change outputs, transaction version, locktime, and input sequences appear on neither page, and the fee sits below an attacker-chosen number of outputs while Confirm stays fixed on screen. The v2-field parser class is closed (PATH-41), but only in the dependency (H-27). |
| Can malicious QR, PSBT, or descriptor data exploit the wallet? | **Yes for malicious PSBT data.** For QR, F-16 and F-28 let frames from two payloads be spliced and never check any checksum, and H-08 lets malformed characters decode silently. None is an independent theft primitive, because the result is still displayed, but they amplify payload confusion. Malicious PSET data additionally reaches the Liquid address encoder and produces a misleading confirmation screen (F-35) or aborts it (H-25). Script, Base58, and Bech32 handling is clean on the Bitcoin side (PATH-34 to PATH-37). Descriptor scope is only partly resolved: the ownership path re-derives and compares the scriptPubKey and the device overwrites host-supplied witness and redeem scripts, but full descriptor, Miniscript, and TapTree parser safety is not established. |
| Can SD or USB data execute unauthorized code? | No application-level adapter evaluates payload data, and boot-time SD module shadowing is not compiled in (PATH-30). However, F-32 plausibly exposes both flash partitions read-write over USB MSC after an inducible boot fault, and writing `/qspi/config.py` then reaches F-15's confirmed pre-PIN import on every normal boot. FatFs and native USB/SD memory safety is unreviewed. |
| Can firmware signature verification be bypassed? | Not by breaking the algorithm: the verifier and the tool/device message construction are sound. But **F-17** can harvest valid authorization through message signing, **F-25** accepts forged CRC records after direct flash write, and **F-33** lets an unsigned SD file clear WRP even though its bytes remain blocked from immediate execution (PATH-23). |
| Can an older vulnerable firmware be installed? | **No through the supported upgrade path.** `check_versions` compares against the maximum of the current integrity record and either version-check record. The erase sequence persists that maximum, so at least one copy survives every power-cut point, and the claimed version sits inside the signed section header and the authorization message. Bootloader fallback accepts only a copy with the same version, never older. Same-version recovery is intentionally allowed for a corrupt resident image. F-25's arbitrary flash write can rewrite records directly, and F-33 can destroy firmware and clear WRP but leaves the version floor intact. Neither is a supported-path rollback. See PATH-24 and PATH-26. |
| Can normal software interfaces extract stored secrets? | No spending seed or private-key path was found. Xpub and fingerprint leave with no confirmation (F-05). The Liquid **master** blinding key leaves with one (H-03 and the `slip77` command). BIP-85 mnemonics, xprv, and WIF are user-initiated only, and are displayed. |
| Can RAM remnants after shutdown be exploited? | Unknown, and not answerable from static review. Structurally, no secret is ever zeroized: they are immutable Python `str`/`bytes` under a GC, and there is no wipe of a secret buffer anywhere in `src/`. |
| Is entropy weak or predictable? | **Conditionally yes.** F-18 confirms that the TRNG driver returns zero-valued words on timeout and never checks the seed-error or clock-error flags. Seed generation becomes reproducible only if the failure persists and the software pool holds no attacker-unknown input. Prior touch timing or coordinates stay mixed into mnemonic-sized requests, so a transient fault does not imply an all-zero or attacker-known seed. Whether the peripheral faults in practice, and how much unpredictable touch state is present, needs hardware testing. |
| Can an attacker manipulate ECDSA nonces? | **No.** Stock deterministic RFC6979, deterministic counter bytes for low-R grinding, and no host-controlled data anywhere in nonce derivation. Hardening gaps only: the context is never randomized (F-14), and H-09 is a latent memory-safety bug in an unreachable nonce helper. Physical side-channel and fault resistance is incomplete. |
| Are address or transaction displays different from signed data? | **Yes. F-03, F-11, F-21, and F-35 are confirmed divergences, and F-23 adds host-chosen Liquid asset names. F-19 and F-24 confirm that the fee, input values, and warnings can be absent from the default view, and that transaction version, locktime, and input sequences are absent from both views.** On the address layer the two networks differ. Bitcoin holds: `bech32.py` passes the complete BIP-173/350 vector set, Base58Check enforces its checksum, `Script.script_type()` pins the witness version to {0,1} and the program to {20,32} bytes, the displayed string comes from the parsed scriptPubKey and nothing else, and `format_addr` only inserts spaces and newlines with no truncation (PATH-34 to PATH-40). Liquid does not: **F-35** shows the confidential-address encoder is neither injective nor total, so four distinct scriptPubKeys render as one address and OP_RETURN renders as a well-formed `lq1…` address. **F-36** breaks the decode direction, and **H-25** turns a Liquid p2pkh output into an aborted confirmation screen. |
| Can signatures or secret-derived material be obtained outside transaction confirmation? | **Yes, four ways.** Xpub and fingerprint with **no** confirmation (F-05). Up to 1000 raw TRNG bytes with **no** confirmation (F-14). A message signature at any path with one confirmation whose contents the host can partly hide (F-21). The SLIP-77 master blinding key with one confirmation. |
| Can a message signature be reused as a transaction signature? | No for Bitcoin or Liquid consensus data. The 25-byte domain prefix sits exactly where a sighash preimage keeps hash output, so a collision needs about 2^168 work, and the length prefix covers the exact bytes hashed. **But the same prefix is deliberately shared with firmware authorization (F-17)**, so a message signature can be a valid firmware signature, which is a higher-value target than a transaction. |
| Can a host obtain a signature at a derivation path the user did not intend? | **Yes.** F-04: derived keys are signed with no script-membership check, under any host-chosen path, over a sighash the host builds. A confirmation is shown, but it shows a transaction the user does not recognize as theirs. |
| Can secure-element replacement bypass PIN or force weaker fallback? | **Yes.** A card reporting `PIN_UNLOCKED` suppresses the PIN and anti-phishing screen (F-22). An attacker card can inject a constant-key seed (F-07). Faults can force the weaker or destructive fallback (H-14). Card-controlled UART bytes reach native memory corruption before PIN entry (F-34). No path extracted the genuine card's existing seed. |
| Can Liquid sign or disclose something Bitcoin would prevent? | **Yes.** The same root serves both networks. Liquid exposes the master blinding key (H-03, H-21), displays unverified amounts and host labels (F-11, F-23), renders addresses that do not identify the script being signed because its encoder lacks the script-type gate the Bitcoin encoder has (F-35 versus PATH-35), and its streaming rangeproof path adds pre-confirmation memory corruption (F-31). Whether a Liquid sighash can equal a Bitcoin sighash was not analysed. |
| Do vendored or submodule trees have unexplained upstream divergence? | **Unresolved, and not currently answerable from the repository.** Two positives: the checked-in secp256k1 generator table was recomputed entry by entry and matches, and all 63 MicroPython fork-only commits were reviewed. Against that, six of eight submodule URLs point at forks under one GitHub org and carry `branch =` declarations, and nothing in the tree records how those pins relate to upstream (§1.2, PATH-18). **D-02 adds** several large native trees flattened inside the MicroPython fork with no recorded upstream SHA, so their provenance cannot be reconstructed at all. No evidence of tampering was found anywhere it could be checked; this is a provenance gap, not a tampering result. |
| Could a malicious contributor add covert exfiltration that survives the build? | **Not ruled out.** Strong hiding places include `mpy-cross -O` removing assert validation (H-13), writable-path import resolution (F-15), warning removal (H-22), and provenance-free dependency flattening (D-02). The repository has no CI or CODEOWNERS control at this tag, and empirical release reproduction is absent. |
| Is released firmware independently reproducible? | **Expected yes, but not independently verified here.** Static inspection found a deterministic Docker route: the base image and toolchain input are fixed, Python packages are version- and hash-pinned, MicroPython emits fixed build metadata, source traversal is sorted, the container build path is fixed, and packaging injects no timestamp, randomness, or host Git metadata. Reproducing the signed upgrade also requires importing the same published signatures in the same order. No two-build or official-release binary comparison was performed. |
| Could the repository contain a non-obvious backdoor? | No deliberate backdoor was found. The Python source has no eval, process, or network implant, but F-15 proves that ordinary import can execute unauthenticated QSPI code, and D-02 shows that large flattened native trees cannot be reproduced from recorded upstream pins. All 63 MicroPython fork commits and the secp binding were reviewed. Full LVGL, FatFs, and HAL content, and release reproduction, remain open. |
| Which questions cannot be answered from static source alone? | RAM remnants, the hardware half of the entropy question, practical RDP/WRP and boot-fault behavior, target memory effects of F-31 and F-32, external applet behavior, and whether official release binaries reproduce exactly. Supported-path downgrade prevention is answered statically (PATH-24, PATH-26). |

## 12. Remediation priority and disclosure routing

### 12.1 Priority

1. **First, and nearly free: close the branch gap.** Cherry-pick `7223458`,
   `fc0e32d`, and `3d1bb8e` from `origin/master`, or rebase this branch onto it.
   That closes DOC-02, DOC-03, and part of F-24 with code that is already
   written, reviewed, and merged upstream of this branch, and it makes the
   shipped `docs/security-info.md` true rather than aspirational. Then diff the
   remaining 30 commits for security content (§1.3). Nothing else in this list
   has a comparable cost-to-benefit ratio.
2. **Emergency, process.** Stop signing releases with a key that can also be used
   by the generic message app, and give firmware authorization its own domain
   separator (F-17). The interim mitigation — a dedicated release key on a
   dedicated device — needs no code change.
3. **High, and cheap.** Reject NUL and non-printable bytes in the message-signing
   path, and cap the message length (F-21). That is a few lines, and it closes a
   display/signing divergence on the same prompt as item 2.
4. **High.** Reject hostile rangeproof lengths at the Python and native
   boundaries, make every stream read length-checked, and add target exploit
   regression coverage for F-31.
5. **High.** Move USB and dupterm shutdown to the first executable boot
   statements, make peripheral initialization fail closed, and prevent MSC from
   exporting wallet partitions in any fault state (F-32). Remove writable module
   roots, the empty import entry, and the executable `config` override (F-15).
6. **High.** Enforce previous-transaction verification (F-03) and equivalent
   script-membership checks for every signing key (F-04). In the same pass, add
   the scope-to-global-output equality check in this repository's wallet manager
   and a regression test that pins the parser's v2-field rejection (H-27) — the
   invariant the whole confirmation screen rests on is currently enforced only
   in a dependency tracked through a fork pin.
7. **High.** Stop trusting the card's PIN state, pin card identity, and correct
   the native receive bound before doing further smartcard work (F-22, F-07,
   F-34). Fix PPS checksum validation in the same change (H-23).
8. **High.** Harden flash-backed PIN derivation and readout protection (F-06).
   Because it needs physical read access, it ranks below remotely supplied
   signing and PSET defects.
9. **Medium.** Make WRP a boot-time invariant and restore it on every upgrade
   exit (F-33). Authenticate firmware at boot rather than trusting CRC32 (F-25).
   Record and separate release key sets (F-08).
10. **Medium.** Move the fee and warnings outside scrolling content, or gate
    confirmation on viewing them (F-19). Label change and preserve all warnings
    (F-24). Verify Liquid commitments and names (F-11, F-23). Confirm xpub and
    fingerprint export (F-05).
11. **Medium, and cheap.** Make TRNG failure fatal before seed generation
    (F-18), and refuse dangerous sighash modes rather than relying on a generic
    warning (F-30).
12. **Medium, and cheap.** Restore the four commented-out validity checks in
    `liquid/blech32.py` and gate `liquid/addresses.py` on `Script.script_type()`
    (F-35). One change closes F-35, F-36, and H-25, and it restores the property
    that a displayed Liquid address identifies exactly one scriptPubKey. Label hex
    fallbacks on the confirmation screen as unrecognized output scripts in the
    same pass.
13. **Medium and Low.** Bound PSBT values (F-10). Verify UR checksums and
    characters (F-28, H-08). Repair QR framing (F-16). Fail closed in crypto
    callbacks (F-13). Harden entropy export (F-14). Fix truthiness, channel-IV,
    backup-name, network-file, and assert-validation issues (H-06, H-10, H-11,
    H-12, H-13).
14. **Secret and UI hardening.** Remove QR stdout leakage (H-18). Sanitize wallet
    names (H-19). Warn and reauthenticate before GUI blinding-key export (H-21).
    Define and implement complete QSPI wipe semantics (H-24).
15. **Documentation, and cheap.** Fix the incorrect security claims in
    `docs/security-info.md`. DOC-01 — the self-contradicting offline-brute-force
    bullet — is a one-paragraph rewrite and is a genuine documentation defect,
    present on `origin/master` too. DOC-02 and DOC-03 are resolved by item 1
    rather than by editing; edit them only if the cherry-pick is rejected. All
    three are shipped user-facing claims, so they rank above the remaining build
    hardening.
16. **Build and dependency hardening.** Restore `-Wall` (H-22). Replace the
    compiler MD5 pin (F-09). Record upstream SHAs for flattened trees (D-02) and
    the upstream relation for the six forked submodules (§1.2, PATH-18). Refresh
    the release-tool lock at `cryptography==3.4.8` (D-03). Decide the
    `branch =` / fork-URL question and assert it in CI. Automate the generator
    and provenance checks.
17. **Planning.** Maintain an explicit security-backport policy for the 2019
    MicroPython base (D-01).
18. **Assurance.** Complete the target, hardware, release, and reproducibility
    tests, and continue below the application adapters into FatFs, mount
    handling, and the native SD and USB drivers.

### 12.2 Disclosure routing

F-04 and F-10 are defects in `embit` (`f469-disco/libs/common/embit/`), not in
this repository's own application code. F-03 is this repository's — a discarded
return value in `manager.py`. This repository is one consumer of that library,
so the remediation owner and the disclosure path differ from the rest of this
report:

- Handle **F-04 and F-10** as a coordinated disclosure to the `embit`
  maintainers first, on normal embargo terms, before any public Specter-DIY
  writeup. Every downstream consumer of the same code is affected the same way,
  not only Specter-DIY. Check whether upstream has already fixed them before
  setting the embargo clock.
- Route that disclosure to the **upstream `embit` project**, not to the fork
  this tree's submodule URL points at (§1.2). Whether the fork's `v0.8.2` is
  identical to upstream's is not established here (PATH-18); establish it before
  assuming an upstream fix would land in this tree.
- F-28 and H-08 belong to `microur` in `f469-disco/libs/common/`, not to this
  repository's application code. F-13, F-31, H-01, H-09, H-16, and H-17 belong
  primarily to the `secp256k1-embedded` binding fork; F-31 also needs a
  caller-side bound in this repository. F-18 belongs to the `micropython` fork.
- F-17, F-25, and F-33 are boot-chain disclosures. The bootloader and firmware
  must change together; for F-17 the interim mitigation is operational. Route
  them to release-key holders directly, not through a public issue.
- F-21, F-22, F-23, F-24, F-32, H-10, H-11, H-12, H-14, H-18, H-19, and H-21 are
  this repository's own code or integration, so they can be fixed without waiting
  on upstream. H-13 belongs to bundled `microur` plus this repository's build
  integration.
- F-15 and H-24 need coordinated changes in this repository and its pinned
  MicroPython storage and import integration. F-34 and H-23 belong to the
  `f469-disco` smartcard user module. H-22 and D-01/D-02 belong to the
  MicroPython fork, and D-03 to the bootloader tools dependency lock.
- F-35, F-36, and H-25 belong to `embit`
  (`liquid/blech32.py`, `liquid/addresses.py`), with unguarded call sites in this
  repository. H-26 is an upstream hardening item.
- Independently of upstream timing, this repository can and should add the
  defense-in-depth check in H-27: compare each displayed scope
  `(value, script_pubkey)` against the exact global transaction output that will
  be signed, in `src/apps/wallets/manager.py`, and add a regression test that
  pins the rejection. That check lives in code this project owns and does not
  depend on any upstream timeline.

## 13. Scope closure

### 13.1 Open questions requiring dynamic or hardware testing

1. Whether a fault on the assembled battery-gauge I2C bus raises before
   `boot.py` disables USB, and whether that state exposes CDC+MSC and internal
   flash exactly as the traced MicroPython fallback specifies (F-32).
2. The target effect of F-31: what occupies SDRAM above `0xC03EE000`, how the FMC
   aperture aliases after the populated region, and whether the sequential
   overwrite can be escalated beyond memory corruption.
3. The actual STM32 option-byte state before and after a signature-rejected
   upgrade, plus power cuts at each version-record erase step (F-33, F-25).
4. How the STM32 TRNG behaves in practice on stuck, repeated, or short reads. The
   *handling* of those cases is settled by F-18: it is fail-open. Hardware testing
   must establish how often faults occur, and whether mnemonic generation can
   begin before the pool receives touch timing or coordinates unknown to an
   attacker.
5. RDP1 extraction practicality on the deployed board and MCU revision, which is
   the precondition that makes F-06 reachable at all.
6. Smartcard substitution and interposition against a real applet, plus the
   card-side PIN attempt and secret-release logic (F-07). The applet source is not
   in this repository.
7. RAM and SDRAM remnants after normal shutdown, wipe, reset, and power
   interruption.
8. Behavior of the fail-closed wipe-on-flash-write-failure path under induced
   hardware faults (F-06).
9. MicroPython-specific memory behavior on the PSBT path. The parser results
   here establish semantics read from source and confirmed under CPython, not
   on-device memory behavior. PATH-41's rejection in particular has not been
   exercised on target.
10. Whether F-19's arithmetic holds on the real display. The layout is settled
    statically; only the exact per-output pixel cost is estimated.
11. Whether LVGL's `lv_label_set_text` truncates at an embedded NUL on target
    (F-21, step 4). Everything else in F-21 is settled statically. This is the
    single cheapest open test in the report.

### 13.2 Upstream and provenance status

Answered:

1. **All recursive gitlinks resolve through their declared origins.** The
   historical repository names `littlevgl/lvgl` and
   `ElementsProject/secp256k1-zkp` redirect to `lvgl/lvgl` and
   `BlockstreamResearch/secp256k1-zkp`, where the exact pinned objects resolve.
2. **The checked-in `ecmult_static_context.h` is canonical.** It is the
   `ecmult_gen` table, on the signing path, and all 1024 entries were recomputed
   from `gen_context.c`'s construction — the nums point from the ASCII seed
   `"The scalar for this x is unknown"` with even y, plus G, then the gbase and
   numsbase ladder with the `j == PREC_N-2` negation — and match exactly.
3. **MicroPython diverges by 63 commits from a v1.12-era base** (D-01), and all
   63 fork-only diffs were inspected. **LVGL does not diverge**; its pin is an
   upstream commit from 2019-10-29.
4. **The operative nested `secp256k1-zkp` pin resolves upstream.** The wrapper at
   `f469-disco/usermods/secp256k1` compiles the nested library at `d9560e0`, and
   the old `ElementsProject` URL redirects to the current upstream repository
   containing that exact commit.

Open:

5. **The upstream relation of the six forked submodules** — `f469-disco`,
   `specter-bootloader`, `micropython`, `secp256k1-embedded`, `embit`, and
   `fatfs`. Nothing in the tree records whether each pin is identical to, ahead
   of, or diverged from the corresponding upstream commit (§1.2, PATH-18).
   `embit` is the priority: it owns F-04, F-10, F-35, F-36, H-26, and the
   PATH-41 invariant.
6. The source and exact upstream commits of the flattened MicroPython `lib/`
   trees, especially the STM32 HAL, TinyUSB, FatFs, and mbedTLS (D-02).
7. End-to-end content review of the upstream borromean, surjection, and generator
   internals beneath the reviewed binding and custom arena code.
8. Which key set and protection configuration the official release binaries were
   built with, and whether two clean Docker builds reproduce each other and the
   official binaries. Static inspection found no deterministic blocker in the
   Docker route.

### 13.3 Tier 1 components and their remaining gaps

Stated plainly, as gaps rather than as coverage:

- **`src/gui/`** — the screen, page, and button layout is established (F-19,
  F-21, F-24, H-04, H-05, H-18, H-19, H-21). Not examined: `screens/input.py`
  (465 lines, the PIN entry UI) beyond the PIN-derivation call path, and target
  LVGL rendering.
- **`f469-disco/libs/common/embit/`** — PSBT and PSET scope parsing, the sighash
  paths, `sign_input`, `Descriptor.owns`, `check_derivation`, and `bip32` depth
  handling were traced, and the upstream delta is complete. The
  address-construction and encoding files are read in full (F-35, F-36, H-25,
  H-26, PATH-34 to PATH-40). **Not read:** `transaction.py`, `bip85.py`,
  `slip77.py`, `liquid/pset.py` beyond the output `verify` and blinding-pubkey
  paths, and `liquid/psetview.py`. Full Miniscript and TapTree behavior, including
  the taproot output-key tweak that feeds `p2tr` address generation, is Shallow.
- **Liquid** — the asset registry and host commands were read (F-23), the
  input/output metadata path produced F-11, and the address path produced F-35,
  F-36, and H-25. Issuance and reissuance, the rest of `pset.py` and
  `psetview.py`, and `rangeproof_preallocated_impl.h` (20 KB, not upstream, parses
  hostile proof data) were not reviewed.
- **`src/hosts/`** — the application-level SD and USB adapters and the whole
  `microur` UR decoder were read (F-28, H-08, H-13). The QR scanner state machine,
  `bcur.py` (legacy, reached from the `SIGN_BCUR` path), GUI transport timing,
  FatFs, and native SD/USB drivers were not traced.
- **`src/keystore/`** — all four classes and the whole JavaCard host-side stack
  were read (F-06, F-07, F-22, H-10, H-11, H-14). RAM remnants, fault injection,
  side channels, and the external card applet are out of reach of static review.
  The applet source is **not in this repository**, so the applet running on a
  user's card cannot be confirmed to match any source here.
- **`bootloader/`** — traced. All of `bootloader.c` plus the section, integrity,
  signature, KAT, utility, startup mailbox, startup selection, flash and
  option-byte, linker-map, platform-build, and host-tool paths were read.
  Version and downgrade enforcement, section parsing, mailbox handling, flash
  bounds, KATs, interrupted recovery, and tool/device differences are recorded in
  F-25, F-33, H-20, and PATH-23 to PATH-29. Remaining work is hardware, FatFs,
  SD-HAL, and LCD validation, not the bootloader core paths.
- **`f469-disco/usermods/secp256k1/`** — the binding and the custom preallocated
  rangeproof module are read in full. Core, rangeproof, surjectionproof,
  generator, Pedersen, Schnorr, callback, and call-site reachability work produced
  F-13, F-31, H-01, H-16, H-17, PATH-04, PATH-20, and PATH-21. Remaining gaps are
  target execution and SDRAM mapping, side-channel behavior, and end-to-end review
  of the upstream borromean, surjection, and generator internals the binding
  assumes correct.
- **`micropython` fork** — all 63 fork-only commits were inspected. Mount, CWD,
  and import resolution, flash partitioning, QSPI and storage, wipe, USB fault
  defaults, RNG, string rendering, native smartcard transport, and relevant build
  flags were traced (F-15, F-18, F-32, F-34, H-22 to H-24, D-01, D-02). Remaining
  gaps are the general upstream-v1.12 security and backport delta, and full
  memory-safety review of the flattened HAL, FatFs, and USB trees whose
  provenance is missing.
- **Application authorization review across `src/apps/`** — complete. Every app
  was read in full. Results are in F-05, F-14, F-21, F-23, the mnemonic-import
  fallback note in Section 8.4, and the confirmation inventory in Section 4.5.
- **`simulate.py` and simulator adapters** — read for production separation and
  hardware differences. No production reachability was found. **`hwidevice.py`,
  `test/`, and `demo_apps/`** received structural and manifest review only and
  remain shallow assurance surfaces.

### 13.4 Recommended follow-up scope

In priority order:

1. **Close the branch gap against `origin/master`** (§1.3). Three security
   changes that exist in this repository are absent from this branch, and the
   shipped security documentation already describes them. This is the cheapest
   item in the report and it retires DOC-02, DOC-03, and part of F-24.
2. **Route F-17 and F-25 to the release-key holders before anything else is
   published.** F-17's mitigation is available today without a code change, and
   publishing the report describes the attack.
3. **Run the first test in Section 10.2** — the F-21 NUL test on hardware. It
   costs one photograph and settles a High finding.
4. **Write the Section 10.2 regression tests.** Nothing in `test/` currently
   pins the v2-field rejection that PATH-41 rests on, so a future submodule bump
   can retire it silently (H-27). Cover crafted v0 PSBTs carrying each v2-only
   key in every field order, including duplicate `0x0f` records.
5. **Open coordinated disclosure with the `embit` maintainers** for F-04 and
   F-10, and establish first whether the fork this tree pins matches upstream
   (PATH-18). F-03 is this repository's own defect, not upstream's.
6. **Route F-35 and F-36 to the `embit` maintainers together with the PSBT
   items.** Restoring the four commented-out checks in `blech32.decode` and adding
   a `script_type()` gate to `addresses.address` closes F-35, F-36, and H-25 in
   one change. Then take the *taproot output-key tweak* and Miniscript/TapTree
   script construction to Deep, since those determine the `p2tr` program this
   encoder renders.
7. **Continue the SD and USB trace below the reviewed Python adapters.** Inspect
   FatFs, mount handling, filesystem edge cases, and the native SD and USB
   drivers, then fuzz malformed files and filenames on target.
8. **Run the native exploit and fault regressions.** Reproduce F-31 on
   target, exercise F-34 with a smartcard emulator and the release compiler, and
   test F-32's I2C fault plus the read-write MSC chain into F-15.
9. **Restore dependency and build assurance.** Record upstream SHAs for
   flattened MicroPython native trees (D-02) and the upstream relation for the
   six forked submodules (§1.2), restore `-Wall` (H-22), refresh the release
   tooling lock (D-03), and add CI attestation.
10. **Defer remaining hardware, physical, and side-channel work** (13.1) to a
    follow-up with device access. Static review cannot advance it further.

## 14. Scope conformance

This table separates document completeness from technical coverage.
**Complete** means the agreed static work and output are present. **Partial**
means the report holds useful evidence but a named source or dynamic boundary
stays open. **Not statically answerable** identifies a question that needs
hardware, an external component, or release artifacts.

| Scope requirement | Status | Evidence in this report | Remaining limitation |
| --- | --- | --- | --- |
| Component inventory, classification, trust boundaries, data flow, production separation | Complete | Sections 4 and 5 cover runtime, build, and simulator boundaries, asset access, hostile-input convergence, and achieved depth | Lower-layer detail is recorded as coverage rather than implied complete |
| Highest-risk theft paths | Complete | Sections 2, 3, 6, 8, and 11 give a finding, a blocking mechanism, or an explicit unresolved prerequisite for every prioritized path | Hardware prerequisites stay conditional where stated |
| Negative results and static-analysis limits | Complete | Section 5 records inspected paths, evidence, open questions, and recommended tests per component. Section 9 gives reproducible negative results and cross-cutting limits | Hardware and external-component questions stay explicitly unresolved rather than inferred |
| Full-form positive findings | Complete | Every `F-*` block records the required classification fields with the enumerated Status, Severity, access-flag, and Confidence values | Expanded prose may keep more nuanced confidence discussion |
| Short-form blocked and adequately handled paths | Complete | Section 9 contains PATH-01 to PATH-41 with evidence, enforcing mechanism, residual risk, and confidence | Each result is scoped only to the reviewed path. PATH-18 does not hold and is recorded as a negative result; PATH-16 holds only in its narrow form |
| Eight-column coverage report | Complete | Section 5 uses the required schema and only Shallow, Moderate, or Deep values | Shallow rows are substantive engagement gaps |
| Hostile-input source mapping | Complete | Section 4.4 gives an explicit source → gate → parser → operation map, and Section 4.5 the full host and APDU command inventory | Native-driver and external-scanner internals stay coverage gaps, not unmapped inputs |
| Malicious-code, backdoor, and static-indicator review | Partial | Section 8.1 closes the application Python sweep, all 63 MicroPython fork commits, and the secp binding, and names the concrete hiding places | Flattened native trees lack provenance and full content review. External scanner firmware and empirical release attestation stay open |
| Cryptographic lifecycle and library use | Partial | Entropy, RNG failure, ECDSA nonces, domains, the native binding and custom proof module, callbacks, and the generator table are covered | Side channels, physical faults, upstream proof internals, and BIP85/SLIP77 internals remain |
| Secret-lifetime audit | Complete for static source | Section 4.6 gives a per-secret create, transform, store, display, cache, and destroy matrix. Section 8.3 records lock-versus-erasure semantics | Physical RAM/SDRAM remanence and fault readout cannot be resolved statically |
| Persistent-storage and keystore audit | Partial | Every local keystore, the native and host smartcard stack, wipe paths, flash and QSPI layout, and backend selection produced F-06, F-07, F-22, F-34, H-10, H-11, H-12, H-14, H-24 | Physical readout, rollback, remanence, fault injection, and external applet behavior need target work |
| Firmware and bootloader audit | Complete for static source | The entire bootloader core, plus section, integrity, signature, KAT, mailbox, startup, flash-map, and tool paths were traced. F-25, F-33, H-20, and PATH-23 to PATH-29 record the result | Real option bytes, power-cut timing, SD HAL/FatFs, LCD, and physical faults stay dynamic |
| Parser audit | Partial | PSBT/PSET scopes, QR and UR paths, and the address and encoding family produced F-03, F-04, F-10, F-11, F-16, F-28, F-35, F-36, H-08, H-13, H-15, H-25, H-26, and PATH-34 to PATH-41 | `transaction.py`, Miniscript/TapTree, Liquid proof, BCUR, FatFs, and native driver parsers are incomplete |
| Transaction-signing audit | Partial | The principal Bitcoin display-to-sighash path is deep and produced F-03, F-04, F-30, PATH-41, and H-27. The address half of display-to-output correspondence is resolved for both networks (PATH-39, F-35) | Advanced policies, full Liquid processing, and target display rendering stay open |
| Multisignature audit | Partial | Bootloader multisignature verification and the descriptor ownership and script-replacement path are covered | Full wallet Miniscript/TapTree construction, ordering, threshold, and malformed-policy behavior stay shallow |
| Message signing and secret-derived export | Complete for application dispatch | All application modules were read. Message signing, xpub and fingerprint, entropy, BIP85 reachability, SLIP77, wallet export, and backups are assessed | Unread BIP85 and SLIP77 internals and target rendering details are disclosed separately |
| Secure element and smartcard | Partial | Host-side identity, channel, PIN, storage, and fallback, plus the native UART and T=1 receive paths, are deep (F-07, F-22, F-34, H-23) | External applet source, deployed-card behavior, and the exact F-34 stack effect stay unavailable or dynamic |
| Liquid and confidential transactions | Partial | Displayed inputs, asset labels, confidential-address generation and decoding, blinding-key export, network separation, and sighash warnings are covered (F-11, F-23, F-35, F-36, H-25) | Issuance and reissuance, the remaining PSET internals, rangeproofs, and surjectionproofs stay shallow |
| Address generation and verification | Complete for static source | `script.py`, `base58.py`, `bech32.py`, `networks.py`, `liquid/blech32.py`, `liquid/addresses.py`, and `liquid/networks.py` were read in full, and every sub-item is recorded: scriptPubKey construction (PATH-35), Bech32/Bech32m against the complete BIP-173/350 vector set (PATH-34), Base58Check (PATH-36, PATH-37), checksums (PATH-34, PATH-36), network prefixes and HRPs (PATH-40), witness versions and script-length constraints (PATH-34, PATH-35, F-35), and displayed-address-to-signed-output correspondence (PATH-39, PATH-38, F-35, F-36). Positive results: F-35, F-36, H-25, H-26 | The taproot output-key tweak and Miniscript/TapTree construction that produce the `p2tr` program feeding this encoder stay Shallow, and on-target rendering of the encoded strings needs a device |
| User-interface security | Complete for static source | Transaction, message, PIN, QR, and popup paths and the relevant LVGL input and recolor behavior are covered (F-19, F-21, F-24, H-04, H-05, H-06, H-18, H-19, H-21) | Exact target rendering, controller-level events, and physical visibility need device tests |
| Communication interfaces and command reachability | Complete at exposed-command level | Section 4 enumerates every host command, channel gate, consent state, smartcard APDU, QR state machine, and pre-PIN behavior | FatFs, SDMMC, USB HAL, and external scanner firmware stay content-level gaps |
| Simulator, hardware, and physical attack | Not statically answerable in full | Production and simulator separation and hardware-specific attack prerequisites are recorded | No hardware was accessed. Simulator, HWI, test, and demo content is shallow |
| Fault handling and recovery | Partial | Ignored verification, RNG timeout, callbacks, channel errors, fallback, boot faults, wipe, mailbox, WRP, and interrupted update were traced | Watchdog and reset breadth, and induced hardware-fault behavior, stay open |
| Control-flow-oriented audit | Partial | Every application module, the whole bootloader, the whole secp binding, the native smartcard path, and the critical runtime and import callers were traced | General interpreter, HAL, and native-driver callers and external firmware are incomplete |
| Security-model differential | Complete | Section 8.10 checks all 42 independently testable `docs/security-info.md` claims against the implementation, performs the reverse comparison, and records DOC-01, DOC-02, and DOC-03 | External hardware claims are marked conditional rather than inferred. Four of the contradictions trace to the branch gap in §1.3 rather than to a documentation error |
| Historical audit | Partial | All 63 MicroPython fork diffs and the security-sensitive regions of project history were reviewed, and the branch's relation to `origin/master` was established (§1.3). Findings include F-15, H-22, D-02, DOC-02, DOC-03 | The full project history was not read commit by commit, the 30 remaining `HEAD..origin/master` commits were not individually assessed, and signer identity could not be cryptographically verified |
| Dependency and submodule trust | Partial | Outer pins and origins, LVGL, the full MicroPython fork delta, the secp binding, the generator table, and the release lock were assessed | Flattened native trees lack upstream SHAs (D-02). Upstream equivalence is not established for the six forked submodules, which also carry `branch =` declarations (§1.2, PATH-18). Full advisory and backport review and official artifact reproduction remain |
| Final funds-theft analysis | Complete | Section 11 maps all 14 attacker capabilities to the strongest identified path and prevention result | Conditional prerequisites are explicit |
| Malicious-maintainer analysis | Partial | Section 8.1 ranks and demonstrates effective hiding places (F-15, H-22, D-02) and assesses the absent isolation, CI, and review controls | Full flattened-tree content, signer trust, and independent release reproduction stay open |
| Final questions and report structure | Complete | Section 11.1 answers every question, including static limits. Result classes and domain assessments have separate headings | None |

A shallow or unavailable component is never treated here as evidence that the
component is secure.
