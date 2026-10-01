#define BLSIG_DEFINE_PRIVATE_TYPES
#include <cstdlib>
#include <fstream>
#include <memory>
#include <string>
#include "catch2/catch.hpp"
#include "bl_signature.h"
#include "secp256k1.h"

extern "C" {
bool verify_signature(secp256k1_context* verify_ctx, const signature_t* sig,
                      const uint8_t* message, size_t message_len,
                      const bl_pubkey_t* pubkey);
secp256k1_context* create_verify_ctx(void);
void destroy_verify_ctx(secp256k1_context* verify_ctx);
}

TEST_CASE("F-17 user-message signature cannot authorize firmware", "[F-17]") {
  const char* fixture_path = std::getenv("SPECTER_EVIDENCE_SIGNATURE");
  REQUIRE(fixture_path != nullptr);
  std::ifstream fixture(fixture_path, std::ios::binary);
  REQUIRE(fixture.is_open());

  uint8_t message_len = 0;
  fixture.read(reinterpret_cast<char*>(&message_len), 1);
  REQUIRE(fixture.good());
  REQUIRE(message_len > 0);
  REQUIRE(message_len <= 0xFC);
  std::string message(message_len, '\0');
  uint8_t digest[32];
  signature_t signature;
  bl_pubkey_t pubkey;
  fixture.read(&message[0], message.size());
  fixture.read(reinterpret_cast<char*>(digest), sizeof(digest));
  fixture.read(reinterpret_cast<char*>(signature.bytes), sizeof(signature.bytes));
  fixture.read(reinterpret_cast<char*>(pubkey.bytes), sizeof(pubkey.bytes));
  REQUIRE(fixture.good());
  REQUIRE(fixture.peek() == std::char_traits<char>::eof());

  std::unique_ptr<secp256k1_context, decltype(&destroy_verify_ctx)>
      verifier(create_verify_ctx(), destroy_verify_ctx);
  REQUIRE(verifier);

  secp256k1_pubkey public_key;
  secp256k1_ecdsa_signature user_signature;
  REQUIRE(secp256k1_ec_pubkey_parse(verifier.get(), &public_key,
                                    pubkey.bytes, sizeof(pubkey.bytes)) == 1);
  REQUIRE(secp256k1_ecdsa_signature_parse_compact(
              verifier.get(), &user_signature, signature.bytes) == 1);
  REQUIRE(secp256k1_ecdsa_verify(verifier.get(), &user_signature, digest,
                                 &public_key) == 1);

  REQUIRE_FALSE(verify_signature(verifier.get(), &signature,
                                 reinterpret_cast<const uint8_t*>(message.data()),
                                 message.size(), &pubkey));
}
