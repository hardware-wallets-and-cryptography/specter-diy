#!/bin/bash
# Abort on the first failure. Otherwise, the script continues after
# a failed compile, prints "saved to ..." for missing files, and returns
# a false 0 exit code, which can cause a broken build to output
# a plausible-looking sha256.txt.
set -eo pipefail

INFO="\e[1;36m"
ENDCOLOR="\e[0m"

echo -e "${INFO}
══════════════════════ Building main firmware ═════════════════════════════
${ENDCOLOR}"
make clean
make disco USE_DBOOT=1

echo -e "${INFO}
═════════════════════ Building secure bootloader ══════════════════════════
${ENDCOLOR}"
cd bootloader
make clean
make stm32f469disco READ_PROTECTION=1 WRITE_PROTECTION=1
cd -

echo -e "${INFO}
══════════════════════ Assembling final binaries ══════════════════════════
${ENDCOLOR}"
mkdir -p release

python3 ./bootloader/tools/make-initial-firmware.py -s ./bootloader/build/stm32f469disco/startup/release/startup.hex -b ./bootloader/build/stm32f469disco/bootloader/release/bootloader.hex -f ./bin/specter-diy.hex -bin ./release/initial_firmware.bin
echo -e "Initial firmware saved to release/initial_firmware.bin"

python3 ./bootloader/tools/upgrade-generator.py gen -f ./bin/specter-diy.hex -p stm32f469disco ./release/specter_upgrade.bin
cp ./release/specter_upgrade.bin ./release/specter_upgrade_unsigned.bin
echo "Unsigned upgrate file saved to release/specter_upgrade_unsigned.bin"

HASH=$(python3 ./bootloader/tools/upgrade-generator.py message ./release/specter_upgrade.bin)

echo "
╔═════════════════════════════════════════════════════════════════════════╗
║                    Message to sign with vendor keys:                    ║
║                                                                         ║
║    ${HASH}   ║
║                                                                         ║
╚═════════════════════════════════════════════════════════════════════════╝
"


echo -e "${INFO}
═════════════════════ Adding signature to the binary ══════════════════════
${ENDCOLOR}"

while true; do
  echo "Provide a signature to add to the upgrade file, or just hit enter to stop."
  # Terminate the loop on either an empty input line or closed stdin (non-interactive mode).
  read -r SIGNATURE || break
  if [ -z "$SIGNATURE" ]; then
    break
  fi
  python3 ./bootloader/tools/upgrade-generator.py import-sig -s "$SIGNATURE" ./release/specter_upgrade.bin
  echo "Signature is added: ${SIGNATURE}"
done

echo -e "${INFO}
═════════════════════════ Hashes of the binaries: ═════════════════════════
${ENDCOLOR}"

cd release
sha256sum *.bin > sha256.txt
cat sha256.txt

echo "
Hashes saved to release/sha256.txt file.
"