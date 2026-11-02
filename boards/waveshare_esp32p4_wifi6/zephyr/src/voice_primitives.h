/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
OBJ voice_available(int,OBJ *);OBJ voice_listen(int,OBJ *);OBJ voice_stop(int,OBJ *);
OBJ voice_command(int,OBJ *);OBJ voice_confidence(int,OBJ *);OBJ voice_score(int,OBJ *);
OBJ voice_status(int,OBJ *);OBJ voice_clip(int,OBJ *);
void p4_voice_poll(void);
#define VOICE_PRIMITIVE_ENTRIES \
 {"voiceAvailable",voice_available},{"voiceListen",voice_listen},{"voiceStop",voice_stop}, \
 {"voiceCommand",voice_command},{"voiceConfidence",voice_confidence},{"voiceScore",voice_score}, \
 {"voiceStatus",voice_status},{"voiceClip",voice_clip},
