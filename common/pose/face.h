/* SPDX-License-Identifier: MIT */
#ifndef MB_FACE_H
#define MB_FACE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    bool received,visible;
    uint8_t left_eye,right_eye,head,look;
    uint16_t x,y;
    uint32_t sequence;
    int64_t received_ms;
} face_state;
bool face_receive(face_state *state,const uint8_t *data,size_t bytes,int64_t now);
bool face_fresh(const face_state *state,int64_t now);
typedef struct {bool enabled,seen;unsigned idle_mode,state;int x,y;int64_t idle_since,last_seen;} eyes_attention;
enum {ATTENTION_OFF,ATTENTION_WANDER,ATTENTION_DROWSY,ATTENTION_SLEEP,ATTENTION_HAPPY,ATTENTION_HOLD};
void attention_enable(eyes_attention *state,bool enabled,unsigned idle_mode,int64_t now);
unsigned attention_update(eyes_attention *state,const face_state *face,int64_t now);
const char *attention_name(unsigned state);
#endif
