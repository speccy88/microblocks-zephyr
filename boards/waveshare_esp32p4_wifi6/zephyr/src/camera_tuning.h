/* SPDX-License-Identifier: MIT */
#pragma once
#include <stddef.h>
void p4_camera_tuning_message(int type,int bytes,const char *body);
void p4_camera_tuning_poll(void);
void p4_camera_tuning_reset(void);
int p4_camera_tuning_settings(int exposure,int analog,int digital);
void p4_camera_tuning_status(char *out,size_t n);
void p4_camera_tuning_open(void);
