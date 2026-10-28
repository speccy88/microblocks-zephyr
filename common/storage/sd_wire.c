/* SPDX-License-Identifier: MIT */
#include "sd_wire.h"
#include "sd_file.h"
#include "sd_service.h"
#include <string.h>
#if defined(CONFIG_ESP_SPIRAM)
#define SD_WIRE_STATE __attribute__((section(".ext_ram.bss.sd_wire"),aligned(16)))
#else
#define SD_WIRE_STATE
#endif
static struct {
 uint8_t staging[MB_SD_FILE_BYTES];
 char name[MB_SD_NAME_BYTES];
 uint32_t generation,token,session,native_generation;
 uint16_t expected,received;
 bool receiving,running;
} transfer SD_WIRE_STATE;
static uint16_t u16(const uint8_t *p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t u32(const uint8_t *p){return u16(p)|((uint32_t)u16(p+2)<<16);}
static void p16(uint8_t *p,uint16_t n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void p32(uint8_t *p,uint32_t n){p16(p,(uint16_t)n);p16(p+2,(uint16_t)(n>>16));}
void mb_sd_files_wire_reset(void) {
 if(!transfer.session&&!transfer.token&&!transfer.receiving&&!transfer.running)return;
 if(transfer.running&&transfer.native_generation==mb_sd_file_generation())mb_sd_cancel();
 transfer.receiving=transfer.running=false;transfer.token=transfer.session=0;
 memset(transfer.staging,0,sizeof(transfer.staging));transfer.name[0]=0;
}
static bool new_token(void) {
 if(transfer.generation==MB_FILE_REFERENCE_MAX)return false;
 transfer.token=++transfer.generation;return true;
}
bool mb_sd_files_wire(mb_files_dispatcher *d,uint32_t owner,uint64_t now,
 const uint8_t *in,size_t n,uint8_t *out,size_t capacity,size_t *written) {
 if(written)*written=0;
 if(!d||!in||!out||!written||capacity<MB_FILES_RESPONSE_MAX||n<26||n>MB_FILES_REQUEST_MAX||
    memcmp(in,"MBFS",4)||in[4]!=1||in[25]||in[5]<MB_SD_CAPS||in[5]>MB_SD_LIST)return false;
 uint8_t op=in[5],names=in[24];uint16_t count=u16(in+22);
 uint32_t id=u32(in+6),session=u32(in+10),token=u32(in+14),arg=u32(in+18);
 size_t data=op==MB_SD_APPEND?count:0;
 if(names>=MB_SD_NAME_BYTES||count>MB_FILES_CHUNK||n!=26+names+data)return false;
 memcpy(out,"MBFR",4);out[4]=1;out[5]=op;p32(out+6,id);p32(out+10,session);out[14]=0;out[15]=0;
 size_t used=16;mb_files_status status=MB_FILES_OK;
 if(mb_files_expire(d,now)){mb_sd_files_wire_reset();status=MB_FILES_TIMEOUT;goto done;}
 if(!owner||owner!=d->owner||!session||session!=d->session){status=MB_FILES_DISCONNECTED;goto done;}
 if(!id||id<=d->last_id){status=MB_FILES_PROTOCOL;goto done;}
 d->last_id=id;
 if(transfer.session&&transfer.session!=session)mb_sd_files_wire_reset();
 transfer.session=session;
 bool named=op==MB_SD_BEGIN||op==MB_SD_READ||op==MB_SD_REMOVE;
 if(named?!mb_sd_file_name((const char*)in+26,names):names!=0){status=MB_FILES_PATH;goto done;}
 switch(op) {
 case MB_SD_CAPS:case MB_SD_LIST:
  if(token||arg||count)status=MB_FILES_PROTOCOL;
  break;
 case MB_SD_BEGIN:if(token||arg>MB_SD_FILE_BYTES||count)status=MB_FILES_PROTOCOL;break;
 case MB_SD_READ:case MB_SD_REMOVE:if(token||arg||count)status=MB_FILES_PROTOCOL;break;
 case MB_SD_APPEND:if(!token||!count)status=MB_FILES_PROTOCOL;break;
 case MB_SD_CHUNK:if(!token||!count)status=MB_FILES_PROTOCOL;break;
 default:if(!token||arg||count)status=MB_FILES_PROTOCOL;break;
 }
 if(status)goto done;
 d->last_ms=now;
 if(op==MB_SD_CAPS) {
  out[used++]=mb_sd_file_available()?1:0;p16(out+used,MB_SD_FILE_BYTES);used+=2;
  p16(out+used,MB_FILES_CHUNK);used+=2;out[used++]=8;out[used++]=3;goto done;
 }
 if(!mb_sd_file_available()){status=MB_FILES_UNAVAILABLE;goto done;}
 if(op==MB_SD_BEGIN||op==MB_SD_READ||op==MB_SD_REMOVE||op==MB_SD_LIST) {
  if(transfer.receiving||mb_sd_busy()){status=MB_FILES_BUSY;goto done;}
  if(!new_token()){status=MB_FILES_FULL;goto done;}
  memset(transfer.staging,0,sizeof(transfer.staging));memset(transfer.name,0,sizeof(transfer.name));
  if(names)memcpy(transfer.name,in+26,names);
  transfer.expected=(uint16_t)arg;transfer.received=0;transfer.running=false;
  if(op==MB_SD_BEGIN)transfer.receiving=true;
  else {
   mb_sd_file_op job=op==MB_SD_READ?MB_SD_FILE_READ:op==MB_SD_LIST?MB_SD_FILE_LIST:MB_SD_FILE_REMOVE_OWN;
   if(!mb_sd_file_start(job,transfer.name,names,NULL,0)){status=MB_FILES_STATE;transfer.token=0;goto done;}
   transfer.running=true;transfer.native_generation=mb_sd_file_generation();
  }
  p32(out+used,transfer.token);used+=4;goto done;
 }
 if(!transfer.token||token!=transfer.token){status=MB_FILES_CONFLICT;goto done;}
 if(op==MB_SD_APPEND) {
  if(!transfer.receiving){status=MB_FILES_STATE;goto done;}
  if(arg!=transfer.received||count>transfer.expected-transfer.received){status=MB_FILES_SIZE;goto done;}
  memcpy(transfer.staging+arg,in+26,count);transfer.received+=count;
  p16(out+used,transfer.received);used+=2;goto done;
 }
 if(op==MB_SD_CREATE) {
  if(!transfer.receiving||transfer.received!=transfer.expected){status=MB_FILES_STATE;goto done;}
  if(!mb_sd_file_start(MB_SD_FILE_CREATE,transfer.name,strlen(transfer.name),transfer.staging,transfer.expected)){status=MB_FILES_BUSY;goto done;}
  transfer.receiving=false;transfer.running=true;transfer.native_generation=mb_sd_file_generation();
  memset(transfer.staging,0,sizeof(transfer.staging));p32(out+used,token);used+=4;goto done;
 }
 if(op==MB_SD_CANCEL) {
  if(transfer.receiving){transfer.receiving=false;memset(transfer.staging,0,sizeof(transfer.staging));}
  if(transfer.running&&transfer.native_generation==mb_sd_file_generation())mb_sd_cancel();
  out[used++]=1;goto done;
 }
 if(!transfer.running||transfer.native_generation!=mb_sd_file_generation()){status=MB_FILES_CONFLICT;goto done;}
 mb_sd_file_result result;
 bool finished=mb_sd_file_result_get(&result);
 if(op==MB_SD_STATUS) {
  out[used++]=finished?0:1;
  p32(out+used,finished?(uint32_t)result.error:0);used+=4;
  p16(out+used,finished?(uint16_t)result.bytes:0);used+=2;
  out[used++]=finished?(result.created?1:0)|(result.synced?2:0)|(result.verified?4:0)|(result.removed?8:0)|(result.truncated?16:0):0;
  size_t size=strlen(transfer.name);out[used++]=(uint8_t)size;memcpy(out+used,transfer.name,size);used+=size;
 } else if(op==MB_SD_CHUNK) {
  if(!finished){status=MB_FILES_BUSY;goto done;}
  if(result.error||arg>result.bytes||count>result.bytes-arg){status=MB_FILES_SIZE;goto done;}
  if(!mb_sd_file_copy(arg,out+used+2,count)){status=MB_FILES_CONFLICT;goto done;}
  p16(out+used,count);used+=2+count;
 }
done:
 out[14]=(uint8_t)status;*written=status?16:used;return true;
}
