# Development firmware build, simulation, testing

## Clone the repository

```sh
git clone https://github.com/hardware-wallets-and-cryptography/specter-diy.git --recursive
```

## Install required development environment

The recommended way to set up your development environment is by using the Nix flakes with `direnv`.

### Install Nix
- *Recommended installer*: [Determinate Nix Installer](https://github.com/DeterminateSystems/nix-installer) (macOS, Linux, Windows Subsystem for Linux)
- *Required version*: `Nix 2.4` or newer (for flakes and `nix develop`) 
- *How to verify*: Run `nix --version` *(Note: The Determinate installer prints two versions. The first one is your current Nix version, and the second is the upstream Nix version.)*

### Enable Nix flakes
- Ensure [flakes](https://wiki.nixos.org/wiki/Flakes) are enabled in your Nix config *(Note: The Determinate installer enables `nix-command` and `flakes` automatically. On Linux, ensure your user is in the `nix-users` group.)*

### Install direnv
   ```sh
   brew install direnv     # macOS
   sudo apt install direnv # Linux
   ```

### Hook direnv into your shell
- Follow the [instructions](https://direnv.net/docs/hook.html) for your shell of choice

## Enter the development environment

Choose **one** of the following three methods. All three provide the exact same environment.

### Option A: `direnv` (Recommended)
Automatically loads the shell when you enter the directory.
```sh
direnv allow
```
*Note: You only need to run this once per clone. `direnv` will automatically load and unload the Nix environment whenever you `cd` in or out of the project.*

### Option B: `nix develop`
Manually loads the shell once per session.
```sh
nix develop
```
*(Alternatively, you can prefix individual commands with `nix develop -c`).*

### Option C: `nix-shell` (Fallback)
Use this if flakes are not enabled in your Nix config or if your tooling expects the classic interface.
```sh
nix-shell
```

> **Technical note on `nix-shell` compatibility:**
> `shell.nix` is a thin compatibility shim. It reads the `flake-compat` input pinned in `flake.lock` and derives the shell from `flake.nix`. This ensures the toolchain remains pinned (e.g., to `nixos-22.05` to retain `gcc-arm-embedded-9`) and packages are never duplicated. Add or change packages in `flake.nix` only. 
> To confirm both paths agree, you can run:
> `nix-instantiate shell.nix`
> `nix eval .#devShells.$(nix eval --raw --impure --expr builtins.currentSystem).default.drvPath`

## Build the firmware

```sh
make disco
```

This compiles an open firmware (no bootloader, no signature verification). It generates `bin/specter-diy.bin`. 

**To flash:** Drag the file onto the board's virtual mass-storage drive, or use programming tools like `STM32CubeProgrammer`.

> **This only works on a board without the secure bootloader.** The firmware links at `0x08000000` and replaces the whole boot chain. A board that was flashed with a release image has readout protection at level 1 and write-protected bootloader sectors, which block programming over ST-LINK. You have to [remove the protections](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/remove_protection.md) first, and that mass-erases the device.

*Note: The `bootloader` and `f469-disco` submodules are fetched automatically on the first build. If you forgot the `--recursive` flag during cloning, `make` will update the submodules for you.*

**Further reading:**
* [Reproduce a release and verify its hashes](./deterministic-firmware-build.md)
* [Build a custom bootloader and self-signed firmware](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/selfsigned.md)

---

## Build and run the simulator

Compile a MicroPython simulator for Unix/macOS:
```sh
make unix
```

Launch the simulator using either of the following commands:
```sh
make simulate
# OR
bin/micropython_unix simulate.py
```

### Interacting with the simulator
The simulator emulates serial communication and USB over fixed TCP ports, displaying the wallet interface on your screen. 
* **QR Scanner:** The console prints `Connect to 127.0.0.1:22849 to send QR code content` on startup. Connect to that port with `telnet` to feed the scanner.
* **QR Output:** The contents of any QR codes rendered on the simulator screen are printed directly to your console.
* **USB:** Port `8789`, announced the same way. It only becomes available after USB is explicitly enabled in the on-device settings menu.

### File system structure
The simulator generates the following directories inside `./fs`:
* `fs/flash` – Internal MCU flash storage.
* `fs/qspi` – External QSPI chip storage (untrusted; data is stored encrypted and authenticated).
* `fs/ramdisk` – External SPIRAM memory (untrusted temporary storage for host communication). Created on first use rather than at startup, and wiped every time it is mounted.
* `fs/sd` – Emulated SD card.

Pass a path to use a different storage root, which is handy for keeping several simulated devices side by side:
```sh
bin/micropython_unix simulate.py ./fs-second-device
```

*Troubleshooting: If the simulator behaves unexpectedly, run `make clean`.*

---

## Run unit tests

Both test suites run in CI automatically. Please run both locally before pushing your code.

### MicroPython tests
These tests run on the MicroPython Unix port (Linux and macOS):
```sh
make test
```

### Native CPython 3 tests
This secondary suite uses stubbed hardware modules and runs on standard CPython 3 (no MicroPython build required). **It is not included in `make test`** and must be run separately:
```sh
cd test && python3 run_native_tests.py
```

### Security finding evidence (expected to fail)
The separate evidence suite exercises the still-open software behaviors in audit findings F-03, F-04, F-06, F-17, F-18, F-19, F-21, F-22, F-23, F-24, F-25, and F-28. It runs CPython tests, a host-compiled STM32 RNG driver with mocked peripheral registers, and focused bootloader C tests using a host C/C++ compiler and `make`:

```sh
python3 test/evidence/run.py
```

The assertions express the desired security properties, so this command exits nonzero while those findings remain open. It is intentionally excluded from normal CI and `run_native_tests.py`; do not mark these tests as expected failures. F-03 and F-04's already-passing checks remain in the normal native suite, while their open fee-provenance and script-commitment cases run here. F-17 signs a test-key message using the application's hashing method and checks the result with the production bootloader C verifier; its separate Python test enforces the interim policy of refusing release-format messages. F-21's previously fixed embedded-NUL case remains in the normal native suite; the evidence suite tests its remaining frame (requiring hex display for a forged delimiter) and address-mapping issues. F-18 tests driver status reporting on timeout, seed, and clock faults with mocked registers and Python-layer error propagation, not physical entropy or every native RNG caller. F-19 and F-24 run the actual screen code against a simplified geometry/widget model; LVGL layout and scrolling still require device validation. F-23 exercises an approved host import and subsequent persisted-label reload; F-25 models an attacker with flash write access recomputing both CRCs; F-28 checks both multipart CRC layers. Offline PIN recovery here assumes a flash dump, and the card stubs do not prove physical readout or real smartcard behavior. After a fix, move applicable passing property tests into the normal regression suite; the F-17 interim refusal test can instead be retired once the signing domains are separated.
