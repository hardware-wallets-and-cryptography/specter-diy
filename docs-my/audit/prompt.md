# Specter-DIY Hostile Security Audit Prompt

## Role And Scope

You are performing a hostile, security-critical source-code audit of the Specter-DIY hardware cryptocurrency wallet firmware.

Treat this as a real hardware-wallet security audit, not as a conventional C/C++/Python code review.

The objective is to determine whether the code contains vulnerabilities, exploitable implementation flaws, malicious functionality, backdoors, supply-chain compromises, intentional or accidental key leakage, transaction-manipulation mechanisms, or other behavior that could cause loss or unauthorized transfer of cryptocurrency.

Do not assume that the project authors are trustworthy. Do not assume that the repository is benign merely because it is open source, popular, old, reviewed by contributors, or accompanied by security documentation.

At the same time, do not manufacture vulnerabilities. Every finding must be supported by concrete evidence in the source code, build system, dependency graph, generated artifacts, Git history, or documented architecture.

## Audit Scope And Depth Tiers

In scope, and enumerated: `src/`, `hwidevice.py`, `simulate.py`, `build_firmware.sh`, `Makefile`, `Dockerfile`, `manifests/`, `boot/`, `test/`, `docs/`.

Out of scope for enumeration: `f469-disco/`, `bootloader/`, `shield/`, `demo_apps/`.

**Trace-following exception.** Follow a trace into an out-of-scope tree when, and only when, an in-scope call site depends on the callee's behavior for its security conclusion. Read that callee, cite it by exact path and line, set `Owning codebase:` to the submodule, and do not enumerate its siblings. Where a conclusion cannot be reached without a broad sweep of an out-of-scope tree, record the path as `Blocked on out-of-scope dependency` and name the specific files that would be required.

This exception carries most of the weight for two trees. embit, at `f469-disco/libs/common/embit`, supplies PSBT, PSET, BIP-32, EC, script, and descriptor handling, and is therefore where most hostile-input byte parsing actually happens. `bootloader/` carries firmware authentication and its own vendored FatFs and secp256k1. Both are reachable by trace-following; neither is subject to enumeration.

Depth tiers:

- **Tier 1** — reachable from hostile input, or handling secrets: `src/hosts/`, `src/keystore/`, `src/apps/`, `src/gui/screens/`, `src/rng.py`, `src/specter.py`, `src/platform.py`, `src/qrencoder.py`, `src/helpers.py`.
- **Tier 2** — everything else in scope: the rest of `src/gui/`, `src/main.py`, `src/app.py`, `src/config_default.py`, `src/errors.py`, `boot/`, `manifests/`, build and release tooling, `hwidevice.py`, `test/`, `docs/`.

Tier is the assigned budget. Review Depth in the coverage report is what was actually achieved. The two are allowed to differ, and any gap must be stated plainly rather than presented as coverage.

## Final Result and Logging

Record all your intermediate findings in AUDIT-medium.log file.

Record all your final findings in audit.md file.

## Audit Execution Rules

- Use the actual source code as the primary evidence.
- Do not treat comments, documentation, project reputation, GitHub stars, or maintainer claims as proof that a security property is implemented.
- Do not claim that the firmware is secure merely because no vulnerability was found.
- Absence of evidence is not evidence of absence.
- Distinguish clearly between confirmed vulnerabilities, probable vulnerabilities, plausible concerns requiring dynamic testing, design limitations, hardening recommendations, and false positives.
- Do not exaggerate severity.
- Do not report merely theoretical concerns unless they have meaningful security consequences.
- Prioritize vulnerabilities that could result in unauthorized signing, private-key disclosure, seed disclosure, entropy compromise, signing nonce compromise, firmware compromise, or loss of funds.
- Deprioritize ordinary availability bugs, code-quality problems, and low-impact denial-of-service issues unless they affect wallet security.
- Do not make changes to the repository.
- Do not silently fix vulnerabilities.
- Do not rewrite code unless specifically requested.
- Several features of this wallet export secret or secret-derived material to the host by design, including raw entropy, BIP-85 derived entropy, Liquid blinding keys, extended public keys, and encrypted backups. Do not classify an intentional, documented export as a backdoor. Audit it as a deliberate secret-egress channel instead: what exactly leaves the device, whether the user is shown and must confirm what is leaving, whether the scope of the exported material is bounded, whether the export is confined to the key material it claims to expose, and whether a malicious host can widen that scope or invoke the export without user confirmation.
- Spend the effort budget on tracing attack paths end to end, not on producing an entry for every item in the checklists below. The checklists direct attention; they are not a required output format. One completely traced path from hostile input to signature is worth more than a full-breadth sweep containing no traced paths.

## Required Audit Phases

Work in phases. Do not proceed to broad conclusions until the current phase has produced concrete evidence.

If the full audit cannot be completed in one response, prioritize the high-risk theft paths in Phase 2, produce an interim report, and explicitly list the remaining phases.

### Phase 1: Trust Boundaries

The component inventory is given below as established fact. Do not spend budget rediscovering it. Verify an individual entry only when a finding depends on it.

In-scope Python is 75 files and roughly 11,000 lines under `src/`, plus roughly 600 lines of root-level tooling. Everything security-critical on the device is MicroPython; the native code, cryptographic libraries, hardware drivers, RNG peripheral, LVGL, FatFs, and firmware authentication all live in the two out-of-scope submodules and are reachable only by trace-following.

| Path | LOC | Role | Tier |
| --- | --- | --- | --- |
| `src/hosts/qr.py` | 1204 | QR host: UR / animated-QR frame reassembly. Largest host-facing parser in the application layer. | 1 |
| `src/hosts/usb.py`, `sd.py`, `core.py` | 182 / 187 / 160 | USB and SD transports; `Host` base class and command dispatch | 1 |
| `src/apps/wallets/` (top level) | 1438 | Wallet manager, PSBT flow, wallet identification, change detection, transaction screens | 1 |
| `src/apps/wallets/liquid/` | 715 | PSET flow, Liquid wallet, blinding | 1 |
| `src/apps/xpubs/` | 483 | Extended-public-key export, device fingerprint | 1 |
| `src/apps/bip85.py` | 189 | BIP-85 derivation of mnemonics and xprvs | 1 |
| `src/apps/compatibility.py` | 141 | Converts host-supplied JSON and files into Specter format | 1 |
| `src/apps/signmessage/` | 105 | Bitcoin message signing | 1 |
| `src/apps/label.py` | 62 | Device label get and set | 1 |
| `src/apps/blindingkeys/` | 54 | Liquid blinding-key export | 1 |
| `src/apps/getrandom.py` | 42 | Raw on-board TRNG bytes exported to the host on request | 1 |
| `src/apps/backup.py` | 33 | Backup creation and load | 1 |
| `src/keystore/` (top level) | 1428 | Four backends: `RAMKeyStore` (411), `MemoryCard` (469), `FlashKeyStore` (354), `SDKeyStore` (169). `__init__.py` re-exports only `FlashKeyStore`. | 1 |
| `src/keystore/javacard/` | 416 | Smartcard channel: `applet`, `securechannel` (201), `secureapplet`, `memorycard`, `blindoracle` (empty) | 1 |
| `src/specter.py` | 705 | Top-level orchestration: unlock flow, host and app wiring | 1 |
| `src/platform.py` | 369 | Platform abstraction: storage paths, USB configuration, flash, SD mount | 1 |
| `src/helpers.py` | 177 | Shared utilities | 1 |
| `src/qrencoder.py` | 147 | Outbound QR encoding | 1 |
| `src/rng.py` | 43 | Software entropy pool layered over the TRNG | 1 |
| `src/gui/screens/` | 1439 | Trusted display. `transaction.py` is the transaction-confirmation surface; `prompt.py`, `mnemonic.py`, `settings.py` are the other security-relevant screens. | 1 |
| `src/gui/` (rest), `components/` | 606 / 509 | LVGL wiring, async loop, widgets, theme. `tcp_gui.py` is simulator-only. | 2 |
| `src/main.py`, `app.py`, `config_default.py`, `errors.py` | 82 / 78 / 23 / 6 | Entry point, `App` base class, default config, error base classes | 2 |
| `boot/main/boot.py` | 65 | Production boot | 2 |
| `boot/debug/` | 143 | Debug boot, `debug.py`, `hardwaretest.py`. Not production, but confirm it cannot ship. | 2 |
| `manifests/disco.py`, `unix.py`, `debug.py` | 6 total | Frozen-module manifests selecting the build variant | 2 |
| `Makefile`, `build_firmware.sh`, `Dockerfile` | 118 / 66 / 23 | Build and release tooling | 2 |
| `hwidevice.py` | 397 | HWI driver. Runs on the host PC, not on the device. | 2 |
| `test/tests/`, `test/run_tests.py` | 2002 | Unit tests, simulator-driven | 2 |
| `test/integration/` | 1081 | Integration tests, simulator plus Bitcoin Core RPC | 2 |
| `docs/` | — | `security.md`, `communication.md`, `reproducible-build.md`, `descriptors.md` are the claim source for the security-model differential audit | 2 |

Production versus non-production separation, as given: `src/` plus `boot/main/` plus `manifests/disco.py` is device firmware; `src/gui/tcp_gui.py`, `simulate.py`, and `config_default.py`'s `simulator` branch are simulator-only; `test/` and `demo_apps/` are not shipped; `boot/debug/` and `manifests/debug.py` are a separate build variant; `hwidevice.py` runs off-device.

Required output — one table, nothing else:

| Boundary | Untrusted side | Trusted side | What crosses it | Enforcement point (`file:line`) | Fails open or closed |
| --- | --- | --- | --- | --- | --- |

One row per boundary. Cover at minimum: host-to-device over each of QR, USB, and SD; device-to-smartcard in both directions; unlocked-to-locked keystore state; bootloader-to-firmware; and the user-confirmation boundary between an app requesting an action and the action executing. The "What crosses it" column is the data-flow map — name the assets, not the general category. Where no enforcement point exists, write `none found` rather than leaving the cell vague.

### Phase 2: Highest-Risk Theft Paths

Prioritize these paths before lower-impact audit areas:

1. A malicious PSBT causes unauthorized signing.
2. A malicious descriptor, xpub, fingerprint, or derivation path causes wrong-wallet or wrong-change signing.
3. Malicious QR, USB, or SD-card input reaches a parser, filesystem API, native interface, or privileged operation.
4. A malicious host causes the displayed transaction to differ from the transaction that is actually signed.
5. Private key, seed, mnemonic, entropy, or signing nonce material is disclosed.
6. Firmware-update or bootloader verification is bypassed.
7. Entropy generation, seed generation, or ECDSA nonce generation is weak, predictable, biased, reused, or attacker-influenced.
8. Persistent storage can be decrypted, brute-forced offline, rolled back, downgraded, or bypassed.
9. A malicious host obtains a signature or secret-derived material outside the transaction-confirmation flow, through message signing, entropy export, BIP-85 derivation, blinding-key export, xpub export, or backup export.
10. The secure-element or smartcard channel is bypassed, spoofed, replayed, or downgraded, or the device silently falls back to a weaker keystore backend.

For each path, provide either:

- a concrete finding;
- an evidence-backed explanation of why the path is blocked; or
- a clear statement that static analysis is insufficient and dynamic testing is required.

### Phase 3: Evidence-Backed Findings

Every finding must include:

- Exact file path.
- Function, class, module, build target, or code region.
- Relevant line numbers or commit region.
- Reachability from attacker-controlled input or privileged execution flow.
- Exploitability assessment.
- Confidence level.
- Reason the issue is not merely theoretical.

### Phase 4: Negative Results And Static-Analysis Limits

For every major audit area, state:

- What was inspected.
- What evidence supports the conclusion.
- What was not inspected.
- What cannot be concluded from static source inspection alone.
- Which dynamic tests, hardware tests, fuzzing campaigns, or reproducible-build checks are needed next.

Do not write generic statements such as "appears safe" without citing the implementation mechanism that enforces the relevant safety property.

## Hostile Input Sources

Attacker-controlled, without further argument: everything entering through `src/hosts/` (each individual frame of an animated QR stream, each USB line, each SD file); everything read from storage a host or physical attacker can write (the `fs` tree, external QSPI, SD card, backup files presented for restore, the network file, firmware-update images); every response from an attached smartcard, including absence, error, and replay; and every host-supplied parameter to an app command — derivation path, index, length, wallet name, device label, Liquid asset name, descriptor, xpub.

Do not re-enumerate this list in the report. For each input you actually trace, state which of these it can influence: signing, secret export, the trusted display, wallet identification, keystore-backend selection, firmware execution, filesystem access, persistent state, or error and recovery behavior.

## Malicious-Code And Backdoor Audit

A backdoor here would be logic-level and would look cryptographically legitimate. It would not look like malware. The places it would be effective, and therefore where to spend the effort: the divergence between what `src/apps/wallets/` displays and what it signs; change detection and wallet identification; `src/rng.py`; keystore-backend selection and the PIN paths in `src/keystore/`; the smartcard channel in `src/keystore/javacard/`; and boot-time initialization and imports in `boot/` and `src/platform.py`.

Two patterns to hunt for. First, behavior conditioned on something an attacker chooses or knows in advance — a specific fingerprint, xpub, address, amount, asset, network, firmware version, counter, date, or device state. Second, security-critical logic that only executes in a branch nobody runs: an exception handler, a legacy or recovery path, a debug or factory mode, a platform-specific branch. Also check for secret material reaching an unexpected sink — a persistent file, a log or stdout write, an error message, apparently harmless metadata, or an outbound QR or USB payload.

Classify each suspicious behavior as: benign and justified / suspicious but explained / suspicious and requiring investigation / strong evidence of malicious functionality. Unusual is not malicious. A comment explaining the code is not evidence that the code does what the comment says; the code is the authority.

Apply the intentional-export rule from the execution rules above. This wallet deliberately exports entropy, BIP-85 derived entropy, extended public keys, Liquid blinding keys, and encrypted backups. Audit those as secret-egress channels with confirmation and scoping requirements, not as backdoors.

## Static Malware Indicators

Run a single pass for dynamic-execution and covert-egress primitives — `eval`, `exec`, `compile`, `__import__`, `importlib`, dynamic imports, reflection, shell or process execution, sockets, HTTP, DNS, Bluetooth, Wi-Fi, raw device access, environment access, hardcoded key, seed, mnemonic, or address constants, encoded and compressed blobs, runtime-generated code, and unexpected native extensions. Determine the legitimate purpose, reachability, and security implication of anything found, then move on.

On MicroPython firmware this pass has low yield. Do not spend meaningful effort on it, and do not let it displace the Phase 2 path tracing or the logic-level backdoor analysis above, which is where a real backdoor in this codebase would live.

## Cryptographic Security Audit

Trace the entire lifecycle of:

- Entropy, including any entropy pool, mixing function, or reseeding behavior layered on top of the hardware source.
- Mnemonic generation.
- Seed derivation.
- Private-key derivation.
- BIP-85 derived entropy and the boundary between exported derived entropy and wallet keys.
- Liquid master blinding key and per-output blinding-key derivation, if Liquid is supported.
- Transaction signing.
- Message signing.
- Signature verification.
- Secret storage.

Determine exactly where randomness comes from and whether the entropy source is appropriate for a hardware wallet.

Establish specifically whether the firmware consumes the hardware entropy source directly or interposes a software pool, mixer, or whitening step. If it interposes one, determine the pool's initial state, whether that initial state is a constant, whether host-supplied or otherwise attacker-influenced data can be mixed into the pool, whether the construction can reduce the entropy that the hardware source already provided, and what happens when the hardware source fails or is unavailable. Determine the same for the simulator build and state whether the simulator's source differs from the device's.

Check for:

- Insufficient entropy.
- Predictable entropy.
- Biased randomness.
- Repeated randomness.
- Failure to detect RNG failure.
- Entropy reuse.
- Attacker-controlled entropy.
- Deterministic fallback behavior.
- Unsafe mixing of entropy sources.
- Weak or attacker-influenced signing nonces.
- Nonce reuse.
- Incorrect deterministic ECDSA signing.
- Unsafe signature validation.
- Unsafe public-key validation.
- Missing scalar-range validation.
- Invalid curve-point handling errors.
- Point-at-infinity handling errors.
- Private-key zero or out-of-range handling errors.
- Cryptographic failures that continue execution unsafely.

Audit:

- BIP-39 implementation and mnemonic handling.
- Seed derivation.
- BIP-32 derivation.
- Hardened and non-hardened derivation paths.
- BIP-85 derivation and the isolation between derived child entropy and the wallet's own keys.
- SLIP-77 or equivalent blinding-key derivation, if Liquid is supported.
- Private-key handling.
- secp256k1 usage, including the MicroPython usermod binding layer and any zero-knowledge or range-proof extensions compiled into it.
- ECDSA signing nonce generation.
- Signature validation.
- Public-key validation.
- Secret-dependent timing, exceptions, memory access patterns, logging, and observable behavior where relevant to the architecture.

Determine whether cryptographic operations are implemented in Python, native code, or external libraries. Identify the security implications of each.

Do not assume that calling a reputable cryptographic library automatically makes the surrounding code secure. Audit how the library is called.

## Secret-Lifetime Audit

For every sensitive value, determine where it is:

- Created.
- Copied.
- Transformed.
- Stored.
- Displayed.
- Serialized.
- Passed between functions.
- Cached.
- Destroyed.

Pay special attention to:

- Mnemonics.
- Seeds.
- Passphrases.
- Private keys.
- HD nodes.
- Temporary byte arrays.
- Serialized private keys.
- Signing nonces.
- PIN-derived keys.
- Device secrets.
- Secure-element session keys, transport keys, and card-resident secrets held in device RAM.
- Liquid blinding keys.
- BIP-85 derived entropy and the entropy pool itself.
- Encryption keys.
- Decrypted persistent data.
- Backup material staged in memory or on removable media.
- Buffers containing PSBTs, PSETs, or transactions.

Determine whether:

- Secrets can remain in RAM after use.
- Python object copies can leave multiple copies of sensitive material in memory.
- Immutable Python strings are used for secrets and prevent reliable zeroization.
- Garbage collection creates additional copies or prevents deterministic wiping.
- Exceptions can retain sensitive objects.
- Tracebacks, logs, assertions, debugging facilities, or crash dumps can expose secrets.
- Secrets are ever written to flash, SD card, USB, external QSPI storage, swap-like mechanisms, or other persistent media.
- Secret data can accidentally enter filesystem caches or serialized application state.

## Persistent-Storage Audit

Identify every location where sensitive information can be stored, and enumerate every keystore backend the firmware supports, including RAM-only, internal flash, SD card, and any secure-element or smartcard backend.

For each backend, determine which security properties it provides, which it does not, how the active backend is selected, whether that selection is recorded anywhere the user can verify, and whether the device can be induced to fall back to a weaker backend without the user noticing. Compare the set of backends actually implemented in code against the set the project documentation claims to support; a backend present in code but described as unavailable in the documentation is a security-model discrepancy and must be reported as one.

For each location, determine:

- Exact stored data.
- Exact protection mechanism.
- Encryption algorithm and mode.
- Key derivation process.
- Whether keys are derived from the PIN and device secret correctly.
- Whether the PIN is verified on the device, on an external secure element, or both, and what an attacker gains by removing, replacing, emulating, or replaying the responses of that external element.
- Offline brute-force resistance.
- PIN attempt rate limiting, and whether the attempt counter is held somewhere an attacker can reset or roll back.
- Lockout behavior.
- Anti-phishing behavior.
- Reset, deletion, reflash, and upgrade behavior.
- Whether deleted or old encrypted secrets can remain recoverable.
- Whether old encryption keys or device secrets remain accessible.
- Rollback and downgrade resistance.

## Firmware And Bootloader Audit

Inspect the bootloader submodule and every relevant bootloader interface.

Determine:

- What establishes the root of trust.
- Which public keys are trusted.
- How firmware signatures are verified.
- What exact bytes, sections, metadata, version fields, and images are authenticated.
- Whether signed data and executed data can differ.
- Whether malformed firmware is rejected safely.
- Whether an attacker with SD-card, USB, or physical access can cause unsigned or unauthorized code to execute.

Check for:

- Signature bypasses.
- Parsing differences between the bootloader and firmware.
- TOCTOU issues.
- Integer overflows.
- Length inconsistencies.
- Rollback vulnerabilities.
- Version-counter handling errors.
- Key-revocation weaknesses.
- Threshold or multisignature verification errors.
- Firmware-update recovery bypasses.
- Debug or development behavior enabled in production.

## Parser-Security Audit

The parsers that matter here, in priority order: the UR / animated-QR reassembler in `src/hosts/qr.py`; the PSBT and PSET paths in `src/apps/wallets/` and `src/apps/wallets/liquid/`, whose byte-level work is done by embit and is reached by trace-following; the descriptor parser; `src/apps/compatibility.py`, which converts host-supplied JSON and files; the message-signing input path including the derivation path and any constraint on the message bytes; and the smartcard response parser in `src/keystore/javacard/`.

For the QR reassembler specifically, because it is the largest host-facing parser and it holds state across frames: sequence numbers, part counts, duplicate and out-of-order parts, mismatched or interleaved streams, incomplete streams, whether any checksum binds a frame to its payload, and whether frames from two different payloads can be combined into one accepted message.

The question for each parser is not whether malformed input crashes. It is whether malformed input yields a *different valid interpretation* than the one the user was shown, or bypasses a check. Concretely: length fields that disagree with the data they bound, duplicate or omitted fields, fields the parser ignores that a signer uses, unknown versions accepted, non-canonical or ambiguous encodings, integer overflow and signed/unsigned confusion in offsets and amounts, unbounded reads and writes in native code reached from Python, and differentials where two components read the same structure differently.

Report a crash, hang, or allocation blow-up only where it is a memory-safety issue in native code, or where it leaves the device in a less safe state than before.

## Transaction-Signing Security Audit

This is the highest-priority part of the review.

Trace the complete path:

```text
host input -> QR/USB/SD transport -> parser -> PSBT/transaction object -> wallet identification -> input verification -> output verification -> fee calculation -> change detection -> user display -> user confirmation -> signature generation -> signed output
```

Determine exactly what the user sees before signing, and whether the bytes displayed — or a transaction object provably equivalent to the one displayed — are the bytes actually signed. A correct displayed representation is not evidence of anything. Name the mechanism that binds display to signature, or state that none exists.

For each property below, establish where it is verified against the transaction actually being signed, and what happens when the PSBT omits it, duplicates it, or supplies two fields that disagree:

- Recipient addresses and amounts; change addresses and amounts; fee and fee rate.
- Input ownership, wallet identity, and the derivation paths of both inputs and outputs.
- Script type, redeem and witness scripts, taproot data if supported, and multisig participants and threshold.
- Sighash flags, including unsupported modes accepted after nothing more than a warning.
- Version, locktime, and sequence numbers.
- Network selection, and mainnet/testnet separation.
- Already-signed inputs, mixed wallets, unknown inputs and outputs, descriptor-derived addresses, gap-limit behavior.
- Liquid, if supported: confidential amounts, confidential assets, asset IDs, and blinded outputs, including whether the user can see and verify unblinded values that correspond to what is signed.

The failure modes to hunt for: display/signing divergence; change-output substitution; xpub or derivation-path substitution; multisig participant substitution; PSBT field substitution or omission, including a field the display path reads but the signing path does not; parser differentials between two components reading the same structure; address-type and network confusion; and integer rounding or conversion errors in amounts and fees.

Do not assume that "Bitcoin Core compatible" means equivalent behavior.

## Multisignature Audit

Determine:

- How cosigners are identified.
- Whether xpub fingerprints are authenticated and correctly compared.
- Whether derivation paths are validated.
- Whether key ordering is enforced correctly.
- Whether script construction is canonical and expected.
- Whether descriptor parsing is strict.
- Whether threshold handling is correct.
- Whether an attacker can substitute one cosigner's key for another.
- Whether malformed or ambiguous multisig configurations can result in signing an unexpected script.

## Message-Signing And Key-Export Audit

Transaction signing is not the only way to obtain a signature or key material from this device. Audit every operation that produces a signature, exports secret-derived material, or reveals wallet structure, independently of the PSBT flow.

Cover at least:

- Message signing.
- Extended-public-key export.
- Entropy export to the host.
- BIP-85 derived-entropy export.
- Liquid blinding-key export.
- Backup creation and restore.

For each, determine:

- Which key or secret is used, and at which derivation path.
- Whether the derivation path is host-controlled, and if so what the accepted range is.
- Whether the device will sign or export at a path belonging to a wallet the user did not intend to use.
- What exactly is displayed before the user confirms, and whether the displayed representation fully determines what is produced.
- Whether the operation can be invoked without user confirmation, or confirmed once and then replayed.
- Whether the signed message or exported payload can be structured so that it is also valid as something else, in particular whether an attacker can obtain a signature over data that a Bitcoin or Liquid node would accept as a transaction, a sighash, or another consensus-relevant preimage.
- Whether a domain separator, prefix, or length-prefixing scheme prevents that cross-protocol reuse, and whether it is applied to the exact bytes that are hashed.
- Whether exported material is scoped to what the feature claims to expose, and whether a malicious host can widen that scope.

Treat an unconfirmed or path-unconstrained signing or export primitive as a high-severity finding even when no complete theft chain is demonstrated, and state what the missing link would be.

## Secure-Element And Smartcard Audit

If the firmware supports a secure element, smartcard, or applet-based keystore, treat the card as a distinct component across a real trust boundary, and treat the channel between the device and the card as an attack surface in both directions.

Determine:

- Which secrets live on the card and which live on the application microcontroller.
- Which operations the card performs and which the firmware performs after receiving a response.
- How the card is authenticated to the device and the device to the card, and whether either direction is unauthenticated.
- Whether the channel is encrypted, integrity-protected, and replay-protected, and how session keys are established.
- Whether the firmware trusts card responses without verification, and what an attacker gains by emulating a card, replacing a card, replaying recorded responses, or injecting errors into the channel.
- Whether PIN verification, attempt counting, and lockout occur on the card, on the application microcontroller, or both, and which of those an attacker can bypass.
- What happens when the card is absent, unresponsive, returns an error, or is removed mid-operation, and whether any of those states causes a fallback to a weaker keystore backend or a fail-open outcome.
- Whether card-resident applet source is present in this repository, whether it is built and verified as part of the release process, and whether the applet running on a user's card can be confirmed to correspond to that source.
- Whether the project documentation accurately describes the availability and security properties of this backend.

## Liquid And Confidential-Transaction Audit

If the firmware supports Liquid, confidential transactions, or PSET, audit that path with the same depth as the Bitcoin path. It is a second parser, a second signing flow, a second class of secret material, and a second display surface.

Determine:

- How PSET parsing differs from PSBT parsing and whether the two disagree about any shared structure.
- How blinding keys are derived, stored, used, and exported, and what a host learns from a blinding-key export.
- Whether blinding-key export is confirmed by the user and scoped to the intended wallet or output.
- Whether asset IDs, confidential amounts, and blinded outputs are verified against what the user is shown.
- Whether an attacker can cause the device to sign a confidential transaction whose true amounts, assets, or recipients differ from the displayed ones.
- Whether Liquid-specific code paths can be reached from the Bitcoin flow, or Bitcoin keys used in the Liquid flow, in a way that crosses wallet or network boundaries.
- Whether range proofs, surjection proofs, and other proof data are validated or trusted, and the consequence of trusting them.

## Address-Generation And Verification Audit

Check every supported address type.

Audit:

- ScriptPubKey construction.
- Bech32 and Bech32m handling.
- Base58 handling.
- Checksum validation.
- Network prefixes.
- Witness versions.
- Script-length constraints.
- Exact correspondence between displayed addresses and transaction outputs being signed.

## User-Interface Security Audit

The screen is the user's primary trusted display.

Determine whether attacker-controlled input can influence what is displayed.

Look for:

- Truncation attacks.
- Unicode and confusable-character attacks.
- Invisible characters.
- Ambiguous address formatting.
- Amount formatting errors.
- Decimal and locale problems.
- Scientific notation or integer formatting problems.
- Screen-buffer manipulation.
- Scroll behavior that can hide critical transaction information.
- UI states in which the transaction can be approved without the security-critical information being displayed.
- Race conditions between displayed data and signed data.

## Communication-Interface Audit

Audit USB, SD-card, QR, secure-element, and other communication interfaces separately.

Assume:

- The host is fully malicious.
- SD-card contents are fully malicious.
- QR data is fully malicious.
- USB input is fully malicious.
- An attached secure element or smartcard may be absent, emulated, replaced, or replaying recorded responses.

For each interface, enumerate the complete command or message set it exposes, including any command that exists only for development, diagnostics, or host tooling, and determine which commands are reachable before PIN entry or other authentication.

Determine whether any of these channels can directly or indirectly execute code, access filesystem APIs, invoke Python evaluation, reach native interfaces, control hardware peripherals, or trigger privileged functionality.

## Simulator, Hardware, And Physical-Attack Audit

Audit simulator-only code separately from production firmware.

Identify code paths that differ between simulator and physical hardware. Do not treat successful simulator tests as evidence that the physical firmware is secure.

Audit hardware-specific code related to:

- Memory-mapped I/O.
- DMA.
- Interrupt handlers.
- Flash access.
- QSPI.
- SD-card drivers.
- USB drivers.
- Display drivers.
- Camera and QR components.
- Entropy and RNG peripherals.
- Watchdog behavior.
- Boot configuration.
- Debug interfaces.
- JTAG, SWD, or equivalent interfaces.

Determine whether debug functionality can remain enabled in production and whether physical access can expose secrets through debug hardware.

## Fault-Handling And Recovery Audit

Security failures must fail closed.

Look for:

- Exception handlers that continue execution after cryptographic, parsing, storage, authentication, or signature-verification failures.
- Default values that become security-sensitive when parsing fails.
- Fail-open behavior.
- Retry loops.
- Recovery modes.
- Factory-reset behavior.
- Firmware-update recovery behavior.
- Watchdog resets that leave sensitive data available.

## Control-Flow-Oriented Audit

Identify security-critical functions and trace all callers.

For every function that can sign, derive keys, access secrets, decrypt secrets, export secret-derived material, authenticate firmware, parse transactions, or authorize a transaction, determine whether alternative call paths bypass expected security checks.

Confirmation is the check most likely to be bypassed. For each such function, identify every call site and determine whether user confirmation is enforced inside the function itself or only by the caller. A security-critical operation whose confirmation lives in one caller and not another is a finding.

Pay special attention to:

- Rarely used functions.
- Exception paths.
- Legacy compatibility paths.
- Test and demo code.
- Recovery paths.
- Factory modes.
- Development modes.
- Conditional compilation.
- Platform-specific branches.
- Version-specific branches.
- Mainnet-specific branches.

## Security-Model Differential Audit

Read the project's security documentation and threat model.

Then verify every claimed security property against the actual implementation.

For every documented guarantee, locate the implementation that enforces it.

For every documented limitation, determine whether the limitation is accurately described.

Look specifically for:

- Security properties claimed by documentation that are not actually enforced by code.
- Security-critical behavior implemented in code but absent from the documentation.
- Documentation that understates or overstates realistic attacker capabilities.

## Historical Audit

Perform a historical audit if Git history is available.

Inspect security-sensitive changes and suspicious commits involving:

- Cryptographic code.
- Randomness.
- Seed generation.
- Signing.
- PSBT parsing.
- Transaction display.
- Address generation.
- Firmware verification.
- Bootloader verification.
- PIN handling.
- Persistent storage.
- Encryption.
- USB.
- SD card.
- QR parsing.
- Filesystem handling.
- Build scripts.
- Dependency changes.

Pay particular attention to:

- Large security-sensitive changes with little test coverage.
- Unexplained changes to cryptographic constants.
- Removed checks.
- Disabled assertions.
- Changes from strict validation to permissive parsing.
- Changes that make security-critical code shorter, more indirect, or harder to review.

## Dependency And Submodule Trust Audit

For every external dependency that influences wallet security, determine:

- What it does.
- Where it comes from.
- Whether source code is included.
- Whether it contains native code.
- Whether it processes attacker-controlled data.
- Whether it handles private keys or signatures.
- Whether it has known security issues.
- Whether the build process verifies its integrity.

Pay special attention to:

- embit, which supplies PSBT, PSET, BIP-32, EC, script, and descriptor handling and is therefore the location of most hostile-input parsing in this project.
- secp256k1, including the MicroPython usermod binding and any zkp or range-proof extensions.
- MicroPython.
- LVGL.
- QR-related code.
- Bootloader code, including its own vendored FatFs and secp256k1.
- Filesystem and storage code.
- Native components.

This section is governed by the trace-following exception in the scope rules. Provenance, integrity verification, and pinning of these dependencies are answered from in-scope files — `.gitmodules`, submodule commit pointers, `Makefile`, `build_firmware.sh`, `Dockerfile`, `requirements.txt` — and those must be checked. Their internals are read only where an in-scope trace lands in them, and are never enumerated.

## Final Funds-Theft Analysis

Assume the attacker wants to steal Bitcoin from a wallet containing significant funds.

Construct realistic attack paths beginning with each major attacker capability:

- Malicious host.
- Malicious QR code.
- Malicious PSBT or PSET.
- Malicious SD card.
- Malicious USB device.
- Malicious, emulated, or substituted secure element or smartcard.
- Malicious firmware update.
- Malicious dependency.
- Malicious repository contributor.
- Malicious physical attacker.
- Compromised build environment.
- Malicious transaction.
- Malicious wallet descriptor.
- Malformed Bitcoin data.

For each attacker capability, determine the strongest realistic attack path and whether the current implementation prevents it.

## Malicious-Maintainer Analysis

Assume one repository contributor intentionally wants to introduce a subtle backdoor that survives normal code review.

Identify the places where such a backdoor could most effectively be hidden.

Evaluate whether the current architecture, tests, reproducible builds, cryptographic design, dependency policy, release process, and review process would detect it.

## Coverage Report Requirement

At the end, include a coverage table with these columns:

| Component | Depth Tier | Files/Directories Inspected | Security Relevance | Review Depth | Evidence Produced | Unresolved Questions | Recommended Dynamic Tests |
| --- | --- | --- | --- | --- | --- | --- | --- |

Depth Tier is the tier assigned in the scope section: 1 or 2. Review Depth is what was actually achieved. Where a Tier 1 component was reviewed only shallowly, say so plainly rather than presenting the gap as coverage.

Use one of these review-depth values:

- Shallow.
- Moderate.
- Deep.

Do not imply full coverage of a component unless its relevant code paths were actually traced.

## Required Finding Format

Two forms are defined. Use the one that matches the result, and do not spend the effort budget filling in template fields that carry no information.

**Short form** — use for any path or area that resolves to blocked, adequately handled, or false positive. Three to six lines:

```markdown
### PATH-ID: Short Title — Blocked / Not reachable / False positive

Evidence: file path, function, and line region of the mechanism that enforces the property.
Why it holds: one or two sentences naming the specific check, not a general impression.
Residual risk: what would break this conclusion, or "none identified".
Confidence: High / Medium / Low
```

**Full form** — required for every finding classified as Confirmed, Probable, or Plausible, and for any Design limitation with a material impact on funds. Also use it for a blocked path whose blocking mechanism is subtle enough that another researcher would need the detail to verify it.

Use this exact structure for each such finding:

```markdown
### FINDING-ID: Short Title

Status: Confirmed / Probable / Plausible / Design limitation / Hardening / False positive
Severity: Critical / High / Medium / Low / Informational
Affected component:
Files:
Functions/classes/modules:
Relevant code region:
Attacker capability:
Prerequisites:
Default reachability:
Impact on funds:
Physical access required: Yes / No / Unknown
Malicious host required: Yes / No / Unknown
Malicious SD/QR/USB input required: Yes / No / Unknown
Malicious firmware update required: Yes / No / Unknown
Prior compromise required: Yes / No / Unknown
Deterministic or probabilistic:
Security property violated:
Evidence:
Attack trace or minimal proof of concept:
Why existing checks do not prevent it:
Recommended remediation:
Confidence: High / Medium / Low
Owning codebase: this repository / named upstream dependency
```

For every finding reported in full form, provide enough technical detail that another security researcher can independently reproduce the analysis.

## Required Final Questions

The final assessment must explicitly answer:

- Can a malicious host steal private keys through the firmware?
- Can a malicious host cause the device to sign a transaction different from what the user believes they approved?
- Can malicious QR, PSBT, or descriptor data exploit the wallet?
- Can malicious SD-card or USB data execute unauthorized code?
- Can an attacker bypass firmware signature verification?
- Can an attacker install an older vulnerable firmware?
- Can an attacker extract stored secrets from the normal software interfaces?
- Can an attacker exploit RAM remnants after shutdown?
- Can an attacker exploit weak or predictable entropy, including any software entropy pool layered over the hardware source?
- Can an attacker manipulate ECDSA signing nonces?
- Can an attacker exploit address or transaction-display discrepancies?
- Can a malicious host obtain a signature or secret-derived material outside the transaction-confirmation flow, through message signing, entropy export, BIP-85, blinding-key export, xpub export, or backup export?
- Can a signature obtained through message signing be reused as a valid signature over consensus-relevant data?
- Can an attacker who can emulate, replace, or remove the secure element extract secrets, bypass PIN verification, or force a fallback to a weaker keystore backend?
- Can the Liquid or confidential-transaction path be used to sign or disclose something the Bitcoin path would prevent?
- Can the released firmware be independently reproduced from source?
- Can the source repository itself contain a backdoor that would not be obvious from a superficial review?

State explicitly which of these questions cannot be answered from static source inspection alone.

## Required Final Report Structure

Produce a prioritized audit report with the most serious findings first.

The final report must contain:

1. Overall risk assessment.
2. Executive summary of highest-risk theft paths.
3. Component inventory and trust-boundary map.
4. Coverage report.
5. Confirmed vulnerabilities.
6. Probable vulnerabilities.
7. Potential vulnerabilities requiring dynamic testing.
8. Malware/backdoor assessment.
9. Cryptographic assessment.
10. Private-key and secret-memory assessment.
11. Transaction-signing assessment, including message signing, key-export operations, and the Liquid path if supported.
12. Parser assessment.
13. Firmware, bootloader, and secure-element assessment.
14. Build and supply-chain assessment.
15. Physical-attack assessment.
16. Dependency assessment.
17. Security-model discrepancies.
18. Negative results and static-analysis limitations.
19. Testing gaps.
20. Recommended next tests.

## Priority Guidance

Because this is a cryptocurrency hardware wallet, the audit must prioritize vulnerabilities that could result in unauthorized signing, private-key disclosure, seed disclosure, entropy compromise, signing nonce compromise, firmware compromise, or direct theft of funds.

Ordinary denial-of-service issues, style problems, and low-impact robustness bugs should be reported only when they have a meaningful security consequence or help explain a higher-impact finding.

## Effort Budget

This charter is longer than any single audit run can execute. Treat it as the full engagement scope, not as a checklist to be completed in one pass. A scoping document may narrow it to specific phases or areas for a given run; where such a document exists, it governs.

Absent other direction, allocate roughly as follows:

- No more than a tenth of the effort to Phase 1. The component inventory is supplied as fact, so Phase 1 produces the trust-boundary table and nothing else. It establishes orientation; it is not where findings come from. The budget this frees goes to Phase 2.
- The majority of the effort to Phase 2 and to the sections that support it: transaction signing, parsers, message signing and key export, cryptography, and secret lifetime.
- The remainder to build and supply chain, bootloader, secure element, and the historical and malicious-maintainer analyses.

If the budget runs short, finish tracing the paths already started rather than opening new areas, and state plainly which areas were not reached. An audit that traces four paths to completion and names the rest as unexamined is more useful than one that touches every section and concludes nothing.

Negative results must stay compact. For each area, one short paragraph citing the enforcing mechanism at a specific file and line region is sufficient. Do not expand the negative-results and coverage sections to compensate for a lack of findings.
