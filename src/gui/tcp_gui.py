from .specter import SpecterGUI
import pyb
import json
import lvgl as lv
import asyncio
import sys

class TCPGUI(SpecterGUI):
    """
    Simulated GUI for testing.
    User interaction can be provided over telnet on port 8787
    """
    def __init__(self, *args, **kwargs):
        self.tcp = pyb.UART('"S') # will be on port 8787
        super().__init__(*args, **kwargs)

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        asyncio.create_task(self.tcp_loop())

    async def tcp_loop(self):
        res = b""
        while True:
            await asyncio.sleep_ms(30)
            try:
                # trying to read something
                chunk = self.tcp.read(100)
                # if we didn't get anything - return
                if chunk is None:
                    continue
                res += chunk
                if b"\r" in res or b"\n" in res:
                    arr = res.replace(b"\r",b"\n").split(b"\n")
                    cmd = arr[0].decode()
                    if cmd == "quit":
                        print("QUIT!")
                        sys.exit(1)
                    res = b""
                    reply = self.widget_command(cmd)
                    if reply is not None:
                        self.tcp.write(reply.encode() + b"\r\n")
                        continue
                    val = json.loads("[%s]" % cmd)[0]
                    if self.scr is not None:
                        self.scr.set_value(val)
            except Exception as e:
                print(e)
                res = b""

    def widget_command(self, cmd):
        """Act through the screen's widgets instead of set_value(), so tests
        reach the Confirm button and its scroll gate (F-19 / F-21).

        Unquoted words, so they never collide with JSON values:
          state          - report the screen state
          press_confirm  - send RELEASED to the Confirm button
          press_cancel   - send RELEASED to the Cancel button
          scroll_end     - scroll the message page to its end
          scroll_top     - scroll the message page to its top
          scroll_by <px> - scroll the message page down by <px>
        Every command replies with one "state ..." line; anything else
        returns None and is handled as a JSON value.
        """
        scr = self.scr
        if cmd in ("press_confirm", "press_cancel"):
            btn = getattr(scr, cmd[6:] + "_button", None)
            if btn is None:
                return "error: screen has no %s button" % cmd[6:]
            # Delivered even when the button is disabled (STATE.INA), so the
            # screen's own guard is what gets tested.
            lv.event_send(btn, lv.EVENT.RELEASED, None)
        elif cmd in ("scroll_end", "scroll_top") or cmd.startswith("scroll_by "):
            page = getattr(scr, "page", None)
            if page is None:
                return "error: screen has no page"
            scrl = page.get_scrl()
            if cmd == "scroll_end":
                y = min(0, page.get_height() - scrl.get_height())
            elif cmd == "scroll_top":
                y = 0
            else:
                y = scrl.get_y() - int(cmd.split()[1])
            scrl.set_y(y)
            # what a real drag sends once the content has come to rest
            lv.event_send(scrl, lv.EVENT.DRAG_END, None)
        elif cmd != "state":
            return None
        return self.widget_state(scr)

    def widget_state(self, scr):
        """y/h: scrollable offset and height; page/page_y: page height and
        top; warn_y/btn_y: top of the Prompt warning and Confirm button, so
        tests can check that the page ends above them."""
        parts = ["state", type(scr).__name__]
        btn = getattr(scr, "confirm_button", None)
        if btn is not None:
            ina = btn.get_state() == lv.btn.STATE.INA
            parts.append("confirm=%s" % ("INA" if ina else "REL"))
        if hasattr(scr, "review_done"):
            parts.append("reviewed=%d" % scr.review_done())
        page = getattr(scr, "page", None)
        if page is not None:
            scrl = page.get_scrl()
            parts.append("y=%d h=%d page=%d page_y=%d" % (
                scrl.get_y(), scrl.get_height(), page.get_height(), page.get_y()))
        warning = getattr(scr, "warning", None)
        if warning is not None:
            parts.append("warn_y=%d" % warning.get_y())
        if btn is not None:
            parts.append("btn_y=%d" % btn.get_y())
        return " ".join(parts)

    async def open_popup(self, scr):
        try:
            self.tcp.write(b"%s\r\n" % type(scr).__name__)
        except:
            pass
        return await super().open_popup(scr)


    async def load_screen(self, scr):
        try:
            self.tcp.write(b"%s\r\n" % type(scr).__name__)
        except:
            pass
        return await super().load_screen(scr)
