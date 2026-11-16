# Specter-DIY

The idea of the project is to build a hardware wallet from off-the-shelf components.

We also want to keep the project flexible such that it can work on any other set of components with minimal changes. Maybe you want to make a hardware wallet on a different architecture (RISC-V?), with an audio modem as a communication channel – you should be able to do it. It should be easy to add or change functionality of Specter and we try to abstract logical modules as much as we can.

QR codes are the default method for Specter to communicate with the host. They are convenient and keep the user in full control of data transmission: each QR code has a strictly limited capacity, and communication is unidirectional. Furthermore, the setup is completely airgapped, meaning you never need to connect the wallet to a computer.

For secret storage, we currently support agnostic mode (the wallet forgets all secrets when powered off) and reckless mode (secrets are stored in the application microcontroller's flash). Secure element integration is coming soon.

Our main focus is multisignature setup with other hardware wallets, but wallet can also work as a single signer. We try to make it compatible with Bitcoin Core where we can – PSBT for unsigned transactions, wallet descriptors for importing/exporting multisig wallets. To communicate with Bitcoin Core easier we are also working on [Specter Desktop app](https://github.com/cryptoadvance/specter-desktop) - a small Python [Flask](https://github.com/pallets/flask) server talking to your Bitcoin Core node.

Most of the firmware is written in MicroPython which makes the code easy to audit and change. We use [secp256k1](https://github.com/bitcoin-core/secp256k1) library from Bitcoin Core for elliptic curve calculations and [LVGL](https://lvgl.io/) library for GUI.

## DISCLAIMER

The project has matured significantly, to the point where the security level of the Specter-DIY wallet is now comparable to commercial hardware wallets on the market. We have implemented a secure bootloader that verifies firmware upgrades, ensuring that only signed firmware can be uploaded to the device after initial setup. However, unlike commercial signing devices, the bootloader is not pre-installed at the factory and must be flashed manually by the user. As a result, pay extra attention during the initial installation – make sure to verify the PGP signatures and flash the firmware from a secure computer.

If something doesn't work open an issue here or ask a question in our [Telegram group](https://t.me/+VEinVSYkW5TUl5Ai).

## Documentation

All the docs are stored in the [`docs/`](./docs) folder:

- [`shopping-list.md`](./docs/shopping-list.md) explains what to buy
- [`assembly.md`](./docs/assembly.md) shows how to put everything together
- [`quickstart.md`](./docs/quickstart.md) guides you through the initial steps how to get firmware on the board
- [`security-info.md`](./docs/security-info.md) explains possible attack vectors and security model of the project
- [`deterministic-firmware-build.md`](./docs/deterministic-firmware-build.md) shows how to reproduce the released binaries in Docker and verify their hashes
- [`development-firmware-build-simulation-testing.md`](./docs/development-firmware-build-simulation-testing.md) describes how to build the firmware and the simulator yourself
- [`This doc block`](./docs/development-firmware-build-simulation-testing.md#build-and-run-the-simulator) shows how to build and run the simulator on Unix/macOS
- [`This doc block`](./docs/development-firmware-build-simulation-testing.md#run-unit-tests) describes how to run the unit tests
- [`development.md`](./docs/development.md) explains how to start developing on Specter
- [`communication.md`](./docs/communication.md) defines communication protocol with the host over QR codes and USB
- [`roadmap.md`](./docs/roadmap.md) explains what we need to implement before we can consider the wallet be ready to use with real funds.

## USB communication on Linux

You may need to set up udev rules and add yourself to `dialout` group. Read more in [`udev`](./udev/README.md) folder.

## Video and screenshots

Check out [this video](https://www.youtube.com/watch?v=1H7FqG_FmCw) to get an idea how to assemble it and how it works.

Here is a [gallery](./docs/pictures/gallery/README.md) with devices assembled by the community.

A few pictures of the UI:

### Wallet screens

![](./docs/pictures/wallet_screens.jpg)

### Key generation and recovery

![](./docs/pictures/init_screens.jpg)
