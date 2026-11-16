import sys

if sys.implementation.name != 'micropython':
    from native_support import setup_native_stubs

    setup_native_stubs()

from unittest import TestCase
from io import BytesIO
import gc

from tests.util import get_keystore, get_wallets_app, clear_testdir
from apps.wallets.manager import ADD_WALLET, DERIVE_ADDRESS, SIGN_PSBT, VERIFY_ADDRESS

DOC_KEYS = [
    "[b317ec86/48h/1h/0h/2h]tpubDEToKMGFhyuP6kfwvjtYaf56khzS1cUcwc47C6aMH6bQ8sNVLMcCK6jr21YDCkU2QhTK5CAnddhfgZ8dD4EL1wGCaAKZaGFeVVdXHaJMTMn",
    "[f04828fe/48h/1h/0h/2h]tpubDFekS5zvPSdW6WWjH2p7vPRkxmeeNGnirmj36AUyoAYbJvfKBj6UARWR5gQ6FRrr98dzT1XFTi6rfGo9AAAeutY1S6SoWijQ8BKxDhYQzDR",
    "[d3c05b2e/48h/1h/0h/2h]tpubDFnAczXQTHxuBh7FxrpLDHBidkC1Di54pTPSPMu4AQjKziFQQTTEFXEVugqm8ucKQhJfLGesBjRZWtLpqAkAmecoXtvaPwCzf4teqrY7Uu5",
]
DOC_DESCRIPTOR = "wsh(sortedmulti(2,%s))" % ",".join(DOC_KEYS)
# Wallet.from_descriptor() adds the default /<0;1>/* derivation when no key
# has one, so this is how the imported wallet's descriptor is stored.
DOC_DESCRIPTOR_DEFAULT_DERIVATION = "wsh(sortedmulti(2,%s))" % ",".join(
    k + "/<0;1>/*" for k in DOC_KEYS
)
DOC_NAMED_DESCRIPTOR = "My multisig&" + DOC_DESCRIPTOR
DOC_NAMED_DESCRIPTOR_NO_SPACE = "Multisig&" + DOC_DESCRIPTOR
DOC_ADDWALLET_COMMAND = "addwallet " + DOC_NAMED_DESCRIPTOR
DOC_ADDRESS_REQUEST = (
    "bitcoin:bcrt1qd3mtrhysk3k4w6fmu7ayjvwk6q98c2dpf0p4x87zauu8rcgq5dzq73tyrx?index=2"
)
# Base64 PSBT magic followed by zero padding. The parser only checks the magic
# bytes, but BaseApp.get_prefix() treats input shorter than 20 bytes without a
# space as a command word, so the fixture must be at least 20 bytes long.
DOC_BASE64_PSBT = "cHNidP8AAAAAAAAAAAAAAAAAAAA="


class WalletManagerParsingTest(TestCase):
    def setUp(self):
        clear_testdir()
        self.keystore = get_keystore()
        self.wallets_app = get_wallets_app(self.keystore, "regtest")
        self.manager = self.wallets_app.manager

    def tearDown(self):
        clear_testdir()
        gc.collect()

    def _parse_command(self, data):
        stream = BytesIO(data)
        cmd, result_stream = self.manager.parse_stream(stream)
        self.assertIs(result_stream, stream)
        return cmd, result_stream

    def test_docs_addwallet_command_is_detected(self):
        cmd, stream = self._parse_command(DOC_ADDWALLET_COMMAND.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), DOC_NAMED_DESCRIPTOR)

    def test_named_descriptor_without_addwallet_prefix_is_parsed(self):
        cmd, stream = self._parse_command(DOC_NAMED_DESCRIPTOR_NO_SPACE.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), DOC_NAMED_DESCRIPTOR_NO_SPACE)
        wallet = self.manager.parse_wallet(DOC_NAMED_DESCRIPTOR_NO_SPACE)
        self.assertEqual(wallet.name, "Multisig")
        self.assertEqual(str(wallet.descriptor), DOC_DESCRIPTOR_DEFAULT_DERIVATION)

    def test_named_descriptor_with_space_without_addwallet_prefix_is_parsed(self):
        # BaseApp.get_prefix() returns b"My" as the command word here
        cmd, stream = self._parse_command(DOC_NAMED_DESCRIPTOR.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), DOC_NAMED_DESCRIPTOR)
        wallet = self.manager.parse_wallet(DOC_NAMED_DESCRIPTOR)
        self.assertEqual(wallet.name, "My multisig")
        self.assertEqual(str(wallet.descriptor), DOC_DESCRIPTOR_DEFAULT_DERIVATION)

    def test_raw_descriptor_with_spaces_is_parsed(self):
        data = "wsh(sortedmulti(2, %s))" % ", ".join(DOC_KEYS)
        cmd, stream = self._parse_command(data.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), data)
        wallet = self.manager.parse_wallet(data)
        self.assertEqual(str(wallet.descriptor), DOC_DESCRIPTOR_DEFAULT_DERIVATION)

    def test_liquid_named_descriptor_with_space_is_parsed(self):
        manager = get_wallets_app(self.keystore, "elementsregtest").manager
        data = (
            "My liquid&blinded(slip77(" + "11" * 32 + "),wpkh(" + DOC_KEYS[0] + "/<0;1>/*))"
        ).encode()
        cmd, stream = manager.parse_stream(BytesIO(data))
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read(), data)

    def test_other_app_commands_are_not_wallet_commands(self):
        for data in (
            # "&" is the last byte parse_stream() reads
            b"signmessage m/84h/1h/0h/0/0 ascii:hello&world",
            b"signmessage m/84h/1h/0h/0/0 ascii:hi&w",
            b"setlabel 12345678 My wallet",
            b"xpub m/84h/1h/0h",
            b"hello world&foo=bar",
        ):
            cmd, _ = self.manager.parse_stream(BytesIO(data))
            self.assertIsNone(cmd, data)

    def test_wallet_command_prefix_still_wins(self):
        cmd, stream = self._parse_command(b"showaddr wpkh m/84h/1h/0h/0/0")
        self.assertEqual(cmd, DERIVE_ADDRESS)
        self.assertEqual(stream.read(), b"wpkh m/84h/1h/0h/0/0")

    def test_raw_descriptor_is_parsed(self):
        cmd, stream = self._parse_command(DOC_DESCRIPTOR.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), DOC_DESCRIPTOR)
        wallet = self.manager.parse_wallet(DOC_DESCRIPTOR)
        self.assertEqual(wallet.name, "Untitled")
        self.assertEqual(str(wallet.descriptor), DOC_DESCRIPTOR_DEFAULT_DERIVATION)

    def test_raw_single_key_descriptor_is_detected(self):
        data = "wpkh(" + DOC_KEYS[0] + "/<0;1>/*)"
        cmd, stream = self._parse_command(data.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), data)

    def test_descriptor_function_inside_data_is_not_a_wallet(self):
        cmd, _ = self.manager.parse_stream(BytesIO(b"0123456789abcdefghijwsh(" + DOC_KEYS[0].encode()))
        self.assertIsNone(cmd)

    def test_name_without_descriptor_is_not_a_wallet(self):
        cmd, _ = self.manager.parse_stream(BytesIO(b"Multisig&notadescriptor,just-text-here"))
        self.assertIsNone(cmd)

    def test_descriptor_cut_off_by_read_window_is_detected(self):
        # parse_stream() sees 40 bytes: the name fills 38, then "&w"
        data = "N" * 38 + "&" + DOC_DESCRIPTOR
        cmd, stream = self._parse_command(data.encode())
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read().decode(), data)

    def test_liquid_blinded_descriptor_is_detected(self):
        manager = get_wallets_app(self.keystore, "elementsregtest").manager
        data = (
            "blinded(slip77(" + "11" * 32 + "),wpkh(" + DOC_KEYS[0] + "/<0;1>/*))"
        ).encode()
        cmd, stream = manager.parse_stream(BytesIO(data))
        self.assertEqual(cmd, ADD_WALLET)
        self.assertEqual(stream.read(), data)

    def test_docs_base64_psbt_is_detected(self):
        cmd, stream = self._parse_command(DOC_BASE64_PSBT.encode())
        self.assertEqual(cmd, SIGN_PSBT)
        # ensure stream is rewound for later processing
        self.assertEqual(stream.read(10), DOC_BASE64_PSBT[:10].encode())

    def test_docs_address_request_is_detected(self):
        cmd, stream = self._parse_command(DOC_ADDRESS_REQUEST.encode())
        self.assertEqual(cmd, VERIFY_ADDRESS)
        # parse_stream should keep address data available for processing
        self.assertEqual(stream.read().decode(), DOC_ADDRESS_REQUEST.replace("bitcoin:", "", 1))
