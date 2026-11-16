import lvgl as lv
from helpers import conv_time
from .prompt import Prompt
from ..common import add_label, format_addr
from ..decorators import on_release

class TransactionScreen(Prompt):
    def __init__(self, title, meta):
        self.default_asset = meta.get("default_asset", "BTC")
        send_amount = sum(
            [out["value"] for out in meta["outputs"] if not out["change"]]
        )
        super().__init__(title, "")

        obj = self.message # for alignments

        enable_inputs = len([k for k in meta["inputs"] if k.get("sighash", "")]) > 0
        # if there is at least one unknown value (liquid)
        enable_inputs = enable_inputs or (-1 in [out["value"] for out in meta["outputs"]])
        enable_inputs = enable_inputs or meta.get("issuance", False) or meta.get("reissuance", False)

        lbl = add_label("Show detailed information                      ", scr=self)
        lbl.align(obj, lv.ALIGN.CENTER, 0, 0)
        self.details_sw = lv.sw(self)
        self.details_sw.align(obj, lv.ALIGN.CENTER, 130, 0)
        self.details_sw.set_event_cb(on_release(self.toggle_details))
        if enable_inputs:
            self.details_sw.on(lv.ANIM.OFF)

        # change page a bit
        self.page.set_pos(0, lbl.get_y()+20)
        self.page.set_size(480, 800-130-lbl.get_y())

        self.page2 = lv.page(self)
        self.page2.set_pos(self.page.get_x(), self.page.get_y())
        self.page2.set_size(self.page.get_width(), self.page.get_height())

        # define styles
        style = lv.style_t()
        lv.style_copy(style, self.message.get_style(0))
        style.text.font = lv.font_roboto_mono_28

        style_primary = lv.style_t()
        lv.style_copy(style_primary, self.message.get_style(0))
        style_primary.text.font = lv.font_roboto_mono_22

        style_secondary = lv.style_t()
        lv.style_copy(style_secondary, self.message.get_style(0))
        style_secondary.text.color = lv.color_hex(0x999999)
        style_secondary.text.font = lv.font_roboto_mono_22

        style_warning = lv.style_t()
        lv.style_copy(style_warning, self.message.get_style(0))
        style_warning.text.color = lv.color_hex(0xFF9A00)
        style_warning.text.font = lv.font_roboto_22

        style_gray = lv.style_t()
        lv.style_copy(style_gray, self.message.get_style(0))
        style_gray.text.color = lv.color_hex(0x999999)
        style_gray.text.font = lv.font_roboto_22

        self.style = style
        self.style_secondary = style_secondary
        self.style_warning = style_warning
        self.style_gray = style_gray

        warning_text = None
        if "warnings" in meta and len(meta["warnings"]) > 0:
            warning_text = "WARNING!\n" + "\n".join(meta["warnings"])
            # Not self.warning: Prompt keeps that name for the warning above
            # the buttons, and this label sits inside the page.
            obj = self.add_warning(self.page, warning_text)

        hidden_change = 0
        for out in meta["outputs"]:
            # Verified change needs no confirmation - the device proved it
            # can't be an attacker-controlled destination. It stays visible
            # on the details page. A warning overrides this: it means the
            # output needs the user's attention.
            if out["change"] and not out.get("warnings"):
                hidden_change += 1
                continue
            obj = self.show_output(out, obj)

        # Say that outputs were left out, so a hidden one is never a surprise (F-24).
        if hidden_change:
            lbl = add_label(
                "%d verified change %s not shown"
                % (hidden_change, "output" if hidden_change == 1 else "outputs"),
                scr=self.page,
            )
            lbl.set_style(0, style_gray)
            lbl.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)
            obj = lbl

        fee = meta.get("fee")
        if fee:
            if send_amount > 0:
                fee_percent = fee * 100 / send_amount
                fee_txt = "%d satoshi (%.2f%%)" % (fee, fee_percent)
            # back to wallet
            else:
                fee_txt = "%d satoshi" % (fee,)
            fee = add_label("Fee: " + fee_txt, scr=self.page)
            fee.set_style(0, style)
            fee.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)

            obj = fee

        page2_warning = None
        if warning_text:
            page2_warning = self.add_warning(self.page2, warning_text)

        meta_inputs_len = len(meta["inputs"])
        lbl = add_label("%d %s" % (meta_inputs_len, "INPUT" if meta_inputs_len == 1 else "INPUTS"), scr=self.page2)
        if page2_warning:
            lbl.align(page2_warning, lv.ALIGN.OUT_BOTTOM_MID, 0, 20)
        else:
            lbl.align(self.page2, lv.ALIGN.IN_TOP_MID, 0, 30)
        obj = lbl
        for i, inp in enumerate(meta["inputs"]):
            idxlbl = lv.label(self.page2)
            idxlbl.set_text("%d:" % i)
            idxlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)
            idxlbl.set_x(30)
            lbl = lv.label(self.page2)
            lbl.set_long_mode(lv.label.LONG.BREAK)
            lbl.set_width(380)
            valuetxt = "???" if inp["value"] == -1 else "%.8f" % (inp["value"]/1e8)
            lbl.set_text("%s %s from %s" % (valuetxt, inp.get("asset", self.default_asset), inp.get("label", "Unknown wallet")))
            lbl.align(idxlbl, lv.ALIGN.IN_TOP_LEFT, 0, 0)
            lbl.set_x(60)

            # https://learnmeabitcoin.com/technical/transaction/input/sequence
            sequence = inp.get("sequence")
            if sequence is not None:
                seq_text, is_relative_locktime = self.sequence_to_text(
                    sequence, meta["tx_version"]
                )
                seqlbl = lv.label(self.page2)
                seqlbl.set_long_mode(lv.label.LONG.BREAK)
                seqlbl.set_width(380)
                seqlbl.set_text("Seq: 0x%08X (%s)" % (sequence, seq_text))
                seqlbl.set_style(0, style_gray)
                seqlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
                seqlbl.set_x(60)
                lbl = seqlbl
                if is_relative_locktime:
                    rltlbl = lv.label(self.page2)
                    rltlbl.set_style(0, style_gray)
                    rltlbl.set_text(self.relative_locktime_to_text(sequence))
                    rltlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 15, 5)
                    lbl = rltlbl
            if inp.get("sighash", ""):
                shlbl = lv.label(self.page2)
                shlbl.set_long_mode(lv.label.LONG.BREAK)
                shlbl.set_width(380)
                shlbl.set_text(inp.get("sighash", ""))
                shlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
                shlbl.set_x(60)
                shlbl.set_style(0, style_warning)
                lbl = shlbl
            if inp.get("warning", ""):
                inwlbl = lv.label(self.page2)
                inwlbl.set_long_mode(lv.label.LONG.BREAK)
                inwlbl.set_width(380)
                inwlbl.set_text(inp["warning"])
                inwlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
                inwlbl.set_x(60)
                inwlbl.set_style(0, style_warning)
                lbl = inwlbl
            obj = lbl

        meta_outputs_len = len(meta["outputs"])
        lbl = add_label("%d %s" % (len(meta["outputs"]), "OUTPUT" if meta_outputs_len == 1 else "OUTPUTS"), scr=self.page2)
        lbl.align(self.page2, lv.ALIGN.IN_TOP_MID, 0, 0)
        lbl.set_y(obj.get_y() + obj.get_height() + 30)
        for i, out in enumerate(meta["outputs"]):
            idxlbl = lv.label(self.page2)
            idxlbl.set_text("%d:" % i)
            idxlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)
            idxlbl.set_x(30)
            lbl = lv.label(self.page2)
            lbl.set_long_mode(lv.label.LONG.BREAK)
            lbl.set_width(380)
            valuetxt = "???" if out["value"] == -1 else "%.8f" % (out["value"]/1e8)
            lbl.set_text("%s %s to %s" % (valuetxt, out.get("asset", self.default_asset), out.get("label", "")))
            lbl.align(idxlbl, lv.ALIGN.IN_TOP_LEFT, 0, 0)
            lbl.set_x(60)

            addrlbl = lv.label(self.page2)
            addrlbl.set_long_mode(lv.label.LONG.BREAK)
            addrlbl.set_width(380)
            addrlbl.set_text(format_addr(out["address"], words=4))
            addrlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
            addrlbl.set_x(60)
            if out.get("label", ""):
                addrlbl.set_style(0, style_secondary)
            else:
                addrlbl.set_style(0, style_primary)
            lbl = addrlbl
            warning_text = "\n".join(out.get("warnings", []))
            if warning_text:
                text = warning_text
                warning = add_label(text, scr=self.page2)
                warning.set_align(lv.label.ALIGN.LEFT)
                warning.set_width(380)
                warning.set_style(0, self.style_warning)
                warning.align(addrlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 10)
                warning.set_x(60)
                lbl = warning

        if fee:
            idxlbl = lv.label(self.page2)
            idxlbl.set_text("Fee:  " + fee_txt)
            idxlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)
            idxlbl.set_x(30)
            lbl = idxlbl

        verlbl = lv.label(self.page2)
        verlbl.set_style(0, style_gray)
        verlbl.set_text("Transaction Version: %d" % meta["tx_version"])
        # If the fee label is present, we want to be close to it. Otherwise, we want a larger margin.
        verlbl.align(lbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5 if fee else 30)
        verlbl.set_x(30)
        locktime = meta["locktime"]
        if all(inp["sequence"] == 0xFFFFFFFF for inp in meta["inputs"]):
            # Locktime disabled. See: https://learnmeabitcoin.com/technical/transaction/input/sequence
            ltlbl = lv.label(self.page2)
            ltlbl.set_style(0, style_gray)
            ltlbl.set_text("Locktime: %d" % locktime)
            ltlbl.align(verlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
            # A zero locktime with final sequences is the normal case. Warn only
            # when a non-zero locktime is set but ignored, or there are no inputs.
            if locktime != 0 or not meta["inputs"]:
                ltdisabledlbl = lv.label(self.page2)
                ltdisabledlbl.set_style(0, style_warning)
                ltdisabledlbl.set_text("All inputs have locktime disabled!" if meta["inputs"] else "No inputs!")
                ltdisabledlbl.align(ltlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 15, 5)
        elif locktime <= 499999999:
            # Block height. See: https://learnmeabitcoin.com/technical/transaction/locktime
            ltlbl = lv.label(self.page2)
            ltlbl.set_style(0, style_gray)
            ltlbl.set_text("Locktime: %d (Block Height)" % locktime)
            ltlbl.align(verlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
        else:
            # Block timestamp. See: https://learnmeabitcoin.com/technical/transaction/locktime
            ltlbl = lv.label(self.page2)
            ltlbl.set_style(0, style_gray)
            ltlbl.set_text("Locktime: %d (Timestamp)" % locktime)
            ltlbl.align(verlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 0, 5)
            mp_time = conv_time(locktime)
            ltdatelbl = lv.label(self.page2)
            ltdatelbl.set_style(0, style_gray)
            ltdatelbl.set_text("%04d-%02d-%02d %02d:%02d:%02d UTC" % mp_time[:6])
            ltdatelbl.align(ltlbl, lv.ALIGN.OUT_BOTTOM_LEFT, 15, 5)

        self.toggle_details()

        # Prompt.__init__ gated an empty page. Gate again now that the pages
        # are filled (F-19), on the page shown first. The details page lists
        # everything the default page does, so it is the one to gate when it
        # comes first.
        self.gate_confirm(self.page2 if enable_inputs else self.page)

    def add_warning(self, page, text):
        warning = add_label(text, scr=page)
        warning.set_style(0, self.style_warning)
        warning.align(page, lv.ALIGN.IN_TOP_MID, 0, 20)
        return warning

    def toggle_details(self):
        if self.details_sw.get_state():
            self.page2.set_hidden(False)
            self.page.set_hidden(True)
        else:
            self.page2.set_hidden(True)
            self.page.set_hidden(False)

    def show_output(self, out, obj):
        # show output
        valuetxt = "???" if out["value"] == -1 else "%.8f" % (out["value"]/1e8)
        lbl = add_label(
            "%s %s to" % (valuetxt, out.get("asset", self.default_asset)), style="title", scr=self.page
        )
        lbl.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 30)
        obj = lbl
        if out.get("label", ""):
            lbl = add_label(out["label"], style="title", scr=self.page)
            lbl.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)
            obj = lbl
        if out.get("label", ""):
            txt = format_addr(out["address"], words=4)
        else:
            txt = format_addr(out["address"])
        addr = add_label(txt, scr=self.page)
        if out.get("label", ""):
            addr.set_style(0, self.style_secondary)
        else:
            addr.set_style(0, self.style)
        addr.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)
        obj = addr
        warning_text = "\n".join(out.get("warnings", []))
        if warning_text:
            text = "WARNING! %s" % warning_text
            warning = add_label(text, scr=self.page)
            warning.set_style(0, self.style_warning)
            warning.align(obj, lv.ALIGN.OUT_BOTTOM_MID, 0, 10)
            obj = warning
        return obj

    def sequence_to_text(self, sequence, tx_version):
        """Label for an input's sequence number: (text, is_relative_locktime).

        BIP-125: any value below 0xFFFFFFFE signals RBF. BIP-68: in a
        version 2+ transaction, a value with bit 31 clear is a relative
        locktime. Only bits 0-15 (the value) and bit 22 (the unit) carry a
        meaning; the other bits are ignored by consensus.
        """
        if sequence == 0xFFFFFFFF:
            return "Locktime disabled", False
        if sequence == 0xFFFFFFFE:
            return 'RBF "disabled"', False
        if tx_version >= 2 and not sequence & 0x80000000:
            text = "RBF enabled, relative locktime"
            if sequence & ~0x0040FFFF:
                text += ", non-standard bits"
            return text, True
        return "RBF enabled", False

    def relative_locktime_to_text(self, sequence):
        # BIP-68: the value is in the low 16 bits, bit 22 selects the unit
        value = sequence & 0xFFFF
        if sequence & 0x00400000:
            # In units of 512 seconds
            rlt_total = value * 512
            rlt_parts = [
                (amount, unit)
                for amount, unit in [
                    (rlt_total // 86400, "day"),
                    ((rlt_total // 3600) % 24, "hour"),
                    ((rlt_total // 60) % 60, "minute"),
                    (rlt_total % 60, "second"),
                ]
                if amount > 0
            ]
            if not rlt_parts:
                return "0 seconds"
            # Break into 2 lines if there are too many parts
            rlt_lines_parts = [rlt_parts] if len(rlt_parts) < 4 else [rlt_parts[:3], rlt_parts[3:]]
            return ",\n".join(
                ", ".join(
                    "%d %s%s" % (amount, unit, "" if amount == 1 else "s")
                    for amount, unit in rlt_line_parts
                )
                for rlt_line_parts in rlt_lines_parts
            )
        else:
            return "%d %s" % (value, "block" if value == 1 else "blocks")
