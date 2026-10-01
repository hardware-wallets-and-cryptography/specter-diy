#define BL_ICR_DEFINE_PRIVATE_TYPES
#include "catch2/catch.hpp"
#include "crc32.h"
#include "flash_buf.hpp"
#include "bl_integrity_check.h"

TEST_CASE("F-25 recomputed CRCs cannot authorize modified firmware", "[F-25]") {
  const uint8_t original[] = {0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef};
  FlashBuf flash(original, sizeof(original), BL_FW_SECT_OVERHEAD);
  REQUIRE(bl_icr_create(flash.base(), flash.size(), sizeof(original), 1));
  REQUIRE(bl_icr_verify(flash.base(), flash.size(), nullptr));

  flash[0] ^= 0x01;
  const auto record_offset = flash.size() - BL_ICR_OFFSET_FROM_END;
  bl_integrity_check_rec_t record;
  memcpy(&record, flash + record_offset, sizeof(record));
  record.main_sect.pl_crc = crc32_fast(flash, sizeof(original), 0U);
  record.struct_crc = crc32_fast(&record, ICR_CRC_CHECKED_SIZE, 0U);
  memcpy(flash + record_offset, &record, sizeof(record));

  REQUIRE(record.main_sect.pl_crc == crc32_fast(flash, sizeof(original), 0U));
  REQUIRE(record.struct_crc == crc32_fast(&record, ICR_CRC_CHECKED_SIZE, 0U));
  REQUIRE_FALSE(bl_icr_verify(flash.base(), flash.size(), nullptr));
}
