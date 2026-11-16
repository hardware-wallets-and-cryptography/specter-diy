#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rng.h"

static evidence_rng_t peripheral;
evidence_rng_t *RNG = &peripheral;
static uint32_t ticks;

uint32_t HAL_GetTick(void) {
    return ticks++;
}

// A production definition overrides this fallback once faults are reported.
__attribute__((weak)) volatile uint32_t rng_last_error;

int main(int argc, char **argv) {
    if (argc != 2) {
        return 2;
    }
    peripheral.DR = 0x12345678U;
    if (strcmp(argv[1], "healthy") == 0) {
        peripheral.SR = RNG_SR_DRDY;
        if (rng_get() == peripheral.DR) {
            return 0;
        }
        fputs("healthy RNG word was not returned\n", stderr);
        return 1;
    }
    if (strcmp(argv[1], "timeout") == 0) {
        peripheral.SR = 0;
    } else if (strcmp(argv[1], "seed") == 0) {
        peripheral.SR = RNG_SR_SECS;
    } else if (strcmp(argv[1], "clock") == 0) {
        peripheral.SR = RNG_SR_DRDY | RNG_SR_CECS;
    } else {
        return 2;
    }
    rng_get();
    if (rng_last_error == 0) {
        fprintf(stderr, "F-18: %s fault was not reported by rng_get\n", argv[1]);
        return 1;
    }
    return 0;
}
