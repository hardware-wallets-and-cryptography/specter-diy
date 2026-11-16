import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import gui.common as common
import gui.decorators as decorators
import gui.screens.screen as screen_module
import lvgl as lv


SCREENS = Path(__file__).resolve().parents[2] / "src/gui/screens"


class _Scrollable:
    def __init__(self, page):
        self.page = page
        self.y = 0
        self.callback = None

    def get_y(self):
        return self.y

    def get_height(self):
        return max(
            [self.page.height]
            + [c.get_y() + c.get_height() for c in self.page.children]
        )

    def set_event_cb(self, callback):
        self.callback = callback


class _Widget:
    LONG = SimpleNamespace(BREAK=1)
    ALIGN = SimpleNamespace(CENTER=1, LEFT=2)

    def __init__(self, parent=None):
        self.parent = parent
        self.children = []
        if parent is not None:
            parent.children.append(self)
        self.x = self.y = 0
        self.width = 480
        self.height = 28
        self.text = ""
        self.state = False
        self.disabled = False
        self.callback = None
        self.style = SimpleNamespace(text=SimpleNamespace(font=None, color=None))
        self._scrl = None

    def get_scrl(self):
        if self._scrl is None:
            self._scrl = _Scrollable(self)
        return self._scrl

    def set_text(self, text):
        self.text = text
        self.height = 28 * sum(max(1, (len(line) + 39) // 40)
                               for line in text.split("\n"))

    def set_size(self, width, height):
        self.width, self.height = width, height

    def set_pos(self, x, y):
        self.x, self.y = x, y

    def set_x(self, x):
        self.x = x

    def set_y(self, y):
        self.y = y

    def set_width(self, width):
        self.width = width

    def set_height(self, height):
        self.height = height

    def set_recolor(self, _):
        pass

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def align(self, reference, alignment, x, y):
        self.x = reference.x + x
        self.y = reference.y + y
        if alignment in (lv.ALIGN.OUT_BOTTOM_MID, lv.ALIGN.OUT_BOTTOM_LEFT):
            self.y += reference.height

    def get_style(self, _):
        return self.style

    def set_style(self, _, style):
        self.style = style

    def set_event_cb(self, callback):
        self.callback = callback

    def set_long_mode(self, _):
        pass

    def set_align(self, _):
        pass

    def set_hidden(self, hidden):
        self.hidden = hidden

    def get_state(self):
        return self.state

    def on(self, _):
        self.state = True

    def set_state(self, state):
        self.disabled = state == lv.btn.STATE.INA

    def click(self):
        if not self.disabled:
            self.callback(self, lv.EVENT.RELEASED)


class _Screen(_Widget):
    def __init__(self):
        super().__init__()
        self.height = 800
        self._value = None

    def set_value(self, value):
        self._value = value


def _label(text, scr, **_):
    label = _Widget(scr)
    label.set_text(text)
    return label


def _buttons(_, cancel, __, confirm, scr):
    cancel_button = _Widget(scr)
    cancel_button.set_y(700)
    cancel_button.set_event_cb(cancel)
    confirm_button = _Widget(scr)
    confirm_button.set_y(700)
    confirm_button.set_event_cb(confirm)
    return cancel_button, confirm_button


def _load_screen(name):
    spec = importlib.util.spec_from_file_location(
        "gui.screens." + name, SCREENS / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


APPS = SCREENS.parents[1] / "apps"


def _load_wallet_screens(prompt_cls):
    """Load apps/wallets/screens.py against the stubbed Prompt.

    apps.wallets/__init__.py pulls in the whole wallet app, so stand in an
    empty package for it, and a gui.screens holding the stubbed Prompt.
    """
    saved = {k: sys.modules.get(k) for k in
             ("apps.wallets", "apps.wallets.commands", "apps.wallets.screens", "gui.screens")}
    package = type(sys)("apps.wallets")
    package.__path__ = [str(APPS / "wallets")]
    sys.modules["apps.wallets"] = package
    sys.modules["gui.screens"] = SimpleNamespace(
        Prompt=prompt_cls, QRAlert=object, Alert=object)
    try:
        spec = importlib.util.spec_from_file_location(
            "apps.wallets.screens", APPS / "wallets/screens.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class ConfirmationUiEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [
            patch.object(lv, "page", _Widget, create=True),
            patch.object(lv, "label", _Widget, create=True),
            patch.object(lv, "sw", _Widget, create=True),
            patch.object(lv, "btn", SimpleNamespace(
                STATE=SimpleNamespace(REL=0, INA=1)
            ), create=True),
            patch.object(lv, "ALIGN", SimpleNamespace(
                OUT_BOTTOM_MID=1, OUT_BOTTOM_LEFT=2, IN_TOP_MID=3,
                IN_TOP_LEFT=4, CENTER=5, IN_LEFT_MID=6,
            ), create=True),
            patch.object(lv, "ANIM", SimpleNamespace(OFF=0), create=True),
            patch.object(lv, "EVENT", SimpleNamespace(
                PRESSED=1, PRESSING=2, PRESS_LOST=3, RELEASED=4,
                SHORT_CLICKED=5, CLICKED=6, LONG_PRESSED=7,
                LONG_PRESSED_REPEAT=8, DRAG_BEGIN=9, DRAG_END=10,
                DRAG_THROW_BEGIN=11,
            ), create=True),
            patch.object(lv, "event_send", lambda obj, event, data=None: (
                obj.callback(obj, event) if getattr(obj, "callback", None) else None
            ), create=True),
            patch.object(lv, "style_t", lambda: SimpleNamespace(
                text=SimpleNamespace(font=None, color=None)), create=True),
            patch.object(lv, "style_copy", lambda dest, source: None, create=True),
            patch.object(lv, "font_roboto_mono_28", object(), create=True),
            patch.object(lv, "font_roboto_mono_22", object(), create=True),
            patch.object(lv, "font_roboto_22", object(), create=True),
            patch.object(lv, "color_hex", lambda value: value, create=True),
            patch.object(common, "add_label", _label),
            patch.object(common, "add_button_pair", _buttons),
            patch.object(common, "format_addr", lambda address, **_: address),
            patch.object(decorators, "on_release", lambda callback: (
                lambda _widget, _event: callback()
            )),
            patch.object(decorators, "cb_with_args", lambda callback, value: (
                lambda: callback(value)
            ), create=True),
            patch.object(screen_module, "Screen", _Screen),
        ]
        for item in cls.patches:
            item.start()
            cls.addClassCleanup(item.stop)
        original_prompt = sys.modules.get("gui.screens.prompt")
        cls.addClassCleanup(
            lambda: (sys.modules.pop("gui.screens.prompt", None)
                     if original_prompt is None
                     else sys.modules.__setitem__("gui.screens.prompt", original_prompt))
        )
        cls.prompt = _load_screen("prompt").Prompt
        cls.transaction = _load_screen("transaction").TransactionScreen
        cls.addClassCleanup(sys.modules.pop, "gui.screens.transaction", None)
        cls.confirm_wallet = _load_wallet_screens(cls.prompt).ConfirmWalletScreen

    def test_long_prompt_cannot_be_approved_before_review(self):
        screen = self.prompt("Review message", "\n".join(["Security text"] * 40))
        self.assertGreater(screen.message.get_height(), screen.page.get_height())
        screen.confirm_button.click()
        self.assertIsNone(
            screen._value,
            "F-19 (audit.md): Confirm accepted while security-critical text was below the viewport",
        )

    def test_short_prompt_can_be_approved_at_once(self):
        screen = self.prompt("Review message", "Security text")
        screen.confirm_button.click()
        self.assertIs(screen._value, True, "gate blocked a prompt that fits")

    def test_long_prompt_can_be_approved_after_scrolling_to_end(self):
        screen = self.prompt("Review message", "\n".join(["Security text"] * 40))
        scrl = screen.page.get_scrl()
        # Scroll part way: still gated.
        scrl.y = -100
        scrl.callback(scrl, lv.EVENT.DRAG_END)
        screen.confirm_button.click()
        self.assertIsNone(screen._value)
        # Scroll to the end: Confirm opens and stays open after scrolling back.
        scrl.y = screen.page.get_height() - scrl.get_height()
        scrl.callback(scrl, lv.EVENT.DRAG_END)
        scrl.y = 0
        scrl.callback(scrl, lv.EVENT.DRAG_END)
        screen.confirm_button.click()
        self.assertIs(screen._value, True, "gate never opened after full scroll")

    def _wallet(self, n_keys):
        key = "[73c5da0a/48h/1h/0h/2h]tpub" + "D" * 107
        keys = [dict(canonical=key, slip132=key, mine=i == 0,
                     is_nums=False, is_private=False) for i in range(n_keys)]
        return self.confirm_wallet("multisig", "Multisig 2 of %d" % n_keys, keys)

    def test_long_wallet_key_list_cannot_be_approved_before_review(self):
        # ConfirmWalletScreen fills its page after Prompt.__init__, so the
        # gate must be re-armed once the key list is in place.
        screen = self._wallet(6)
        scrl = screen.page.get_scrl()
        self.assertGreater(scrl.get_height(), screen.page.get_height(), "keys fit; test is void")
        screen.confirm_button.click()
        self.assertIsNone(
            screen._value, "F-19 (audit.md): wallet keys below the viewport could be approved unseen")
        scrl.y = screen.page.get_height() - scrl.get_height()
        scrl.callback(scrl, lv.EVENT.DRAG_END)
        screen.confirm_button.click()
        self.assertIs(screen._value, True, "gate never opened after full scroll")

    def test_short_wallet_key_list_can_be_approved_at_once(self):
        screen = self._wallet(1)
        screen.confirm_button.click()
        self.assertIs(screen._value, True, "gate blocked a key list that fits")

    def _transaction(self, outputs):
        return self.transaction("Confirm transaction", {
            "inputs": [{"value": 100_000, "sequence": 0xFFFFFFFF}],
            "outputs": outputs,
            "fee": 1_000,
            "tx_version": 2,
            "locktime": 0,
        })

    def test_fee_below_output_list_cannot_be_approved_without_review(self):
        outputs = [{"value": 10_000, "change": False, "address": "bc1recipient"}
                   for _ in range(10)]
        screen = self._transaction(outputs)
        fees = [child for child in screen.page.children + screen.children
                if child.text.startswith("Fee:")]
        self.assertEqual(len(fees), 1)
        fee = fees[0]
        if fee.parent is screen.page and (
            fee.get_y() > screen.page.get_y() + screen.page.get_height()
        ):
            screen.confirm_button.click()
            self.assertIsNone(
                screen._value, "F-19 (audit.md): hidden fee could be approved without scrolling"
            )
        else:
            self.assertLessEqual(
                fee.get_y() + fee.get_height(), screen.confirm_button.get_y(),
                "F-19 (audit.md): fee must be visible above Confirm if approval is immediate",
            )

    def test_default_page_reports_omitted_verified_change(self):
        screen = self._transaction([
            {"value": 19_000, "change": True, "address": "bc1change"},
            {"value": 80_000, "change": False, "address": "bc1recipient"},
        ])
        self.assertTrue(any("bc1change" in label.text
                            for label in screen.page2.children))
        default_text = " ".join(label.text for label in screen.page.children)
        self.assertTrue(
            "bc1change" in default_text or
            ("change" in default_text.lower() and "1" in default_text),
            "F-24 (audit.md): default confirmation silently omitted one verified change output",
        )

    def test_page_ends_above_warning_and_buttons(self):
        # A long title, a note and a warning push the page down. It must end
        # above the warning and the buttons, or the gate opens while its last
        # lines are hidden behind them.
        message = "\n".join(["Security text"] * 40)
        title = "\n".join(["Long title"] * 6)
        note = "Derivation path: m/84h/1h/0h/0/0"
        warning = "Non-standard derivation path!\nCheck it before signing."
        for kwargs in ({}, {"note": note}, {"warning": warning},
                       {"note": note, "warning": warning}):
            with self.subTest(**{k: True for k in kwargs}):
                screen = self.prompt(title, message, **kwargs)
                page = screen.page
                page_bottom = page.get_y() + page.get_height()
                self.assertLessEqual(page_bottom, screen.confirm_button.get_y(),
                                     "F-19 (audit.md): page end hidden behind the buttons")
                if "warning" in kwargs:
                    self.assertLessEqual(page_bottom, screen.warning.get_y(),
                                         "F-19 (audit.md): page end hidden behind the warning")
                if "note" in kwargs:
                    self.assertGreaterEqual(
                        page.get_y(), screen.note.get_y() + screen.note.get_height(),
                        "note covers the top of the page")
                # The gate still works on the shortened page.
                screen.confirm_button.click()
                self.assertIsNone(screen._value)
                scrl = page.get_scrl()
                scrl.y = page.get_height() - scrl.get_height()
                scrl.callback(scrl, lv.EVENT.DRAG_END)
                screen.confirm_button.click()
                self.assertIs(screen._value, True, "gate never opened after full scroll")
