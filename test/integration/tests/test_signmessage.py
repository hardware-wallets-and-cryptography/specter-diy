"""F-21 (audit.md): message signing end to end on the MicroPython simulator.

SignMessageTest approves through the GUI control socket's JSON values, which
call Prompt.set_value() directly and bypass the Confirm button.
SignMessageGateTest uses the simulator's widget commands (press_confirm,
scroll_end, ... in TCPGUI.widget_command) to go through the button and the
scroll gate. What the screen looks like is a manual check: see
F_21_walkthrough.py.
"""
from unittest import TestCase

from util.controller import sim
from util.signmessage import DEEP_PATH, LONG_MESSAGE, command, check_signature


class SignMessageTest(TestCase):
    def sign(self, path, message, confirm=True):
        return sim.query(command(path, message), [confirm])

    def assertSigned(self, path, message):
        res = self.sign(path, message)
        self.assertIsNone(check_signature(res, path, message), res)

    def test_printable_message_signs_full_digest(self):
        for path in ("m/44h/1h/0h/0/0", "m/49h/1h/0h/0/0", "m/84h/1h/0h/0/0"):
            with self.subTest(path=path):
                self.assertSigned(path, b"Pay Alice 1 BTC\nnonce 42")

    def test_forged_frame_message_still_signs(self):
        self.assertSigned("m/84h/1h/0h/0/0", b"Pay Alice\n" + b"_" * 34 + b"\nPay Mallory")

    def test_nul_message_signs_every_byte(self):
        # The display shows a hex dump; the signature must cover the tail too.
        self.assertSigned("m/84h/1h/0h/0/0", b"I authorise nothing.\x00<hidden tail>")

    def test_non_standard_paths_still_sign(self):
        for path in ("m/86h/1h/0h/0/0", "m/48h/1h/0h/2h/0/0"):
            with self.subTest(path=path):
                self.assertSigned(path, b"hello")

    def test_message_at_length_cap_signs(self):
        self.assertSigned("m/84h/1h/0h/0/0", b"a" * 512)

    def test_message_over_length_cap_is_rejected(self):
        res = sim.query(command("m/84h/1h/0h/0/0", b"a" * 513))
        self.assertTrue(res.startswith(b"error:"), res)
        self.assertIn(b"too long", res)

    def test_path_over_depth_cap_is_rejected(self):
        res = sim.query(command("m" + "/0" * 11, b"hello"))
        self.assertTrue(res.startswith(b"error:"), res)
        self.assertIn(b"too deep", res)

    def test_cancel(self):
        res = self.sign("m/84h/1h/0h/0/0", b"hello", confirm=False)
        self.assertEqual(res, b"error: User cancelled")


class SignMessageGateTest(TestCase):
    """Confirm on the signing prompt only works once the message was
    scrolled to its end (F-19 action plan item 2, F-21 item 5)."""

    path = "m/84h/1h/0h/0/0"

    def setUp(self):
        sim.gui.drain()
        sim.usb.drain()

    def open_prompt(self, message, path=None):
        sim.usb.s.sendall(command(path or self.path, message) + b"\r\n")
        self.assertIn(b"ACK", sim.usb.readline(eol=b"ACK\r\n"))
        self.assertIsNotNone(sim.gui.wait_screen("Prompt"), "signing prompt never opened")
        # if a check fails, do not leave the prompt open for the next test
        self.addCleanup(self._close_prompt)

    def _close_prompt(self):
        if (self.widget("state").get("screen") == "Prompt"
                and sim.usb.readline(timeout=0.3) == b""):
            sim.gui.s.send(b"false\r\n")
            sim.usb.readline(timeout=2)

    def widget(self, cmd):
        line = sim.gui.command(cmd)
        self.assertIsNotNone(line, "no reply to %r" % cmd)
        self.assertTrue(line.startswith(b"state "), line)
        words = line.decode().split()
        state = dict(w.split("=", 1) for w in words[2:])
        state["screen"] = words[1]
        return state

    def assertNoReply(self):
        self.assertEqual(sim.usb.readline(timeout=1), b"", "prompt was approved")

    def assertSigned(self, message, path=None):
        res = sim.usb.readline(timeout=5).strip()
        self.assertIsNone(check_signature(res, path or self.path, message), res)

    def test_short_message_confirms_at_once(self):
        self.open_prompt(b"hello")
        state = self.widget("state")
        self.assertEqual((state["confirm"], state["reviewed"]), ("REL", "1"), state)
        self.widget("press_confirm")
        self.assertSigned(b"hello")

    def test_long_message_needs_scroll_to_end(self):
        self.open_prompt(LONG_MESSAGE)
        state = self.widget("state")
        self.assertGreater(int(state["h"]), int(state["page"]), "message fits; test is void")
        self.assertEqual((state["confirm"], state["reviewed"]), ("INA", "0"), state)

        # pressing before review is ignored, even though the event is delivered
        self.widget("press_confirm")
        self.assertNoReply()

        state = self.widget("scroll_by 100")
        self.assertEqual(state["confirm"], "INA", state)
        self.widget("press_confirm")
        self.assertNoReply()

        state = self.widget("scroll_end")
        self.assertEqual((state["confirm"], state["reviewed"]), ("REL", "1"), state)

        # latched: scrolling back up keeps Confirm enabled
        state = self.widget("scroll_top")
        self.assertEqual(state["confirm"], "REL", state)

        self.widget("press_confirm")
        self.assertSigned(LONG_MESSAGE)

    def test_long_message_can_be_cancelled_without_scrolling(self):
        self.open_prompt(LONG_MESSAGE)
        self.widget("press_cancel")
        self.assertEqual(sim.usb.readline(timeout=5).strip(), b"error: User cancelled")

    def test_page_ends_above_warning_and_buttons(self):
        # Deepest accepted path plus a long message: the warning is shown and
        # the path note is long. If the page ran under the warning or the
        # buttons, the gate would open with the last lines hidden.
        self.open_prompt(LONG_MESSAGE, DEEP_PATH)
        state = self.widget("state")
        self.assertIn("warn_y", state, "no warning for a non-standard path")
        page_bottom = int(state["page_y"]) + int(state["page"])
        self.assertLessEqual(page_bottom, int(state["warn_y"]), state)
        self.assertLessEqual(page_bottom, int(state["btn_y"]), state)

        self.assertGreater(int(state["h"]), int(state["page"]), "message fits; test is void")
        self.assertEqual(state["confirm"], "INA", state)
        state = self.widget("scroll_end")
        self.assertEqual(state["confirm"], "REL", state)
        self.widget("press_confirm")
        self.assertSigned(LONG_MESSAGE, DEEP_PATH)
