/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
void p4_nn_init(void);
int p4_nn_available(void);
uint32_t p4_nn_builtin(const char *name);
int p4_nn_busy(void);
int p4_nn_ready(uint32_t token);
uint32_t p4_nn_current(void);
int p4_nn_set_value(uint32_t token,unsigned index,int value_milli);
int p4_nn_output_value(uint32_t token,unsigned index,int *value_milli);
int p4_nn_run(uint32_t token,unsigned repetitions);
void p4_nn_cancel(void);
int p4_nn_unload(uint32_t token);
void p4_nn_status(char *out,size_t n);
void p4_nn_info(uint32_t token,char *out,size_t n);
void p4_nn_capabilities(char *out,size_t n);
void p4_nn_poll(void);
/* Bounded binary protocol, no VM/GC object is retained by the backend. */
int p4_nn_transfer(unsigned op,uint32_t *token,uint32_t offset,uint32_t arg,
 const uint8_t *data,unsigned count,uint8_t *out,unsigned *bytes);
#ifdef __cplusplus
}
#endif
