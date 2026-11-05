/* SPDX-License-Identifier: MPL-2.0 */
/* General files share the mounted LittleFS volume, but can only name user-*
   files. The VM program and temp files cannot be reached through this API. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#ifndef P2_PERIPHERAL_HOST_TEST
#include <dirent.h>
#endif
#include "mem.h"
#include "interp.h"
#ifndef P2_FILE_PREFIX
#define P2_FILE_PREFIX "/flash/user-"
#endif
#define FILE_CHUNK 512
static FILE *reader;
static char readerName[80];
extern int p2FileSystemReady(void);

static int userPath(const char *name,char *path) {
    int count=strlen(name);
    if(!count||count>48||name[0]=='.'||strstr(name,"..")) return 0;
    for(int i=0;i<count;i++) {
        char c=name[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='_'||c=='-')) return 0;
    }
    strcpy(path,P2_FILE_PREFIX);strcat(path,name);return 1;
}
void p2FilesClose(void) {
    if(reader) fclose(reader);
    reader=NULL;readerName[0]=0;
}
static int openRead(const char *name) {
    char path[80];
    if(!userPath(name,path)||!p2FileSystemReady()) return 0;
    if(reader&&!strcmp(name,readerName)) return 1;
    p2FilesClose();reader=fopen(path,"rb");
    if(reader) strcpy(readerName,name);
    return reader!=NULL;
}
static int appendData(const char *name,const void *data,int count) {
    char path[80];
    if(count<0||count>FILE_CHUNK||!userPath(name,path)||!p2FileSystemReady()) return -1;
    FILE *file=fopen(path,"ab");if(!file) return -1;
    int written=fwrite(data,1,count,file),ok=!ferror(file);
    if(fflush(file)) ok=0;
    if(fclose(file)) ok=0;
    if(reader&&!strcmp(readerName,name)) clearerr(reader);
    return ok?written:-1;
}
static int fileSize(const char *name) {
    char path[80];if(!userPath(name,path)||!p2FileSystemReady()) return -1;
    FILE *file=fopen(path,"rb");if(!file) return -1;
    int ok=!fseek(file,0,SEEK_END),size=ok?ftell(file):-1;
    fclose(file);return size;
}
static int deleteFile(const char *name) {
    char path[80];if(!userPath(name,path)||!p2FileSystemReady()) return 0;
    if(reader&&!strcmp(readerName,name)) p2FilesClose();
    return !remove(path);
}
#ifndef P2_PERIPHERAL_HOST_TEST
static DIR *directory;
static OBJ nameArgument(int argc,OBJ *args,int index,char *name) {
    char path[80];
    if(argc<=index||!IS_TYPE(args[index],StringType)) return fail(needsStringError);
    if(!userPath(obj2str(args[index]),path)) return fail(indexOutOfRangeError);
    strcpy(name,obj2str(args[index]));return trueObj;
}
static OBJ ready(int argc,OBJ *args) { (void)argc;(void)args;return p2FileSystemReady()?trueObj:falseObj; }
static OBJ openFile(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    p2FilesClose();return openRead(name)?trueObj:falseObj;
}
static OBJ closeFile(int argc,OBJ *args) {
    (void)argc;(void)args;p2FilesClose();return falseObj;
}
static OBJ removeFile(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    return deleteFile(name)?trueObj:falseObj;
}
static OBJ sizeFile(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    return int2obj(fileSize(name));
}
static OBJ appendBytes(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,1,name)!=trueObj) return falseObj;
    if(!IS_TYPE(args[0],StringType)&&!IS_TYPE(args[0],ByteArrayType)) return fail(needsByteArray);
    const char *bytes=(char *)&FIELD(args[0],0);
    int count=IS_TYPE(args[0],StringType)?strlen(bytes):BYTES(args[0]);
    return int2obj(appendData(name,bytes,count));
}
static OBJ appendLine(int argc,OBJ *args) {
    char name[49],line[FILE_CHUNK];if(nameArgument(argc,args,1,name)!=trueObj) return falseObj;
    if(!IS_TYPE(args[0],StringType)) return fail(needsStringError);
    int count=strlen(obj2str(args[0]));if(count>=FILE_CHUNK) return fail(indexOutOfRangeError);
    memcpy(line,obj2str(args[0]),count);line[count++]='\n';
    return int2obj(appendData(name,line,count));
}
static OBJ readInto(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,1,name)!=trueObj) return falseObj;
    if(!IS_TYPE(args[0],ByteArrayType)) return fail(needsByteArray);
    if(!openRead(name)) return int2obj(-1);
    int count=BYTES(args[0]);if(count>FILE_CHUNK) count=FILE_CHUNK;
    return int2obj(fread(&FIELD(args[0],0),1,count,reader));
}
static OBJ readBytes(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,1,name)!=trueObj) return falseObj;
    if(!isInt(args[0])) return fail(needsIntegerError);
    int count=obj2int(args[0]);if(count<0||count>FILE_CHUNK) return fail(indexOutOfRangeError);
    if(!openRead(name)) return falseObj;
    if(argc>2) {
        if(!isInt(args[2])||obj2int(args[2])<0) return fail(indexOutOfRangeError);
        if(fseek(reader,obj2int(args[2]),SEEK_SET)) return falseObj;
    }
    uint8_t buffer[FILE_CHUNK];count=fread(buffer,1,count,reader);
    OBJ result=newObj(ByteArrayType,(count+3)/4,falseObj);
    if(!result) return falseObj;
    setByteCountAdjust(result,count);memcpy(&FIELD(result,0),buffer,count);return result;
}
static OBJ readLine(int argc,OBJ *args) {
    char name[49],line[256];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    if(!openRead(name)) return falseObj;
    int count=0,value;
    while(count<255&&(value=fgetc(reader))!=EOF) { if(value=='\n') break;line[count++]=value; }
    if(count&&line[count-1]=='\r') count--;
    return newStringFromBytes(line,count);
}
static OBJ atEnd(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    if(!openRead(name)) return trueObj;
    int byte=fgetc(reader);if(byte==EOF) return trueObj;ungetc(byte,reader);return falseObj;
}
static OBJ position(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,0,name)!=trueObj) return falseObj;
    return int2obj(openRead(name)?ftell(reader):-1);
}
static OBJ seekFile(int argc,OBJ *args) {
    char name[49];if(nameArgument(argc,args,1,name)!=trueObj) return falseObj;
    if(!isInt(args[0])||obj2int(args[0])<0) return fail(indexOutOfRangeError);
    return openRead(name)&&!fseek(reader,obj2int(args[0]),SEEK_SET)?trueObj:falseObj;
}
static OBJ startList(int argc,OBJ *args) {
    if(directory) closedir(directory);
    directory=NULL;
    if(argc && (!IS_TYPE(args[0],StringType)||strlen(obj2str(args[0])))) return fail(indexOutOfRangeError);
    if(p2FileSystemReady()) directory=opendir("/flash");
    return falseObj;
}
static OBJ nextFile(int argc,OBJ *args) {
    (void)argc;(void)args;
    while(directory) {
        struct dirent *entry=readdir(directory);
        if(!entry) {closedir(directory);directory=NULL;break;}
        if(!strncmp(entry->d_name,"user-",5)) return newStringFromBytes(entry->d_name+5,strlen(entry->d_name+5));
    }
    return newString(0);
}
static OBJ noDirectories(int argc,OBJ *args) { (void)argc;(void)args;return newString(0); }
static OBJ systemInfo(int argc,OBJ *args) {
    (void)argc;(void)args;const char *s=p2FileSystemReady()?"LittleFS /flash; isolated user- files; free space unknown":"LittleFS unavailable; no format attempted";
    return newStringFromBytes(s,strlen(s));
}
static PrimEntry entries[]={
    {"p2Ready",ready},{"open",openFile},{"close",closeFile},{"delete",removeFile},
    {"appendLine",appendLine},{"appendBytes",appendBytes},{"fileSize",sizeFile},
    {"readBytes",readBytes},{"readInto",readInto},{"readLine",readLine},{"endOfFile",atEnd},
    {"readPosition",position},{"setReadPosition",seekFile},{"startList",startList},
    {"nextInList",nextFile},{"nextDirInList",noDirectories},{"systemInfo",systemInfo}
};
void addFilePrims(void) { addPrimitiveSet(FilePrims,"file",sizeof(entries)/sizeof(PrimEntry),entries); }
#endif
