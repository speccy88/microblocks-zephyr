/* SPDX-License-Identifier: MIT */
#include "dispatcher.h"
#include <string.h>

static mb_files_status convert(mb_store_error e) {
    switch(e) {
    case MB_STORE_OK: return MB_FILES_OK;
    case MB_STORE_PATH: return MB_FILES_PATH;
    case MB_STORE_UNAVAILABLE: return MB_FILES_UNAVAILABLE;
    case MB_STORE_NOT_FOUND: return MB_FILES_NOT_FOUND;
    case MB_STORE_EXISTS: return MB_FILES_EXISTS;
    case MB_STORE_FULL: case MB_STORE_EXHAUSTED: return MB_FILES_FULL;
    case MB_STORE_SIZE: return MB_FILES_SIZE;
    case MB_STORE_BUSY: return MB_FILES_BUSY;
    case MB_STORE_CONFLICT: return MB_FILES_CONFLICT;
    default: return MB_FILES_STATE;
    }
}
static void cancel_owned(mb_files_dispatcher *d) {
    if (d->job) (void)mb_store_cancel(d->store,d->job);
    d->job=0;
}
void mb_files_init(mb_files_dispatcher *d, mb_store *s) {
    memset(d,0,sizeof(*d)); d->store=s;
}
bool mb_files_close(mb_files_dispatcher *d, uint32_t owner, uint32_t session) {
    if (!owner || owner!=d->owner || !session || session!=d->session) return false;
    cancel_owned(d); d->owner=0; d->session=0; d->last_id=0;
    return true;
}
bool mb_files_expire(mb_files_dispatcher *d, uint64_t now) {
    if (!d->owner || (now>=d->last_ms && now-d->last_ms<MB_FILES_IDLE_MS)) return false;
    (void)mb_files_close(d,d->owner,d->session); return true;
}
mb_files_status mb_files_open(mb_files_dispatcher *d, uint32_t owner, uint64_t now, uint32_t *session) {
    if (!d || !d->store || !owner || !session) return MB_FILES_PROTOCOL;
    (void)mb_files_expire(d,now);
    if (d->owner) return MB_FILES_BUSY;
    if (d->generation==MB_FILE_REFERENCE_MAX) return MB_FILES_FULL;
    d->owner=owner; d->session=++d->generation; d->last_id=0; d->last_ms=now;
    *session=d->session; return MB_FILES_OK;
}
static bool syntax(const mb_files_request *r) {
    if (r->path_length>=MB_FILE_PATH || r->count>MB_FILES_CHUNK) return false;
    switch(r->op) {
    case MB_FILES_CAPS: case MB_FILES_LIST:
        return !r->path_length && !r->token && !r->arg && !r->count;
    case MB_FILES_STAT:
        return r->path_length && !r->token && !r->arg && !r->count;
    case MB_FILES_READ:
        return r->path_length && r->token && r->token<=MB_FILE_REFERENCE_MAX;
    case MB_FILES_BEGIN:
        return r->path_length && r->token<=MB_FILE_REFERENCE_MAX && !r->count;
    case MB_FILES_APPEND:
        return !r->path_length && r->token && r->token<=MB_FILE_REFERENCE_MAX && r->count;
    case MB_FILES_FINISH: case MB_FILES_CANCEL:
        return !r->path_length && r->token && r->token<=MB_FILE_REFERENCE_MAX && !r->arg && !r->count;
    default: return false;
    }
}
static void meta(mb_files_meta *m, const mb_ram_file *f) {
    memcpy(m->path,f->path,MB_FILE_PATH); m->bytes=f->length; m->revision=f->revision;
}
void mb_files_dispatch(mb_files_dispatcher *d, uint32_t owner, uint64_t now,
    const mb_files_request *r, mb_files_reply *out) {
    memset(out,0,sizeof(*out));
    if (!r || !d || !d->store) { out->status=MB_FILES_PROTOCOL; return; }
    out->id=r->id; out->session=r->session; out->op=r->op;
    if (mb_files_expire(d,now)) { out->status=MB_FILES_TIMEOUT; return; }
    if (!owner || owner!=d->owner || !r->session || r->session!=d->session) {
        out->status=MB_FILES_DISCONNECTED; return;
    }
    if (!r->id || r->id<=d->last_id) { out->status=MB_FILES_PROTOCOL; return; }
    d->last_id=r->id; /* Consume even invalid payload IDs; never replay mutations. */
    if (!syntax(r)) { out->status=MB_FILES_PROTOCOL; return; }
    d->last_ms=now;
    if (d->job) {
        mb_write_state state;
        if (mb_store_job(d->store,d->job,&state)!=MB_STORE_OK ||
            (state!=MB_WRITE_RECEIVING && state!=MB_WRITE_READY)) d->job=0;
    }
    mb_store_error e=MB_STORE_OK; const mb_ram_file *f;
    switch(r->op) {
    case MB_FILES_CAPS:
        out->file_count=MB_FILE_COUNT; out->count=MB_FILES_CHUNK; out->token=MB_FILE_BYTES; break;
    case MB_FILES_LIST:
        for (unsigned i=0;i<MB_FILE_COUNT;i++) if (d->store->files[i].present)
            meta(&out->files[out->file_count++],&d->store->files[i]);
        out->free_slots=MB_FILE_COUNT-out->file_count; out->used=(uint32_t)mb_store_used(d->store); break;
    case MB_FILES_STAT:
        e=mb_store_view(d->store,r->path,r->path_length,&f);
        if (!e) meta(&out->files[0],f);
        break;
    case MB_FILES_READ:
        e=mb_store_read_revision(d->store,r->path,r->path_length,r->token,r->arg,out->data,r->count);
        if (!e) { out->token=r->token; out->count=r->count; }
        break;
    case MB_FILES_BEGIN:
        if (d->job) e=MB_STORE_BUSY;
        else e=mb_store_begin_revision(d->store,r->path,r->path_length,r->arg,r->token,&d->job);
        if (!e) out->token=d->job;
        break;
    case MB_FILES_APPEND:
        if (!d->job || d->job!=r->token) e=MB_STORE_STATE;
        else e=mb_store_append(d->store,r->token,r->arg,r->data,r->count);
        if (!e) out->count=d->store->received;
        break;
    case MB_FILES_FINISH:
        if (!d->job || d->job!=r->token) e=MB_STORE_STATE;
        else {
            e=mb_store_finish(d->store,r->token);
            if (!e) {
                (void)mb_store_poll(d->store);
                e=d->store->state==MB_WRITE_DONE ? MB_STORE_OK : d->store->job_error;
                if (!e) meta(&out->files[0],&d->store->files[d->store->slot]);
                d->job=0;
            }
        }
        break;
    case MB_FILES_CANCEL:
        if (!d->job || d->job!=r->token) e=MB_STORE_STATE;
        else { e=mb_store_cancel(d->store,r->token); if (!e) d->job=0; }
        break;
    default: out->status=MB_FILES_PROTOCOL; return;
    }
    out->status=convert(e);
}
