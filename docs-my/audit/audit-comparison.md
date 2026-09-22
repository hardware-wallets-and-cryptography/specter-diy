# Audit Comparison: `audit.md` vs. current tree

**Audit baseline:** `24d1137a` (tag `v1.9.0`), report dated 2026-08-31

**Verified against:** branch `master-from-tag-1.9.0--my-changes--int`, HEAD `666d26d`

**Verification date:** 2026-09-22

## Status Summary

| Class | Total | Resolved | Partially Resolved | Active | No action |
| --- | --- | --- | --- | --- | --- |
| F (findings) | 31 | 2 | 2 | 27 | 0 |
| H (hardening) | 24 | 0 | 0 | 23 | 1 |
| D (dependency) | 3 | 0 | 1 | 2 | 0 |
| **Total** | **58** | **2** | **3** | **52** | **1** |

Plus seven audit-hygiene, provenance, and doc-vs-code items (`AD-01` … `AD-07`) recorded in
[Audit document hygiene and doc-vs-code drift](#audit-document-hygiene-and-doc-vs-code-drift).
These are outside the finding-by-finding scope, but three deserve attention alongside the
findings:

- **AD-04 and AD-05** are live incorrect security claims in the shipped documentation.
- **AD-06** invalidates the audit's submodule-provenance premise (§1.2, PATH-16, PATH-18):
  six `branch =` declarations now exist where the audit certified none, and six of eight
  submodule URLs moved to forks.
- **AD-07** records the largest gap in this comparison: 37 of the audit's 40 `PATH-xx`
  "defenses that hold" were **not** re-verified, including eight embit-owned ones that the
  submodule swap directly exposes.

### Resolved

| ID | Severity | What fixed it |
| --- | --- | --- |
| ✅ F-01 | Critical | embit v0.8.2 `PSBTScope.read_from` version guard |
| ✅ F-02 | High | Same guard |

### Partially resolved

| ID | Severity | Closed | Still open |
| --- | --- | --- | --- |
| F-18 | Medium | Python-layer TRNG liveness check | `rng_get()` still returns `0` on timeout; `SECS`/`CECS` unchecked |
| F-14 | Low | "No runtime TRNG health test" bullet | Constant pool seed, >64-byte pool bypass, unconfirmed `getrandom` export, no `context_randomize` |
| D-03 | Informational | `cryptography` 3.3.2 → 3.4.8 | 3.4.8 is from Aug 2021 and still predates several advisories |

### Active by severity

- **Critical:** none
- **High:** F-03, F-04, F-06, F-17, F-21, F-22, F-31, F-32
- **Medium:** F-05, F-07, F-08, F-10, F-11, F-15, F-19, F-23, F-24, F-25, F-28, F-30, F-33, F-34, F-35
- **Low:** F-09, F-13, F-16, F-36, H-01, H-03, H-05, H-06, H-08, H-09, H-10, H-11, H-12, H-13, H-14, H-15, H-16, H-17, H-18, H-19, H-20, H-21, H-22, H-23, H-24, H-25
- **Informational:** H-26, D-01, D-02

### No action

H-04 was recorded as "No defect found" in the original audit. Re-checked: unchanged, still no defect.

### Overall risk

The audit set overall risk at **Critical until the PSBT display/signing divergence is fixed**.
That divergence is fixed. With ✅ F-01 and ✅ F-02 closed the top remaining items are F-03 (an
equally real display/fee divergence with no parser fix behind it), F-04 (a signing oracle),
F-31 (pre-confirmation native OOB write), and F-21 (message signing shows less than it signs).
**Current overall risk: High.**

---

## Detailed Audit Review

### F-03: Input verification failures are discarded

- **Current Status:** Active
- **Codebase Evidence:**
  [manager.py:654](../../src/apps/wallets/manager.py#L654) is unchanged:

  ```python
  # verify, do not require non_witness_utxo if witness_utxo is set
  inp.verify(ignore_missing=True)
  ```

  Return value discarded. `grep -rn "is_verified" src/` returns **zero** hits, so the
  `embit` API for this is still never consulted — confirmed against embit v0.8.2, which
  still sets `self._verified` in [psbt.py:297-299](../../f469-disco/libs/common/embit/src/embit/psbt.py#L297-L299).
  The Liquid manager has the same call at
  [liquid/manager.py:294](../../src/apps/wallets/liquid/manager.py#L294).
  The aggravating factors also hold: per-input values are still drawn only on `page2`
  ([transaction.py:85-108](../../src/gui/screens/transaction.py#L85-L108)), and
  `meta["warnings"]` is still never populated on the Bitcoin path.
- **Actionable Fix / Changes Needed:**
  1. In [manager.py:648-699](../../src/apps/wallets/manager.py#L648-L699), capture and act
     on the result:

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
     [transaction.py:66-77](../../src/gui/screens/transaction.py#L66-L77) render
     `Fee: ~N satoshi (UNVERIFIED)` in `style_warning` when it is False.
  3. Preferred, if no wallet depends on unverified amounts: make it fatal —
     `raise WalletError("Missing non_witness_utxo for input %d" % i)`.
  4. Add the F-24 fee sanity check as the compensating control.

---

### F-04: Derived keys are signed without the root-key script-membership check

- **Current Status:** Active
- **Codebase Evidence:**
  embit v0.8.2 reordered `derived_keypairs` into an `OrderedDict` for determinism but did
  not add the membership test. [psbtview.py:857-867](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L857-L867):

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

  The x-only comparison is also unchanged at
  [psbtview.py:820-821](../../f469-disco/libs/common/embit/src/embit/psbtview.py#L820-L821).
  [ram.py:77-78](../../src/keystore/ram.py#L77-L78) still passes `self.root`, and
  [manager.py:786](../../src/apps/wallets/manager.py#L786) still calls
  `self.keystore.sign_input(...)` for every input regardless of whether a wallet resolved.
- **Actionable Fix / Changes Needed:**
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
     `keystore.sign_input` when no wallet resolved for that input, rather than relying on
     the generic "Unknown wallet in inputs!" prompt.

---

### F-06: Flash-backed PIN protection allows one-HMAC-per-guess offline brute force

- **Current Status:** Active
- **Codebase Evidence:**
  Unchanged. [flash.py:126-128](../../src/keystore/flash.py#L126-L128):

  ```python
  key = tagged_hash("pin", self.secret)
  pin_hmac = hmac.new(key=key, msg=pin.encode(), digestmod="sha256").digest()
  ```

  [flash.py:139](../../src/keystore/flash.py#L139) still derives
  `pin_secret = tagged_hash("pin", self.secret + pin.encode())`. The device secret is still
  read in cleartext from `/flash/keystore/secret` at
  [ram.py:130-138](../../src/keystore/ram.py#L130-L138). No memory-hard KDF, no minimum PIN
  length. RDP2 is still compiled out in the bootloader — see F-08.
- **Actionable Fix / Changes Needed:**
  1. Replace the single HMAC with a memory-hard KDF. MicroPython on this board has no
     scrypt/argon2, so the practical option is a PBKDF2-SHA256 wrapper with a high, tuned
     iteration count plus a stored per-device salt:

     ```python
     # flash.py
     PIN_KDF_ITERS = 200_000   # tune against the F469 budget, target ~1s
     def _pin_kdf(self, pin: str) -> bytes:
         return hashlib.pbkdf2_hmac("sha256", pin.encode(),
                                    tagged_hash("pin-salt", self.secret),
                                    self.PIN_KDF_ITERS, 32)
     ```

     Use it for both `self.pin` (verifier) and `self.pin_secret`. Version the on-flash
     record so existing devices migrate on next successful unlock.
  2. Enforce a minimum PIN length in [input.py:208-300](../../src/gui/screens/input.py#L208-L300)
     — the PIN screen currently imposes none.
  3. Keep the RDP1 limitation documented next to the storage guarantees in
     [docs/security-info.md](../../docs/security-info.md) — the successor to the
     `docs/security.md` the audit cites. It already covers this at
     [security-info.md:139-148](../../docs/security-info.md#L139-L148), but see AD-04:
     a later bullet in the same document contradicts it.

---

### F-17: Firmware authorization and user message signing share one signing domain

- **Current Status:** Active
- **Codebase Evidence:**
  Both sides unchanged across the bootloader bump.
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

  Same prefix, same length encoding, same double SHA-256, no domain separator on either
  side. The message app still accepts any derivation path with no allowlist. Commit
  `b971923` bumped the bootloader to 1.0.2 for key rotation but did not change the
  signature message construction.
- **Actionable Fix / Changes Needed:**
  1. **Real fix (coordinated bootloader + firmware change):** give firmware authorization
     its own prefix in `bl_signature.c`, e.g.
     `#define SPECTER_FW_SIG_PREFIX ("\x1eSpecter Firmware Authorization:\n")`, and bump
     the upgrade-file format version so old bootloaders reject new files and vice versa.
     Update [bootloader/tools/upgrade-generator.py](../../bootloader/tools/upgrade-generator.py)
     `message` output at the same time.
  2. **Interim, no firmware change required:** in
     [signmessage.py](../../src/apps/signmessage/signmessage.py), refuse to sign any message
     whose Bech32 HRP matches the bootloader grammar (`^b\d+\.\d+\.\d+`), or refuse paths
     under the release-key branch. Document the release-key derivation path and constrain it.
  3. Have the message app detect the bootloader `hrp` grammar and show an explicit
     "This authorizes a FIRMWARE RELEASE" screen rather than the generic message prompt.

---

### F-21: Message signing displays less than it signs

- **Current Status:** Active
- **Codebase Evidence:**
  [signmessage.py:59-68](../../src/apps/signmessage/signmessage.py#L59-L68) is unchanged:

  ```python
  try:
      msg = "Message:\n\n"
      msg += "__________________________________\n"
      msg += message.decode("ascii")
      msg += "\n__________________________________"
  except:
      msg = "Hex message:\n\n%s" % hexlify(message).decode()
  ```

  No NUL rejection, no control-character filter, no length cap. `base64:` decoding at
  [signmessage.py:57](../../src/apps/signmessage/signmessage.py#L57) is unbounded. The
  MicroPython fork is still pinned at `6bdf1b6`, so `objstr.c`'s discarded encoding
  argument and `unicode.c`'s NUL-accepting `utf8_check()` are unchanged. The path is still
  unbounded ([signmessage.py:43-51](../../src/apps/signmessage/signmessage.py#L43-L51)),
  the signature is still recoverable
  ([ram.py:83-88](../../src/keystore/ram.py#L83-L88)), and the address mapping still falls
  through to p2pkh for `m/86h`
  ([signmessage.py:78-83](../../src/apps/signmessage/signmessage.py#L78-L83)).
- **Actionable Fix / Changes Needed:**
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

     This closes the NUL truncation, the U+202E/homoglyph variants, and the forged
     `__________` separator in one change.
  2. Move the frame lines out of the message label into their own labels so they cannot be
     forged.
  3. Bound the derivation path (see H-15 item 3) and warn when it lies outside any known
     wallet's paths.
  4. Fix the address mapping: add `86h → p2tr`, or drop the address line for unrecognized
     purposes rather than showing a misleading p2pkh address.
  5. Gate Confirm on scroll-to-end — see F-19.

---

### F-22: The device trusts the smartcard's own report of its PIN state

- **Current Status:** Active
- **Codebase Evidence:**
  Unchanged. [secureapplet.py:48-51](../../src/keystore/javacard/applets/secureapplet.py#L48-L51)
  still takes the whole PIN policy from a card response:

  ```python
  def get_pin_status(self):
      status = self.sc.request(self.PIN_STATUS)
      (self._pin_attempts_left, self._pin_attempts_max, self._pin_status) = list(status)
  ```

  [secureapplet.py:77-80](../../src/keystore/javacard/applets/secureapplet.py#L77-L80)
  derives `is_locked` from `self._pin_status`, [secureapplet.py:105-106](../../src/keystore/javacard/applets/secureapplet.py#L105-L106)
  short-circuits `unlock()` on it, and [memorycard.py:101-102](../../src/keystore/memorycard.py#L101-L102)
  forwards it straight through. `RAMKeyStore.unlock`'s `while self.is_locked` loop is
  unchanged. No device-side PIN-attempt counter exists anywhere in `src/keystore/`.
- **Actionable Fix / Changes Needed:**
  1. Always prompt for a PIN at boot when a smartcard keystore is selected, regardless of
     what the card reports. In `RAMKeyStore.unlock`, replace `while self.is_locked` with a
     first-iteration-unconditional loop for card-backed keystores.
  2. Add a device-side monotonic PIN-attempt counter in `/flash/keystore/` and cross-check
     it against `_pin_attempts_left`; treat a disagreement as a card-swap and hard-fail.
  3. Pin the card public key at pairing — see F-07, which is the prerequisite for this
     being meaningful.
  4. Require confirmation of the resulting wallet fingerprint after each "Load key from
     smartcard".

---

### F-31: A short PSET rangeproof length underflows the rewind read loop into an out-of-bounds write

- **Current Status:** Active
- **Codebase Evidence:**
  `f469-disco/usermods` is byte-identical to the audited tree.
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

  The Python caller is also unchanged.
  [liquid/wallet.py:65-80](../../src/apps/wallets/liquid/wallet.py#L65-L80) reads the
  CompactSize straight from the PSET stream and passes it with no minimum and no arena
  bound:

  ```python
  stream.seek(rangeproof_offset)
  l = compact.read_from(stream)
  ...
  value, vbf, msg, _, _ = secp256k1.rangeproof_rewind_from(
      stream, l, memptr, memlen, nonce, commit, vout.script_pubkey.data, gen)
  ```
- **Actionable Fix / Changes Needed:**
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

     Treat a short read as failure regardless of `errcode` — `mp_stream_rw` reports EOF
     with `errcode == 0` ([stream.c:59-68](../../f469-disco/micropython/py/stream.c#L59-L68)).
  2. Python, in `LWallet.fill_pset_scope`, validate before crossing the boundary:

     ```python
     l = compact.read_from(stream)
     if l < 65 or l > memlen:
         raise RewindError("Invalid rangeproof length %d" % l)
     ```
  3. Fix the ABI mismatch in the same module first — see H-16 — or the arena bound the
     native check relies on is itself garbage.

---

### F-32: Boot-time USB hardening is applied last, and MicroPython's fault default is CDC+MSC

- **Current Status:** Active
- **Codebase Evidence:**
  [boot/main/boot.py](../../boot/main/boot.py) is unchanged. The ordering is still:
  power hold (line 13-14) → I2C init and battery-gauge write (lines 19-23) →
  LEDs → `pyb.ExtInt(...)` (line 49) → and only then, at lines 57-59:

  ```python
  pyb.usb_mode(None)
  os.dupterm(None,0)
  os.dupterm(None,1)
  ```

  The buggy `sys.path` cleanup at lines 7-10 is also unchanged (see F-15).
  `f469-disco/micropython` is still pinned at `6bdf1b6`, so `flash_error(4)` returning
  rather than halting, the `USBD_MODE_CDC_MSC` default, and the read-write MSC partition
  map are all unchanged.
- **Actionable Fix / Changes Needed:**
  1. Move the three USB-off lines to the very top of `boot.py`, above the power hold:

     ```python
     # boot.py -- first three statements, before anything fallible
     import pyb, os
     pyb.usb_mode(None)
     os.dupterm(None, 0)
     os.dupterm(None, 1)
     ```
  2. Wrap the fallible peripheral setup (I2C, ExtInt) so a raise cannot leave the device
     in a less-secure state than it started:

     ```python
     try:
         i2c = pyb.I2C(1); i2c.init()
         if 112 in i2c.scan():
             i2c.mem_write(0b00010000, 112, 0)
     except Exception:
         i2c = None          # continue with USB already off
     ```
  3. Make `platform.enable_usb` clear both dupterm slots itself, so no caller can enable
     USB and leave the REPL attached.
  4. Longer term: patch the fork so `flash_error()` halts instead of returning for the
     frozen-`boot.py` failure case.

---

### F-05: USB exports arbitrary-path xpubs and the fingerprint without confirmation

- **Current Status:** Active
- **Codebase Evidence:**
  [xpubs.py:257-277](../../src/apps/xpubs/xpubs.py#L257-L277) is unchanged. `show_screen`
  is a parameter and is never called:

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

  `LIST_WALLETS` at [manager.py:238-240](../../src/apps/wallets/manager.py#L238-L240) is
  likewise unconfirmed.
- **Actionable Fix / Changes Needed:**
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
  3. Decide explicitly whether `LIST_WALLETS` needs a prompt or an interface-level opt-in;
     it currently enumerates wallet names to any host.
  4. Bound the path depth here too — this handler is the reachable entry point for
     H-15 item 3.

---

### F-07: Smartcard identity is trust-on-first-use, and public-constant blobs lack origin authentication

- **Current Status:** Active
- **Codebase Evidence:**
  [securechannel.py:52-58](../../src/keystore/javacard/applets/securechannel.py#L52-L58)
  still fetches `card_pubkey` from the card and never pins it;
  [securechannel.py:201](../../src/keystore/javacard/applets/securechannel.py#L201) still
  discards it on close. The public-constant blob format is unchanged —
  [memorycard.py:171](../../src/keystore/memorycard.py#L171) and
  [memorycard.py:185](../../src/keystore/memorycard.py#L185):

  ```python
  res = aead_encrypt(b"\xcc"*32, self.MAGIC + fingerprint, r)
  ...
  key = b"\xcc"*32
  ```

  The anti-phishing words still come only from `PinScreen`, and whether a PIN screen is
  drawn is still decided by the card (F-22). The destructive no-PIN fallback in
  [flash.py:173-186](../../src/keystore/flash.py#L173-L186) is unchanged (H-14).
- **Actionable Fix / Changes Needed:**
  1. Pin the card key at first pairing, stored AEAD-encrypted under the device secret:

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
  2. Remove the `b"\xcc"*32` blob format, or gate it behind a per-load "this seed is
     unauthenticated" prompt.
  3. Always require PIN entry at boot (F-22), so the anti-phishing words are always shown.
  4. Confirm the resulting wallet fingerprint after each card load.

---

### F-08: Bootloader key selection is unrecorded in build output, and RDP1 is the default

- **Current Status:** Active
- **Codebase Evidence:**
  [bootloader/Makefile:20](../../bootloader/Makefile#L20) still has `KEYS ?= selfsigned`,
  and [build_firmware.sh:21](../../build_firmware.sh#L21) still calls
  `make stm32f469disco READ_PROTECTION=1 WRITE_PROTECTION=1` without `KEYS=production`.
  The fail-closed guard at [bootloader/Makefile:35](../../bootloader/Makefile#L35) is intact.
  RDP2 is still compiled out at
  [bl_syscalls.c:750-753](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L750-L753):

  ```c
  // RDP Level 2 is intentionally disabled. If misused may brick your board!
  ```

  Commit `d7597b6` rotated the production keys, but `vendor_pubkey_list` and
  `maintainer_pubkey_list` in
  [bootloader/keys/production/pubkeys.c](../../bootloader/keys/production/pubkeys.c) remain
  **byte-identical** — the same four keys (k9ert, Mike, Stepan, Backup m/99h) in the same
  order, with `bootloader_sig_threshold = 2` and `main_fw_sig_threshold = 2`. So the
  role separation still gives no defense in depth.

  Partial improvement, not a fix: the bumped bootloader adds
  [tools/introspect-binary.py](../../bootloader/tools/introspect-binary.py) and
  [tools/parse_pubkeys.py](../../bootloader/tools/parse_pubkeys.py), which can verify a
  signed binary against a `pubkeys.c`. These read the **source** file, so they do not let
  a finished artifact carry evidence of its own trust root.
- **Actionable Fix / Changes Needed:**
  1. `build_firmware.sh`: pass `KEYS=production` explicitly instead of relying on a manual
     `cp` into a directory named `selfsigned`.
  2. Record the key set in the artifact. Emit a `keyset.txt` next to the release binaries
     containing the SHA-256 fingerprint of each compiled-in key —
     `parse_pubkeys.get_pubkey_info` already computes exactly this, so wiring it into
     `build_firmware.sh` is a few lines.
  3. Make the vendor and maintainer lists genuinely distinct, so 2-of-4 on firmware is not
     the same 2-of-4 as on the bootloader.
  4. Tighten the bound at [bootloader.c:247-248](../../bootloader/core/bootloader.c#L247-L248)
     to count *distinct* keys rather than key slots.
  5. Document the RDP1 limitation next to the storage guarantees; RDP2 being irreversible
     is a legitimate reason not to enable it by default, but it should be stated where
     F-06's threat model is described.

---

### F-10: `non_witness_utxo` parsing is not bounded to its declared field length

- **Current Status:** Active
- **Codebase Evidence:**
  embit v0.8.2 did not change this. [psbt.py:307-322](../../f469-disco/libs/common/embit/src/embit/psbt.py#L307-L322):

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

  `l` is discarded. The embedded transaction is parsed directly from the parent stream, so
  no bounded substream and no exact-consumption check tie it to the declared field
  boundary. Independent `PSBTView` scanners still honor the declared length.
- **Actionable Fix / Changes Needed:**
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

     `read_vout` may legitimately stop early; in that case seek to `start + l` and verify
     the seek lands inside the scope rather than requiring exact consumption for that branch.
  2. Add a differential test asserting `InputScope` and the length-honoring `PSBTView`
     scanner see the same key set over identical bytes.

---

### F-11: Liquid input values and assets are displayed from unverified fields

- **Current Status:** Active
- **Codebase Evidence:**
  [liquid/wallet.py:62-64](../../src/apps/wallets/liquid/wallet.py#L62-L64) is unchanged —
  the comment still describes a verification that does not happen:

  ```python
  if None not in [scope.asset, scope.value, scope.asset_blinding_factor, scope.value_blinding_factor]:
      # verify that asset and value blinding factors lead to value and asset commitments
      return True
  ```

  `grep -rn "unblind" src/` finds no call site for `LInputScope.unblind` in the PSET
  signing flow. Display metadata still uses the host-supplied values directly at
  [liquid/manager.py:375-380](../../src/apps/wallets/liquid/manager.py#L375-L380).
- **Actionable Fix / Changes Needed:**
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
  2. If the check cannot be performed (missing blinders), set `scope.value = -1` so the
     screen renders `???` — `TransactionScreen` already handles that sentinel at
     [transaction.py:95](../../src/gui/screens/transaction.py#L95) — and exclude the input
     from any computed total.
  3. Do not compute or display a fee when any input amount is unverified.

---

### F-15: A production boot import executes unsigned Python from writable QSPI

- **Current Status:** Active
- **Codebase Evidence:**
  [boot.py:7-10](../../boot/main/boot.py#L7-L10) is unchanged and still inert:

  ```python
  for p in sys.path:
      if "qspi" in sys.path:     # tests for the exact element "qspi", never present
          sys.path.remove(p)
  ```

  [platform.py:9-12](../../src/platform.py#L9-L12) still runs the unauthenticated import at
  module top level:

  ```python
  try:
      import config
  except:
      import config_default as config
  ```

  `find . -name config.py` outside `f469-disco/` and `.git/` returns nothing, and `config`
  is not in the frozen manifest, so the importer still probes the VFS. `f469-disco/micropython`
  is unchanged, so the CWD-at-`/qspi` behavior and the `""` `sys.path` entry are unchanged.
- **Actionable Fix / Changes Needed:**
  1. Remove the executable-import escape hatch. Freeze a `config.py` into the manifest so
     the VFS is never probed, or replace the mechanism with authenticated data:

     ```python
     # platform.py
     try:
         import config            # frozen only
     except ImportError:
         import config_default as config
     ```

     and add `config.py` to [manifests/](../../manifests/) so the frozen module always wins.
     Note the bare `except:` must become `except ImportError:` or a syntax error in a
     planted `/qspi/config.py` would still be swallowed.
  2. Fix the `sys.path` sanitization and drop the `""` entry:

     ```python
     sys.path[:] = [p for p in sys.path if p and "qspi" not in p]
     ```
  3. Chdir to a non-persistent location before any import runs.
  4. Add a boot-time assertion that every security-relevant module resolved to a frozen
     path (`__file__` absent on frozen modules is a usable signal).

---

### F-18: The hardware TRNG fails open and emits zero-valued words

- **Current Status:** Partially Resolved
- **Codebase Evidence:**
  **What was fixed.** [src/rng.py](../../src/rng.py) now carries a liveness check.
  [rng.py:22](../../src/rng.py#L22) defines `RNGError(BaseError)`;
  [rng.py:57-93](../../src/rng.py#L57-L93) defines `_looks_dead(data)`, which rejects a
  buffer where any single byte value covers more than half of it (n ≥ 8), or where the
  distinct-value count is below half the expected count for healthy output. The threshold
  is computed in fixed point (`_expected_distinct`) so it is identical on MicroPython
  single-precision and CPython double-precision builds. It is wired into the only entry
  point at [rng.py:96-101](../../src/rng.py#L96-L101):

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
  16 unit tests in [test/tests_native/test_rng.py](../../test/tests_native/test_rng.py)
  cover the partial-stall, majority-stall, low-variety, short-buffer, and >64-byte paths.

  **What is still open.** The C layer is untouched — `f469-disco/micropython` is still
  pinned at `6bdf1b6`. [rng.c:48-49](../../f469-disco/micropython/ports/stm32/rng.c#L48-L49)
  still returns `0` on timeout with no error signal, `RNG->SR` `SECS`/`CECS` are still never
  inspected (`grep -n "SECS\|CECS" rng.c` returns nothing), and `os_urandom` still consumes
  one 32-bit word per output byte. So the *failure* is now detected at the Python boundary,
  but the *source* still fails open, and there is no Python-visible health API — only an
  inferred statistical check.

  Two residual bypasses, both assessed as non-security-critical:
  `get_random_bytes(1)` at [input.py:233](../../src/gui/screens/input.py#L233) skips the
  check (`n < 4`), which is intentional and documented in the docstring; and
  [platform.py:271](../../src/platform.py#L271) calls `os.urandom` directly, but only to
  overwrite flash blocks during wipe.
- **Actionable Fix / Changes Needed:**
  1. Fix the driver in the fork. `rng_get()` should signal failure rather than return `0`:

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

     Have `os_urandom` raise `OSError` when `rng_last_error` is set, and consume full
     32-bit words rather than one word per byte.
  2. Expose `pyb.rng_health()` so `src/rng.py` can check the peripheral directly instead of
     inferring from output statistics.
  3. Replace the constant pool seed `b"7" * 64` ([rng.py:5](../../src/rng.py#L5)) with a
     health-checked hardware seed at boot — see F-14.

---

### F-19: Confirmation buttons stay fixed while security-critical text scrolls

- **Current Status:** Active
- **Codebase Evidence:**
  [prompt.py:16-30](../../src/gui/screens/prompt.py#L16-L30) is unchanged. The message goes
  into a scrolling page, the buttons attach to the screen:

  ```python
  self.page = lv.page(self)
  self.page.set_size(480, 600)
  self.message = add_label(message, scr=self.page)
  ...
  (self.cancel_button, self.confirm_button) = add_button_pair(..., scr=self)
  ```

  `TransactionScreen` still appends outputs, then the fee
  ([transaction.py:66-77](../../src/gui/screens/transaction.py#L66-L77)), then warnings
  ([transaction.py:79-83](../../src/gui/screens/transaction.py#L79-L83)) into the same
  `self.page`, so the fee's vertical position is still a function of the attacker-chosen
  output count. No scroll-to-end gate exists anywhere in `src/gui/`.
- **Actionable Fix / Changes Needed:**
  1. Cheapest effective change: move the fee and the aggregated warning block out of
     `self.page` and into fixed screen-level labels above the button pair, so they cannot
     be scrolled off.
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

     Start the button in `lv.btn.STATE.INA` when the content overflows the viewport.
  3. Cap or paginate the output list on the default page, and render
     `"%d change outputs not shown" % num_change_outputs` — the counter already exists at
     [transaction.py:60-64](../../src/gui/screens/transaction.py#L60-L64) and is discarded
     (see F-24).

---

### F-23: Liquid asset names are chosen by the host

- **Current Status:** Active
- **Codebase Evidence:**
  [liquid/manager.py:129-139](../../src/apps/wallets/liquid/manager.py#L129-L139) still
  stores a host-supplied label after one prompt, and
  [liquid/manager.py:580-589](../../src/apps/wallets/liquid/manager.py#L580-L589) still
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

  There is still no built-in table of known asset IDs — `grep -rn "policy_asset\|L-BTC"
  src/apps/wallets/liquid/` finds no reserved mapping. `DUMP_ASSETS` at
  [liquid/manager.py:140-141](../../src/apps/wallets/liquid/manager.py#L140-L141) still
  returns the whole registry with no confirmation.
- **Actionable Fix / Changes Needed:**
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
  2. Reject host labels that collide with a reserved name in the `ADD_ASSET` handler.
  3. Always render the first and last bytes of the raw asset ID next to any label, so a
     name can never fully replace identity:
     `"%s (%s…%s)" % (label, h[:4], h[-4:])`.
  4. Restrict labels to short printable ASCII, and drop `check_unknown_assets`' habit of
     asking for labels during the signing confirmation.

---

### F-24: The transaction screen is incomplete by default

- **Current Status:** Active
- **Codebase Evidence:**
  All three sub-defects are unchanged.

  **1. Dead `branch_txt`** — [manager.py:746-752](../../src/apps/wallets/manager.py#L746-L752):

  ```python
  branch_txt = ""
  if branch_idx == 1:
      "change "                       # bare expression, discarded
  elif branch_idx > 1:
      "branch %d " % branch_idx       # bare expression, discarded
  metaout["label"] = "%s %s#%d" % (wallet.name, branch_txt, idx)
  ```

  **2. Overwritten warning** — [manager.py:757-760](../../src/apps/wallets/manager.py#L757-L760):

  ```python
  if allowed_idx <= idx:
      metaout["warning"] = "Derivation index is by %d larger than ..." % ...
  if wallet.is_watchonly:
      metaout["warning"] = "Watch-only wallet!"     # overwrites
  ```

  **3. No fee sanity check** — [transaction.py:66](../../src/gui/screens/transaction.py#L66)
  is still `if meta.get("fee"):`, so a zero fee renders no row (H-05) and a negative fee
  renders as an ordinary line. `grep -rn 'meta\["warnings"\]' src/apps/wallets/manager.py`
  returns nothing, so `meta["warnings"]` is still never populated on the Bitcoin path, and
  the `if "warnings" in meta` block at
  [transaction.py:79-83](../../src/gui/screens/transaction.py#L79-L83) is dead for Bitcoin.
  `num_change_outputs` at [transaction.py:59-64](../../src/gui/screens/transaction.py#L59-L64)
  is still computed and discarded.
- **Actionable Fix / Changes Needed:**
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
  4. Change `if meta.get("fee"):` to `if "fee" in meta:` so a zero fee renders (H-05).
  5. Render `"%d change outputs not shown" % num_change_outputs` on the default page.

---

### F-25: Boot-time firmware integrity is only a CRC32

- **Current Status:** Active
- **Codebase Evidence:**
  [bl_integrity_check.h:47-63](../../bootloader/core/bl_integrity_check.h#L47-L63) still
  defines the record with only `pl_crc` and `struct_crc`:

  ```c
  typedef struct BL_ATTRS((packed)) bl_icr_sect_ {
    ...
    uint32_t pl_crc;   ///< Payload CRC
  ...
    uint32_t struct_crc;      ///< CRC of this structure using LE representation
  ```

  No signature, MAC, or key at boot. ECDSA still runs exactly once, in the SD upgrade path
  at [bootloader.c:1254-1256](../../bootloader/core/bootloader.c#L1254-L1256), after the
  copy to flash — which remains the one positive: signed bytes are the executed bytes.
  The bootloader bump did not touch `bl_integrity_check.c` or `startup/startup.c`.
- **Actionable Fix / Changes Needed:**
  1. Verify at boot rather than CRC. Cheapest version that keeps boot time acceptable: add
     a keyed MAC field to `bl_integrity_check_rec_t`, computed over the payload under a
     device-unique key derived at first boot and stored in the key-storage sector the fork
     already reserves. Bump `struct_rev` so old records are rejected.
  2. If full ECDSA at boot is affordable on this MCU, prefer it — the signature is already
     present in the upgrade file and could be retained alongside the payload.
  3. Make write protection unconditional for release builds instead of `#ifdef
     WRITE_PROTECTION`, and reassert WRP as a boot-time invariant in `blsys_init()` for the
     firmware and bootloader regions, not only the start-up sector.
  4. Have `make-initial-firmware.py` document that a factory-flashed device has RDP1 but no
     WRP until the first successful upgrade.

---

### F-28: The UR fountain decoder never verifies any checksum

- **Current Status:** Active
- **Codebase Evidence:**
  `f469-disco/libs/common/microur` is byte-identical to the audited tree.
  [decoder.py](../../f469-disco/libs/common/microur/decoder.py) still stores the header
  checksum and only compares declarations across parts:

  ```text
  decoder.py:51  data = bytewords.decode_check(stream.read())   # single-part only
  decoder.py:67  self.checksum = self.checksum or checksum
  decoder.py:68  assert self.checksum == checksum               # declaration vs declaration
  ```

  `grep -n "crc32" decoder.py` returns nothing, so `_combine()` still returns the
  reassembled message without computing CRC32 over it. The multi-part path still goes
  through `decode_write()` → `decodeinto()`, which has no CRC check.
- **Actionable Fix / Changes Needed:**
  1. Verify the message-level CRC32 in `_combine()`:

     ```python
     # decoder.py, at the end of _combine()
     import binascii
     crc = binascii.crc32(result) & 0xFFFFFFFF
     if crc != self.checksum:
         raise URError("UR message checksum mismatch: got %08x, declared %08x"
                       % (crc, self.checksum))
     ```

     For the streaming case, accumulate the CRC32 incrementally rather than buffering.
  2. Use `stream_decode_check` on the multi-part path so the per-part bytewords CRC is also
     enforced, and remove the stale "TODO: Checksum is currently ignored" docstring.
  3. Apply H-08 (bytewords range validation) and H-13 (`assert` → `raise`) in the same
     change; all three protect the same parser.

---

### F-30: `SIGHASH_NONE` and `ANYONECANPAY` are accepted after a generic warning

- **Current Status:** Active
- **Codebase Evidence:**
  [manager.py:37-44](../../src/apps/wallets/manager.py#L37-L44) still builds all six
  combinations into the accepted set:

  ```python
  SIGHASH_NAMES = {SIGHASH.ALL: "ALL", SIGHASH.NONE: "NONE", SIGHASH.SINGLE: "SINGLE"}
  for sh in list(SIGHASH_NAMES):
      SIGHASH_NAMES[sh | SIGHASH.ANYONECANPAY] = SIGHASH_NAMES[sh] + " | ANYONECANPAY"
  ```

  [manager.py:417-422](../../src/apps/wallets/manager.py#L417-L422) still shows
  `"\nCustom SIGHASH flags are used!\n\n"` with `confirm_text="Proceed anyway"` and returns
  `None` on confirm, and [manager.py:778](../../src/apps/wallets/manager.py#L778) still does
  `inp_sighash = sighash or inp.sighash_type or self.DEFAULT_SIGHASH`. The Liquid manager
  still adds a `| RANGEPROOF` variant of each at
  [liquid/manager.py:19-29](../../src/apps/wallets/liquid/manager.py#L19-L29).
- **Actionable Fix / Changes Needed:**
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
  2. For `SINGLE`, verify a matching output index exists before offering the prompt.
  3. Rewrite the warning to state the consequence, and swap the button roles so Cancel is
     the affirmative action:

     ```python
     Prompt("DANGER", "\nInput %d asks to sign with %s.\n\n"
                      "This does NOT commit to the outputs. Anyone holding this "
                      "signature can spend the input into any transaction.\n"
            % (i, name),
            confirm_text="Cancel", cancel_text="I understand, sign anyway")
     ```
  4. Separately, add `SIGHASH.DEFAULT` (`0x00`) to `SIGHASH_NAMES` so Taproot PSBTs are not
     rejected with "Unknown sighash type: 0!" — availability, not security.

---

### F-33: Flash write protection is removed before authentication and not restored on failure

- **Current Status:** Active
- **Codebase Evidence:**
  [bootloader.c:1230-1234](../../bootloader/core/bootloader.c#L1230-L1234) still clears WRP
  before anything is verified:

  ```c
  // Remove write protection from needed sections of the flash memory
  if (!set_write_protection_state(&bl_ctx.file_metadata, p_args->loaded_from, false)) {
    fatal_error("Error while removing write protection");
  }
  ```

  Then erase (1237), copy (1242), hash (1247), and only at
  [bootloader.c:1254-1263](../../bootloader/core/bootloader.c#L1254-L1263) does
  `verify_multisig` run — whose failure branch does `return false` **without** restoring
  WRP. The restore at
  [bootloader.c:1271-1277](../../bootloader/core/bootloader.c#L1271-L1277) is reachable only
  on the success path.
- **Actionable Fix / Changes Needed:**
  1. Restore WRP on every exit from `do_upgrade_with_file`. Simplest correct shape:

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

     Audit every other early `return` and `fatal_error` between the unprotect and the
     restore for the same problem.
  2. Better: verify the file's signature **before** touching WRP, then verify again from
     flash after the copy. The first check costs one extra hash pass and removes the
     attacker's ability to clear WRP with an unsigned card at all. The second preserves the
     "signed bytes are executed bytes" property F-25 notes as a positive.
  3. Reassert WRP for the firmware and bootloader regions in `blsys_init()` on every boot,
     so a device that was left unprotected recovers at next power-on.

---

### F-34: Smartcard receive drains one byte past its stack buffer

- **Current Status:** Active
- **Codebase Evidence:**
  `f469-disco/usermods/scard` is byte-identical to the audited tree.
  [scard_io.c:333-345](../../f469-disco/usermods/scard/ports/stm32/scard_io.c#L333-L345):

  ```c
  size_t scard_rx_readinto(scard_handle_t handle, uint8_t* buf, size_t nbytes) {
    size_t bytes_read = 0;
    uint8_t* p_data = buf;

    while(bytes_read <= nbytes && uart_rx_any(handle->uart_obj)) {   // <= is the bug
      ...
      *p_data++ = uart_rx_char(handle->uart_obj);
      ++bytes_read;
  ```

  Both callers still allocate `uint8_t rx_buf[32]` and forward the returned count
  unchecked ([connection.c:656-661](../../f469-disco/usermods/scard/connection.c#L656-L661),
  [connection.c:854-859](../../f469-disco/usermods/scard/connection.c#L854-L859)).
  [memorycard.py:51-59](../../src/keystore/memorycard.py#L51-L59) still reaches this before
  PIN entry via `is_available()`.
- **Actionable Fix / Changes Needed:**
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
  3. Restore `-Wall` (H-22) and fuzz ATR/T=1 timing with a card emulator under the release
     toolchain — this defect and H-23 are both in classes `-Wall -Werror` would surface.

---

### F-35: The Liquid confidential-address encoder is not gated by script type

- **Current Status:** Active
- **Codebase Evidence:**
  embit v0.8.2 did not touch either file.
  [liquid/addresses.py:19-30](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L19-L30):

  ```python
  else:
      data = script.data
      ver = data[0]
      # FIXME: should be one of OP_N
      if ver > 0:
          ver = ver % 0x50
      ...
      return blech32.encode(network["blech32"], ver, blinding_key.sec() + data[2:])
  ```

  No `script_type()` gate, and the round-trip guard is still inert —
  [blech32.py:112-124](../../f469-disco/libs/common/embit/src/embit/liquid/blech32.py#L112-L124)
  still has all four validation checks commented out. The strict `bech32.decode` used on
  the Bitcoin path retains them, which is why only the confidential branch is permissive.
  The unguarded call site is unchanged at
  [liquid/manager.py:70-74](../../src/apps/wallets/liquid/manager.py#L70-L74), which calls
  `liquid_address` before the Bitcoin manager's `try/except` hex fallback at
  [manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99) is reachable.
- **Actionable Fix / Changes Needed:**
  1. Uncomment the four checks in `blech32.decode` — they cost nothing and re-arm the
     round-trip guard in `blech32.encode`:

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

     Note the confidential payload is `blinding_key.sec() + program`, so the length bounds
     must account for the 33-byte prefix on the blech32 side.
  2. Gate `addresses.address` on script type and decode OP_N explicitly, resolving the
     `FIXME`:

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
  3. Wrap `LWalletManager.get_address` in the same `try/except` the Bitcoin manager uses,
     and label the hex fallback on screen as "UNRECOGNIZED OUTPUT SCRIPT" rather than
     rendering bare hex where an address normally appears. This also fixes H-25.

---

### F-09: The ARM compiler archive is pinned with a legacy MD5 digest

- **Current Status:** Active
- **Codebase Evidence:**
  [Dockerfile:12-15](../../Dockerfile#L12-L15) is unchanged:

  ```dockerfile
  # Integrity is checked using the MD5 checksum provided by ARM at ...
  RUN curl -sSfL -o arm-toolchain.tar.bz2 "https://developer.arm.com/-/media/Files/downloads/gnu-rm/9-2020q2/..." && \
      echo 2b9eeccc33470f9d3cda26983b9d2dc6 arm-toolchain.tar.bz2 > /tmp/arm-toolchain.md5 && \
      md5sum --check /tmp/arm-toolchain.md5 && rm /tmp/arm-toolchain.md5 && \
  ```

  The Docker path is still the documented deterministic build
  ([docs/deterministic-firmware-build.md](../../docs/deterministic-firmware-build.md)).
  A parallel Nix dev-shell path was added ([flake.nix](../../flake.nix),
  `pkgs.buildPackages.gcc-arm-embedded-9`, pinned through `flake.lock` narHashes), which
  avoids MD5 — but it is a dev shell, not the release build, so it does not close this.
  The base image is still digest-pinned and Python requirements are still
  `--require-hashes`, so the inconsistency the audit noted persists.
- **Actionable Fix / Changes Needed:**
  1. Replace the MD5 pin with SHA-256 and an immutable URL:

     ```dockerfile
     RUN curl -sSfL -o arm-toolchain.tar.bz2 "<immutable-release-url>" && \
         echo "<sha256>  arm-toolchain.tar.bz2" | sha256sum --check - && \
         tar xf arm-toolchain.tar.bz2 -C /opt && rm arm-toolchain.tar.bz2
     ```

     ARM publishes SHA-256 for the 9-2020-q2 archives; record where the digest came from
     in a comment.
  2. Or make the Nix flake the release build path, so the toolchain comes from a
     content-addressed store with a `flake.lock` narHash, and retire the Dockerfile's
     independent download.

---

### F-13: libsecp256k1 error and illegal callbacks return instead of failing closed

- **Current Status:** Active
- **Codebase Evidence:**
  [ext_callbacks.c](../../f469-disco/usermods/secp256k1/mpy/config/ext_callbacks.c) is
  unchanged and still two empty function bodies:

  ```c
  void secp256k1_default_illegal_callback_fn(const char* str, void* data){}
  void secp256k1_default_error_callback_fn(const char* str, void* data){}
  ```

  Still not reachable: the surjection-proof list branches are the only unchecked `gc_alloc`
  sinks, and their Specter call sites remain commented out at
  [liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454).
- **Actionable Fix / Changes Needed:**
  Route both to a fail-closed handler, matching what the bootloader already does with
  `blsys_fatal_error`:

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

  Verify the NLR jump is valid at every call site; if any callback can fire outside a
  MicroPython NLR context, use a hard reset there instead.

---

### F-14: Entropy hardening gaps and unconfirmed raw-TRNG export

- **Current Status:** Partially Resolved
- **Codebase Evidence:**
  **Closed.** The bullet "There is no runtime TRNG health or liveness test" no longer
  holds: [rng.py:57-93](../../src/rng.py#L57-L93) adds `_looks_dead`, enforced in
  `get_random_bytes` for every request of 4 bytes or more. See F-18.

  **Still open, all verified unchanged:**
  - The pool still starts as the constant `b"7" * 64`
    ([rng.py:5](../../src/rng.py#L5)).
  - Requests above 64 bytes still bypass the pool
    ([rng.py:103-104](../../src/rng.py#L103-L104)) — they are now liveness-checked, but
    still returned raw.
  - [getrandom.py:36-42](../../src/apps/getrandom.py#L36-L42) still returns up to 1000
    bytes to a host with no confirmation; `show_fn` is a parameter and is never called.
  - `getrandom` and `label` are still in the production manifest
    ([apps/__init__.py:1-11](../../src/apps/__init__.py#L1-L11)) despite their
    "Demo of a single-file app" docstrings.
  - `grep -rn "context_randomize" src/` returns nothing.
  - Schnorr signing still supplies no BIP340 auxiliary randomness.
- **Actionable Fix / Changes Needed:**
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
  2. Route all sizes through the pool — remove the `if nbytes > 64: return d` shortcut and
     generate in 64-byte chunks from the pool.
  3. Confirm `getrandom` exports:

     ```python
     if not await show_fn(Prompt("Send entropy to host?",
             "The host is requesting %d bytes of entropy from the device TRNG."
             % num_bytes)):
         return
     ```
  4. Curate the production app list — drop `getrandom` unless it has a use case, or
     re-document it as a supported feature rather than a demo.
  5. Call `secp256k1.context_randomize` at boot and after each unlock, and pass auxiliary
     randomness to Schnorr signing.

---

### F-16: Animated QR reassembly accepts invalid indexes and weakly binds frames

- **Current Status:** Active
- **Codebase Evidence:**
  [qr.py:552-561](../../src/hosts/qr.py#L552-L561) is unchanged:

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

  So `p0ofN` still yields `m = 0`, `self.parts[m - 1]` still aliases `self.parts[-1]`, and
  `n == 0` still gives an empty `self.parts` with `self.animated` already set. Session
  binding is still only by part count `N`. The `print(prefix)` on line 553 is a second
  instance of H-18.
- **Actionable Fix / Changes Needed:**
  1. Correct the guard:

     ```python
     if m < 1 or n < 1 or n < m:
         raise HostError("Invalid prefix")
     ```
  2. Set `self.animated = True` only after `self.parts` has been successfully sized, so a
     raise cannot leave the decoder half-initialized for the bare `except:` to swallow.
  3. Bind frames to a session: hash the first frame's payload prefix and require every
     later frame to carry the same `(N, session_id)`, rather than only `N`.
  4. Verify the assembled BCUR shared hash in the wallet-manager decode path before
     dispatch, and apply F-28's UR-level fixes at the same time.
  5. Remove the `print(prefix)`.

---

### F-36: Liquid address decoding discards the witness version and rebuilds every address as `OP_0`

- **Current Status:** Active
- **Codebase Evidence:**
  [liquid/addresses.py:41-53](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L41-L53)
  is unchanged in embit v0.8.2 — `ver` is bound and then never used:

  ```python
  ver, data = blech32.decode(hrp, addr)
  data = bytes(data)
  pub = ec.PublicKey.parse(data[:33])
  pubhash = data[33:]
  sc = script.Script(b"\x00" + bytes([len(pubhash)]) + pubhash)      # ver unused
  ...
  ver, data = bech32.decode(hrp, addr)
  pub = None
  sc = script.Script(b"\x00" + bytes([len(data)]) + bytes(data))     # ver unused
  ```

  `find_wallet_from_address` at
  [liquid/manager.py:98-123](../../src/apps/wallets/liquid/manager.py#L98-L123) still
  compares `addr in [a, unconf_a]`, so a non-v0 Liquid wallet fails verification silently.
- **Actionable Fix / Changes Needed:**
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
  2. Fix `blech32.decode` first (F-35) — without those checks `addr_decode` will also
     accept versions above 16 and programs outside 2–40 bytes, so `_wit_script` becomes the
     only guard.
  3. Add a round-trip test: for each supported Liquid descriptor type, assert
     `addr_decode(address(spk, bkey))[0].data == spk.data`.

---

## Hardening items (H-01 … H-26)

All 24 are re-verified below. Every `f469-disco/usermods` and `microur` item is Active by
construction, since those trees are byte-identical to the audited ones.

### H-01: Adequate secp256k1 context size is hard-coded without a guard

- **Current Status:** Active
- **Codebase Evidence:** `usermods/secp256k1` unchanged.
  [libsecp256k1.c:27-38](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L27-L38)
  still hard-codes `PREALLOCATED_CTX_SIZE` to 880 with a `FIXME` in place of a comparison
  against `secp256k1_context_preallocated_size()`.
- **Actionable Fix:** Add a boot-time check in `maybe_init_ctx()`:

  ```c
  size_t need = secp256k1_context_preallocated_size(SECP256K1_CONTEXT_SIGN |
                                                    SECP256K1_CONTEXT_VERIFY);
  if (need > PREALLOCATED_CTX_SIZE) {
      mp_raise_ValueError("secp256k1 context buffer too small");
  }
  ```

  Plus a compile-time `_Static_assert` where the configuration is known.

---

### H-03: Liquid wallet export includes the master blinding private key

- **Current Status:** Active
- **Codebase Evidence:** The Liquid default descriptor still embeds the SLIP77 key —
  [liquid/manager.py:203](../../src/apps/wallets/liquid/manager.py#L203):

  ```python
  desc = "blinded(slip77(%s),%s)" % (self.keystore.slip77_key, desc)
  ```

  `Wallet.export_menu` at [wallet.py:66-95](../../src/apps/wallets/wallet.py#L66-L95)
  serializes `self.descriptor.branch(0)` into a QR or an SD JSON file with no warning
  about the private key it contains.
- **Actionable Fix:** In `export_menu`, detect a `slip77(` private key in the serialized
  descriptor and require an explicit prompt before export, reusing the wording from the
  host path in [blindingkeys/app.py](../../src/apps/blindingkeys/app.py). Offer a
  "public-only" export variant that substitutes the blinding *public* key.

---

### H-04: GUI popup preemption cannot retarget a confirmation press

- **Current Status:** No action (original finding was "No defect found")
- **Codebase Evidence:** [async_gui.py:46-60](../../src/gui/async_gui.py#L46-L60),
  [decorators.py:32-41](../../src/gui/decorators.py#L32-L41), and
  [screen.py:53-57](../../src/gui/screens/screen.py#L53-L57) are unchanged apart from
  wording edits in `async_gui.py`. The conclusion still holds: no authorization bypass.
- **Actionable Fix:** None. The residual risks it names are tracked as H-06.

---

### H-05: A fee of exactly zero is not displayed

- **Current Status:** Active
- **Codebase Evidence:** [transaction.py:66](../../src/gui/screens/transaction.py#L66) and
  [transaction.py:145](../../src/gui/screens/transaction.py#L145) both guard with
  `if meta.get("fee"):`. `0` is falsy, so no fee row is rendered on either page.
- **Actionable Fix:** Change both to `if "fee" in meta:`. Fixed together with F-24 item 4.

---

### H-06: Confirmation results are compared by identity rather than truthiness

- **Current Status:** Active
- **Codebase Evidence:** `grep -rn "is False" src/` returns exactly the four sites the
  audit listed, plus one correct one:

  ```text
  src/keystore/flash.py:235            if res is False:
  src/keystore/sdcard.py:81            if res is False:
  src/apps/label.py:41                 if res is False:
  src/apps/signmessage/signmessage.py:74  if res is False:
  src/hosts/usb.py:78                  if res is None or res is False:   # correct
  ```
- **Actionable Fix:** Replace the four with `if not res:`. Still latent — no path returns
  `None` today — but it sits on the message-signing confirmation that F-17 turns into a
  firmware-authorization confirmation.

---

### H-08: Bytewords decoding does no range validation on input characters

- **Current Status:** Active
- **Codebase Evidence:** `microur` unchanged.
  [bytewords.py:44-46](../../f469-disco/libs/common/microur/util/bytewords.py#L44-L46)
  still has `_minus_aA` with no range check, and the `LOOKUP_TABLE` index at
  [bytewords.py:56-99](../../f469-disco/libs/common/microur/util/bytewords.py#L56-L99) is
  unguarded.
- **Actionable Fix:**

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

---

### H-09: Two bugs in the exported `nonce_function_default` wrapper

- **Current Status:** Active
- **Codebase Evidence:** `usermods/secp256k1` unchanged.
  [libsecp256k1.c:328-343](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L328-L343)
  still reads `algo16` from `args[0]` and still casts a non-buffer `args[3]` to a raw
  pointer. Still unreachable — no caller in `src/` or `embit`.
- **Actionable Fix:**

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

---

### H-10: The secure-channel IV is not advanced or reset after a failed round trip

- **Current Status:** Active
- **Codebase Evidence:**
  [securechannel.py:180-195](../../src/keystore/javacard/applets/securechannel.py#L180-L195)
  is unchanged. `self.iv += 1` is on line 192, after `self.decrypt(res)` on line 191, so a
  raise leaves both `iv` and `is_open` untouched.
- **Actionable Fix:**

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

---

### H-11: The mnemonic backup filename defaults to the first BIP-39 word

- **Current Status:** Active
- **Codebase Evidence:** All three sites unchanged:

  ```text
  src/keystore/flash.py:223   filename = await self.get_input(suggestion=self.mnemonic.split()[0])
  src/keystore/sdcard.py:66   filename = await self.get_input(suggestion=self.mnemonic.split()[0])
  src/keystore/ram.py:402     fname = "%s.txt" % self.mnemonic.split()[0]
  ```
- **Actionable Fix:** Default to the fingerprint:
  `suggestion=hexlify(self.fingerprint).decode()`. The encrypted-save path
  (`flash.py:223`, `sdcard.py:66`) is the one that matters — it currently publishes seed
  word 1 in a FAT directory entry on removable media, and FAT entries survive deletion.

---

### H-12: The network file is unauthenticated and is read before unlock

- **Current Status:** Active
- **Codebase Evidence:**
  [specter.py:405-411](../../src/specter.py#L405-L411) still uses a bare `open()`:

  ```python
  def load_network(self, path, network="main"):
      try:
          with open(path + "/network", "r") as f:
              network = f.read()
      except:
          pass
      self.set_network(network)
  ```

  and [specter.py:393-395](../../src/specter.py#L393-L395) still silently falls back to
  mainnet on garbage input.
- **Actionable Fix:** Route through `load_aead`/`save_aead` under
  `keystore.settings_key` like every other setting, and move the read after `unlock()`.
  If a pre-unlock network hint is genuinely needed, treat it as untrusted display state
  and re-derive the authoritative value after unlock.

---

### H-13: All UR cross-part validation is written with bare `assert`

- **Current Status:** Active
- **Codebase Evidence:** `microur` unchanged — `grep -n "assert" decoder.py` returns 12
  hits covering `ur_type`, `seq_num`, `seq_len`, `msg_len`, `checksum`, `payload_len`, the
  `readinto` length, and the part-set completeness check. The build still cannot strip
  them: [ports/stm32/Makefile:142](../../f469-disco/micropython/ports/stm32/Makefile#L142)
  sets `MPY_CROSS_FLAGS = -march=armv7m` only, and `grep -rn "mpy-cross" Makefile
  build_firmware.sh` shows no `-O` flag anywhere.
- **Actionable Fix:** Convert every security-relevant `assert` in `microur` to an explicit
  `raise URError(...)`, and add a boot-time tripwire so the invariant cannot silently
  regress:

  ```python
  # main.py, early
  if not __debug__:
      raise RuntimeError("Firmware built with asserts stripped - refusing to run")
  ```

---

### H-14: Keystore backend naming and a destructive no-PIN fallback

- **Current Status:** Active
- **Codebase Evidence:**
  [sdcard.py:21](../../src/keystore/sdcard.py#L21) still has `NAME = "Internal storage"`,
  identical to [flash.py:29](../../src/keystore/flash.py#L29), so an SD-stored seed is
  labelled "Internal storage" at every unlock.
  `Specter.select_keystore` at [specter.py:97-113](../../src/specter.py#L97-L113) still
  takes the first available backend, `MemoryCard.is_available()` still swallows every
  fault, and `_set_pin` at [flash.py:182-186](../../src/keystore/flash.py#L182-L186) still
  overwrites `enc_secret` with fresh randomness when it finds `None`.
- **Actionable Fix:**
  1. Rename: `SDKeyStore.NAME = "SD card"`.
  2. Before `setup_pin()` on a device that has a smartcard-era `enc_secret` or any stored
     seed, require an explicit destructive-action confirmation:

     ```python
     if self.has_stored_seed() and self.enc_secret is None:
         if not await show_screen(Prompt(
                 "WARNING",
                 "Setting a new PIN here will PERMANENTLY DESTROY the seed "
                 "stored on this device. Continue?")):
             raise KeyStoreError("Aborted")
     ```
  3. Announce backend fallback on screen rather than switching silently.

---

### H-15: Three small robustness items

- **Current Status:** Active (all three)
- **Codebase Evidence:**
  1. **PIN HMAC type mismatch.** [flash.py:178](../../src/keystore/flash.py#L178) passes a
     `str`: `self.pin = hmac.new(key=key, msg=pin, digestmod="sha256").digest()`, while
     [flash.py:128](../../src/keystore/flash.py#L128) passes `bytes`:
     `msg=pin.encode()`. Unchanged.
  2. **Unbounded UR `seq_len`.** `microur` unchanged;
     [util/ur.py:9-25](../../f469-disco/libs/common/microur/util/ur.py#L9-L25) still parses
     `seq_len` with no upper bound.
  3. **No BIP-32 depth limit.** embit v0.8.2 unchanged —
     [bip32.py:292-299](../../f469-disco/libs/common/embit/src/embit/bip32.py#L292-L299)
     still returns `[_parse_der_item(e) for e in arr]` with no cap.
- **Actionable Fix:**
  1. `self.pin = hmac.new(key=key, msg=pin.encode(), digestmod="sha256").digest()`.
  2. `if seq_len < 1 or seq_len > 1000: raise URError("Invalid seq_len")`.
  3. Cap depth in `parse_path`:

     ```python
     MAX_DERIVATION_DEPTH = 10
     if len(arr) > MAX_DERIVATION_DEPTH:
         raise ValueError("Derivation path too deep: %d" % len(arr))
     ```

     Reachable through F-05, which needs no confirmation, so enforce it in
     [xpubs.py](../../src/apps/xpubs/xpubs.py) too rather than relying on the dependency.

---

### H-16: The rangeproof rewind arena bound uses an ABI-mismatched length

- **Current Status:** Active
- **Codebase Evidence:** `usermods/secp256k1` unchanged.
  [rangeproof_preallocated.h:9-13](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated.h#L9-L13)
  declares `uint64_t allocated_len`;
  [rangeproof_preallocated_impl.h:491-495](../../f469-disco/usermods/secp256k1/mpy/config/rangeproof_preallocated/rangeproof_preallocated_impl.h#L491-L495)
  defines `intptr_t allocated_len`. Separate translation units, so no diagnostic.
- **Actionable Fix:** Use one type (`size_t`) in both, `#include` the public declaration in
  the translation unit that compiles the definition so the compiler can diagnose future
  drift, and restore warnings-as-errors for this user module. Fix this **before** F-31,
  since F-31's proposed arena bound relies on this parameter being read correctly.

---

### H-17: Unreachable surjection-proof copy loops scale their index twice

- **Current Status:** Active
- **Codebase Evidence:** `usermods/secp256k1` unchanged.
  [libsecp256k1.c:1300-1304](../../f469-disco/usermods/secp256k1/mpy/libsecp256k1.c#L1300-L1304)
  and the equivalent code at `:1376-1380` and `:1438-1442` still add `i * element_size` to
  an already typed pointer. Still unreachable — the list-argument call sites are commented
  out at [liquid/manager.py:441-454](../../src/apps/wallets/liquid/manager.py#L441-L454).
- **Actionable Fix:** Change `ptr + i * element_size` to `ptr + i`, check the `gc_alloc`
  result before use, and validate the argument is actually a list before casting to
  `mp_obj_list_t`.

---

### H-18: Every QR payload is printed to stdout unconditionally

- **Current Status:** Active
- **Codebase Evidence:**
  [qrcode.py:290-292](../../src/gui/components/qrcode.py#L290-L292) is unchanged:

  ```python
  def _set_text(self, text):
      # one bcur frame doesn't require checksum
      print(text)
  ```

  A second instance exists at [qr.py:553](../../src/hosts/qr.py#L553) (`print(prefix)`).
  Inert on a correctly booted production image, live in the debug image and in F-32's
  boot-failure state.
- **Actionable Fix:** Delete both, or gate them:

  ```python
  if platform.simulator:
      print(text)
  ```

---

### H-19: Host-supplied wallet names reach a recolor-enabled label

- **Current Status:** Active
- **Codebase Evidence:**
  [wallet.py:294-302](../../src/apps/wallets/wallet.py#L294-L302) still strips the checksum
  from the descriptor half only:

  ```python
  name = "Untitled"
  if "&" in desc:
      arr = desc.split("&")
      desc = arr[-1]
      name = "&".join(arr[:-1])      # host-controlled, unsanitized
  ```

  `desc.split("#")[0]` on line 308 sanitizes the descriptor, not the name. The name is
  persisted and concatenated into the recolor-enabled `WalletScreen.title`.
- **Actionable Fix:**

  ```python
  def _sanitize_name(name):
      name = "".join(c for c in name if 0x20 <= ord(c) <= 0x7E and c != "#")
      return name[:32] or "Untitled"
  ...
  w.name = _sanitize_name(name)
  ```

  Or render the edit glyph in a separate styled label so the title does not need recolor
  enabled at all.

---

### H-20: Two fail-closed start-up-code robustness defects

- **Current Status:** Active
- **Codebase Evidence:** The bootloader bump touched
  `platforms/stm32f469disco/bootloader/{gui.c,main.c}` but not
  `platforms/stm32f469disco/startup/startup.c`. The out-of-bounds `version[selected]` read
  at [startup.c:209-244](../../bootloader/platforms/stm32f469disco/startup/startup.c#L209-L244)
  and the unguarded `blsys_flash_read`/`blsys_flash_crc32` at
  [startup.c:47-61](../../bootloader/platforms/stm32f469disco/startup/startup.c#L47-L61)
  are unchanged. Both still end in a halt, not attacker-controlled execution.
- **Actionable Fix:**
  1. `if (selected < 0) { fatal_error("No valid bootloader copy"); }` before the fallback
     loop.
  2. Add `check_flash_area()` to the start-up flash syscalls, matching
     [bl_syscalls.c:396-402](../../bootloader/platforms/stm32f469disco/bootloader/bl_syscalls.c#L396-L402),
     and bound `pl_size` against the selected section in shared integrity code.

---

### H-21: The GUI blinding-key export displays the private key without confirmation

- **Current Status:** Active
- **Codebase Evidence:**
  [blindingkeys/app.py:31-36](../../src/apps/blindingkeys/app.py#L31-L36) still renders the
  key immediately:

  ```python
  async def menu(self, show_screen, show_all=False):
      await show_screen(QRAlert("Standard SLIP-77 blinding key",
              self.keystore.slip77_key.wif(NETWORKS[self.network]),
              note="Blinding private key allows your software wallet\nto track your balance."))
      return False
  ```

  No `Prompt`, no warning, no cancel path, no PIN re-entry — in contrast to the same app's
  host path, which does prompt.
- **Actionable Fix:** Gate the GUI path on the same prompt the host path uses, and require
  PIN re-entry before display, matching how mnemonic display is handled.

---

### H-22: The STM32 fork removed `-Wall` while keeping `-Werror`

- **Current Status:** Active
- **Codebase Evidence:** `f469-disco/micropython` still pinned at `6bdf1b6`.
  [ports/stm32/Makefile:93](../../f469-disco/micropython/ports/stm32/Makefile#L93):

  ```make
  CFLAGS = $(INC) -Wpointer-arith -Werror -std=gnu99 -nostdlib $(CFLAGS_MOD) $(CFLAGS_EXTRA)
  ```

  No `-Wall`, no `-Wextra`.
- **Actionable Fix:** Restore `-Wall` (ideally `-Wextra`) and work through the resulting
  diagnostics under the release compiler. Expect H-23 (`-Wparentheses`) and possibly F-34
  to surface immediately. Stage it: add `-Wall -Wno-error=...` for the noisy categories
  first, then tighten.

---

### H-23: Smartcard PPS checksum validation accepts 255 of 256 values

- **Current Status:** Active
- **Codebase Evidence:** `usermods/scard` unchanged.
  [t1_protocol.c:1020-1030](../../f469-disco/usermods/scard/t1_protocol/t1_protocol.c#L1020-L1030)
  still has the unparenthesized expression:

  ```c
  0U == buf[pps_ppss] ^ buf[pps_pps0] ^ buf[pps_pck]
  ```

  `==` binds tighter than `^`, so with the first two bytes forced to `0xFF` and `0x01` the
  expression accepts every PCK except `0x01`, instead of only `0xFE`.
- **Actionable Fix:**

  ```c
  0U == (buf[pps_ppss] ^ buf[pps_pps0] ^ buf[pps_pck])
  ```

  Add positive and negative PPS test vectors so this cannot regress.

---

### H-24: Device wipe unlinks QSPI files but does not erase their blocks

- **Current Status:** Active
- **Codebase Evidence:**
  [platform.py:263-274](../../src/platform.py#L263-L274) is unchanged:

  ```python
  # on real hardware overwrite flash with random data
  if not simulator:
      os.umount("/flash"); os.umount("/qspi")
      f = pyb.Flash()
      block_size = f.ioctl(5, None)
      for i in range(256, 450):        # QSPI is 448..33215
          b = os.urandom(block_size)
          f.writeblocks(i, b)
  ```

  Internal flash (256-447) plus two QSPI blocks are erased; 32,766 QSPI blocks are left.
- **Actionable Fix:** Either erase the full external device —

  ```python
  for i in range(256, 33216):
      f.writeblocks(i, os.urandom(block_size))
      gc.collect()
  ```

  with a progress screen, since this will take a while — or document and test an explicit
  cryptographic-erasure model that states plaintext QSPI metadata (labels, file names,
  sizes, existence) is intentionally retained.

---

### H-25: A Liquid p2pkh output aborts the confirmation screen with an uncaught `IndexError`

- **Current Status:** Active
- **Codebase Evidence:** Same root cause as F-35, both sides unchanged.
  `ver = data[0] % 0x50` at
  [liquid/addresses.py:21-23](../../f469-disco/libs/common/embit/src/embit/liquid/addresses.py#L21-L23)
  maps a p2pkh leading byte `0x76` to 38, outside the 32-entry Bech32 `CHARSET`.
  [liquid/manager.py:64-76](../../src/apps/wallets/liquid/manager.py#L64-L76) calls
  `liquid_address` with no `try/except`, unlike the Bitcoin manager at
  [manager.py:91-99](../../src/apps/wallets/manager.py#L91-L99).
- **Actionable Fix:** Fixed by F-35's `script_type()` gate. Additionally wrap
  `LWalletManager.get_address` in the Bitcoin manager's `try/except` so any future encoder
  exception degrades to a labelled hex fallback rather than aborting `preprocess_psbt`.

---

### H-26: `address_to_scriptpubkey` validates neither payload length nor network, and is unreachable here

- **Current Status:** Active (Informational)
- **Codebase Evidence:** embit v0.8.2 unchanged.
  [script.py:174-195](../../f469-disco/libs/common/embit/src/embit/script.py#L174-L195)
  still emits a hardcoded `\x14` push regardless of payload length, still iterates
  `NETWORKS.values()` with no network parameter, and still falls off the end of the loop
  returning `None` rather than raising. Note the bech32 branch *does* validate `ver` and
  length (lines 188-191) — only the base58 branch is unvalidated.
  Still unreachable: no caller for `Script.from_address` or `address_to_scriptpubkey` in
  `src/` or `boot/`.
- **Actionable Fix:** Upstream hardening only:

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

  Also replace the bare `except:` on line 184 so a base58 failure is distinguishable from
  a bech32 address.

---

## Dependency items (D-01 … D-03)

### D-01: MicroPython is a 2019 base with 63 fork-only commits

- **Current Status:** Active
- **Codebase Evidence:** `f469-disco/micropython` is still pinned at
  `6bdf1b69162b673d48042ccd021f9efa019091fa` (2022-11-07), `git describe` →
  `v1.10-1185-g6bdf1b691`, merge-base still `10709846f` (`v1.12-35`, December 2019). No
  rebase, no backport ledger in the tree.
- **Actionable Fix:** Rebase onto a current MicroPython, or maintain an explicit backport
  and advisory ledger under `docs-my/` and require security review for each fork-only
  change. Start by triaging upstream interpreter, VFS, USB, and `objstr`/`unicode` fixes
  since v1.12 — the last of those is directly relevant to F-21.

---

### D-02: Flattened MicroPython third-party trees have no recoverable upstream pins

- **Current Status:** Active
- **Codebase Evidence:** Same pin, so unchanged. `lib/stm32lib`, `lib/tinyusb`,
  `lib/mbedtls`, and `lib/lwip` remain in-tree with an empty `.gitmodules` and no upstream
  commit identifiers.
- **Actionable Fix:** Record a source URL and commit SHA for every flattened tree in a
  manifest file, or restore the submodules. Then add a CI job that re-verifies each
  vendored tree against its recorded revision.

---

### D-03: Release tooling pins an obsolete `cryptography` package

- **Current Status:** Partially Resolved
- **Codebase Evidence:** Bootloader commit `d6b87bf` ("chore: updating cryptography to
  3.4.8") moved the pin.
  [bootloader/tools/requirements.txt:92](../../bootloader/tools/requirements.txt#L92) now
  reads `cryptography==3.4.8`, still hash-locked. The Dockerfile still installs this lock
  with `--require-hashes` before running upgrade assembly and signature tools.
  3.4.8 dates from August 2021, so the version is newer than 3.3.2 but still predates
  several published advisories in `cryptography` and its bundled OpenSSL.
- **Actionable Fix:** Regenerate the hash-locked requirements against a current
  `cryptography`, verify `upgrade-generator.py`, `make-initial-firmware.py`, and the new
  `introspect-binary.py` against it, and add a scheduled advisory check (`pip-audit` in
  CI) so the pin does not silently age again.

---

## Audit document hygiene and doc-vs-code drift

This section is outside the finding-by-finding scope above. It records where `audit.md`
itself has drifted against the current tree, and — more importantly — two places where the
**current** documentation makes claims the code does not support. The second kind postdates
the audit, so the audit could not have caught them.

### AD-01: 16 of 108 linked paths no longer resolve

- **Current Status:** Drift caused by this tree, not an audit error
- **Evidence:** Extracting every `](../../…)` link from `audit.md` gives 108 distinct paths,
  of which 16 do not exist at HEAD:

  | Broken path | Refs | Cause |
  | --- | --- | --- |
  | `f469-disco/libs/common/embit/*.py` (13 files) | 53 | Vendored tree → submodule; files now under `…/embit/src/embit/` |
  | `docs/security.md` | 24 | Renamed to `docs/security-info.md` and rewritten |
  | `src/apps/bip85`, `src/apps/base.py` | 2 | Genuine audit errors — see AD-02 |

  The embit paths and `docs/security.md` were all correct at the audited tree.
  `git cat-file -e db3ce3e:libs/common/embit/psbt.py` succeeds inside the `f469-disco`
  submodule at its v1.9.0 pin, and `git cat-file -e v1.9.0:docs/security.md` succeeds in
  the parent repo. So the audit was accurate when written.

  The dead links are the smaller half of the problem. The embit **line numbers** are stale
  too: every `#L` anchor points into the vendored upstream `189efc4` tree, and the file
  now shipped is v0.8.2. Anyone following an embit citation from `audit.md` will land on
  unrelated code.
- **Actionable Fix / Changes Needed:**
  1. Rewrite the embit link prefix `../../f469-disco/libs/common/embit/` →
     `../../f469-disco/libs/common/embit/src/embit/`, then re-anchor the line numbers
     against v0.8.2. The 13 affected files are listed above.
  2. Repoint `docs/security.md` → `docs/security-info.md`, but see AD-03 — the line anchors
     cannot be salvaged, since the document was rewritten from 44 to 361 lines.
  3. Add a CI link-checker over `docs-my/` so this cannot silently rot again:

     ```bash
     grep -oP '\]\(\K\.\./\.\./[^)#]+' docs-my/audit/*.md | sort -u \
       | while read -r p; do [ -e "docs-my/audit/$p" ] || echo "BROKEN: $p"; done
     ```

### AD-02: Two citations that were wrong when written

- **Current Status:** Genuine audit errors; conclusion unaffected
- **Evidence:** Both are on the same line, [audit.md:4552](audit.md#L4552) in PATH-06:

  ```markdown
  ([src/apps/bip85/](../../src/apps/bip85), [src/apps/base.py](../../src/apps/base.py)).
  ```

  Neither path existed at v1.9.0. `git ls-tree v1.9.0 src/apps/` shows `src/apps/bip85.py`
  as a blob, not a tree, and there is no `src/apps/base.py` — the file defining `BaseApp`
  is [src/app.py](../../src/app.py).

  The claim they support is correct. [app.py:13](../../src/app.py#L13) has `prefixes = []`,
  [app.py:27-30](../../src/app.py#L27-L30) defines `can_process` as
  `return prefix in self.prefixes`, and `grep -n "prefixes" src/apps/bip85.py` returns
  nothing, so BIP-85 inherits the empty list and is genuinely unreachable from host
  dispatch. PATH-06's "Not reachable" verdict stands.
- **Actionable Fix / Changes Needed:** Correct the two paths to `src/apps/bip85.py` and
  `src/app.py`. No change to the verdict.

### AD-03: Section 8.10 evaluates a document that no longer exists

- **Current Status:** Substantively stale
- **Evidence:** [Section 8.10](audit.md#L4400) is a 23-row table (`SM-01` … `SM-23`) plus a
  reverse comparison, and its entire premise is stated at
  [audit.md:4402-4404](audit.md#L4402-L4404):

  > The dedicated security-model statement is `docs/security.md`, last changed in 2021.
  > The comparison below treats each independently testable clause or bullet as a claim.

  That document was deleted in this tree and replaced by a 361-line
  [docs/security-info.md](../../docs/security-info.md). Every `SM-xx` row's *documented
  claim* column therefore describes text that is no longer shipped. The *implementation
  comparison* column mostly still holds, because it cites code — but the verdicts
  (Confirmed / Qualified / Contradicted) are verdicts about a doc-code pair, and half that
  pair is gone.

  Spot-checked four rows against the replacement (**not** a full re-verification of all 23):

  | Row | Old claim | Status against `security-info.md` |
  | --- | --- | --- |
  | SM-02 | "secure element integration is not there yet" | Claim removed — discrepancy resolved |
  | SM-06 | "all user files on QSPI are signed and checked" | Claim removed — discrepancy resolved |
  | SM-18 | entropy is "always better than any of the individual sources" | Claim removed — discrepancy resolved |
  | SM-21 | mixed-wallet inputs produce a warning | **Still contradicted, and now stated more strongly** — see AD-05 |

- **Actionable Fix / Changes Needed:** Re-run Section 8.10 against
  `docs/security-info.md` as a standalone task. Three of four spot-checked discrepancies
  were resolved by deletion during the rewrite, so the rewrite was net positive, but the
  remaining 19 rows are unverified against the new text and two new discrepancies were
  introduced (AD-04, AD-05).

### AD-04: `security-info.md` contradicts itself on offline PIN brute force

- **Current Status:** Active — new defect, introduced after the audit
- **Codebase Evidence:**
  [security-info.md:158-159](../../docs/security-info.md#L158-L159) states a safety
  property that is false:

  > - The PIN check is an HMAC keyed with the internal secret, so the PIN
  >   cannot be brute-forced offline from flash contents alone.

  The internal secret **is** flash contents. It is stored in cleartext at
  `/flash/keystore/secret` and read with a bare `open()` at
  [ram.py:130-138](../../src/keystore/ram.py#L130-L138). The PIN verifier
  (`tagged_hash("pin", secret)` keyed HMAC, [flash.py:126-128](../../src/keystore/flash.py#L126-L128))
  and the attempt counter live in the same readable-flash trust domain. An attacker who
  reads flash has everything needed to check guesses offline. That is precisely F-06.

  The same document says the opposite twice, correctly:
  - [security-info.md:139-148](../../docs/security-info.md#L139-L148): "if an attacker
    manages to read the internal flash … they obtain the device secret together with the
    PIN file. That enables … brute-forcing your PIN **offline** at full speed."
  - [security-info.md:171-176](../../docs/security-info.md#L171-L176): "**There is no key
    stretching.** … a 4-digit PIN falls in milliseconds, a 6-digit PIN in seconds."

  So the bullet is not merely imprecise; it is refuted by its own surrounding prose. A
  reader who skims the "Brute-force protection is enforced on the device" list and stops
  there takes away the opposite of the truth.
- **Actionable Fix / Changes Needed:** Rewrite the bullet to say what the HMAC actually
  buys — that the PIN is not recoverable from the PIN file *without* the device secret,
  which is a statement about an attacker who has one and not the other:

  ```markdown
  - The PIN check is an HMAC keyed with the internal secret, so the PIN file alone
    is useless without that secret. Note both live in internal flash: an attacker who
    reads flash obtains both and can brute-force offline (see above). RDP is what
    separates these two cases, not the HMAC.
  ```

  This is a documentation fix. The underlying weakness is F-06 and needs the memory-hard
  KDF proposed there.

### AD-05: `security-info.md` documents a mixed-inputs warning that does not exist

- **Current Status:** Active — new defect, introduced after the audit
- **Codebase Evidence:**
  [security-info.md:284-291](../../docs/security-info.md#L284-L291) claims:

  > If a transaction spends inputs from more than one wallet group, the device
  > shows an explicit mixed-inputs warning at the top of the transaction
  > confirmation, so it is visible without scrolling.
  > This also applies when known-wallet and unknown-wallet inputs are mixed …
  > The warning is particularly intended to mitigate the class of multisig/mixed-input
  > change-address [attack](https://blog.trezor.io/details-of-the-multisig-change-address-issue-and-its-mitigation-6370ad73ed2a).

  No such warning exists. `grep -rn -i "mixed" src/ --include=*.py` returns only an
  unrelated comment in [rng.py:52](../../src/rng.py#L52) and a descriptor xpub/tpub check at
  [manager.py:536](../../src/apps/wallets/manager.py#L536).
  `confirm_wallets` ([manager.py:370-382](../../src/apps/wallets/manager.py#L370-L382))
  returns early whenever every input resolved:

  ```python
  async def confirm_wallets(self, wallets, show_screen):
      # check if any inputs belong to unknown wallets
      if None not in wallets:
          return True                     # two known wallets -> no warning at all
  ```

  The only use of `len(wallets)` is [manager.py:738](../../src/apps/wallets/manager.py#L738),
  which *suppresses* the change flag when more than one wallet is present — a
  classification behaviour, not a warning. `confirm_transaction_final` does build a title
  listing each wallet and amount, which the audit already characterised under SM-21 as
  "useful disclosure but not the documented mixed-wallet warning".

  Two aggravating details:
  1. This is **stronger** than the claim the audit found Contradicted in SM-21. The old doc
     said mixed inputs "cause a warning"; the new one specifies placement, scroll
     visibility, and a named attack it mitigates. The drift moved in the wrong direction.
  2. "at the top … visible without scrolling" is structurally false even for the warnings
     that *do* exist. `meta["warnings"]` is rendered inside the scrolling `lv.page`, appended
     after all outputs and the fee
     ([transaction.py:79-83](../../src/gui/screens/transaction.py#L79-L83)) — that is F-19.
     And `meta["warnings"]` is never populated on the Bitcoin path at all, which is F-24.
- **Actionable Fix / Changes Needed:** Two options, and the choice is a product decision:
  1. **Correct the document.** Remove the mixed-inputs paragraph and the Trezor-attack
     mitigation claim. This is the honest short-term move — the device currently does not
     mitigate that attack class.
  2. **Implement the warning,** then the document becomes true. Minimal version:

     ```python
     # manager.py, in preprocess_psbt after the input loop
     known = [w for w in wallets if w is not None]
     if len(known) > 1:
         meta.setdefault("warnings", []).append(
             "Inputs come from %d different wallets. Change addresses for "
             "the other wallets cannot be verified." % len(known))
     ```

     This depends on F-24 (populating `meta["warnings"]` on the Bitcoin path at all) and on
     F-19 (rendering warnings outside the scrolling container) before the "visible without
     scrolling" half of the claim becomes true. Until all three land, option 1 is the only
     accurate state.

### AD-06: The audit's submodule-provenance premise is no longer true

- **Current Status:** Invalidated by this tree — audit §1.2 and PATH-16 must be redone
- **Evidence:** [audit.md:80-84](audit.md#L80-L84) states two things that are now false:

  > No `branch =` declaration exists anywhere in the recursive submodule
  > configuration, so commits are pinned by immutable gitlinks rather than by
  > mutable branch names. The URLs in `f469-disco/.gitmodules` are relative …

  There are now **six** `branch =` declarations across the recursive configuration:

  ```text
  ./.gitmodules:4              branch = dev          (f469-disco)
  ./.gitmodules:9              branch = dev          (bootloader)
  ./bootloader/.gitmodules:8   branch = dev          (lib/fatfs)
  ./f469-disco/.gitmodules:8   branch = release/v6   (lvgl)
  ./f469-disco/.gitmodules:13  branch = secp-zkp     (usermods/secp256k1)
  ./f469-disco/.gitmodules:18  branch = dev          (libs/common/embit)
  ```

  and the `f469-disco/.gitmodules` URLs are absolute, not relative. Six of the eight
  submodule URLs now point at forks under one GitHub org
  (`hardware-wallets-and-cryptography/*`) rather than at the upstreams the audit resolved
  them against — `f469-disco`, `bootloader`, `micropython`, `secp256k1-embedded`, `embit`,
  and `fatfs`. Only `lvgl/lvgl` and `bitcoin-core/secp256k1` still point upstream.

  **Accurate severity.** The gitlink SHAs are still immutable, and a normal
  `git clone --recursive` / `git submodule update` still fetches exactly the recorded
  commits. `branch =` only takes effect under `git submodule update --remote`. So this is
  not an exploitable weakening of the pin today. What it does is:
  1. reintroduce the footgun the audit certified as absent — any `--remote` update, or CI
     that uses one, silently advances to a mutable branch tip;
  2. void the §1.2 provenance table. Every "Resolves on its declared origin" row was
     verified against the old upstream URL. The declared origin has changed for six of
     eight entries, so those verifications no longer apply to this tree.

  PATH-18 ("Vendored embit matches its identified upstream tree") is separately void: its
  evidence is "all 41 vendored Python files match upstream `189efc4`", and there is no
  vendored embit any more. That property needs restating against the v0.8.2 submodule.
- **Actionable Fix / Changes Needed:**
  1. Decide whether the `branch =` lines are wanted. If the intent is reproducible builds,
     drop them — they buy nothing for `git submodule update` and only enable `--remote`
     drift. If they are wanted for maintenance convenience, document that release builds
     must never use `--remote`, and assert it in CI.
  2. Re-run the §1.2 provenance verification against the fork URLs: for each of the six
     moved submodules, record that the pinned SHA exists in the fork **and** its relation
     to the corresponding upstream commit (identical, ahead by N, or diverged). The
     `f469-disco` and `embit` forks are known to be ahead; the others should be confirmed
     identical or the divergence explained.
  3. Restate PATH-18 against embit v0.8.2 — the relevant question is now "does the pinned
     submodule match upstream `embit` v0.8.2", not "do 41 vendored files match `189efc4`".

### AD-07: 39 of the audit's 40 `PATH-xx` items were not re-verified

- **Current Status:** Scope gap in this comparison, recorded rather than closed
- **Evidence:** [Section 9.1](audit.md#L4477) of the audit defines 40 `PATH-xx` entries —
  attack paths it examined and found **Blocked** or **Not reachable**. These are the
  audit's "defenses that hold" set. This comparison re-verified exactly one of them
  (PATH-06, incidentally, via AD-02) and invalidated two more (PATH-16 and PATH-18, via
  AD-06). The remaining 37 have not been re-checked.

  This matters because a property that held at v1.9.0 can be *unblocked* by a change, and
  three code deltas landed. Triaged by exposure to those deltas:

  | Risk | PATH items | Why |
  | --- | --- | --- |
  | **Needs re-check — embit swap** | PATH-08, PATH-34, PATH-35, PATH-36, PATH-37, PATH-38, PATH-39, PATH-40 | All are embit-owned properties (RFC6979 nonces, BIP-173/350 vectors, `Script.address` witness constraints, Base58Check, address verification and display). Every one was verified against the vendored `189efc4` tree that no longer exists. |
  | **Needs re-check — bootloader bump** | PATH-10, PATH-13, PATH-23 … PATH-29 | Bootloader moved `fc6e61e` → `c331570`, touching keys, `gui.c`, `main.c`, and tools. |
  | **Holds by construction** | PATH-19, PATH-20, PATH-21, PATH-30, PATH-31, PATH-32, PATH-33 | Owned by `usermods` / `micropython` / `microur`, all confirmed byte-identical to the audited trees. |
  | **Invalidated** | PATH-16, PATH-18 | See AD-06. |
  | **Re-verified** | PATH-06 | Verdict stands; only its two citations were wrong (AD-02). |

  No claim is made here that any of the 37 has actually regressed — only that this
  document does not establish that they have not.
- **Actionable Fix / Changes Needed:** Re-run Section 9.1's eight embit-owned entries
  against v0.8.2 first; that is the largest single block of unverified "holds" claims and
  the delta most likely to have moved one. The bootloader block is second. The
  "holds by construction" group needs no work while those submodules stay pinned.

---

## Method notes

- Every "Resolved" and "Partially Resolved" verdict above cites the specific code that
  implements the fix. ✅ F-01 and ✅ F-02 were additionally verified by **executing** the current
  `embit` under CPython against forged v0 PSBTs carrying v2-only scope keys, through both
  `PSBT.parse` and `PSBTView` (the class Specter-DIY actually uses), for all four keys the
  audit named (`0x03`/`0x04` on outputs, `0x0e`/`0x0f`/`0x10` on inputs).
- "Active" verdicts were established by reading the current source at the cited line
  ranges, not by assuming the absence of a commit.
- Submodule-owned findings were cross-checked with `git diff --stat <audited-sha>..HEAD`
  inside each submodule, so "unchanged" claims are mechanical rather than inferred.
- Not re-verified: anything the audit itself marked as requiring hardware or dynamic
  testing (Section 13.1). F-32's fault inducibility, F-34's trigger timing, and F-31's
  post-overwrite impact remain open in the same way the audit left them.
- The `AD-*` section was produced by extracting every `](../../…)` link from `audit.md`
  and testing each path against HEAD, then against the audited tree
  (`git cat-file -e v1.9.0:<path>` in the parent repo, `git cat-file -e db3ce3e:<path>`
  inside `f469-disco`) to separate audit errors from drift this tree caused.
- AD-03's table is a **spot check of 4 of the 23 `SM-xx` rows**, not a re-verification of
  Section 8.10. The remaining 19 rows have not been re-checked against
  `docs/security-info.md`; that is listed as follow-up work, not as a completed result.
- AD-04 and AD-05 are defects in documentation written *after* the audit date, so they are
  not audit misses. They are reported here because verifying the audit's doc-vs-code rows
  is what surfaced them.
- **Known scope limits of this document**, stated so they are not mistaken for clean
  results: Section 9.1's `PATH-xx` set is 37/40 unverified (AD-07); Section 8.10's `SM-xx`
  table is 19/23 unverified against the replacement security document (AD-03); and the
  audit's Sections 10 to 14 (testing gaps, final funds-theft analysis, remediation
  priority, disclosure routing, scope closure) were not re-assessed at all, since they are
  recommendations rather than findings.
