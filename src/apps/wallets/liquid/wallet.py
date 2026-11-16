from ..wallet import *
from platform import maybe_mkdir, delete_recursively, get_preallocated_ram
from embit import ec, hashes, script, compact
from embit.liquid.networks import NETWORKS
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.arguments import AllowedDerivation
from embit.liquid.pset import LInputScope, LOutputScope
import hashlib
import secp256k1

# error that happened during rangeproof_rewind
class RewindError(Exception):
    pass

class LWallet(Wallet):
    DescriptorClass = LDescriptor
    Networks = NETWORKS

    def fill_scope(self, scope, fingerprint, stream=None, rangeproof_offset=None, surj_proof_offset=None):
        """
        Fills derivation paths in inputs.
        Returns:
        - True if all went well
        - False if wallet doesn't own input
        """
        if not self.owns(scope):
            return False
        der = self.get_derivation(
            scope.bip32_derivations, getattr(scope, "taproot_bip32_derivations", {})
        )
        if der is None:
            return False
        idx, branch_idx = der
        desc = self.descriptor.derive(idx, branch_index=branch_idx)
        # find keys with our fingerprint
        for key in desc.keys:
            if key.fingerprint == fingerprint:
                pub = key.get_public_key()
                # fill our derivations
                scope.bip32_derivations[pub] = DerivationPath(
                    fingerprint, key.derivation
                )
        # if liquid - unblind / blind etc
        if desc.is_blinded:
            try:
                if not self.fill_pset_scope(scope, desc, stream, rangeproof_offset, surj_proof_offset):
                    return False
            except RewindError as e:
                print(e)
                return False
        # fill script
        scope.witness_script = desc.witness_script()
        scope.redeem_script = desc.redeem_script()
        return True

    def fill_pset_scope(self, scope, desc, stream=None, rangeproof_offset=None, surj_proof_offset=None):
        # An output is ours only if it is provably blinded to our blinding key.
        # Otherwise the host could blind our change to its own key: we could
        # not unblind the output, and so not spend it, without that key.
        is_output = isinstance(scope, LOutputScope)
        # The device blinds an output to its blinding pubkey from the PSET.
        # This must run before the early return below: when the device
        # blinds the output itself there is no rangeproof yet.
        if is_output:
            bkey = desc.blinding_key.get_blinding_key(scope.script_pubkey)
            bpub = bkey.get_public_key() if bkey.is_private else bkey
            if scope.blinding_pubkey != bpub.sec():
                return False
        # if we don't have a rangeproof offset - nothing we can really do
        if rangeproof_offset is None:
            return True
        # Only a private blinding key can rewind the host's rangeproof. With a
        # watch-only blinding key we cannot tell whose key the proof is for.
        if is_output and not bkey.is_private:
            return False
        # pointer and length of preallocated memory for rangeproof rewind
        memptr, memlen = get_preallocated_ram()
        # For inputs, skip the rewind if the host supplied all values.
        # Outputs are always rewound: the blinding pubkey field does not bind
        # the host's nonce and rangeproof, which may be made for any key.
        if not is_output and None not in [scope.asset, scope.value, scope.asset_blinding_factor, scope.value_blinding_factor]:
            # verify that asset and value blinding factors lead to value and asset commitments
            return True
        stream.seek(rangeproof_offset)
        l = compact.read_from(stream)
        vout = scope.utxo if isinstance(scope, LInputScope) else scope.blinded_vout
        blinding_key = desc.blinding_key.get_blinding_key(vout.script_pubkey).secret
        # get the nonce for unblinding
        pub = secp256k1.ec_pubkey_parse(vout.ecdh_pubkey)
        secp256k1.ec_pubkey_tweak_mul(pub, blinding_key)
        sec = secp256k1.ec_pubkey_serialize(pub)
        nonce = hashlib.sha256(hashlib.sha256(sec).digest()).digest()
        commit = secp256k1.pedersen_commitment_parse(vout.value)
        gen = secp256k1.generator_parse(vout.asset)
        try:
            value, vbf, msg, _, _ = secp256k1.rangeproof_rewind_from(
                stream, l, memptr, memlen,
                nonce, commit, vout.script_pubkey.data, gen
            )
        except ValueError as e:
            raise RewindError(str(e))
        asset = msg[:32]
        abf = msg[32:64]
        # These replace any values the host supplied. The rewind binds value
        # and vbf to the commitment, but asset and abf come from the proof's
        # message; the caller's verify() rejects ones that do not open the
        # asset commitment.
        scope.value = value
        scope.value_blinding_factor = vbf
        scope.asset = asset
        scope.asset_blinding_factor = abf
        return True
