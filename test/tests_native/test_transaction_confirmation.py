import ast
from pathlib import Path
from unittest import TestCase

# gui.screens.transaction.TransactionScreen builds real LVGL widgets (pages,
# labels, switches, styles) directly in __init__, and the native test stubs
# in native_support.py replace gui.screens.TransactionScreen with a trivial
# placeholder class (as they do for the other screen classes) so the rest of
# the wallet-manager code can be exercised without a display. That means the
# real screen implementation cannot be instantiated - or its widget tree
# inspected - under the current native/unix test infrastructure.
#
# The UX/security invariant this file guards, after reviewing PR #13's
# original "always show every output" behaviour against how BitBox02
# handles the same distinction:
#
#   - An output that WalletManager.get_output_status() has
#     cryptographically verified as change (descriptor branch 1, and an
#     on-device re-derivation of the script_pubkey that matches the actual
#     output) and that carries no warning is *not* shown individually on
#     the primary confirmation page. The device itself already proved this
#     output can't be an attacker-controlled destination, so asking the
#     user to re-check it adds noise without adding security. It stays
#     fully visible on the details page ("Show detailed information"),
#     which lists every output unconditionally.
#   - Every other output is always shown on the primary page: external or
#     unverifiable recipients (the actual security-relevant case - a
#     malicious host must not be able to hide an injected output), and
#     same-wallet outputs that are *not* on the verified change branch
#     (e.g. a receive-branch self-payment, which WalletManager labels
#     "This wallet (...)" rather than leaving it looking like automatic
#     change). A "change" output that carries a warning (e.g. gap-limit
#     exceeded) is shown too, since the warning means it needs attention.
#
# Since we cannot drive the real widget tree here, this test statically
# proves (via the AST, not a text/regex match) that the loop over
# meta["outputs"] in the primary confirmation section of
# TransactionScreen.__init__ skips an output if and only if it is guarded
# by exactly `out["change"] and not out.get("warnings")`, with no other
# conditional skip anywhere in the loop.

TRANSACTION_SCREEN_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "gui" / "screens" / "transaction.py"
)


class TransactionConfirmationVisibilityTest(TestCase):
    def setUp(self):
        self.source = TRANSACTION_SCREEN_PATH.read_text()
        self.tree = ast.parse(self.source)

    def _find_class(self, name):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                return node
        self.fail("class %s not found in %s" % (name, TRANSACTION_SCREEN_PATH))

    def _find_init(self, class_node):
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                return node
        self.fail("__init__ not found on TransactionScreen")

    def _primary_output_loop(self, init_node):
        # the primary-confirmation loop is `for out in meta["outputs"]: ...`
        for node in ast.walk(init_node):
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "out":
                if (
                    isinstance(node.iter, ast.Subscript)
                    and isinstance(node.iter.value, ast.Name)
                    and node.iter.value.id == "meta"
                ):
                    return node
        self.fail('for out in meta["outputs"]: loop not found in TransactionScreen.__init__')

    def _is_out_subscript_of(self, node, name, key):
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == name
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == key
        )

    def _is_change_guard(self, test):
        # out["change"] and not out.get("warnings")
        if not (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And)):
            return False
        if len(test.values) != 2:
            return False
        change_check, warning_check = test.values
        if not self._is_out_subscript_of(change_check, "out", "change"):
            return False
        if not (isinstance(warning_check, ast.UnaryOp) and isinstance(warning_check.op, ast.Not)):
            return False
        call = warning_check.operand
        return (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "out"
            and call.args
            and self._is_str_arg(call.args[0], "warnings")
        )

    def _is_str_arg(self, node, value):
        return (
            isinstance(node, ast.Constant)
            and node.value == value
        )

    def test_primary_confirmation_loop_only_skips_verified_change_without_warning(self):
        cls = self._find_class("TransactionScreen")
        init = self._find_init(cls)
        loop = self._primary_output_loop(init)

        guard_stmts = [stmt for stmt in loop.body if isinstance(stmt, ast.If)]
        self.assertEqual(
            len(guard_stmts), 1,
            "primary confirmation loop must have exactly one skip guard",
        )
        guard = guard_stmts[0]
        self.assertTrue(
            self._is_change_guard(guard.test),
            'the only skip guard must be exactly `out["change"] and not out.get("warnings")` '
            '- a verified change output without a warning, and nothing else, may be hidden',
        )
        self.assertTrue(
            any(isinstance(s, ast.Continue) for s in guard.body),
            "the change guard must skip past show_output via continue",
        )
        self.assertEqual(
            len(guard.orelse), 0,
            "the change guard must not have an else branch hiding other logic",
        )

        # every other statement in the loop body must call
        # self.show_output(out, obj) unconditionally - external, unverified,
        # and same-wallet-but-not-change outputs are never skipped.
        other_stmts = [stmt for stmt in loop.body if stmt is not guard]
        for stmt in other_stmts:
            self.assertNotIsInstance(
                stmt,
                (ast.If, ast.Continue, ast.Break),
                "no output other than verified, warning-free change may be conditionally skipped",
            )
        calls_show_output = any(
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and stmt.value.func.attr == "show_output"
            for stmt in other_stmts
        )
        self.assertTrue(
            calls_show_output,
            "primary confirmation loop must call self.show_output() for every non-change (or warned) output",
        )

    def test_details_page_still_lists_every_output_unconditionally(self):
        # the details page ("Show detailed information") is the fallback
        # that keeps a hidden verified-change output inspectable; it must
        # keep iterating meta["outputs"] without a change-keyed skip.
        cls = self._find_class("TransactionScreen")
        init = self._find_init(cls)

        details_loops = [
            node
            for node in ast.walk(init)
            if isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "enumerate"
            and node.iter.args
            and self._is_out_subscript_of(node.iter.args[0], "meta", "outputs")
        ]
        self.assertEqual(
            len(details_loops), 1,
            'for i, out in enumerate(meta["outputs"]): loop not found on the details page',
        )
        loop = details_loops[0]
        # cosmetic `if out.get("label", ""): ... else: ...` / warning-text
        # branches (styling, optional warning label) are fine here
        # - only a continue/break would actually skip an output.
        for node in ast.walk(loop):
            self.assertNotIsInstance(
                node,
                (ast.Continue, ast.Break),
                "the details page must list every output, including hidden verified change",
            )

    def test_default_page_announces_omitted_change(self):
        # Hiding verified change is safe, but the user must be told that
        # outputs were left out (F-24): the skip guard counts each one, and
        # the count is shown on the default page when it is above zero.
        init = self._find_init(self._find_class("TransactionScreen"))
        loop = self._primary_output_loop(init)
        guard = next(stmt for stmt in loop.body if isinstance(stmt, ast.If))
        counters = [
            stmt.target.id
            for stmt in guard.body
            if isinstance(stmt, ast.AugAssign)
            and isinstance(stmt.op, ast.Add)
            and isinstance(stmt.target, ast.Name)
        ]
        self.assertEqual(len(counters), 1, "the change guard must count each omitted output")
        counter = counters[0]
        self.assertTrue(
            any(
                isinstance(stmt, ast.Assign)
                and [ast.unparse(t) for t in stmt.targets] == [counter]
                and ast.unparse(stmt.value) == "0"
                for stmt in init.body
            ),
            "the omitted-output counter must start at 0 before the loop",
        )
        announce = [
            stmt for stmt in init.body
            if isinstance(stmt, ast.If) and ast.unparse(stmt.test) == counter
        ]
        self.assertEqual(len(announce), 1, "the omitted count must be shown when above zero")
        self.assertTrue(
            any(
                isinstance(node, ast.Call) and ast.unparse(node.func) == "add_label"
                for node in ast.walk(announce[0])
            ),
            "the omitted count must be rendered as a label on the default page",
        )

    def test_init_gates_confirm_last_on_the_page_shown_first(self):
        # Prompt.__init__ gates the page while it is still empty, which
        # enables Confirm at once. TransactionScreen fills its pages
        # afterwards, so it must gate again as its final step (F-19), or a
        # fee or output below the viewport can be approved unseen. The page
        # shown first is gated: the details page when it is switched on
        # (non-default sighash, unknown Liquid values), else the default page.
        init = self._find_init(self._find_class("TransactionScreen"))
        last = init.body[-1]
        self.assertTrue(
            isinstance(last, ast.Expr)
            and isinstance(last.value, ast.Call)
            and ast.unparse(last.value.func) == "self.gate_confirm",
            "the last statement of TransactionScreen.__init__ must be self.gate_confirm(...)",
        )
        self.assertEqual(
            [ast.unparse(arg) for arg in last.value.args],
            ["self.page2 if enable_inputs else self.page"],
        )
        self.assertEqual(last.value.keywords, [])

    def test_init_does_not_shadow_the_prompt_warning(self):
        # Prompt keeps self.warning for the label above the buttons, and the
        # debug GUI reports its position. A label inside the page must not
        # take that name.
        init = self._find_init(self._find_class("TransactionScreen"))
        for node in ast.walk(init):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    self.assertNotEqual(
                        ast.unparse(target), "self.warning",
                        "TransactionScreen must not assign self.warning",
                    )


def _compile_screen_method(name):
    """Compile one TransactionScreen method from the source.

    The method must not touch self: the screen class cannot be imported here
    (see the note at the top of this file).
    """
    tree = ast.parse(TRANSACTION_SCREEN_PATH.read_text())
    method = next(
        node
        for cls in ast.walk(tree)
        if isinstance(cls, ast.ClassDef) and cls.name == "TransactionScreen"
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    namespace = {}
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), str(TRANSACTION_SCREEN_PATH), "exec"),
        namespace,
    )
    return namespace[name]


class SequenceTextTest(TestCase):
    def setUp(self):
        method = _compile_screen_method("sequence_to_text")
        self.to_text = lambda sequence, version=2: method(None, sequence, version)

    def test_labels(self):
        for sequence, version, expected in (
            (0xFFFFFFFF, 2, ("Locktime disabled", False)),
            (0xFFFFFFFE, 2, ('RBF "disabled"', False)),
            (0xFFFFFFFD, 2, ("RBF enabled", False)),
            # any value below 0xFFFFFFFE signals RBF, not only 0xFFFFFFFD
            (0xFFFFFFFC, 2, ("RBF enabled", False)),
            # bit 31 set: relative locktime disabled
            (0x80000005, 2, ("RBF enabled", False)),
            (0x00000005, 2, ("RBF enabled, relative locktime", True)),
            (0x00400001, 2, ("RBF enabled, relative locktime", True)),
            # consensus ignores the other bits, the locktime still applies
            (0x00010005, 2, ("RBF enabled, relative locktime, non-standard bits", True)),
            # BIP-68 applies only from transaction version 2
            (0x00000005, 1, ("RBF enabled", False)),
        ):
            with self.subTest(sequence=hex(sequence), version=version):
                self.assertEqual(self.to_text(sequence, version), expected)


class RelativeLocktimeTextTest(TestCase):
    def setUp(self):
        method = _compile_screen_method("relative_locktime_to_text")
        self.to_text = lambda sequence: method(None, sequence)

    def test_time_based(self):
        for sequence, text in (
            # zero must still render something
            (0x00400000, "0 seconds"),
            (0x00400001, "8 minutes, 32 seconds"),
            (0x00400002, "17 minutes, 4 seconds"),
            (0x0040FFFF, "388 days, 8 hours, 32 minutes"),
            # four parts are split over two lines
            (0x004000C8, "1 day, 4 hours, 26 minutes,\n40 seconds"),
        ):
            with self.subTest(sequence=hex(sequence)):
                self.assertEqual(self.to_text(sequence), text)

    def test_block_based(self):
        for sequence, text in (
            (0x00000000, "0 blocks"),
            (0x00000001, "1 block"),
            (0x00000090, "144 blocks"),
            # only the low 16 bits are the value
            (0x00010005, "5 blocks"),
        ):
            with self.subTest(sequence=hex(sequence)):
                self.assertEqual(self.to_text(sequence), text)
