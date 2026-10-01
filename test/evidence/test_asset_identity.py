import asyncio
import unittest
from io import BytesIO
from unittest.mock import patch

from apps.wallets.liquid import manager as liquid


LBTC_ID = "6f0279e9ed041c3d710a9f57d0c02928416460c4b722ae3457a11eec381c526d"
OTHER_ID = "00" * 31 + "01"


class _Card:
    uid = "evidence"
    userkey = b"evidence"

    def __init__(self):
        self.records = {}

    def save_aead(self, path, plaintext, key):
        self.records[path] = plaintext

    def load_aead(self, path, key):
        return b"", self.records[path]


class _ImportPrompt:
    def __init__(self, title, message):
        self.title = title
        self.message = message


class AssetIdentityEvidence(unittest.TestCase):
    def setUp(self):
        self.card = _Card()
        self.manager = object.__new__(liquid.LWalletManager)
        self.manager.root_path = "assets"
        self.manager.keystore = self.card
        self.manager.network = "liquidv1"
        self.manager.assets = {}
        self.mocks = (
            patch.object(liquid.platform, "maybe_mkdir"),
            patch.object(liquid.platform, "file_exists",
                         side_effect=lambda path: path in self.card.records),
            patch.object(liquid.platform, "delete_recursively"),
            patch.object(liquid, "Prompt", _ImportPrompt),
            patch.object(liquid, "format_addr", side_effect=lambda value, **_: value),
        )
        for mock in self.mocks:
            mock.start()
            self.addCleanup(mock.stop)
        self.manager.load_assets()

    def _import(self, asset_id, label):
        prompts = []

        async def approve(prompt):
            prompts.append(prompt)
            return True

        command = "addasset %s %s" % (asset_id, label)
        try:
            asyncio.run(self.manager.process_host_command(
                BytesIO(command.encode()), approve
            ))
        except liquid.WalletError as exc:
            self.assertRegex(str(exc).lower(), "asset|label|reserved")
            return
        self.assertEqual(len(prompts), 1)
        self.assertIn(asset_id, prompts[0].message)

    def test_host_cannot_replace_built_in_lbtc_name_even_after_reload(self):
        real = bytes.fromhex(LBTC_ID)[::-1]
        self.assertEqual(self.manager.asset_label(real), "LBTC")
        self._import(LBTC_ID, "TestToken")
        self.manager.load_assets()
        self.assertEqual(
            self.manager.asset_label(real), "LBTC",
            "F-23: host-supplied label replaced the built-in LBTC identity",
        )

    def test_host_cannot_label_another_asset_lbtc(self):
        impostor = bytes.fromhex(OTHER_ID)[::-1]
        self._import(OTHER_ID, "LBTC")
        self.assertNotEqual(
            self.manager.asset_label(impostor), "LBTC",
            "F-23: an unrelated asset acquired the trusted LBTC label",
        )
