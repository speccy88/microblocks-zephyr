/* SPDX-License-Identifier: MIT */
#ifndef MB_POSE_CAMERA_WIRE_H
#define MB_POSE_CAMERA_WIRE_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef struct {uint8_t operation;uint32_t request,session,offset;uint16_t count;} pose_camera_request;
bool pose_camera_decode(const uint8_t *data,size_t bytes,pose_camera_request *out);
void pose_camera_reply(uint8_t *out,const pose_camera_request *request,uint8_t status,uint8_t state);
#endif
