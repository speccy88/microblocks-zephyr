/* SPDX-License-Identifier: MPL-2.0 */
/* Actual SmallVM bridge. All entry points are called on the VM thread. */
#include "vm/interp.h"
#include "storage_primitives.h"
#include "storage_protocol.h"
#include "controller.h"
#if defined(CONFIG_P4_SD_FILES)
#include "sd_wire.h"
#endif
/* CPU-only staging; no DMA/ISR access. Preserve scarce internal SRAM on P4. */
#if defined(CONFIG_ESP_SPIRAM)
#define STORAGE_TRANSFER __attribute__((section(".ext_ram.bss.storage_transfer"), aligned(16)))
#else
#define STORAGE_TRANSFER
#endif
/* Only the VM thread touches session metadata, after init() establishes it. */
static mb_files_controller controller STORAGE_TRANSFER;
static mb_files_wire_workspace workspace STORAGE_TRANSFER;
static uint8_t response[MB_FILES_RESPONSE_MAX] STORAGE_TRANSFER;
static bool initialized;
static void init(void){if(!initialized){mb_files_controller_init(&controller,mb_storage_store());initialized=true;}}
void mb_storage_protocol_reset(void){
 if(initialized)mb_files_controller_reset(&controller);
#if defined(CONFIG_P4_SD_FILES)
 mb_sd_files_wire_reset();
#endif
}
void mb_storage_protocol_poll(uint64_t now,bool connected){
 if(!initialized)return;
 if(!connected)mb_storage_protocol_reset();else {
  mb_files_controller_poll(&controller,now);
#if defined(CONFIG_P4_SD_FILES)
  if(!controller.dispatcher.owner)mb_sd_files_wire_reset();
#endif
 }
}
void mb_storage_protocol_message(int type,int bytes,const char *body,uint64_t now){
 if(type!=MB_FILES_MESSAGE||bytes<0||bytes>MB_FILES_REQUEST_MAX)return;
 /* Reserve response space before processing any mutating operation. */
 if(!hasOutputSpace(MB_FILES_RESPONSE_MAX+5))return;
 init();size_t n=0;
#if defined(CONFIG_P4_SD_FILES)
 if(bytes>=6&&((const uint8_t*)body)[5]>=MB_SD_CAPS) {
  if(mb_sd_files_wire(&controller.dispatcher,1,now,(const uint8_t*)body,(size_t)bytes,response,sizeof(response),&n))
   waitAndSendMessage(MB_FILES_MESSAGE,0,(int)n,(char*)response);
  return;
 }
#endif
 if(mb_files_controller_message(&controller,1,now,(const uint8_t *)body,(size_t)bytes,
     response,sizeof(response),&n,&workspace))
  waitAndSendMessage(MB_FILES_MESSAGE,0,(int)n,(char *)response);
}
