# Specter-DIY on macOS — Build and Setup

A step-by-step build of a Specter-DIY hardware wallet on an STM32F469I-DISCO board.

The application firmware is MicroPython, so you can read it. The layers under it
(MicroPython, `secp256k1`, LVGL, and the secure bootloader) are C and live outside this
repo.

**The initial flash is unverified.** Nothing checks it but you. Use a clean machine and
verify the signature. After that first flash the bootloader takes over and accepts only
signed firmware.

For the Specter Shield add-on (smartcard slot, scanner, battery, printed case) see
[`shield/`](../shield).

---

## Hardware

| Item                   | Notes |
|---|---|
| STM32F469I-DISCO board | The main part. |
| **Mini**-USB cable     | Not Micro-USB. Used once, for the initial flash. |
| Power bank             | Powers the wallet away from a computer. |
| QR scanner             | Optional. Needed for the QR workflow. |
| 4 pin headers          | To connect the QR scanner. No soldering required. |
| microSD card           | FAT, 32 GB max. Required for every future firmware update. |

Details: [`docs/shopping-list.md`](../docs/shopping-list.md) and
[`docs/assembly.md`](../docs/assembly.md). The firmware configures the scanner on first
boot — no manual setup.

Without a scanner, use the SD card to move data. Still airgapped, just slower. USB works
too but breaks the airgap; the project discourages it.

---

## 1. Install tools

```bash
brew install gnupg          # install Homebrew first if you don't have it
```

## 2. Download the release

From <https://github.com/cryptoadvance/specter-diy/releases>, grab two files into
`~/Downloads`:

- `initial_firmware_<version>.bin` — for the first flash. **Not**
  `specter_upgrade_<version>.bin`, which is for later SD-card updates.
- `sha256.signed.txt` — contains the hashes *and* the signature.

## 3. Verify the signature

Two links in a chain:

1. The **key** proves who wrote the hash list. `sha256.signed.txt` is a signed file;
   `gpg --decrypt` checks that signature and writes out the bare list as `sha256.txt`.
2. The **hash list** proves the binary is intact. `shasum -c` compares your `.bin`
   against it.

Don't skip to link 2. An attacker who replaced the firmware would replace the hash list
with it. The hashes only mean something because the signature says who wrote them.

The signing key changed in v1.10.3. Pick the row matching your download:

| Release | Key | Fingerprint |
|---|---|---|
| v1.10.3+ | `Specter Signer 2026 <noreply@specter.solutions>`, rsa4096 | `9DC33CA830589DE3B3225C26EEF5756B2EA42349` |
| up to v1.9.0 (including) | `Stepan Snigirev (Specter release signing key) <snigirev.stepan@gmail.com>`, secp256k1, expires 2027-11-04 | `6F16E354F83393D6E52EC25F36ED357AB24B915F` |

Confirm the fingerprint against the release notes for your exact version. Keys rotate;
the release notes outrank this table.

### Import the key

**Download ≠ import.** Downloading puts the key file on disk, where gpg ignores it.
Importing copies it into your keyring (`~/.gnupg/`), and gpg verifies signatures *only*
against keys in the keyring.

| Command | Downloads | Imports |
|---|---|---|
| `gpg --recv-keys` | yes | yes — both in one step |
| `curl -O` | yes | no |
| `gpg --show-keys <file>` | no | no — just reads the file and prints the fingerprint |
| `gpg --import <file>` | no | yes |

#### Route A — v1.9.0 and older (Stepan's key, published as a `.asc` file)

1. Go to your downloads folder:

   ```bash
   cd ~/Downloads
   ```

2. Download the key file. It lands on disk; your keyring is untouched:

   ```bash
   curl -O https://stepansnigirev.com/ss-specter-release.asc
   ```

3. Read the key without importing it:

   ```bash
   gpg --show-keys ss-specter-release.asc
   ```

   ```
   pub   secp256k1 2020-10-01 [SC] [expires: 2027-11-04]
         6F16E354F83393D6E52EC25F36ED357AB24B915F
   uid                      Stepan Snigirev (Specter release signing key) <snigirev.stepan@gmail.com>
   ```

4. Compare that fingerprint to the table above — all 40 characters. If it differs, stop
   and delete the file.

5. Import it into your keyring. This is what makes the next command work — gpg only
   verifies against keys in the keyring, never against a loose file:

   ```bash
   gpg --import ss-specter-release.asc
   ```

#### Route B — v1.10.3+ (Specter Signer 2026, keyserver only)

1. Fetch the key by fingerprint. This downloads **and** imports in one step:

   ```bash
   gpg --keyserver hkps://keyserver.ubuntu.com \
       --recv-keys 9DC33CA830589DE3B3225C26EEF5756B2EA42349
   ```

2. Re-print the fingerprint of what actually landed in your keyring:

   ```bash
   gpg --fingerprint 9DC33CA830589DE3B3225C26EEF5756B2EA42349
   ```

3. Compare it to the table — all 40 characters. There is no inspect-before-import here,
   so if it's wrong, remove it:

   ```bash
   gpg --delete-keys 9DC33CA830589DE3B3225C26EEF5756B2EA42349
   ```

Anyone can publish a key under any name, on a keyserver or a website. The fingerprint
comparison is the actual check — compare all 40 characters, never a short key ID.

**Verify and extract the hashes:**

```bash
gpg --output sha256.txt --decrypt sha256.signed.txt
```

Look for `gpg: Good signature from "..."` and check the name matches the table.

**Check the binary:**

```bash
shasum -a 256 --ignore-missing -c sha256.txt
# initial_firmware_<version>.bin: OK
```

### Reading the output

- `WARNING: This key is not certified with a trusted signature!` — normal. It only means
  you never signed the key yourself. `Good signature` is what matters.
- `Note: This key has expired!` — not a failure. An expired key can't sign new releases
  but what it signed while valid stays valid.
- `Can't check signature: No public key` — the key isn't in your keyring. You skipped or
  botched the import step.
- `BAD signature` or a failed hash check — **stop.** Delete, re-download, don't flash.
- GnuPG 2.4+ prints fingerprints unspaced; older versions use ten groups of four. Same 40
  characters.

---

## 4. Flash the board

The board mounts as a USB drive. No STM32CubeProgrammer, no st.com account.

1. Set the **power jumper** (top side) to **STLK**.
2. Connect the **mini-USB** cable to the port on the **top edge** (ST-LINK).
3. The board appears in Finder as **`DIS_F469NI`**.
4. Copy `initial_firmware_<version>.bin` to the root of that drive.
5. The board resets, boots the bootloader, verifies the firmware, starts Specter.

Drag-and-drop flashing is flaky — usually the cable or a USB hub. Plug straight into the
Mac and retry 2–3 times. If it keeps failing:

```bash
brew install stlink
st-flash write ~/Downloads/initial_firmware_<version>.bin 0x8000000
```

### After the first flash

**The bootloader sets the MCU read/write protection flag.** You can still re-flash the
board as often as you like — but the route changes:

| | Works after protection? |
|---|---|
| SD-card upgrade (signed `specter_upgrade_*.bin`) | Yes, indefinitely. This is the normal path. |
| Mini-USB drag-and-drop, `st-flash` | No. You get `FAIL.txt` on the drive. |
| Unsigned or self-built firmware | No, unless you build the bootloader with your own keys — see [selfsigned.md](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/selfsigned.md). |

To update: put **exactly one** `specter_upgrade_<version>.bin` in the root of a FAT SD
card, insert it, power on.

**Two unrelated key systems — don't confuse them.** The PGP key from step 3 is not what
gates re-flashing:

| | PGP key (step 3) | Bootloader keys |
|---|---|---|
| Lives in | GnuPG on your Mac | Compiled into the bootloader — [`bootloader/keys/production/pubkeys.c`](../bootloader/keys/production/pubkeys.c) |
| Type | one signer's key | secp256k1 ECDSA, separate vendor and maintainer lists |
| Answers | "is this download the original release?" | "may this firmware run on the device?" |
| Enforced by | you, manually | the device, on every boot |

The board never sees your PGP keyring — that's why the initial flash is unverified.
Afterwards, upgrades need **2 valid signatures** (`bootloader_sig_threshold = 2`,
`main_fw_sig_threshold = 2`), so no single developer can push firmware to your device.

To run your own builds you must compile the bootloader with your own keys
(`KEYS=selfsigned`) **before** the initial flash. Afterwards, replacing the bootloader
needs 2 production signatures or a full unlock and erase.

### What I did

- Checked that the jumper on the top of the board is set to STLK
- Connected the board to macOS via mini-USB
- Copied firmware to the board
- The screen (as in all the tutorial videos) appeared
- Disconnected the board from macOS
- Switched the jumper on the top of the board to USB
- Connected the board to power-bank via micro-USB
- Nothing happened
- Jumped back and forth (selected the mini-USB back and micro-USB again)
- Nothing happened
- Then I flashed the board with STM32CubeProgrammer
- Copied the same way firmware to the board
- Connected the board again to power-bank via micro-USB
- And now it worked!!

### Getting mini-USB flashing back (full reset)

The protection is reversible. This is not a firmware update — it wipes the board back to
factory-blank.

**Why you can still reach a "locked" board.** The mini-USB port connects to the on-board
ST-LINK chip, which is a *separate* microcontroller from the STM32F469 target. Protection
locks the target's **flash**, not the debug link. The debugger still connects; it just
can't read or write flash — that's what `FAIL.txt` and CubeProgrammer's read error mean.

What it *can* still write is the **option bytes**. STM32 hardware enforces that dropping
RDP from level 1 to level 0 mass-erases the flash first. That's the designed escape hatch:
the flash can never be extracted, only destroyed.

OpenOCD way didn't work for me on macOS:
[Repo link](https://github.com/hardware-wallets-and-cryptography/specter-bootloader/blob/master/doc/remove_protection.md?plain=1#L3)
[Submodule link to `bootloader/doc/remove_protection.md`](../bootloader/doc/remove_protection.md#L3)

GUI alternative with STM32CubeProgrammer worked for me:
[Repo link](https://github.com/hardware-wallets-and-cryptography/specter-bootloader/blob/master/doc/remove_protection.md?plain=1#L11)
[Submodule link to `bootloader/doc/remove_protection.md`](../bootloader/doc/remove_protection.md#L11) — connect,
ignore the read error, then OB → Read Out Protection → `AA`, and check every Write
Protection box.

First, the STM32CubeProgrammer said I do not have firmware and I need to re-install it. I did it with STM32CubeProgrammer, then on the right I selected `Connect`, but it didn't work. I selected from the dropdown the numbers (registers?) and it connected. Actually, the firmware installation recovered write access to the board. "Unlocked" it, so to speak.

**What you lose.** Everything on the chip, including the device secret: your PIN, any
stored recovery phrase, and your anti-phishing words. That is the point — new words on the
next boot are the signal that a wipe happened, so an attacker who erases your board to
install malicious firmware cannot hide it. This is never a way to recover coins; only your
seed backup does that.

Move the power jumper to match your power source and unplug from the Mac.

---

## 5. First boot — PIN

Power the board from a power bank from here on. Never the computer.

1. At **"Choose your PIN code"**, enter and confirm a PIN.
2. **Anti-phishing words.** Typing your PIN reveals words derived from a secret generated
   on first boot. Memorize them. They must be identical every boot. Different words mean
   the device was erased and re-flashed.
3. **10 wrong attempts wipes the device**, including any stored recovery phrase. Your
   paper/steel backup is the only recovery path.

---

## 6. Create your key

Choose **Generate new key**.

- Entropy comes from the STM32 TRNG *and* the touchscreen — every press mixes in its
  coordinates and the CPU tick count. All hashed with SHA-512
  ([`docs/security-info.md`](../docs/security-info.md)).
- 12 words by default. Toggle **"Use 24 words"** for 24.
- **Set the word count before editing anything.** The toggle regenerates the whole phrase.
- Tapping a word replaces it. This adds no entropy — it overwrites. The editor is a
  bit-toggle keypad (`1 2 4 8 … 1024`) for the word's BIP-39 index; the checksum word is
  fixed automatically.

**Dice entropy:** roll the phrase offline yourself, then use **Enter recovery phrase**
instead of Generate new key.

### Back it up

Paper first, in order. Then steel or titanium. Verify against the screen word by word
before powering off.

---

## 7. Choose a storage mode

**Default is amnesic: the phrase is erased on power-off.** You retype it every session via
**Enter recovery phrase**.

To store it: **Settings → Key management → "Flash & SD card storage" → Save key**.

| Option | Behavior |
|---|---|
| Internal flash | Phrase stays on the device, encrypted with your PIN + the device secret. The project calls this "reckless"; the menus don't. |
| SD card | Encrypted with the device secret. Card alone is useless, device alone can't unlock. A real second factor. |

Amnesic is most secure, least convenient. Pick deliberately.

With a Specter Shield the button reads **"Smartcard storage"** and the smartcard is the
second factor.

---

## 8. Passphrase (optional, the "25th word")

**Settings → Key management → "Enter BIP-39 password"**. The button says "password", the
screen says "passphrase" — same thing.

A passphrase produces an entirely different set of keys.

- **It is stored nowhere.** Lose it and the funds are gone, seed backup or not.
- You re-enter it every session. **A typo silently opens a different, empty wallet** with
  no error. Check your fingerprint first: **Master public keys** → any path → leave **Show
  derivation path** on. The key shows as `[fingerprint/derivation]xpub…`; the first 8 hex
  characters are your master fingerprint.

Store it separately from the steel plate.

---

## 9. Export the public key

1. **Master public keys**.
2. Pick a path (mainnet values shown; other networks shift the coin type automatically):
   - Single key → `m/84h/0h/0h` (native SegWit — the normal choice)
   - Multisig → `m/48h/0h/0h/2h`
   - **Show more keys** → Taproot `m/86h/0h/0h`, nested SegWit `m/49h/0h/0h`, nested
     multisig `m/48h/0h/0h/1h`
3. Scan the QR with your webcam in **Sparrow Wallet** to build a watch-only wallet.

The computer watches balances, builds transactions, and broadcasts. The board does none of
that.

---

## 10. Daily use

### Receiving

Register the wallet on the device first — press **"Create wallet"** on the Master public
keys screen, or import the descriptor from Sparrow over QR/SD. An xpub alone isn't enough;
the device needs the descriptor to recognize its own addresses.

Then **Wallets** → your wallet shows **"Receiving address #N"** with a QR, ◀ ▶ to step
through indexes.

**Always compare a deposit address on the device screen before sending to it.** Malware
swaps receive addresses as easily as send addresses, and nothing else here catches that.

### Sending

1. Sparrow builds an unsigned PSBT and shows it as an animated QR.
2. Specter-DIY scans it and displays amounts and destinations. **Verify on the device
   screen, not the computer.** Approve.
3. The device shows the signed PSBT as a QR.
4. Sparrow scans it back and broadcasts.

No scanner? Move PSBT files by SD card. USB works but breaks the airgap.

Protocol: [`docs/communication.md`](../docs/communication.md).

### Software wallet

**Sparrow** on the Mac — best airgapped QR support, PSBT handling, coin control, and it
connects to your own node later. BlueWallet on a phone is fine for watch-only balances.
[Specter Desktop](https://github.com/cryptoadvance/specter-desktop) is the project's own
app if you run Bitcoin Core.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `FAIL.txt` on `DIS_F469NI`: interface firmware failed to reset/halt target MCU | Device is already protected. Use the SD-card path. |
| Bootloader reports no valid firmware | Do an SD-card upgrade — [`docs/quickstart.md`](../docs/quickstart.md). |
| SD upgrade ignored | More than one `specter_upgrade*.bin` in the root, or the card isn't FAT / is over 32 GB. |
| Need mini-USB flashing back / factory reset | Reset option bytes to `AA` — [remove_protection.md](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/remove_protection.md:#11). Erases the flash and the device secret. |
| Which firmware version? | Device settings, under the title. |

---

## Reference

- [`docs/README.md`](../docs/README.md)
