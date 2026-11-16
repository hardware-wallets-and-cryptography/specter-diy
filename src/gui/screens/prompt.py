import lvgl as lv
from .screen import Screen
from ..common import add_label, add_button_pair
from ..decorators import on_release, cb_with_args


FRAME_LINE = "_" * 34

# Tolerance in px when deciding that a page is scrolled to its end.
SCROLL_END_TOLERANCE = 4

PAGE_HEIGHT = 600
# Space in px kept between the page and the warning or the buttons below it.
PAGE_GAP = 10


class Prompt(Screen):
    def __init__(self, title="Are you sure?", message="Make a choice",
                 confirm_text="Confirm", cancel_text="Cancel", note=None, warning=None,
                 frame_title=None):
        super().__init__()
        self.title = add_label(title, scr=self, style="title")
        obj = self.title
        if note is not None:
            self.note = add_label(note, scr=self, style="hint")
            self.note.align(self.title, lv.ALIGN.OUT_BOTTOM_MID, 0, 5)
            obj = self.note
        self.page = lv.page(self)
        self.page.set_size(480, PAGE_HEIGHT)
        if frame_title is None:
            self.message = add_label(message, scr=self.page)
        else:
            # The frame is drawn by trusted labels in their own style, apart
            # from the message label, so untrusted message text cannot
            # imitate where the message starts or ends.
            self.frame_top = add_label(
                frame_title + "\n" + FRAME_LINE, scr=self.page, style="hint"
            )
            self.message = add_label(message, scr=self.page)
            self.message.align(self.frame_top, lv.ALIGN.OUT_BOTTOM_MID, 0, 0)
            self.frame_bottom = add_label(FRAME_LINE, scr=self.page, style="hint")
            self.frame_bottom.align(self.message, lv.ALIGN.OUT_BOTTOM_MID, 0, 0)
        # below the note if there is one, so the note does not cover the page
        self.page.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 0)
        # Initialize an empty icon label. It will display nothing until a symbol is set.
        self.icon = lv.label(self)
        self.icon.set_text("")

        (self.cancel_button, self.confirm_button) = add_button_pair(
            cancel_text,
            on_release(cb_with_args(self.set_value, False)),
            confirm_text,
            on_release(self._confirm),
            scr=self,
        )

        if warning:
            self.warning = add_label(warning, scr=self, style="warning")
            # Display warning symbol in the icon label 
            self.icon.set_text(lv.SYMBOL.WARNING)
            
            # Align warning text
            y_pos = self.cancel_button.get_y() - 60 # above the buttons
            x_pos = self.get_width() // 2 - self.warning.get_width() // 2 # in the center of the prompt
            self.warning.set_pos(x_pos, y_pos)
            
            # Align warning icon to the left of the title
            self.icon.align(self.title, lv.ALIGN.IN_LEFT_MID, 90, 0)

        # A long title or note pushes the page down. Shorten it so it ends
        # above the warning or the buttons; otherwise its last lines would sit
        # behind them or off screen while the gate below counts them as seen.
        bottom = self.warning.get_y() if warning else self.cancel_button.get_y()
        self.page.set_height(
            max(0, min(PAGE_HEIGHT, bottom - self.page.get_y() - PAGE_GAP))
        )

        # Confirm stays disabled until the message page has been scrolled
        # to its end (F-19). Content that fits enables it at once. Runs last,
        # once the page has its final content and size.
        self.gate_confirm(self.page)

    def gate_confirm(self, *pages):
        """Keep Confirm disabled until every page was scrolled to its end.

        Call once the page content is final. The latch does not reset when
        the user scrolls back up.
        """
        self._gated_pages = list(pages)
        self._seen_end = [False] * len(pages)
        for i, page in enumerate(pages):
            page.get_scrl().set_event_cb(
                lambda obj, event, i=i: self._on_scrl_event(i, event)
            )
        for i in range(len(pages)):
            self._check_end(i)

    def review_done(self):
        return all(getattr(self, "_seen_end", ()))

    def _confirm(self):
        # Second guard in case a disabled button still delivers RELEASED.
        if self.review_done():
            self.set_value(True)

    def _on_scrl_event(self, i, event):
        # This replaces the scrollable's default callback (scrl_def_event_cb
        # in lv_page.c), so keep forwarding the events it forwards.
        if event in (
            lv.EVENT.PRESSED, lv.EVENT.PRESSING, lv.EVENT.PRESS_LOST,
            lv.EVENT.RELEASED, lv.EVENT.SHORT_CLICKED, lv.EVENT.CLICKED,
            lv.EVENT.LONG_PRESSED, lv.EVENT.LONG_PRESSED_REPEAT,
            lv.EVENT.DRAG_BEGIN, lv.EVENT.DRAG_END, lv.EVENT.DRAG_THROW_BEGIN,
        ):
            lv.event_send(self._gated_pages[i], event, None)
        # DRAG_END arrives after a drag throw has come to rest.
        if event in (lv.EVENT.DRAG_END, lv.EVENT.RELEASED):
            self._check_end(i)

    def _check_end(self, i):
        page = self._gated_pages[i]
        scrl = page.get_scrl()
        if scrl.get_y() + scrl.get_height() <= page.get_height() + SCROLL_END_TOLERANCE:
            self._seen_end[i] = True
        self.confirm_button.set_state(
            lv.btn.STATE.REL if self.review_done() else lv.btn.STATE.INA
        )

