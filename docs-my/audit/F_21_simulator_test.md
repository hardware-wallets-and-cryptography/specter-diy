# F-21 simulator test

How to check the F-21 message-signing fixes on the simulator: the trusted frame,
the hex view, the path warning, the address note, the Confirm scroll gate, and
that the message page ends above the warning and the buttons.

The simulator runs the real MicroPython and LVGL code in an SDL window that you
control with the mouse. It is not the device: touch, flick physics and the
display panel can differ, so a device check is still needed (see
[audit.md, F-21](audit.md#f-21-message-signing-displays-less-than-it-signs)).

## 1. Build the simulator

`src` is frozen into the simulator binary
([manifests/unix.py](../../manifests/unix.py)). **Rebuild after every change in
`src`**, or the simulator runs the old code.

```sh
nix develop -c make unix        # or `make unix` inside direnv / nix develop
```

Outside the Nix shell, linking fails with `library 'SDL2' not found`.

## 2. Automated checks (no clicking)

```sh
python3 test/integration/F_21_walkthrough.py --auto
```

This starts the simulator, unlocks it with the test mnemonic (fingerprint
`73c5da0a`, regtest) and runs
[tests/test_signmessage.py](../../test/integration/tests/test_signmessage.py) over
the simulated USB port. It checks:

| Test                                                                       | Checks                                                                                                                                                                                           |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `test_printable_message_signs_full_digest`                                 | 44h/49h/84h signatures recover to the right key over the BIP-137 digest                                                                                                                          |
| `test_forged_frame_message_still_signs`                                    | a message with a fake underscore line signs normally                                                                                                                                             |
| `test_nul_message_signs_every_byte`                                        | the signature covers the bytes after the NUL                                                                                                                                                     |
| `test_non_standard_paths_still_sign`                                       | 86h and 48h paths sign (with a warning)                                                                                                                                                          |
| `test_message_at_length_cap_signs` / `..._over_length_cap_is_rejected`     | 512 bytes signs, 513 is rejected                                                                                                                                                                 |
| `test_path_over_depth_cap_is_rejected`                                     | 11-level path is rejected                                                                                                                                                                        |
| `test_cancel`                                                              | Cancel returns `error: User cancelled`                                                                                                                                                           |
| `SignMessageGateTest.test_short_message_confirms_at_once`                  | short message: Confirm enabled at once, pressing it signs                                                                                                                                        |
| `SignMessageGateTest.test_long_message_needs_scroll_to_end`                | 40-line message: Confirm disabled; pressing it before and after a partial scroll does nothing; enabled after scrolling to the end; stays enabled after scrolling back up; pressing it then signs |
| `SignMessageGateTest.test_long_message_can_be_cancelled_without_scrolling` | Cancel works on a long message without scrolling                                                                                                                                                 |
| `SignMessageGateTest.test_page_ends_above_warning_and_buttons`             | deepest accepted path (10 × `2147483647h`, shows the warning) and a 40-line message: the page ends above the warning and the buttons; the gate still opens at the end and the signature is valid |

`SignMessageTest` approves with JSON values on the GUI control socket (port
8787), which call `set_value()` directly and skip the Confirm button.

`SignMessageGateTest` uses simulator-only widget commands on the same socket
([tcp_gui.py](../../src/gui/tcp_gui.py), `TCPGUI.widget_command`). They act on the
real LVGL widgets and each reply with one state line:

| Command                                        | Does                                                                                                                     |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `state`                                        | reports the screen: `state Prompt confirm=INA reviewed=0 y=… h=… page=… page_y=… [warn_y=…] btn_y=…` (see below)         |
| `press_confirm` / `press_cancel`               | sends `RELEASED` to the button. It is sent even when the button is disabled, so the screen's own guard is what is tested |
| `scroll_by <px>` / `scroll_end` / `scroll_top` | moves the scrollable, then sends `DRAG_END` as a real drag does                                                          |

State fields: `y`/`h` are the scrollable's offset and height, `page`/`page_y`
the page's height and top, `warn_y` the top of the warning (only when shown)
and `btn_y` the top of the Confirm button. The page is fully visible when
`page_y + page` is at most `warn_y` and `btn_y`.

You can try them by hand while the simulator runs: `telnet 127.0.0.1 8787`,
then type `state`.

Limits of the automated checks:

- Of what the screen looks like, only the page position is checked, from
  widget coordinates. Frame style, hex view and the rendered text are not.
  Section 3 covers them.
- `scroll_end` places the content flush with the page bottom (`y = page - h`,
  e.g. `-514`). A finger drag on LVGL stops at the bottom padding instead. So
  these tests prove the gate logic, not that a real drag reaches the 4 px
  end-of-scroll tolerance. The `scroll-gate` case in section 3 covers that,
  and finally the device.
- `TCPGUI` is only used when `platform.simulator` is true
  ([main.py](../../src/main.py)), so the widget commands never run on a device.

`python3 run_tests.py` in `test/integration` runs the same tests together with
the Bitcoin Core tests, so it needs `bitcoind` on regtest and `requests`. It
cannot run only the F-21 tests: `run_tests.py` imports the whole `tests`
package, and
[tests/test_with_rpc.py](../../test/integration/tests/test_with_rpc.py) connects
to Bitcoin Core as soon as it is imported. Without `bitcoind` the run fails
before any test starts, even with a name filter such as
`run_tests.py SignMessageTest`. `--auto` avoids this by loading only
`tests/test_signmessage.py`.

## 3. Interactive walkthrough (you check the screen)

```sh
python3 test/integration/F_21_walkthrough.py          # USB cases
python3 test/integration/F_21_walkthrough.py --qr     # plus the QR address cases
python3 test/integration/F_21_walkthrough.py --only scroll-gate,nul-byte
python3 test/integration/F_21_walkthrough.py --list
```

For each case the script:

1. prints what to expect on screen and what to click,
2. waits for Enter, then sends the `signmessage` command over USB (TCP 8789),
3. waits up to 5 minutes for you to act in the simulator window,
4. checks the reply automatically (signature valid over all bytes, or the
   expected error),
5. asks you `y/n/s` for each on-screen item.

At the end it prints a table of all checks and exits with 1 if any failed.

### Cases

| Case                          | Path                  | Message                                        | What to check on screen                                                                                                          | Click     |
| ----------------------------- | --------------------- | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `short`                       | `m/84h/1h/0h/0/0`     | `hello`                                        | title "Sign message?" with the path in small grey text under it; "Message:" and both underscore lines are small and grey; `hello` is in the larger white font; no warning; Confirm active at once | Confirm   |
| `forged-frame`                | `m/84h/1h/0h/0/0`     | `Pay Alice\n` + 34 `_` + `\nPay Mallory`       | the attacker's underscore line is in the large white message font, so it does not look like the grey frame                       | Confirm   |
| `nul-byte`                    | `m/84h/1h/0h/0/0`     | `I authorise nothing.\0<hidden attacker text>` | header "Hex message:"; body is a hex dump; "hidden attacker text" does not appear as text                                        | Confirm   |
| `scroll-gate`                 | `m/84h/1h/0h/0/0`     | 40 lines `line 00`…`line 39`                   | see below                                                                                                                        | see below |
| `cancel-long`                 | `m/84h/1h/0h/0/0`     | same 40 lines                                  | Cancel works without scrolling                                                                                                   | Cancel    |
| `taproot-warning`             | `m/86h/1h/0h/0/0`     | `hello`                                        | orange "Non-standard derivation path!" warning and icon; it does not cover the message or the buttons                            | Confirm   |
| `deep-path-long`              | 10 × `2147483647h`    | same 40 lines                                  | whole path visible under the title; warning shown; scrolled to the bottom, `line 39` and the grey line under it sit fully above the warning | scroll, Confirm |
| `wrong-coin-warning`          | `m/84h/0h/0h/0/0`     | `hello`                                        | same warning (coin 0h is mainnet, the simulator is on regtest)                                                                   | Cancel    |
| `standard-no-warning`         | `m/44h/1h/0h/0/0`     | `hello`                                        | grey frame, no warning                                                                                                           | Confirm   |
| `too-deep`                    | `m/0/…/0` (11 levels) | `hello`                                        | no prompt appears; reply `error: Derivation path too deep (11 > 10)`                                                             | —         |
| `too-long`                    | `m/84h/1h/0h/0/0`     | 513 × `a`                                      | no prompt appears; reply `error: Message too long (513 > 512 bytes)`                                                             | —         |
| `qr-address` (`--qr`)         | `m/84h/1h/0h/0/0`     | `hello`                                        | result screen note `Address: bcrt1q…` matches the address the script prints                                                      | Confirm   |
| `qr-taproot-address` (`--qr`) | `m/86h/1h/0h/0/0`     | `hello`                                        | warning on the prompt; result note `Address: not shown for this path`                                                            | Confirm   |

### Scroll gate (`scroll-gate`)

1. Click Confirm right away. Nothing happens and the button looks dimmed.
2. Drag the text up part way and release. Confirm still does nothing.
3. Drag or flick to the bottom until `line 39` is visible and the scrolling
   stops. Confirm becomes active.
4. Scroll back to the top. Confirm stays active.
5. Click Confirm. The script checks the signature.

If Confirm never becomes active at the bottom, the end-of-scroll test in
`Prompt._check_end` ([prompt.py](../../src/gui/screens/prompt.py)) does not match
the real page geometry. Add a temporary
`print(scrl.get_y(), scrl.get_height(), page.get_height())` there, rebuild, and
read the values in the terminal running the walkthrough.

### QR cases

The USB host only returns the signature. The address note is shown on the
result screen of the QR and SD hosts, so `--qr` uses the simulated scanner
(TCP 22849):

1. When the script says so, click **Scan QR code** in the simulator menu.
2. Press Enter in the terminal. The script sends the command as the scanned
   QR content.
3. Review the prompt, click Confirm, and read the note under the result QR.

The QR cases were not run while writing this document, because they need a
click on the main menu that the control socket cannot make.

## 4. Other screens

The gate covers what is on a `Prompt` page when `gate_confirm` runs. Plain
`Prompt` runs it at the end of `__init__`, after it has shortened the page to
end above the warning or the buttons. A subclass that fills its page later
must call `gate_confirm` again, or its gate opens at once. A subclass that
moves or resizes its page must keep it above the warning and the buttons.
These checks are not scripted. Start the simulator with `make simulate`
(mainnet, USB off) and check by hand:

| Screen                                                       | Expected                                                                                                  |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| Short prompts (e.g. "Overwrite?", "Encrypt the secret?")     | Confirm works at once                                                                                     |
| Prompts with a multi-line title ("File already exists", "Set device label") | The page is shorter and ends above the buttons; its text is not cut off                    |
| Wallet import with a key list taller than the page           | Confirm works only after scrolling to the end (`ConfirmWalletScreen` re-arms the gate)                    |
| Wallet import with a short key list                          | Confirm works at once                                                                                     |
| Mnemonic prompts (`MnemonicPrompt`)                          | Confirm works at once: the word table sits outside the page and is not gated                              |
| Device settings → Communication, developer settings          | Confirm still saves (these screens replace the Confirm callback, so the gate does not apply)              |
| Transaction signing                                          | Confirm works at once (the F-19 transaction gate is not done yet: `TransactionScreen` does not re-arm it) |

## Troubleshooting

| Symptom                                                                                    | Fix                                                                                                                  |
| ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| Behavior matches the old code                                                              | Rebuild: `nix develop -c make unix`                                                                                  |
| Script hangs at start-up                                                                   | The GUI was not ready in time. Raise `SIM_STARTUP_DELAY` (seconds, default 5), e.g. `SIM_STARTUP_DELAY=10 python3 …` |
| Simulator prints ports other than 8787/8789/22849, or the script talks to the wrong window | An earlier simulator still holds the ports: `pkill -f micropython_unix`                                              |
| Odd state from an earlier run                                                              | The script deletes `test/integration/fs` at start; delete it by hand if a run was killed                             |
