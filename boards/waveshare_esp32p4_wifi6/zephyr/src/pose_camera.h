/* SPDX-License-Identifier: MIT */
#ifndef P4_POSE_CAMERA_H
#define P4_POSE_CAMERA_H
#include <stdbool.h>
#include <stddef.h>
void p4_pose_camera_enable(bool enabled);
void p4_pose_camera_reset(bool disable);
void p4_pose_camera_poll(void);
void p4_pose_camera_message(int type,int bytes,const char *body);
void p4_pose_camera_status(char *out,size_t bytes);
#endif
