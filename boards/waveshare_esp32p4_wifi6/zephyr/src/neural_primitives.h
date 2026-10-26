/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
/* Include after vm/interp.h (the upstream VM header has no include guard). */
OBJ nn_available(int,OBJ *);OBJ nn_load(int,OBJ *);OBJ nn_busy(int,OBJ *);OBJ nn_ready(int,OBJ *);
OBJ nn_info(int,OBJ *);OBJ nn_status(int,OBJ *);OBJ nn_caps(int,OBJ *);OBJ nn_set(int,OBJ *);
OBJ nn_run(int,OBJ *);OBJ nn_output(int,OBJ *);OBJ nn_cancel(int,OBJ *);OBJ nn_unload(int,OBJ *);
OBJ nn_input_bytes(int,OBJ *);OBJ nn_output_bytes(int,OBJ *);
OBJ nn_current(int,OBJ *);
#define NN_PRIMITIVE_ENTRIES \
 {"nnAvailable",nn_available},{"nnLoadBuiltin",nn_load},{"nnBusy",nn_busy},{"nnReady",nn_ready}, \
 {"nnModelInfo",nn_info},{"nnStatus",nn_status},{"nnCapabilities",nn_caps},{"nnSetValue",nn_set}, \
 {"nnRun",nn_run},{"nnOutputValue",nn_output},{"nnCancel",nn_cancel},{"nnUnload",nn_unload}, \
 {"nnInputBytes",nn_input_bytes},{"nnOutputBytes",nn_output_bytes},{"nnCurrentModel",nn_current},
void p4_nn_message(int,int,char *);
