/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
OBJ kws_available(int,OBJ *);OBJ kws_fixture(int,OBJ *);OBJ kws_clip(int,OBJ *);
OBJ kws_busy(int,OBJ *);OBJ kws_cancel(int,OBJ *);OBJ kws_status(int,OBJ *);OBJ kws_scores(int,OBJ *);
OBJ kws_state(int,OBJ *);OBJ kws_confidence(int,OBJ *);
OBJ kws_listen(int,OBJ *);OBJ kws_listening(int,OBJ *);
void p4_kws_poll(void);
#define KWS_PRIMITIVE_ENTRIES \
 {"kwsAvailable",kws_available},{"kwsFixture",kws_fixture},{"kwsClip",kws_clip},{"kwsBusy",kws_busy}, \
 {"kwsCancel",kws_cancel},{"kwsStatus",kws_status},{"kwsScores",kws_scores}, \
 {"kwsState",kws_state},{"kwsConfidence",kws_confidence},{"kwsListen",kws_listen},{"kwsListening",kws_listening},
