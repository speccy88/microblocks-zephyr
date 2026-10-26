/* SPDX-License-Identifier: MIT */
#include "kws_backend.h"
#include <stdio.h>
void p4_kws_init(void){}
int p4_kws_available(void){return 0;}
int p4_kws_fixture(unsigned id){(void)id;return 0;}
int p4_kws_clip(int h){(void)h;return 0;}
int p4_kws_listen(unsigned ms,unsigned c,unsigned d){(void)ms;(void)c;(void)d;return 0;}
int p4_kws_listening(void){return 0;}
int p4_kws_busy(void){return 0;}
void p4_kws_cancel(void){}
int p4_kws_take_event(void){return 0;}
unsigned p4_kws_confidence(void){return 0;}
const char *p4_kws_state(void){return "Wake-word model not installed";}
int p4_kws_scores(unsigned o,unsigned n,uint8_t *p){(void)o;(void)n;(void)p;return 0;}
void p4_kws_status(char *p,size_t n){snprintf(p,n,"{\"available\":false,\"busy\":false,\"listening\":false,\"phase\":\"unavailable\",\"message\":\"wake-word model not installed\"}");}
