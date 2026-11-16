#ifndef SPECTER_EVIDENCE_RNG_STUBS_H
#define SPECTER_EVIDENCE_RNG_STUBS_H

#include <stdint.h>

#define MICROPY_HW_ENABLE_RNG (1)
#define STATIC static
#define RNG_CR_RNGEN (1U)
#define RNG_SR_DRDY (1U)
#define RNG_SR_SECS (2U)
#define RNG_SR_CECS (4U)
#define __HAL_RCC_RNG_CLK_ENABLE() ((void)0)

typedef struct {
    uint32_t CR;
    uint32_t SR;
    uint32_t DR;
} evidence_rng_t;

extern evidence_rng_t *RNG;
uint32_t HAL_GetTick(void);

#endif
