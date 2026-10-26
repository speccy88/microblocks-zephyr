/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "storage.h"
#include "storage_primitives.h"
#include <string.h>

#if defined(CONFIG_ESP_SPIRAM)
#define STORAGE_STATE __attribute__((section(".ext_ram.bss.storage"), aligned(16)))
#else
#define STORAGE_STATE
#endif
static mb_store files STORAGE_STATE;
static mb_store_error last_error;
static bool initialized;
static OBJ text(const char *s) { return newStringFromBytes(s, strlen(s)); }
static OBJ result(mb_store_error e) { last_error = e; return e ? falseObj : trueObj; }

/* Strings are word-padded in SmallVM. Reject hidden bytes after the first NUL. */
static bool vm_text(OBJ arg, size_t max, const char **p, size_t *length) {
    if (!IS_TYPE(arg, StringType)) { fail(needsStringError); return false; }
    const char *s = obj2str(arg);
    last_error = mb_store_padded_text(s,4*(size_t)WORDS(arg),max,length);
    if (last_error) return false;
    *p = s; return true;
}
static bool path_arg(int n, OBJ *args, const char **p, size_t *length) {
    if (n != 1) { fail(notEnoughArguments); return false; }
    return vm_text(args[0], MB_FILE_PATH - 1, p, length);
}
static bool job_arg(int n, OBJ *args, uint32_t *job) {
    if (n != 1) { fail(notEnoughArguments); return false; }
    if (!isInt(args[0])) { fail(needsIntegerError); return false; }
    *job = (uint32_t)obj2int(args[0]); return true;
}
void mb_storage_poll(void) {
    if (initialized && mb_store_poll(&files) && files.state == MB_WRITE_FAILED)
        last_error = files.job_error;
}
void mb_storage_stop(void) { if (initialized) mb_store_stop(&files); }

static OBJ write_file(int n, OBJ *args) {
    if (n != 3) return fail(notEnoughArguments);
    const char *path; size_t path_length;
    if (!vm_text(args[0], MB_FILE_PATH - 1, &path, &path_length)) return falseObj;
    if (args[2] != trueObj && args[2] != falseObj) return result(MB_STORE_STATE);
    const uint8_t *data; size_t length;
    if (IS_TYPE(args[1], ByteArrayType)) {
        length = BYTES(args[1]); data = (const uint8_t *)&FIELD(args[1],0);
    } else {
        const char *s;
        if (!vm_text(args[1], MB_FILE_BYTES, &s, &length)) return falseObj;
        data = (const uint8_t *)s;
    }
    uint32_t job;
    last_error = mb_store_begin(&files, path, path_length, length, args[2] == trueObj, &job);
    if (last_error) return falseObj;
    for (size_t i = 0; i < length;) {
        size_t chunk = length - i > MB_FILE_CHUNK ? MB_FILE_CHUNK : length - i;
        last_error = mb_store_append(&files, job, i, data + i, chunk);
        if (last_error) { mb_store_stop(&files); return falseObj; }
        i += chunk;
    }
    last_error = mb_store_finish(&files, job);
    if (last_error) { mb_store_stop(&files); return falseObj; }
    /* Data and path have been copied. No pointer to args survives this call. */
    return int2obj(job);
}
static OBJ state(int n, OBJ *args) {
    uint32_t job; if (!job_arg(n,args,&job)) return falseObj;
    mb_write_state value;
    last_error = mb_store_job(&files,job,&value);
    if (last_error) return falseObj;
    if (!last_error && value == MB_WRITE_FAILED) last_error = files.job_error;
    return text(mb_store_state_text(value));
}
static OBJ cancel(int n, OBJ *args) {
    uint32_t job; if (!job_arg(n,args,&job)) return falseObj;
    return result(mb_store_cancel(&files,job));
}
static const mb_ram_file *view(int n, OBJ *args) {
    const char *path; size_t length; const mb_ram_file *file;
    if (!path_arg(n,args,&path,&length)) return NULL;
    last_error = mb_store_view(&files,path,length,&file);
    return last_error ? NULL : file;
}
static OBJ read_text(int n, OBJ *args) {
    const mb_ram_file *file = view(n,args);
    if (!file) return falseObj;
    if (!mb_store_utf8(file->data,file->length)) return result(MB_STORE_TEXT);
    return newStringFromBytes((const char *)file->data,file->length);
}
static OBJ read_bytes(int n, OBJ *args) {
    const mb_ram_file *file = view(n,args);
    if (!file) return falseObj;
    size_t length = file->length;
    OBJ out = newObj(ByteArrayType,(length+3)/4,zeroObj);
    if (out == falseObj) return out;
    setByteCountAdjust(out,length);
    /* Native store is stable across GC; do not read args after allocation. */
    memcpy(&FIELD(out,0),file->data,length);
    return out;
}
static OBJ size(int n, OBJ *args) {
    const mb_ram_file *file = view(n,args);
    return file ? int2obj(file->length) : falseObj;
}
static OBJ exists(int n, OBJ *args) { return view(n,args) ? trueObj : falseObj; }
static OBJ remove_file(int n, OBJ *args) {
    const char *path; size_t length;
    if (!path_arg(n,args,&path,&length)) return falseObj;
    return result(mb_store_delete(&files,path,length));
}
static OBJ list(int n, OBJ *args) {
    (void)args; if (n) return fail(notEnoughArguments);
    char out[MB_FILE_COUNT * MB_FILE_PATH + 1]; size_t used = 0;
    for (unsigned i=0;i<MB_FILE_COUNT;i++) if (files.files[i].present) {
        if (used) out[used++] = '\n';
        size_t length = strlen(files.files[i].path);
        memcpy(out+used,files.files[i].path,length); used += length;
    }
    out[used] = 0; last_error = MB_STORE_OK; return newStringFromBytes(out,used);
}
static OBJ available(int n, OBJ *args) {
    const char *backend; size_t length;
    if (n != 1) return fail(notEnoughArguments);
    if (!vm_text(args[0],5,&backend,&length)) return falseObj;
    if (length == 3 && !memcmp(backend,"RAM",3)) return result(MB_STORE_OK);
    return result(MB_STORE_UNAVAILABLE);
}
static OBJ used(int n, OBJ *args) { (void)args; return n ? fail(notEnoughArguments) : int2obj(mb_store_used(&files)); }
static OBJ slots(int n, OBJ *args) { (void)args; return n ? fail(notEnoughArguments) : int2obj(MB_FILE_COUNT-mb_store_count(&files)); }
static OBJ maximum(int n, OBJ *args) { (void)args; return n ? fail(notEnoughArguments) : int2obj(MB_FILE_BYTES); }
static OBJ status(int n, OBJ *args) { (void)args; return n ? fail(notEnoughArguments) : text(mb_store_error_text(last_error)); }
static PrimEntry entries[] = {
    {"write",write_file},{"state",state},{"cancel",cancel},{"text",read_text},
    {"bytes",read_bytes},{"size",size},{"exists",exists},{"delete",remove_file},
    {"list",list},{"available",available},{"used",used},{"slots",slots},
    {"maxFile",maximum},{"status",status}
};
mb_store *mb_storage_store(void) {
    if (!initialized) { mb_store_init(&files); initialized = true; }
    return &files;
}
void addStoragePrims(void) {
    (void)mb_storage_store();
    addPrimitiveSet(StoragePrims,"storage",sizeof(entries)/sizeof(entries[0]),entries);
}
