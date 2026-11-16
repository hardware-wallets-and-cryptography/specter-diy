#!/usr/bin/env python3
"""Interactive F-21 walkthrough on the simulator.

Starts the simulator (regtest, USB on), unlocks it with the test mnemonic,
then for each case sends a `signmessage` command and asks you to check the
simulator window. Signatures and error replies are checked automatically.

Run from anywhere (needs bin/micropython_unix built from the current tree):

    python3 test/integration/F_21_walkthrough.py            # all USB cases
    python3 test/integration/F_21_walkthrough.py --qr       # plus QR cases
    python3 test/integration/F_21_walkthrough.py --only scroll-gate,nul-byte
    python3 test/integration/F_21_walkthrough.py --list
"""
import argparse
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # the controller uses paths relative to test/integration
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str((ROOT / "../../f469-disco/libs/common/embit/src").resolve()))

from util.controller import sim  # noqa: E402
from util.signmessage import (  # noqa: E402
    DEEP_PATH, LONG_MESSAGE, check_signature, command, expected_address)

LONG = LONG_MESSAGE
FRAME_LOOK = [
    'Title "Sign message?"; under it "Derivation path: <path>" in small grey text.',
    'Above the message: "Message:" and a line of underscores in SMALL GREY text.',
    "Below the message: another small grey underscore line.",
]
NO_WARNING = "No orange warning above the buttons."
WARNING = ('Orange "Non-standard derivation path! Check it before signing." with a '
           "warning icon. It does not cover the message text or the buttons.")

CASES = [
    dict(id="short", path="m/84h/1h/0h/0/0", message=b"hello",
         look=FRAME_LOOK + ['"hello" in the normal (larger, white) font.', NO_WARNING,
                           "Confirm is active at once (not dimmed)."],
         action="Click Confirm.", expect="sig"),
    dict(id="forged-frame", path="m/84h/1h/0h/0/0",
         message=b"Pay Alice\n" + b"_" * 34 + b"\nPay Mallory",
         look=FRAME_LOOK + [
             "The underscore line between 'Pay Alice' and 'Pay Mallory' is in the "
             "LARGE WHITE message font, not the small grey frame style.",
             "So it is clear that 'Pay Mallory' is still inside the message."],
         action="Click Confirm.", expect="sig"),
    dict(id="nul-byte", path="m/84h/1h/0h/0/0",
         message=b"I authorise nothing.\x00<hidden attacker text>",
         look=['Header reads "Hex message:" (small grey), not "Message:".',
               "Body is a hex dump; the words 'hidden attacker text' do not appear as text."],
         action="Click Confirm.", expect="sig"),
    dict(id="scroll-gate", path="m/84h/1h/0h/0/0", message=LONG,
         steps=["a) Click Confirm right away: nothing happens (button dimmed).",
                "b) Drag the text up part way and release: Confirm still does nothing.",
                "c) Drag or flick to the bottom until 'line 39' is visible and the "
                "scrolling stops: Confirm becomes active.",
                "d) Scroll back to the top: Confirm stays active.",
                "e) Click Confirm."],
         look=["Step a: Confirm did nothing.", "Step b: Confirm still did nothing.",
               "Step c: Confirm became active at the bottom.",
               "Step d: Confirm stayed active after scrolling up."],
         action="Do steps a-e above.", expect="sig"),
    dict(id="cancel-long", path="m/84h/1h/0h/0/0", message=LONG,
         look=["Cancel worked without scrolling."],
         action="Click Cancel without scrolling.", expect="cancel"),
    dict(id="taproot-warning", path="m/86h/1h/0h/0/0", message=b"hello",
         look=[WARNING], action="Click Confirm.", expect="sig"),
    dict(id="deep-path-long", path=DEEP_PATH, message=LONG,
         steps=["a) Drag or flick to the bottom until the scrolling stops.",
                "b) Click Confirm."],
         look=['Title "Sign message?"; the whole 10-level path in small grey '
               "text under it, nothing cut off or covered.",
               WARNING,
               "At the bottom, 'line 39' and the grey line under it are fully "
               "visible ABOVE the warning; no text overlaps the warning.",
               "Confirm became active only at the bottom."],
         action="Do steps a-b above.", expect="sig"),
    dict(id="wrong-coin-warning", path="m/84h/0h/0h/0/0", message=b"hello",
         look=[WARNING + " (coin type 0h is mainnet; the simulator is on regtest)"],
         action="Click Cancel.", expect="cancel"),
    dict(id="standard-no-warning", path="m/44h/1h/0h/0/0", message=b"hello",
         look=FRAME_LOOK + [NO_WARNING], action="Click Confirm.", expect="sig"),
    dict(id="too-deep", path="m" + "/0" * 11, message=b"hello",
         look=["No signing prompt appeared."], action="Nothing to click.",
         expect="error:too deep"),
    dict(id="too-long", path="m/84h/1h/0h/0/0", message=b"a" * 513,
         look=["No signing prompt appeared."], action="Nothing to click.",
         expect="error:too long"),
    # The USB host only returns the signature; the address note is shown on
    # the result screen of the QR (or SD) host.
    dict(id="qr-address", via="qr", path="m/84h/1h/0h/0/0", message=b"hello",
         look=["Result screen 'Message signature:' shows "
               "'Address: %s'." % expected_address("m/84h/1h/0h/0/0")],
         action="Click Confirm, then read the note under the result QR.", expect=None),
    dict(id="qr-taproot-address", via="qr", path="m/86h/1h/0h/0/0", message=b"hello",
         look=[WARNING, "Result screen shows 'Address: not shown for this path'."],
         action="Click Confirm, then read the note under the result QR.", expect=None),
]


def ask(question):
    while True:
        a = input("  %s [y/n/s=skip] " % question).strip().lower()
        if a in ("y", "n", "s"):
            return {"y": "PASS", "n": "FAIL", "s": "SKIP"}[a]


def check_reply(case, reply):
    expect = case["expect"]
    if expect == "sig":
        err = check_signature(reply, case["path"], case["message"])
        return ("PASS", "valid signature over all %d bytes" % len(case["message"])) \
            if err is None else ("FAIL", err)
    if expect == "cancel":
        ok = reply == b"error: User cancelled"
        return ("PASS" if ok else "FAIL", reply.decode(errors="replace"))
    if expect.startswith("error:"):
        ok = reply.startswith(b"error:") and expect[6:].encode() in reply
        return ("PASS" if ok else "FAIL", reply.decode(errors="replace"))
    return ("SKIP", "")


def usb_roundtrip(data):
    """Send a host command; return the reply line after ACK (waits for you)."""
    sim.usb.s.sendall(data + b"\r\n")
    buf = sim.usb.readline(eol=b"ACK\r\n", timeout=5)
    if b"ACK\r\n" not in buf:
        return None
    rest = buf.split(b"ACK\r\n", 1)[1]
    if b"\r\n" not in rest:
        print("  ... waiting for you in the simulator window (up to 5 min)")
        rest += sim.usb.readline(timeout=300)
    return rest.strip()


def qr_send(data):
    q = socket.create_connection(("127.0.0.1", 22849))
    q.sendall(data + b"\r\n")
    q.close()


def run_case(case):
    print("\n" + "=" * 72)
    print("CASE %s   path %s   via %s" % (case["id"], case["path"], case.get("via", "usb")))
    print("  message: %r" % (case["message"][:60] + (b"..." if len(case["message"]) > 60 else b"")))
    for s in case.get("steps", []):
        print("  " + s)
    print("  Expect on screen:")
    for item in case["look"]:
        print("   - " + item)
    print("  Then: " + case["action"])
    results = []
    if case.get("via") == "qr":
        input("  In the simulator, tap 'Scan QR code', then press Enter here...")
        msg = case["message"].decode()
        qr_send(b"signmessage %s ascii:%s" % (case["path"].encode(), msg.encode()))
        input("  Do the action in the window, then press Enter here...")
    else:
        input("  Press Enter to send the command...")
        reply = usb_roundtrip(command(case["path"], case["message"]))
        if reply is None:
            results.append(("auto", "FAIL", "no ACK from the simulator"))
        else:
            verdict, detail = check_reply(case, reply)
            print("  auto check: %s %s" % (verdict, detail))
            results.append(("auto", verdict, detail))
    for item in case["look"]:
        results.append(("screen", ask(item), item))
    return results


def run_auto():
    # Load the module file directly: importing the `tests` package would pull
    # in test_with_rpc, which needs a running Bitcoin Core at import time.
    import importlib.util
    import unittest
    spec = importlib.util.spec_from_file_location(
        "test_signmessage", ROOT / "tests/test_signmessage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sim.start()
    try:
        sim.load()
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(mod))
    finally:
        sim.shutdown()
    return 0 if result.wasSuccessful() else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="comma-separated case ids")
    p.add_argument("--qr", action="store_true", help="also run the QR address cases")
    p.add_argument("--list", action="store_true", help="list cases and exit")
    p.add_argument("--auto", action="store_true",
                   help="run only the automated tests in tests/test_signmessage.py "
                        "(no Bitcoin Core needed, no clicking) and exit")
    args = p.parse_args()

    if args.auto:
        return run_auto()

    cases = [c for c in CASES if args.qr or c.get("via") != "qr"]
    if args.only:
        wanted = args.only.split(",")
        cases = [c for c in CASES if c["id"] in wanted]
    if args.list:
        for c in CASES:
            print("%-22s %-4s %s" % (c["id"], c.get("via", "usb"), c["path"]))
        return 0

    print("Starting the simulator; a window will open. Keep it visible.")
    sim.start()
    summary = []
    try:
        sim.load()
        print("Unlocked with the test mnemonic (fingerprint 73c5da0a), regtest.")
        for case in cases:
            for kind, verdict, detail in run_case(case):
                summary.append((case["id"], kind, verdict, detail))
        input("\nAll cases done. Press Enter to close the simulator...")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        sim.shutdown()

    print("\n%-22s %-7s %-5s %s" % ("case", "check", "result", "detail"))
    for row in summary:
        print("%-22s %-7s %-5s %s" % (row[0], row[1], row[2], row[3][:70]))
    failed = [r for r in summary if r[2] == "FAIL"]
    print("\n%d checks, %d failed" % (len(summary), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
