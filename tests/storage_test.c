/* SPDX-License-Identifier: MIT */
#include "storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#define OK(x) assert((x) == MB_STORE_OK)
static mb_store store, before;
static unsigned checks;
static uint32_t write_file(const char *path, const uint8_t *p, size_t n, bool replace) {
    uint32_t job;
    OK(mb_store_begin(&store, path, strlen(path), n, replace, &job));
    for (size_t i = 0; i < n;) {
        size_t chunk = n - i > MB_FILE_CHUNK ? MB_FILE_CHUNK : n - i;
        OK(mb_store_append(&store, job, i, p + i, chunk)); i += chunk;
    }
    OK(mb_store_finish(&store, job)); assert(mb_store_poll(&store));
    mb_write_state state; OK(mb_store_job(&store, job, &state)); assert(state == MB_WRITE_DONE);
    checks++; return job;
}
static void unchanged(const char *path, const char *value) {
    const mb_ram_file *f;
    OK(mb_store_view(&store, path, strlen(path), &f));
    assert(f->length == strlen(value) && !memcmp(f->data, value, f->length));
    checks++;
}
int main(void) {
    mb_store_init(&store); assert(mb_store_count(&store) == 0 && mb_store_used(&store) == 0);
    const char *bad[] = {"", "RAM/a", "/RAM/", "/RAM//a", "/RAM/../a", "/RAM/.a", "/RAM/a/./b",
        "/RAM/a/../b", "/RAM/a\\b", "/RAM/a%2fb", "/RAM/a:b", "/RAM/a?b", "/RAM/a#b",
        "/RAM/a/", "/RAM/a/b/c/d/e", "/RAM/\x01", "/RAM/a b", "/NVS/secret", "/firmware/a"};
    for (unsigned i = 0; i < sizeof(bad)/sizeof(bad[0]); i++) { assert(mb_store_path(bad[i],strlen(bad[i])) == MB_STORE_PATH); checks++; }
    assert(mb_store_path("/RAM/a\0b", 8) == MB_STORE_PATH);
    OK(mb_store_path("/RAM/a/b/c/d-1.txt", strlen("/RAM/a/b/c/d-1.txt")));
    assert(mb_store_path("/SD/a",5) == MB_STORE_UNAVAILABLE);
    assert(mb_store_path("/Flash/a",8) == MB_STORE_UNAVAILABLE);
    uint32_t j1 = write_file("/RAM/a", (const uint8_t *)"old", 3, false), j2;
    assert(mb_store_begin(&store,"/RAM/a",6,3,false,&j2) == MB_STORE_EXISTS);
    assert(mb_store_begin(&store,"/RAM/a",6,MB_FILE_BYTES+1,true,&j2) == MB_STORE_SIZE);
    unchanged("/RAM/a", "old");
    OK(mb_store_begin(&store,"/RAM/a",6,3,true,&j2));
    assert(mb_store_cancel(&store,j1) == MB_STORE_STALE);
    assert(mb_store_delete(&store,"/RAM/a",6) == MB_STORE_BUSY);
    uint32_t other; assert(mb_store_begin(&store,"/RAM/b",6,0,false,&other) == MB_STORE_BUSY);
    assert(mb_store_append(&store,j2,1,(const uint8_t *)"new",3) == MB_STORE_ORDER);
    assert(mb_store_finish(&store,j2) == MB_STORE_SIZE);
    unchanged("/RAM/a","old");
    OK(mb_store_append(&store,j2,0,(const uint8_t *)"ne",2));
    before = store;
    assert(mb_store_append(&store,j2,SIZE_MAX,(const uint8_t *)"w",1) == MB_STORE_ORDER);
    assert(!memcmp(&store,&before,sizeof(store)));
    OK(mb_store_append(&store,j2,2,(const uint8_t *)"w",1)); OK(mb_store_finish(&store,j2));
    unchanged("/RAM/a","old"); mb_store_stop(&store); unchanged("/RAM/a","old");
    assert(!mb_store_poll(&store)); mb_write_state state; OK(mb_store_job(&store,j2,&state)); assert(state == MB_WRITE_CANCELLED);
    for (unsigned i=0;i<MB_FILE_BYTES;i++) assert(store.staging[i]==0);
    write_file("/RAM/a",(const uint8_t *)"new",3,true); unchanged("/RAM/a","new");
    assert(mb_store_cancel(&store,store.generation) == MB_STORE_STATE); /* done cannot be undone */
    mb_store_stop(&store); unchanged("/RAM/a","new");
    write_file("/RAM/empty",NULL,0,false); const mb_ram_file *f;
    OK(mb_store_view(&store,"/RAM/empty",10,&f)); assert(f->length==0);
    static uint8_t binary[MB_FILE_BYTES]; for (unsigned i=0;i<sizeof(binary);i++) binary[i]=(uint8_t)i;
    write_file("/RAM/data.bin",binary,sizeof(binary),false);
    uint8_t out[MB_FILE_CHUNK]; OK(mb_store_read(&store,"/RAM/data.bin",13,7000,out,100)); assert(!memcmp(out,binary+7000,100));
    assert(mb_store_read(&store,"/RAM/data.bin",13,SIZE_MAX,out,1)==MB_STORE_SIZE);
    assert(mb_store_read(&store,"/RAM/data.bin",13,0,out,MB_FILE_CHUNK+1)==MB_STORE_SIZE);
    assert(mb_store_read(&store,"/RAM/data.bin",13,MB_FILE_BYTES,out,1)==MB_STORE_SIZE);
    OK(mb_store_read(&store,"/RAM/data.bin",13,MB_FILE_BYTES,NULL,0));
    assert(mb_store_used(&store)==MB_FILE_BYTES+3 && mb_store_count(&store)==3);
    for (unsigned i=3;i<MB_FILE_COUNT;i++) { char path[32]; snprintf(path,sizeof(path),"/RAM/file%u",i); write_file(path,binary,1,false); }
    assert(mb_store_begin(&store,"/RAM/full",9,0,false,&j1)==MB_STORE_FULL);
    OK(mb_store_delete(&store,"/RAM/a",6)); assert(mb_store_view(&store,"/RAM/a",6,&f)==MB_STORE_NOT_FOUND);
    write_file("/RAM/reused",binary,1,false); assert(mb_store_count(&store)==MB_FILE_COUNT);
    mb_store_init(&store); assert(!mb_store_count(&store)); /* simulated reboot loses files */
    assert(mb_store_utf8((const uint8_t *)"\xc3\xa9\xe2\x82\xac\xf0\x9f\x98\x80",9));
    const uint8_t invalid[][5]={{0},{0xc0,0x80},{0xed,0xa0,0x80},{0xf4,0x90,0x80,0x80},{0xe2,0x82},{0x80}};
    const size_t lengths[]={1,2,3,4,2,1};
    for(unsigned i=0;i<6;i++) { assert(!mb_store_utf8(invalid[i],lengths[i])); checks++; }
    assert(mb_store_utf8(NULL,0)); assert(!mb_store_utf8(NULL,1));
    size_t text_length;
    OK(mb_store_padded_text("abc",4,3,&text_length)); assert(text_length==3);
    OK(mb_store_padded_text("",1,0,&text_length)); assert(!text_length);
    assert(mb_store_padded_text("a\0b",4,3,&text_length)==MB_STORE_TEXT);
    assert(mb_store_padded_text("abcd",4,4,&text_length)==MB_STORE_SIZE);
    assert(mb_store_padded_text("abc",4,2,&text_length)==MB_STORE_SIZE);
    assert(mb_store_padded_text("\xc0\x80",3,2,&text_length)==MB_STORE_TEXT);
    assert(mb_store_padded_text("",SIZE_MAX,1,&text_length)==MB_STORE_SIZE);
    assert(mb_store_padded_text("",1,SIZE_MAX,&text_length)==MB_STORE_SIZE);
    checks+=8;
    uint32_t random=17; char malformed[MB_FILE_PATH+1];
    for(unsigned n=0;n<10000;n++) {
        for(unsigned i=0;i<sizeof(malformed);i++) { random=random*1664525u+1013904223u; malformed[i]=(char)(random>>24); }
        size_t len=n%sizeof(malformed); before=store;
        mb_store_error e=mb_store_begin(&store,malformed,len,1,false,&j1);
        assert(e==MB_STORE_PATH||e==MB_STORE_UNAVAILABLE); assert(!memcmp(&store,&before,sizeof(store)));
        (void)mb_store_utf8((const uint8_t *)malformed,len);
    }
    store.generation=0x3fffffff;
    assert(mb_store_begin(&store,"/RAM/a",6,0,false,&j1)==MB_STORE_FULL);
    printf("{\"result\":\"PASS\",\"named_checks\":%u,\"malformed_inputs\":10000,\"file_slots\":%u,\"max_file_bytes\":%u,\"host_state_bytes\":%zu,\"hardware_access\":false}\n",checks,MB_FILE_COUNT,MB_FILE_BYTES,sizeof(store));
}
