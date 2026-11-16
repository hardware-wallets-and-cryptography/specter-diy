from unittest import TestCase
from .util import get_keystore, get_wallets_app, clear_testdir, check_sigs
from embit.psbt import PSBT
from embit.psbtview import PSBTView
from apps.wallets.wallet import Wallet, WalletError
from io import BytesIO

WALLETS = [
    "cpfp_descriptor&wsh(multi(1,xpub661MyMwAqRbcG9F1VX1rYev3ZsFRQ8XdJYk7rYLiaCfLt3WjVQ5o12SeJHPQEUCC8NmTWFmyejXrp3GWTFQNrXHL7iUXcoRo79VEnmKGYhc/*,xpub6CZFHPW1GiB8YgV7zGpeQDB6mMHZYPQyUaHrM1nMvKMgLxwok4xCtnzjuxQ3p1LHJUkz5i1Y7bRy5fmGrdg8UBVb39XdXNtWWd2wTsNd7T9/*))",
    "deposit_descriptor&wsh(multi(2,xpub661MyMwAqRbcEgaXJWejvvXw2PHvr6ZF5ybqahrCnptM1kTNirjVETa6Ba4oTJz3Uppghzow6pQaGzyPaUVeb7vSufEYRUVMyNKX9PyRxWC/*,xpub6DEzq5DNPx2rPiZJ7wvFhxRKUKDoV1GwjFmFdaxFfbsw9HsHyxc9usoRUMxqJaMrwoXh4apahsGEnjAS4cVCBDgqsx5Groww22AdHbgxVDg/*))",
    "unvault_descriptor&wsh(andor(multi(1,xpub661MyMwAqRbcG9F1VX1rYev3ZsFRQ8XdJYk7rYLiaCfLt3WjVQ5o12SeJHPQEUCC8NmTWFmyejXrp3GWTFQNrXHL7iUXcoRo79VEnmKGYhc/*,xpub6CZFHPW1GiB8YgV7zGpeQDB6mMHZYPQyUaHrM1nMvKMgLxwok4xCtnzjuxQ3p1LHJUkz5i1Y7bRy5fmGrdg8UBVb39XdXNtWWd2wTsNd7T9/*),and_v(v:multi(2,02abe475b199ec3d62fa576faee16a334fdb86ffb26dce75becebaaedf328ac3fe,030f64b922aee2fd597f104bc6cb3b670f1ca2c6c49b1071a1a6c010575d94fe5a),older(3)),thresh(2,pkh(xpub661MyMwAqRbcEgaXJWejvvXw2PHvr6ZF5ybqahrCnptM1kTNirjVETa6Ba4oTJz3Uppghzow6pQaGzyPaUVeb7vSufEYRUVMyNKX9PyRxWC/*),a:pkh(xpub6DEzq5DNPx2rPiZJ7wvFhxRKUKDoV1GwjFmFdaxFfbsw9HsHyxc9usoRUMxqJaMrwoXh4apahsGEnjAS4cVCBDgqsx5Groww22AdHbgxVDg/*))))#0v6kshkd",
    # unvault_descriptor without cosigners and using xpub
    "unvault_descriptor_without_cosigs&wsh(andor(thresh(1,pk(xpub661MyMwAqRbcFozCJEKQbfoEScGGAeV8Mx6RGwwYmFgeKyJTAfyye2L7uuCmNaZycG9DK3jWB9Gvpre94LTu7J3CheiQitNJjDF9RMtT5Kt/*)),older(10),thresh(2,pkh(xpub661MyMwAqRbcEyoQHjRmcCXrEw8YVZxecB1fmm17Dqs9muXBAQUrLGk9JGWBBoqrB9VnMdzN5u2D8dVdLnViTxWSbRmb58xNEX3GARisZBx/*),a:pkh(xpub661MyMwAqRbcGB7fwdofjHV6FsR2fTxC8tkb96eT453UaCaxKTgLUNHW2sjShw4eez7afHnwF2F8G4VfaeeD5Kg3TXrKtMKtXJvUK3Jh3uE/*))))",
]

MNEMONICS = [
    "glue possible carpet youth pepper damp capital wrist wage weird fame drastic story vehicle same",
    "toddler vanish target people solar lens midnight great ability state imitate spot discover swamp park",
    "rapid veteran belt horse evidence wine rabbit price protect foam summer excuse",
]

PSBTS = [
    # emergency tx
    (   # unsigned, signed tx
        "cHNidP8BAF4CAAAAAZ/Gi4iUvzDstuyDVggeYfAJVz/h9NhM2TMvw/Jf1cHEAQAAAAD9////AXCWmjsAAAAAIgAgy7Co1PHzwoce0hHQR5RHMS72lSZudTF3bYrNgqLbkDYAAAAAAAEAaAIAAAABbF0wBdzYu2hFnktkhLnHMGIJwx8NHEO6qWM6Np1K7pkBAAAAAP////8CAAAAAAAAAAABagDKmjsAAAAAIgAgslrG3QMtjTKpRrHl3ptzoveYxLV1H4x72eg19U2FZPUAAAAAAQErAMqaOwAAAAAiACCyWsbdAy2NMqlGseXem3Oi95jEtXUfjHvZ6DX1TYVk9QEDBIEAAAABBUdSIQNUKwPjJgeR9IwGYHua8tps2C35VLsfdydmK+/BAJnQfyECWC3tv0T0ZWTl2M2wZ1NtYOvjTNHRgBz/Ubv516wom0NSriIGA1QrA+MmB5H0jAZge5ry2mzYLflUux93J2Yr78EAmdB/CAwi9cUAAAAAAAA=",
        "cHNidP8BAF4CAAAAAZ/Gi4iUvzDstuyDVggeYfAJVz/h9NhM2TMvw/Jf1cHEAQAAAAD9////AXCWmjsAAAAAIgAgy7Co1PHzwoce0hHQR5RHMS72lSZudTF3bYrNgqLbkDYAAAAAACICA1QrA+MmB5H0jAZge5ry2mzYLflUux93J2Yr78EAmdB/RzBEAiBhe5OHRq+FcEy68BqJJjijQ1LYTEYrgsh37k2MoIClXAIgH7pJ36NnILs5FiX6yECXpTyhV2r2z+eF3JwOVkFUyLOBAAA=",
        [0], # mnemonics that can sign, signed by the first one in the list
        ["deposit_descriptor"], # signing wallets
    ),
    # emergency_unvault_tx
    (
        "cHNidP8BAF4CAAAAAUBJ+e7mLGXt97WREhIOI4WtYCpeK3L0fS3jFabc3R8wAAAAAAD9////AYr9mTsAAAAAIgAgy7Co1PHzwoce0hHQR5RHMS72lSZudTF3bYrNgqLbkDYAAAAAAAEAXgIAAAAB8G1OcpPZyLJAWI2wz6d0WJSw6GBJBsi4ibeF1kxTtrsAAAAAAP////8BuEKaOwAAAAAiACBvamFBqMtmhN3irCsD63lF+JPQShP737yCcrETt/YAsgAAAAABASu4Qpo7AAAAACIAIG9qYUGoy2aE3eKsKwPreUX4k9BKE/vfvIJysRO39gCyAQMEgQAAAAEFylEhA0LcwAQlohsN86JoIY6//iWJUVj2qZDJBc9W2AD8hF+hIQICkzqxA36tCqSnhYxtSdZwXh+zvF9msAkYr3ufAOzVJlKuZHapFE3hX7ORvISDR4K9pRFxqgtaapobiKxrdqkUcqlfIq+aG664UvmpUnL4wh2Y8mSIrGyTUodnUiECq+R1sZnsPWL6V2+u4WozT9uG/7JtznW+zrqu3zKKw/4hAw9kuSKu4v1ZfxBLxss7Zw8cosbEmxBxoabAEFddlP5aUq9TsmgiBgNUKwPjJgeR9IwGYHua8tps2C35VLsfdydmK+/BAJnQfwgMIvXFAAAAAAAA",
        "cHNidP8BAF4CAAAAAUBJ+e7mLGXt97WREhIOI4WtYCpeK3L0fS3jFabc3R8wAAAAAAD9////AYr9mTsAAAAAIgAgy7Co1PHzwoce0hHQR5RHMS72lSZudTF3bYrNgqLbkDYAAAAAACICA1QrA+MmB5H0jAZge5ry2mzYLflUux93J2Yr78EAmdB/RzBEAiBDJR8Xva19XBYPBVyATqYg8zqKuRHI0vHy7SvT+cuR6AIgDrB3YG2fVx5m6ijD1OP6KNnjNNtXnjKc40PaTCFHVMaBAAA=",
        [0, 1],
        ["unvault_descriptor"],
    ),
    # cancel_tx
    (
        "cHNidP8BAF4CAAAAAUBJ+e7mLGXt97WREhIOI4WtYCpeK3L0fS3jFabc3R8wAAAAAAD9////AYr9mTsAAAAAIgAgslrG3QMtjTKpRrHl3ptzoveYxLV1H4x72eg19U2FZPUAAAAAAAEAXgIAAAAB8G1OcpPZyLJAWI2wz6d0WJSw6GBJBsi4ibeF1kxTtrsAAAAAAP////8BuEKaOwAAAAAiACBvamFBqMtmhN3irCsD63lF+JPQShP737yCcrETt/YAsgAAAAABASu4Qpo7AAAAACIAIG9qYUGoy2aE3eKsKwPreUX4k9BKE/vfvIJysRO39gCyAQMEgQAAAAEFylEhA0LcwAQlohsN86JoIY6//iWJUVj2qZDJBc9W2AD8hF+hIQICkzqxA36tCqSnhYxtSdZwXh+zvF9msAkYr3ufAOzVJlKuZHapFE3hX7ORvISDR4K9pRFxqgtaapobiKxrdqkUcqlfIq+aG664UvmpUnL4wh2Y8mSIrGyTUodnUiECq+R1sZnsPWL6V2+u4WozT9uG/7JtznW+zrqu3zKKw/4hAw9kuSKu4v1ZfxBLxss7Zw8cosbEmxBxoabAEFddlP5aUq9TsmgiBgNUKwPjJgeR9IwGYHua8tps2C35VLsfdydmK+/BAJnQfwgMIvXFAAAAAAAA",
        "cHNidP8BAF4CAAAAAUBJ+e7mLGXt97WREhIOI4WtYCpeK3L0fS3jFabc3R8wAAAAAAD9////AYr9mTsAAAAAIgAgslrG3QMtjTKpRrHl3ptzoveYxLV1H4x72eg19U2FZPUAAAAAACICA1QrA+MmB5H0jAZge5ry2mzYLflUux93J2Yr78EAmdB/RzBEAiAkXZx07Oc/COwXU1dB5XUlB7U29eFc1OA70qrn58QyuQIgZUr7g2OhZHskQW3myx/j20vAC2aQZe8PScz+TKGMc0iBAAA=",
        [0, 1],
        ["unvault_descriptor"],
    ),
    # cancel_tx with unvault_descriptor_without_cosigs
    (
        "cHNidP8BAF4CAAAAAY/fio7tHaoXcadRWdayItRJWXfhZTpKxGKpnMmQpzz+AAAAAAD9////AbRW9wcAAAAAIgAgJMk4bvxMit7yF7KTHK7Rz0iR9JdwUmrVcD1ok7SRAs4AAAAAAAEAXgIAAAAB4mdLAhD0FZ0spfwuuQzRWhGVyGbqmqMU6kGksUvZ/E4AAAAAAP////8BWJL3BwAAAAAiACAjzwrd2yIvVTxWaDckuGDqBScUJca9OQr7vzUNLS57BgAAAAABAStYkvcHAAAAACIAICPPCt3bIi9VPFZoNyS4YOoFJxQlxr05Cvu/NQ0tLnsGAQMEgQAAAAEFYSECptuNnNtT2nF1rp30VkmcJO1Wm5aRj4u1YPA0ODPXDwmsUYdkdqkUJwy9u8lI29VvKKYmXIazEVO6zFOIrGt2qRSVm+syNYzNGfuT6f0lVC0MjZovfIisbJNSh2dasmgiBgKm242c21PacXWunfRWSZwk7VablpGPi7Vg8DQ4M9cPCQh+CFEoAAAAACIGAr7MXr0GScg2kizopytUz529ydfeVhY9z3BjaLO1reMJCOcE/74AAAAAIgYDYU9S5v+HS+1xza3rDKe+2s5xtA8+gEWYLIIi/PLkRPsIimTyqQAAAAAAIgICvsxevQZJyDaSLOinK1TPnb3J195WFj3PcGNos7Wt4wkI5wT/vgAAAAAiAgNhT1Lm/4dL7XHNresMp77aznG0Dz6ARZgsgiL88uRE+wiKZPKpAAAAAAA=",
        "cHNidP8BAF4CAAAAAY/fio7tHaoXcadRWdayItRJWXfhZTpKxGKpnMmQpzz+AAAAAAD9////AbRW9wcAAAAAIgAgJMk4bvxMit7yF7KTHK7Rz0iR9JdwUmrVcD1ok7SRAs4AAAAAACICA2FPUub/h0vtcc2t6wynvtrOcbQPPoBFmCyCIvzy5ET7RzBEAiAmS3DDqEpq94fmHb+vrMGtsEiZbK80L1OQqvLExW5scgIgGx4a+fYo6kqMj6OWM/aYVlkI1BzxF7tlmJAhD1fvI3mBAAA=",
        [2],
        ["unvault_descriptor_without_cosigs"],
    ),
]

class RevaultTest(TestCase):

    def test_revault_sign(self):
        """Basic signing of the PSBT"""
        for i, mnemonic in enumerate(MNEMONICS):
            clear_testdir()
            ks = get_keystore(mnemonic=mnemonic, password="")
            wapp = get_wallets_app(ks, 'main')
            # add wallets
            for wdesc in WALLETS:
                w = wapp.manager.parse_wallet(wdesc)
                wapp.manager.add_wallet(w)
            for j, (unsigned, signed, mnemonic_idx, wnames) in enumerate(PSBTS):
                psbt = PSBT.from_string(unsigned)
                s = BytesIO(psbt.to_string().encode())
                # check it can sign b64-psbt
                self.assertTrue(wapp.can_process(s))
                # check it can sign raw psbt
                s = BytesIO(psbt.serialize())
                self.assertTrue(wapp.can_process(s))

                fout = BytesIO()
                wallets, meta = wapp.manager.preprocess_psbt(s, fout)
                # check that we detected wallet and a non-standard sighash
                self.assertEqual([w.name for w in wallets], wnames)
                self.assertEqual([inp.get("label").replace(" (watch-only)", "") for inp in meta["inputs"]], wnames)
                self.assertEqual(meta["inputs"][0].get("sighash"), "ALL | ANYONECANPAY")

                fout.seek(0)
                psbtv = PSBTView.view(fout)

                b = BytesIO()
                if i not in mnemonic_idx:
                    with self.assertRaises(WalletError):
                        sig_count = wapp.manager.sign_psbtview(psbtv, b, wallets, None)
                elif i == mnemonic_idx[0]:
                    sig_count = wapp.manager.sign_psbtview(psbtv, b, wallets, None)
                    self.assertTrue(check_sigs(PSBT.parse(b.getvalue()), PSBT.from_base64(signed)))
