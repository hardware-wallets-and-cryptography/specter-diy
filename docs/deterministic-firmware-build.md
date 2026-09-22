# Deterministic firmware build

## Initial notes

With [Docker](https://docs.docker.com/get-docker/) you can build the firmware yourself in the same environment as we do, and check that `initial_firmware.bin` has the same hash as the one in the GitHub release. This way you can be sure that the binary you flash is actually built from the code in this repository, no backdoors included.

The build is deterministic: the MicroPython version header is pinned to a fixed tag and build date (see `f469-disco/micropython/py/makeversionhdr.py`), and the firmware version string is a literal in `boot/main/boot.py`. No git metadata, timestamp or build path is embedded in the output, so two builds of the same commit produce identical binaries.

Because nothing is derived from git, building the wrong commit still produces a clean, plausible-looking `sha256.txt` that simply does not match. Check out the tag you are verifying before you build.

## Docker

Install Docker with BuildKit. Any current Docker Engine, Docker Desktop, Colima or Podman with a Docker-compatible CLI works. On macOS, the CLI plus Colima is enough - Docker Desktop is not needed:

```sh
brew install docker docker-buildx colima
```

`docker` is the client only, `colima` provides the daemon (see below) and `docker-buildx` is the BuildKit builder that `docker build` uses.

Homebrew does not register the plugin with the client, so link it once. Create the plugin directory:

```sh
mkdir -p ~/.docker/cli-plugins
```

Link the plugin into it:

```sh
ln -sfn "$(brew --prefix)/opt/docker-buildx/bin/docker-buildx" ~/.docker/cli-plugins/docker-buildx
```

Confirm the client found it:

```sh
docker buildx version
```

## Git

Check out the release you are verifying, for example:

```sh
git checkout v1.9.0
```

Check out submodules, otherwise the build has no sources to compile. This is also where `bootloader/tools/requirements.txt` comes from, which the image needs, so `docker build` fails without it:

```sh
git submodule update --init --recursive
```

## Cleanup

Remove the output of any previous run. The build script hashes every `.bin` in `release/`, so a stale file there ends up in `sha256.txt`:

```sh
rm -rf release
```

Nothing else is needed on the host: the toolchain and Python live in the image, and the sources are bind mounted at run time. The script runs `make clean` in both trees itself, so the build directories need no manual cleanup.

## Colima

Colima runs the daemon inside a VM that is not started for you. Start it before any `docker` command.

The default VM is 2 CPUs and 2 GiB of RAM. This build compiles MicroPython and the bootloader from scratch under amd64 emulation, so give it more. On Apple Silicon, also enable Rosetta, which emulates amd64 considerably faster than the alternatives:

```sh
colima start --cpu 4 --memory 8 --vz-rosetta
```

Pass these on the very first start. `cpu` and `memory` can be raised later by restarting with new flags, but `vmType` and `rosetta` are fixed when the VM is created - starting a plain `colima start` first and adding `--vz-rosetta` afterwards silently leaves Rosetta off. To change them on an existing VM you have to recreate it:

```sh
colima delete
```

`vz` is already the default virtual machine type on Apple Silicon, so `--vm-type vz` is redundant on current Colima. `colima status` and `docker info` show what the running VM actually has.

If the VM is not running, the socket does not exist and the CLI fails before it does anything:

```
ERROR: failed to connect to the docker API at unix:///Users/<you>/.colima/default/docker.sock;
check if the path is correct and if the daemon is running:
dial unix /Users/<you>/.colima/default/docker.sock: connect: no such file or directory
```

## Build

From the root of the repository:

1. Set up the bootloader to use production keys. The bootloader Makefile defaults to `KEYS=selfsigned`, and that directory ships with nothing but a `.gitignore`, so this step is required:

```sh
cp bootloader/keys/production/pubkeys.c bootloader/keys/selfsigned/
```

2. Build the Docker image:

```sh
docker build -t diy .
```

3. Run the build. The sources are bind mounted, so the binaries appear in `release/` on the host:

```sh
docker run -it --rm -v "$(pwd)":/app diy
```

On arm64 hosts Docker prints a `platform ... does not match` warning here. It is informational - the build runs correctly under emulation.

The script stops at the first failure, so a non-zero exit status means the binaries are not trustworthy. Do not use `release/sha256.txt` from a run that failed.

## Output

When the build finishes, `release/` contains:

| File                           | Description                                                                |
| ------------------------------ | -------------------------------------------------------------------------- |
| `initial_firmware.bin`         | startup code, bootloader and firmware combined, for the initial flashing   |
| `specter_upgrade.bin`          | upgrade file, with any signatures you added during the run                 |
| `specter_upgrade_unsigned.bin` | copy of the upgrade file taken before any signature was added              |
| `sha256.txt`                   | hashes of the three binaries above                                         |

## Verifying against a release

Only `initial_firmware.bin` can be compared against a release. It carries no signatures, so a local build of the right tag reproduces it byte for byte. Compare its hash in `release/sha256.txt` against the entry for `initial_firmware_<version>.bin` in the release's `sha256.signed.txt`.

The upgrade files cannot be compared. The released `specter_upgrade_<version>.bin` carries vendor signatures that you do not have, and no unsigned counterpart is published.

## Signing

Near the end the script prints the message to sign with the vendor keys and then waits for signatures, adding each one to `release/specter_upgrade.bin`. Press enter on an empty line to finish. If you are only reproducing hashes, press enter straight away.

To run non-interactively (in CI, for example), drop the `-t` flag and close stdin, which ends the signature loop immediately:

```sh
docker run -i --rm -v "$(pwd)":/app diy < /dev/null
```

An upgrade file signed with your own keys is only accepted by a device whose bootloader was built with the matching public keys. It is not a substitute for an official release.

## Flashing

`initial_firmware.bin` is the file to flash on a device that has no bootloader yet. It is copied onto the board's `DIS_F469NI` mass-storage drive over ST-LINK, not uploaded over DFU. See [quickstart.md](./quickstart.md) for the jumper position, the cable and the `st-flash` fallback.

**Flashing this binary locks the board.** The build enables `READ_PROTECTION=1` and `WRITE_PROTECTION=1`, so on first boot the bootloader sets flash readout protection to level 1 and write-protects its own sectors. After that:

- flash cannot be read back over SWD,
- returning to RDP level 0 triggers a mass erase, which wipes the device,
- the device only accepts upgrades signed by the keys compiled into the bootloader - the production keys, if you followed the step above - so you cannot load your own unsigned build over SD card afterwards.

To build a device that accepts your own keys instead, put your own `pubkeys.c` in `bootloader/keys/selfsigned/`; see the [bootloader self-signing documentation](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/selfsigned.md). Your binaries will then not match the released hashes. To undo the protections on a device, see [removing protections](https://github.com/cryptoadvance/specter-bootloader/blob/master/doc/remove_protection.md).

## Closing notes

The container runs as root. Depending on your Docker setup the files written to `release/` and the build directories may end up owned by root; `sudo chown -R "$(id -u):$(id -g)" release bin` fixes that if it happens. Docker Desktop and Colima map ownership back to your user automatically.
