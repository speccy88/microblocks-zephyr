/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum { VOICE_ACTIONS=8,VOICE_CLASSES=10 };
typedef struct {
    uint16_t smooth[10],threshold,cooldown;
    uint8_t candidate,stable,release;
    bool initialized,armed,has_event;
    uint32_t last_event;
} voice_decision;
void voice_decision_begin(voice_decision *,unsigned threshold,unsigned cooldown);
/* Scores are 0..1000; at most one accepted action until sustained release.
 * Return -1 for rejection, otherwise 0..7. Time uses wrap-safe uint32 math. */
int voice_decision_push(voice_decision *,const uint16_t scores[10],uint32_t ms);
#ifdef __cplusplus
}
#endif
