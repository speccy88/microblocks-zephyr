/* SPDX-License-Identifier: MPL-2.0 */
/* SmallVM adapter: portable service, no GPIO/network/Zephyr dependencies. */
#include "vm/interp.h"
#include "json_service.h"
#include <string.h>
#if defined(CONFIG_ESP_SPIRAM)
#define JSON_SCRATCH __attribute__((section(".ext_ram.bss.json"),aligned(16)))
#else
#define JSON_SCRATCH
#endif
/* Only the VM thread calls these synchronous primitives. No yielding or native
 * worker may share scratch. Results are copied after native parsing completes. */
static union {long double alignment;unsigned char bytes[MB_JSON_ARENA_BYTES];} arena JSON_SCRATCH;
static char output[MB_JSON_MAX_BYTES+1] JSON_SCRATCH;
static mb_json_error last_error;
static void clear_bytes(void *p,size_t n) {volatile unsigned char *b=p;while(n--) *b++=0;}
static OBJ run(mb_json_op op,int n,OBJ *args,int expected) {
 if(n!=expected) {last_error=MB_JSON_BAD_ARGUMENT;return fail(notEnoughArguments);}
 for(int i=0;i<n;i++) if(!IS_TYPE(args[i],StringType)) {last_error=MB_JSON_BAD_ARGUMENT;return fail(needsStringError);}
 const char *input=obj2str(args[0]),*path=n>1?obj2str(args[1]):"",*value=n>2?obj2str(args[2]):"";
 size_t lengths[3]={0,0,0},length=0;
 for(int i=0;i<n;i++) {
  last_error=mb_json_padded_text_length(obj2str(args[i]),4*(size_t)WORDS(args[i]),i==1?MB_JSON_MAX_PATH:MB_JSON_MAX_BYTES,&lengths[i]);
  if(last_error) return falseObj;
 }
 size_t a=lengths[0],b=lengths[1],c=lengths[2];
 last_error=mb_json_run(op,input,a,path,b,value,c,arena.bytes,sizeof(arena.bytes),output,sizeof(output),&length);
 clear_bytes(arena.bytes,sizeof(arena.bytes));
 OBJ result=falseObj;
 if(last_error==MB_JSON_OK) {
  result=op==MB_JSON_VALIDATE?trueObj:newStringFromBytes(output,length);
  if(result==falseObj) last_error=MB_JSON_MEMORY;
 }
 clear_bytes(output,sizeof(output));
 return result;
}
#define PRIM(name,op,count) static OBJ name(int n,OBJ *a){return run(op,n,a,count);}
PRIM(valid,MB_JSON_VALIDATE,1) PRIM(compact,MB_JSON_COMPACT,1)
PRIM(get,MB_JSON_GET,2) PRIM(text,MB_JSON_TEXT,2) PRIM(type,MB_JSON_TYPE,2)
PRIM(length,MB_JSON_LENGTH,2) PRIM(keys,MB_JSON_KEYS,2) PRIM(set,MB_JSON_SET,3)
PRIM(remove_value,MB_JSON_REMOVE,2) PRIM(append,MB_JSON_APPEND,3) PRIM(quote,MB_JSON_QUOTE,1)
static OBJ status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);const char *s=mb_json_error_text(last_error);return newStringFromBytes(s,strlen(s));}
static OBJ available(int n,OBJ *a){(void)a;return n?fail(notEnoughArguments):trueObj;}
static PrimEntry entries[]={
 {"valid",valid},{"compact",compact},{"get",get},{"text",text},{"type",type},{"length",length},
 {"keys",keys},{"set",set},{"remove",remove_value},{"append",append},{"quote",quote},{"status",status},{"available",available}};
void addJSONPrims(void){addPrimitiveSet(JSONPrims,"json",sizeof(entries)/sizeof(entries[0]),entries);}
