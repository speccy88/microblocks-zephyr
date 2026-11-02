/* SPDX-License-Identifier: MPL-2.0 */
/* Generic Python operations and pure JSON conversion, no blocking Python in VM. */
#include "vm/interp.h"
#include "python_extensions.h"
#include "microduck.h"
#include "third_party/yyjson/yyjson.h"
#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static union {max_align_t align;unsigned char bytes[2u*1024u*1024u];} pool;
static unsigned nodes;
static int vmText(OBJ value,char *out,size_t maximum) {
    size_t length;return linuxRpcCopyString(value,out,maximum,&length);
}
static yyjson_mut_val *encodeValue(yyjson_mut_doc *doc,OBJ value,unsigned depth) {
    if(depth>16||++nodes>4096)return NULL;
    if(value==trueObj||value==falseObj)return yyjson_mut_bool(doc,value==trueObj);
    if(isInt(value))return yyjson_mut_sint(doc,obj2int(value));
    if(IS_TYPE(value,StringType)){
        char text[8193];if(!vmText(value,text,8192))return NULL;
        return yyjson_mut_strcpy(doc,text);
    }
    if(IS_TYPE(value,ListType)){
        int count=obj2int(FIELD(value,0));if(count<0||count>1024||(unsigned)count>=WORDS(value))return NULL;
        yyjson_mut_val *array=yyjson_mut_arr(doc);if(!array)return NULL;
        for(int i=1;i<=count;i++){yyjson_mut_val *item=encodeValue(doc,FIELD(value,i),depth+1);if(!item||!yyjson_mut_arr_append(array,item))return NULL;}
        return array;
    }
    return NULL;
}
static OBJ jsonEncode(int argc,OBJ *args) {
    if(argc!=1)return fail(notEnoughArguments);
    yyjson_alc allocator;if(!yyjson_alc_pool_init(&allocator,pool.bytes,sizeof(pool.bytes)))return fail(insufficientMemoryError);
    yyjson_mut_doc *doc=yyjson_mut_doc_new(&allocator);if(!doc)return fail(insufficientMemoryError);
    nodes=0;yyjson_mut_val *value=encodeValue(doc,args[0],0);char buffer[8193];size_t size=0;
    if(value){yyjson_mut_doc_set_root(doc,value);size=yyjson_mut_write_buf(buffer,sizeof(buffer),doc,0,NULL);}
    yyjson_mut_doc_free(doc);
    if(!size||size>8192)return fail(argIndexOutOfRange);
    return newStringFromBytes(buffer,(int)size);
}
static OBJ decodeValue(yyjson_val *value,unsigned depth) {
    if(depth>8||++nodes>4096)return fail(argIndexOutOfRange);
    if(yyjson_is_bool(value))return yyjson_get_bool(value)?trueObj:falseObj;
    if(yyjson_is_int(value)&&(!yyjson_is_uint(value)||yyjson_get_uint(value)<=1073741823u)){
        int64_t n=yyjson_get_sint(value);if(n>=-1073741824&&n<=1073741823)return int2obj((int)n);
    }
    if(yyjson_is_str(value)){
        if(memchr(yyjson_get_str(value),0,yyjson_get_len(value)))return fail(argIndexOutOfRange);
        return newStringFromBytes(yyjson_get_str(value),(int)yyjson_get_len(value));
    }
    if(yyjson_is_arr(value)){
        size_t count=yyjson_arr_size(value);if(count>1024)return fail(argIndexOutOfRange);
        OBJ list=newObj(ListType,(int)count+2,tempGCRoot);if(list==falseObj)return falseObj;
        tempGCRoot=list;FIELD(list,0)=int2obj((int)count);
        for(size_t i=0;i<count;i++){
            OBJ child=decodeValue(yyjson_arr_get(value,i),depth+1);
            if(failure()){tempGCRoot=FIELD(tempGCRoot,count+1);return falseObj;}
            FIELD(tempGCRoot,i+1)=child;
        }
        list=tempGCRoot;OBJ previous=FIELD(list,count+1);FIELD(list,count+1)=zeroObj;tempGCRoot=previous;return list;
    }
    /* Match upstream JSON's object/null representation. Large integers and
     * decimals remain exact JSON text instead of silently narrowing to int31. */
    char buffer[65537];size_t size=yyjson_val_write_buf(buffer,sizeof(buffer),value,0,NULL);
    if(!size||size>65536)return fail(argIndexOutOfRange);
    return newStringFromBytes(buffer,(int)size);
}
static OBJ jsonRead(int argc,OBJ *args,int typeOnly) {
    if(argc!=2)return fail(notEnoughArguments);
    if(!IS_TYPE(args[0],StringType)||!IS_TYPE(args[1],StringType))return fail(needsStringError);
    char text[65537],pointer[257];if(!vmText(args[0],text,65536)||!vmText(args[1],pointer,256))return fail(argIndexOutOfRange);
    yyjson_alc allocator;if(!yyjson_alc_pool_init(&allocator,pool.bytes,sizeof(pool.bytes)))return fail(insufficientMemoryError);
    yyjson_doc *doc=yyjson_read_opts(text,strlen(text),0,&allocator,NULL);if(!doc)return fail(argIndexOutOfRange);
    yyjson_val *value=yyjson_ptr_get(yyjson_doc_get_root(doc),pointer);OBJ result;
    if(typeOnly){
        const char *type=!value?"missing":yyjson_is_null(value)?"null":yyjson_is_bool(value)?"boolean":yyjson_is_str(value)?"string":yyjson_is_num(value)?"number":yyjson_is_arr(value)?"array":"object";
        result=newStringFromBytes(type,(int)strlen(type));
    }else if(!value)result=newStringFromBytes("",0);
    else{nodes=0;result=decodeValue(value,0);}
    yyjson_doc_free(doc);return result;
}
static OBJ jsonGet(int n,OBJ *a){return jsonRead(n,a,0);}
static OBJ jsonType(int n,OBJ *a){return jsonRead(n,a,1);}
static OBJ configured(int n,OBJ *a){return linuxRpcPrimitive(0,n,a);}
static OBJ status(int n,OBJ *a){return linuxRpcPrimitive(1,n,a);}
static OBJ result(int n,OBJ *a){return linuxRpcPrimitive(2,n,a);}
static OBJ release(int n,OBJ *a){return linuxRpcPrimitive(3,n,a);}
static int nameOK(const char *name){
    size_t length=strlen(name);if(length<1||length>64||name[0]<'a'||name[0]>'z')return 0;
    for(size_t i=0;i<length;i++)if(!((name[i]>='a'&&name[i]<='z')||(name[i]>='0'&&name[i]<='9')||name[i]=='_'||name[i]=='-'||name[i]=='.'))return 0;
    return 1;
}
static OBJ begin(int argc,OBJ *args){
    if(argc!=3)return fail(notEnoughArguments);
    if(!IS_TYPE(args[0],StringType)||!IS_TYPE(args[1],StringType)||!IS_TYPE(args[2],StringType))return fail(needsStringError);
    char extension[65],method[65],arguments[8193],params[8193];
    if(!vmText(args[0],extension,64)||!vmText(args[1],method,64)||!vmText(args[2],arguments,8192)||!nameOK(extension)||!nameOK(method))return fail(argIndexOutOfRange);
    int length=snprintf(params,sizeof(params),"{\"extension\":\"%s\",\"method\":\"%s\",\"args\":%s}",extension,method,arguments);
    if(length<0||(size_t)length>=sizeof(params))return fail(argIndexOutOfRange);
    return linuxRpcBegin("extensions.call",params,(size_t)length,0);
}
static PrimEntry entries[]={
    {"pythonConfigured",configured},{"pythonBegin",begin},{"pythonStatus",status},{"pythonResult",result},{"pythonRelease",release},
    {"pythonJSON",jsonEncode},{"pythonGet",jsonGet},{"pythonType",jsonType}
};
void addLinuxPythonPrims(void){addPrimitiveSet(IOPrims,"linux",(int)(sizeof(entries)/sizeof(entries[0])),entries);}
