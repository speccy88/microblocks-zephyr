/* SPDX-License-Identifier: MIT */
#include "controller.h"
#include <string.h>
static uint32_t get32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void put32(uint8_t *p,uint32_t n){for(unsigned i=0;i<4;i++)p[i]=(uint8_t)(n>>(8*i));}
void mb_files_controller_init(mb_files_controller *c,mb_store *store){memset(c,0,sizeof(*c));mb_files_init(&c->dispatcher,store);}
void mb_files_controller_reset(mb_files_controller *c){
 (void)mb_files_close(&c->dispatcher,c->dispatcher.owner,c->dispatcher.session);c->nonce=0;
}
void mb_files_controller_poll(mb_files_controller *c,uint64_t now){if(mb_files_expire(&c->dispatcher,now))c->nonce=0;}
bool mb_files_controller_message(mb_files_controller *c,uint32_t owner,uint64_t now,
 const uint8_t *in,size_t n,uint8_t *out,size_t cap,size_t *written,mb_files_wire_workspace *workspace){
 if(written)*written=0;
 if(!c||!in||!out||!written||!workspace||cap<MB_FILES_RESPONSE_MAX||n<MB_FILES_REQUEST_HEADER)return false;
 if(in[5]!=MB_FILES_OPEN&&in[5]!=MB_FILES_CLOSE)
  return mb_files_wire(&c->dispatcher,owner,now,in,n,out,cap,written,workspace);
 if(n!=26||memcmp(in,"MBFS",4)||in[4]!=1||in[25]||in[24]||in[22]||in[23]||get32(in+18))return false;
 uint32_t id=get32(in+6),session=get32(in+10),nonce=get32(in+14);unsigned op=in[5];
 if(!id||!owner||(op==MB_FILES_OPEN?session||!nonce:!session||nonce))return false;
 mb_files_controller_poll(c,now);
 mb_files_status status=MB_FILES_OK;
 if(op==MB_FILES_OPEN){
  if(c->dispatcher.owner){
   if(c->dispatcher.owner!=owner||c->nonce!=nonce)status=MB_FILES_BUSY;
   /* Duplicate opens cannot reset the data request sequence or staging. */
  }else{status=mb_files_open(&c->dispatcher,owner,now,&session);if(!status)c->nonce=nonce;}
 }else if(!mb_files_close(&c->dispatcher,owner,session))status=MB_FILES_DISCONNECTED;
 else c->nonce=0;
 memcpy(out,"MBFR",4);out[4]=1;out[5]=(uint8_t)op;put32(out+6,id);put32(out+10,get32(in+10));out[14]=(uint8_t)status;out[15]=0;
 size_t size=16;
 if(!status){if(op==MB_FILES_OPEN){put32(out+16,c->dispatcher.session);put32(out+20,c->nonce);size=24;}else{out[16]=1;size=17;}}
 *written=size;return true;
}
