/* SPDX-License-Identifier: MIT */
#include "json_service.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static union {long double align;unsigned char data[MB_JSON_ARENA_BYTES];} scratch;
static char output[4097];
static size_t cases;
static mb_json_error call(mb_json_op op,const char *s,size_t n,const char *p,const char *v,size_t space,size_t cap,size_t *length) {
 return mb_json_run(op,s,n,p,strlen(p),v,strlen(v),scratch.data,space,output,cap,length);
}
static void check(mb_json_op op,const char *s,const char *p,const char *v,mb_json_error expected,const char *answer) {
 size_t n=123;strcpy(output,"UNCHANGED");char original[4097];strcpy(original,s);
 mb_json_error got=call(op,s,strlen(s),p,v,sizeof(scratch.data),sizeof(output),&n);
 if(got!=expected || (got==MB_JSON_OK && strcmp(output,answer))) {
  fprintf(stderr,"case %zu: expected %d / %s, got %d / %s\n",cases,expected,answer?answer:"",got,output);assert(0);
 }
 assert(!strcmp(original,s));
 if(got) {assert(!n);assert(!strcmp(output,"UNCHANGED"));} else assert(n==strlen(output));cases++;
}
int main(void) {
 size_t padded_length=0;
 const char padded[]={'{','}',0,0},hidden[]={'{','}',0,'x'},unterminated[]={'a','b','c','d'};
 assert(mb_json_padded_text_length(padded,4,4096,&padded_length)==MB_JSON_OK && padded_length==2);
 assert(mb_json_padded_text_length(hidden,4,4096,&padded_length)==MB_JSON_INVALID);
 assert(mb_json_padded_text_length(unterminated,4,4096,&padded_length)==MB_JSON_INVALID);
 assert(mb_json_padded_text_length(padded,4,1,&padded_length)==MB_JSON_LIMIT);
 assert(mb_json_padded_text_length(padded,4,4096,NULL)==MB_JSON_BAD_ARGUMENT);
 cases+=5;
 check(MB_JSON_COMPACT," { \"n\" : 9007199254740993123, \"f\": -0.1234567890123456789e+250 } ","","",MB_JSON_OK,"{\"n\":9007199254740993123,\"f\":-0.1234567890123456789e+250}");
 check(MB_JSON_GET,"{\"a/b\":{\"~x\":[null,true,3]}}","/a~1b/~0x/0","",MB_JSON_OK,"null");
 check(MB_JSON_GET,"{\"x\":null}","/absent","",MB_JSON_MISSING,NULL);
 check(MB_JSON_TEXT,"{\"x\":\"\\uD83D\\uDE00\\n\"}","/x","",MB_JSON_OK,"\xf0\x9f\x98\x80\n");
 check(MB_JSON_GET,"\"a\\u0000b\"","","",MB_JSON_OK,"\"a\\u0000b\"");
 check(MB_JSON_TEXT,"\"a\\u0000b\"","","",MB_JSON_TEXT_NUL,NULL);
 check(MB_JSON_SET,"{\"a\":{}}","/a/x","[1,2]",MB_JSON_OK,"{\"a\":{\"x\":[1,2]}}");
 check(MB_JSON_SET,"{}","/missing/x","1",MB_JSON_MISSING,NULL);
 check(MB_JSON_SET,"[1,2]","/1","false",MB_JSON_OK,"[1,false]");
 check(MB_JSON_SET,"[1,2]","/2","3",MB_JSON_MISSING,NULL);
 check(MB_JSON_SET,"[1,2]","/01","3",MB_JSON_PATH,NULL);
 check(MB_JSON_SET,"{}","/a~1b","2",MB_JSON_OK,"{\"a/b\":2}");
 check(MB_JSON_SET,"{}","","[]",MB_JSON_OK,"[]");
 check(MB_JSON_APPEND,"{\"a\":[1]}","/a","{\"x\":true}",MB_JSON_OK,"{\"a\":[1,{\"x\":true}]}");
 check(MB_JSON_REMOVE,"{\"a\":1,\"b\":2}","/a","",MB_JSON_OK,"{\"b\":2}");
 check(MB_JSON_REMOVE,"[1,2,3]","/1","",MB_JSON_OK,"[1,3]");
 check(MB_JSON_REMOVE,"{}","","",MB_JSON_ROOT_REMOVE,NULL);
 check(MB_JSON_KEYS,"{\"x\":1,\"a/b\":2}","","",MB_JSON_OK,"[\"x\",\"a/b\"]");
 check(MB_JSON_LENGTH,"{\"a\":1,\"b\":2}","","",MB_JSON_OK,"2");
 check(MB_JSON_LENGTH,"\"hello\"","","",MB_JSON_WRONG_TYPE,NULL);
 check(MB_JSON_TYPE,"1e9999","","",MB_JSON_OK,"number");
 check(MB_JSON_TYPE,"null","","",MB_JSON_OK,"null");
 check(MB_JSON_QUOTE,"a\"b\n","","",MB_JSON_OK,"\"a\\\"b\\n\"");
 check(MB_JSON_QUOTE,"\xc0\xaf","","",MB_JSON_INVALID,NULL);
 check(MB_JSON_VALIDATE,"{\"\\u0000\":1,\"\\u0000\":2}","","",MB_JSON_DUPLICATE,NULL);
 check(MB_JSON_GET,"{}","a","",MB_JSON_PATH,NULL);
 check(MB_JSON_GET,"{}","/a~2","",MB_JSON_PATH,NULL);
 check(MB_JSON_COMPACT,"{\"x\":1,\"\\u0078\":2}","","",MB_JSON_DUPLICATE,NULL);
 check(MB_JSON_SET,"{}","/x","{\"a\":1,\"a\":2}",MB_JSON_DUPLICATE,NULL);
 const char *invalid[]={"","01","[1,]","{\"a\":1,}","NaN","Infinity","1 2","+1",".1","1.","/*x*/1","\"\\uD800\"","\"\\uDC00\"","\"\xc0\xaf\"","\"\xed\xa0\x80\"","\"\xf4\x90\x80\x80\"","{\"x\" 1}","[true false]","[","{", "\xef\xbb\xbf{}"};
 for(size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) check(MB_JSON_VALIDATE,invalid[i],"","",MB_JSON_INVALID,NULL);
 char nested[100];memset(nested,'[',16);nested[16]='0';memset(nested+17,']',16);nested[33]=0;
 check(MB_JSON_COMPACT,nested,"","",MB_JSON_OK,nested);
 nested[33]=']';nested[34]=0;memmove(nested+1,nested,35);nested[0]='[';
 check(MB_JSON_VALIDATE,nested,"","",MB_JSON_INVALID,NULL);
 char many[600]="[0";for(int i=1;i<127;i++) strcat(many,",0");strcat(many,"]");
 check(MB_JSON_VALIDATE,many,"","",MB_JSON_OK,"true");
 check(MB_JSON_APPEND,many,"","0",MB_JSON_LIMIT,NULL);
 size_t len;char nul[]={'{','}',0,'x'};
 assert(call(MB_JSON_VALIDATE,nul,sizeof(nul),"","",sizeof(scratch.data),sizeof(output),&len)==MB_JSON_INVALID);
 char maximum[4098];maximum[0]='\"';memset(maximum+1,'x',4094);maximum[4095]='\"';maximum[4096]=0;
 check(MB_JSON_COMPACT,maximum,"","",MB_JSON_OK,maximum);
 maximum[4096]=' ';maximum[4097]=0;
 assert(call(MB_JSON_VALIDATE,maximum,4097,"","",sizeof(scratch.data),sizeof(output),&len)==MB_JSON_LIMIT);
 char expanded[1025];memset(expanded,1,1024);expanded[1024]=0;
 check(MB_JSON_QUOTE,expanded,"","",MB_JSON_LIMIT,NULL);
 cases++;
 memset(output,'X',sizeof(output));assert(call(MB_JSON_COMPACT,"[1,2]",5,"","",sizeof(scratch.data),5,&len)==MB_JSON_LIMIT);assert(output[0]=='X'&&len==0);
 unsigned failures=0,successes=0;
 for(size_t bytes=8;bytes<=MB_JSON_ARENA_BYTES;bytes+=257) {
  strcpy(output,"UNCHANGED");mb_json_error e=call(MB_JSON_SET,"{\"x\":[]}",8,"/x","{\"y\":[1,2,3]}",bytes,sizeof(output),&len);
  if(e) {assert(e==MB_JSON_MEMORY);assert(!strcmp(output,"UNCHANGED"));failures++;}else {assert(!strcmp(output,"{\"x\":{\"y\":[1,2,3]}}"));successes++;}
 }
 assert(failures && successes);
 /* Deterministic malformed-data stress under sanitizers. */
 uint32_t seed=1;char fuzz[256];unsigned fuzz_cases=10000;
 for(unsigned i=0;i<fuzz_cases;i++) {
  seed=1664525*seed+1013904223;size_t n=seed%sizeof(fuzz);
  for(size_t k=0;k<n;k++) {seed=1664525*seed+1013904223;fuzz[k]=(char)(seed>>24);}
  call(MB_JSON_COMPACT,fuzz,n,"","",sizeof(scratch.data),sizeof(output),&len);
 }
 printf("{\"result\":\"PASS\",\"cases\":%zu,\"workspace_sizes_failed_cleanly\":%u,\"workspace_sizes_succeeded\":%u,\"fuzz_cases\":%u,\"arena_reserved_bytes\":%d}\n",cases,failures,successes,fuzz_cases,MB_JSON_ARENA_BYTES);
}
