#ifndef SPECTER_EVIDENCE_PY_OBJ_H
#define SPECTER_EVIDENCE_PY_OBJ_H

#include <stdint.h>

typedef uintptr_t mp_obj_t;
#define MP_DECLARE_CONST_FUN_OBJ_0(name) extern const int name
#define MP_DEFINE_CONST_FUN_OBJ_0(name, function) const int name = 0

static inline mp_obj_t mp_obj_new_int(uint32_t value) {
    return value;
}

#endif
