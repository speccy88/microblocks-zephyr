/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdio.h>
#define P2_PERIPHERAL_HOST_TEST
#define P2_FILE_PREFIX "user-"
#include "../boards/propeller2/native/propeller2/p2Files.c"
static int available=1;
int p2FileSystemReady(void) { return available; }
int main(void) {
    char path[80];
    const char *invalid[]={"","../ublockscode","/flash/ublockscode","a/b","a\\b","C:foo",".hidden","a..b"};
    for(unsigned i=0;i<sizeof(invalid)/sizeof(*invalid);i++) {
        assert(!userPath(invalid[i],path));assert(appendData(invalid[i],"bad",3)==-1);
    }
    FILE *program=fopen("ublockscode","wb");assert(program);fwrite("KEEP",1,4,program);fclose(program);
    assert(userPath("ublockscode",path)&&!strcmp(path,"user-ublockscode"));
    assert(appendData("ublockscode","separate",8)==8);
    assert(fileSize("notes.txt")==-1);
    const unsigned char data[]={0,255,128,'\n'};
    assert(appendData("notes.txt",data,4)==4&&fileSize("notes.txt")==4);
    assert(appendData("notes.txt","hello\n",6)==6&&fileSize("notes.txt")==10);
    assert(openRead("notes.txt"));
    unsigned char read[16]={0};assert(fread(read,1,4,reader)==4&&!memcmp(read,data,4));
    assert(openRead("notes.txt")&&ftell(reader)==4); /* same file retains cursor */
    assert(fread(read,1,6,reader)==6&&!memcmp(read,"hello\n",6));
    assert(fgetc(reader)==EOF);
    assert(appendData("notes.txt","X",1)==1&&fgetc(reader)=='X');
    assert(appendData("notes.txt",read,513)==-1&&fileSize("notes.txt")==11);
    available=0;assert(appendData("other.txt","bad",3)==-1&&!openRead("other.txt"));available=1;
    assert(deleteFile("notes.txt")&&!reader&&fileSize("notes.txt")==-1);
    assert(deleteFile("ublockscode"));
    program=fopen("ublockscode","rb");assert(program);assert(fread(read,1,4,program)==4&&!memcmp(read,"KEEP",4));fclose(program);
    assert(!deleteFile("../ublockscode"));
    puts("LittleFS adapter production names/isolated program/binary append/read/cursor/bounds/mount failure PASS; actual flash untested");
    return 0;
}
