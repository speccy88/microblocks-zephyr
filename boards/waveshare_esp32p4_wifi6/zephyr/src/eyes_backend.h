/* SPDX-License-Identifier: MIT */
#ifndef P4_EYES_BACKEND_H
#define P4_EYES_BACKEND_H
#include "eyes.h"
#include "pose.h"
#include "face.h"
void p4_eyes_init(void);
bool p4_eyes_begin(int height,int controller,int address);
bool p4_eyes_get(eyes_config *out);
bool p4_eyes_set(const eyes_config *config);
bool p4_eyes_action(unsigned action);
bool p4_eyes_ready(void);
bool p4_eyes_probe(void);
bool p4_eyes_probing(void);
int p4_eyes_address(void);
void p4_eyes_bus_status(char *out,size_t bytes);
void p4_eyes_status(char *out,size_t bytes);
void p4_eyes_stop(void);
void p4_eyes_poll(void);
void p4_pose_message(int type,int bytes,const char *body);
void p4_pose_reset(void);
void p4_pose_follow(bool follow,bool react);
pose_state p4_pose_snapshot(void);
face_state p4_face_snapshot(void);
void p4_attention_enable(bool enabled,unsigned idle_mode);
const char *p4_attention_status(void);
void addEyesPrims(void);
void addPosePrims(void);
#endif
