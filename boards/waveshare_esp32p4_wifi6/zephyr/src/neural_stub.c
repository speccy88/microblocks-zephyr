/* SPDX-License-Identifier: MPL-2.0 */
#include "neural_backend.h"
#include <stdio.h>
#include <string.h>
void p4_nn_init(void){}
int p4_nn_available(void){return 0;}
uint32_t p4_nn_builtin(const char *s){(void)s;return 0;}
int p4_nn_busy(void){return 0;}
int p4_nn_ready(uint32_t t){(void)t;return 0;}
uint32_t p4_nn_current(void){return 0;}
int p4_nn_set_value(uint32_t t,unsigned i,int v){(void)t;(void)i;(void)v;return 0;}
int p4_nn_output_value(uint32_t t,unsigned i,int *v){(void)t;(void)i;(void)v;return 0;}
int p4_nn_run(uint32_t t,unsigned r){(void)t;(void)r;return 0;}
void p4_nn_cancel(void){}
int p4_nn_unload(uint32_t t){(void)t;return 0;}
void p4_nn_status(char *s,size_t n){snprintf(s,n,"{\"phase\":\"unsupported\",\"message\":\"build the native neural profile\"}");}
void p4_nn_info(uint32_t t,char *s,size_t n){(void)t;p4_nn_status(s,n);}
void p4_nn_capabilities(char *s,size_t n){snprintf(s,n,"{\"available\":false,\"direct_onnx_runtime\":false,\"reason\":\"native neural profile required\"}");}
void p4_nn_poll(void){}
int p4_nn_transfer(unsigned op,uint32_t *t,uint32_t o,uint32_t a,const uint8_t *d,unsigned c,uint8_t *out,unsigned *n)
{(void)t;(void)o;(void)a;(void)d;(void)c;if(op==0){p4_nn_capabilities((char *)out,*n);*n=strlen((char *)out);return 0;}*n=0;return 3;}
