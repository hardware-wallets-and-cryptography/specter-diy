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


class ConfirmationUiEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patches = [
            patch.object(lv, "page", _Widget, create=True),
            patch.object(lv, "label", _Widget, create=True),
            patch.object(lv, "sw", _Widget, create=True),
            patch.object(lv, "btn", SimpleNamespace(STATE=SimpleNamespace(INA=1)),
                         create=True),
            patch.object(lv, "ALIGN", SimpleNamespace(
                OUT_BOTTOM_MID=1, OUT_BOTTOM_LEFT=2, IN_TOP_MID=3,
                IN_TOP_LEFT=4, CENTER=5, IN_LEFT_MID=6,
            ), create=True),
            patch.object(lv, "ANIM", SimpleNamespace(OFF=0), create=True),
            patch.object(lv, "EVENT", SimpleNamespace(RELEASED=1), create=True),
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

    def test_long_prompt_cannot_be_approved_before_review(self):
        screen = self.prompt("Review message", "\n".join(["Security text"] * 40))
        self.assertGreater(screen.message.get_height(), screen.page.get_height())
        screen.confirm_button.click()
        self.assertIsNone(
            screen._value,
            "F-19: Confirm accepted while security-critical text was below the viewport",
        )

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
                screen._value, "F-19: hidden fee could be approved without scrolling"
            )
        else:
            self.assertLessEqual(
                fee.get_y() + fee.get_height(), screen.confirm_button.get_y(),
                "F-19: fee must be visible above Confirm if approval is immediate",
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
            "F-24: default confirmation silently omitted one verified change output",
        )
