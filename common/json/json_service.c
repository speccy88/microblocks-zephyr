/* SPDX-License-Identifier: MIT */
#include "json_config.h"
#include "json_service.h"
#include "yyjson.h"
#include <string.h>
#include <stdio.h>

mb_json_error mb_json_padded_text_length(const char *s,size_t cap,size_t limit,size_t *length) {
 if(!s||!length||!cap) return MB_JSON_BAD_ARGUMENT;
 *length=0;
 if(cap>limit+4) return MB_JSON_LIMIT;
 size_t n=0;while(n<cap && s[n]) n++;
 if(n==cap) return MB_JSON_INVALID;
 if(n>limit) return MB_JSON_LIMIT;
 for(size_t i=n+1;i<cap;i++) if(s[i]) return MB_JSON_INVALID;
 *length=n;return MB_JSON_OK;
}

static mb_json_error inspect(yyjson_mut_val *v, unsigned depth, size_t *count) {
 if (!v) return MB_JSON_MEMORY;
 if (++*count > MB_JSON_MAX_VALUES) return MB_JSON_LIMIT;
 if (yyjson_mut_is_ctn(v) && depth >= MB_JSON_MAX_DEPTH) return MB_JSON_LIMIT;
 if (yyjson_mut_is_arr(v)) {
  yyjson_mut_arr_iter it=yyjson_mut_arr_iter_with(v); yyjson_mut_val *child;
  while ((child=yyjson_mut_arr_iter_next(&it))) {
   mb_json_error e=inspect(child,depth+1,count); if(e) return e;
  }
 } else if (yyjson_mut_is_obj(v)) {
  yyjson_mut_obj_iter it=yyjson_mut_obj_iter_with(v); yyjson_mut_val *key;
  while ((key=yyjson_mut_obj_iter_next(&it))) {
   if (++*count > MB_JSON_MAX_VALUES) return MB_JSON_LIMIT;
   yyjson_mut_obj_iter scan=yyjson_mut_obj_iter_with(v); yyjson_mut_val *other;
   while ((other=yyjson_mut_obj_iter_next(&scan)) && other!=key) {
    if (yyjson_mut_get_len(other)==yyjson_mut_get_len(key) &&
        !memcmp(yyjson_mut_get_str(other),yyjson_mut_get_str(key),yyjson_mut_get_len(key)))
     return MB_JSON_DUPLICATE;
   }
   mb_json_error e=inspect(yyjson_mut_obj_iter_get_val(key),depth+1,count); if(e) return e;
  }
 }
 return MB_JSON_OK;
}

static mb_json_error parse(const char *s,size_t n,yyjson_alc *alc,yyjson_mut_doc **out) {
 if (!s || !n || memchr(s,0,n)) return MB_JSON_INVALID;
 if (n>MB_JSON_MAX_BYTES) return MB_JSON_LIMIT;
 yyjson_read_err err;
 yyjson_doc *doc=yyjson_read_opts((char *)s,n,YYJSON_READ_NUMBER_AS_RAW,alc,&err);
 if (!doc) return err.code==YYJSON_READ_ERROR_MEMORY_ALLOCATION?MB_JSON_MEMORY:MB_JSON_INVALID;
 if (yyjson_doc_get_val_count(doc)>MB_JSON_MAX_VALUES) {yyjson_doc_free(doc);return MB_JSON_LIMIT;}
 *out=yyjson_doc_mut_copy(doc,alc); yyjson_doc_free(doc);
 if (!*out) return MB_JSON_MEMORY;
 size_t count=0;return inspect(yyjson_mut_doc_get_root(*out),0,&count);
}

static int valid_path(const char *s,size_t n) {
 if (!s || (n && s[0]!='/') || memchr(s,0,n)) return 0;
 for (size_t i=0;i<n;i++) if(s[i]=='~') {
  if(++i>=n || (s[i]!='0' && s[i]!='1')) return 0;
 }
 return 1;
}

/* Explicit parent lookup prevents implicit containers or array growth. */
static mb_json_error set_value(yyjson_mut_doc *doc,const char *path,size_t n,yyjson_mut_val *val) {
 if(!n) {yyjson_mut_doc_set_root(doc,val);return MB_JSON_OK;}
 size_t split=n;while(split && path[split-1]!='/') split--;
 yyjson_mut_val *parent=yyjson_mut_ptr_getn(yyjson_mut_doc_get_root(doc),path,split-1);
 if(!parent) return MB_JSON_MISSING;
 char key[MB_JSON_MAX_PATH+1];size_t length=0;
 for(size_t i=split;i<n;i++) {char c=path[i];if(c=='~') c=path[++i]=='0'?'~':'/';key[length++]=c;}
 if(yyjson_mut_is_obj(parent)) {
  yyjson_mut_val *k=yyjson_mut_strncpy(doc,key,length);
  if(!k || !yyjson_mut_obj_put(parent,k,val)) return MB_JSON_MEMORY;
  return MB_JSON_OK;
 }
 if(!yyjson_mut_is_arr(parent)) return MB_JSON_WRONG_TYPE;
 if(!length || (length>1 && key[0]=='0')) return MB_JSON_PATH;
 size_t index=0;
 for(size_t i=0;i<length;i++) {
  if(key[i]<'0'||key[i]>'9') return MB_JSON_PATH;
  if(index>MB_JSON_MAX_VALUES) return MB_JSON_MISSING;
  index=index*10+(size_t)(key[i]-'0');
 }
 return yyjson_mut_arr_replace(parent,index,val)?MB_JSON_OK:MB_JSON_MISSING;
}

static mb_json_error deliver(const char *s,size_t n,char *out,size_t cap,size_t *length) {
 if(n>MB_JSON_MAX_BYTES || n>=cap) return MB_JSON_LIMIT;
 memcpy(out,s,n);out[n]=0;*length=n;return MB_JSON_OK;
}

mb_json_error mb_json_run(mb_json_op op,
 const char *input,size_t input_length,const char *path,size_t path_length,
 const char *value,size_t value_length,void *arena,size_t arena_length,
 char *output,size_t output_capacity,size_t *output_length) {
 if(!output_length) return MB_JSON_BAD_ARGUMENT;
 *output_length=0;
 if(!input||!path||!value||!arena||!output||!output_capacity||
    op<MB_JSON_VALIDATE||op>MB_JSON_QUOTE) return MB_JSON_BAD_ARGUMENT;
 if(input_length>MB_JSON_MAX_BYTES || value_length>MB_JSON_MAX_BYTES || path_length>MB_JSON_MAX_PATH)
  return MB_JSON_LIMIT;
 if(!valid_path(path,path_length)) return MB_JSON_PATH;
 yyjson_alc alc;
 if(!yyjson_alc_pool_init(&alc,arena,arena_length)) return MB_JSON_MEMORY;
 yyjson_mut_doc *doc=NULL,*extra=NULL;mb_json_error e=MB_JSON_OK;
 yyjson_mut_val *target=NULL,*result=NULL;
 if(op==MB_JSON_QUOTE) {
  if(input_length>MB_JSON_MAX_PATH) return MB_JSON_LIMIT;
  doc=yyjson_mut_doc_new(&alc);
  if(!doc) return MB_JSON_MEMORY;
  result=yyjson_mut_strncpy(doc,input,input_length);
  if(!result) return MB_JSON_MEMORY;
 } else {
  e=parse(input,input_length,&alc,&doc);if(e) return e;
  target=yyjson_mut_ptr_getn(yyjson_mut_doc_get_root(doc),path,path_length);
  if(op!=MB_JSON_SET && !target) return MB_JSON_MISSING;
  result=target;
 }
 if(op==MB_JSON_VALIDATE) return deliver("true",4,output,output_capacity,output_length);
 if(op==MB_JSON_TEXT) {
  if(!yyjson_mut_is_str(target)) return MB_JSON_WRONG_TYPE;
  if(memchr(yyjson_mut_get_str(target),0,yyjson_mut_get_len(target))) return MB_JSON_TEXT_NUL;
  return deliver(yyjson_mut_get_str(target),yyjson_mut_get_len(target),output,output_capacity,output_length);
 }
 if(op==MB_JSON_TYPE) {
  const char *type=yyjson_mut_is_raw(target)?"number":yyjson_mut_is_obj(target)?"object":
   yyjson_mut_is_arr(target)?"array":yyjson_mut_is_str(target)?"string":
   yyjson_mut_is_bool(target)?"boolean":"null";
  return deliver(type,strlen(type),output,output_capacity,output_length);
 }
 if(op==MB_JSON_LENGTH) {
  if(!yyjson_mut_is_ctn(target)) return MB_JSON_WRONG_TYPE;
  char count[16];int n=snprintf(count,sizeof(count),"%u",(unsigned)yyjson_mut_get_len(target));
  return deliver(count,(size_t)n,output,output_capacity,output_length);
 }
 if(op==MB_JSON_KEYS) {
  if(!yyjson_mut_is_obj(target)) return MB_JSON_WRONG_TYPE;
  result=yyjson_mut_arr(doc);if(!result) return MB_JSON_MEMORY;
  yyjson_mut_obj_iter it=yyjson_mut_obj_iter_with(target);yyjson_mut_val *key;
  while((key=yyjson_mut_obj_iter_next(&it))) {
   yyjson_mut_val *copy=yyjson_mut_strncpy(doc,yyjson_mut_get_str(key),yyjson_mut_get_len(key));
   if(!copy||!yyjson_mut_arr_append(result,copy)) return MB_JSON_MEMORY;
  }
 }
 if(op==MB_JSON_SET||op==MB_JSON_APPEND) {
  e=parse(value,value_length,&alc,&extra);if(e) return e;
  yyjson_mut_val *copy=yyjson_mut_val_mut_copy(doc,yyjson_mut_doc_get_root(extra));
  if(!copy) return MB_JSON_MEMORY;
  if(op==MB_JSON_SET) e=set_value(doc,path,path_length,copy);
  else if(!yyjson_mut_is_arr(target)) e=MB_JSON_WRONG_TYPE;
  else if(!yyjson_mut_arr_append(target,copy)) e=MB_JSON_MEMORY;
  if(e) return e;
  result=yyjson_mut_doc_get_root(doc);
 }
 if(op==MB_JSON_REMOVE) {
  if(!path_length) return MB_JSON_ROOT_REMOVE;
  if(!yyjson_mut_doc_ptr_removen(doc,path,path_length)) return MB_JSON_MISSING;
  result=yyjson_mut_doc_get_root(doc);
 }
 size_t count=0;e=inspect(result,0,&count);if(e) return e;
 yyjson_write_err err;size_t length=0;
 char *serialized=yyjson_mut_val_write_opts(result,0,&alc,&length,&err);
 if(!serialized) return err.code==YYJSON_WRITE_ERROR_MEMORY_ALLOCATION?MB_JSON_MEMORY:MB_JSON_INVALID;
 return deliver(serialized,length,output,output_capacity,output_length);
}

const char *mb_json_error_text(mb_json_error e) {
 static const char *const messages[]={"OK","Invalid JSON or Unicode","JSON size, depth or value limit",
  "JSON workspace full","Duplicate JSON field","Invalid JSON path","JSON path not found",
  "Wrong JSON value type","Text contains a NUL character","Cannot remove JSON root","Invalid JSON arguments"};
 return (unsigned)e<sizeof(messages)/sizeof(messages[0])?messages[e]:"Unknown JSON error";
}
