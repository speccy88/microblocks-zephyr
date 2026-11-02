/* SPDX-License-Identifier: MIT */
#ifndef MB_POSE_H
#define MB_POSE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
enum { POSE_NEUTRAL,POSE_LEFT_UP,POSE_RIGHT_UP,POSE_BOTH_UP,POSE_ARMS_OUT,POSE_WAVE };
typedef struct {bool received,visible;uint32_t sequence;uint64_t updated;uint16_t x,y,confidence;uint8_t gesture;} pose_state;
bool pose_receive(pose_state *state,const uint8_t *body,size_t bytes,uint64_t now);
bool pose_fresh(const pose_state *state,uint64_t now);
const char *pose_gesture(unsigned gesture);
#endif
