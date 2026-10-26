/* SPDX-License-Identifier: MIT */
#include "storage.h"
#include <string.h>

static bool busy(const mb_store *s) {
    return s->state == MB_WRITE_RECEIVING || s->state == MB_WRITE_READY;
}
static bool first_char(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9') || c == '_';
}
void mb_store_init(mb_store *s) { memset(s, 0, sizeof(*s)); }

mb_store_error mb_store_path(const char *p, size_t n) {
    if (!p || n < 5 || n >= MB_FILE_PATH) return MB_STORE_PATH;
    size_t start;
    bool available;
    if (!memcmp(p, "/RAM/", 5)) { start = 5; available = true; }
    else if (n >= 8 && !memcmp(p, "/Flash/", 7)) { start = 7; available = false; }
    else if (!memcmp(p, "/SD/", 4)) { start = 4; available = false; }
    else return MB_STORE_PATH;
    unsigned components = 1;
    bool first = true;
    for (size_t i = start; i < n; i++) {
        unsigned char c = (unsigned char)p[i];
        if (c == '/') {
            if (first || ++components > 4) return MB_STORE_PATH;
            first = true;
        } else {
            if (!first_char(c) && (first || (c != '-' && c != '.'))) return MB_STORE_PATH;
            first = false;
        }
    }
    if (first) return MB_STORE_PATH;
    return available ? MB_STORE_OK : MB_STORE_UNAVAILABLE;
}

/* Strict UTF-8 text; binary files may contain any byte. */
bool mb_store_utf8(const uint8_t *p, size_t n) {
    if (!p && n) return false;
    for (size_t i = 0; i < n;) {
        uint32_t c = p[i++], min;
        unsigned extra;
        if (!c) return false;
        if (c < 0x80) continue;
        if (c >= 0xc2 && c <= 0xdf) { extra = 1; min = 0x80; c &= 0x1f; }
        else if (c >= 0xe0 && c <= 0xef) { extra = 2; min = 0x800; c &= 0x0f; }
        else if (c >= 0xf0 && c <= 0xf4) { extra = 3; min = 0x10000; c &= 7; }
        else return false;
        if (extra > n - i) return false;
        while (extra--) {
            uint8_t b = p[i++];
            if ((b & 0xc0) != 0x80) return false;
            c = (c << 6) | (b & 0x3f);
        }
        if (c < min || c > 0x10ffff || (c >= 0xd800 && c <= 0xdfff)) return false;
    }
    return true;
}

mb_store_error mb_store_padded_text(const char *p, size_t capacity, size_t max, size_t *length) {
    if (!p || !length || max > MB_FILE_BYTES || !capacity ||
        capacity > ((max + 4) & ~(size_t)3)) return MB_STORE_SIZE;
    size_t n = 0;
    while (n < capacity && p[n]) n++;
    if (n == capacity || n > max) return MB_STORE_SIZE;
    for (size_t i = n; i < capacity; i++) if (p[i]) return MB_STORE_TEXT;
    if (!mb_store_utf8((const uint8_t *)p,n)) return MB_STORE_TEXT;
    *length = n;
    return MB_STORE_OK;
}

static int find(const mb_store *s, const char *p, size_t n) {
    for (unsigned i = 0; i < MB_FILE_COUNT; i++) {
        const mb_ram_file *f = &s->files[i];
        if (f->present && strlen(f->path) == n && !memcmp(f->path, p, n)) return (int)i;
    }
    return -1;
}
static mb_store_error job_valid(const mb_store *s, uint32_t job) {
    return job && job == s->generation ? MB_STORE_OK : MB_STORE_STALE;
}

mb_store_error mb_store_begin_revision(mb_store *s, const char *p, size_t n,
    size_t length, uint32_t revision, uint32_t *job) {
    mb_store_error error = mb_store_path(p, n);
    if (error) return error;
    if (!job || length > MB_FILE_BYTES) return MB_STORE_SIZE;
    if (busy(s)) return MB_STORE_BUSY;
    if (s->generation == MB_FILE_REFERENCE_MAX) return MB_STORE_FULL;
    if (s->revision_counter == MB_FILE_REFERENCE_MAX) return MB_STORE_EXHAUSTED;
    if (revision > MB_FILE_REFERENCE_MAX) return MB_STORE_CONFLICT;
    int slot = find(s, p, n);
    if (!revision && slot >= 0) return MB_STORE_EXISTS;
    if (revision && (slot < 0 || s->files[slot].revision != revision)) return MB_STORE_CONFLICT;
    if (slot < 0) {
        for (unsigned i = 0; i < MB_FILE_COUNT; i++)
            if (!s->files[i].present) { slot = (int)i; break; }
        if (slot < 0) return MB_STORE_FULL;
    }
    memset(s->path, 0, sizeof(s->path));
    memcpy(s->path, p, n);
    s->slot = (uint8_t)slot;
    s->expected = (uint16_t)length; s->received = 0;
    s->expected_revision = revision; s->job_error = MB_STORE_OK;
    s->state = MB_WRITE_RECEIVING;
    *job = ++s->generation;
    return MB_STORE_OK;
}

mb_store_error mb_store_begin(mb_store *s, const char *p, size_t n,
    size_t length, bool replace, uint32_t *job) {
    mb_store_error e = mb_store_path(p,n);
    if (e) return e;
    int slot = find(s,p,n);
    uint32_t revision = replace && slot >= 0 ? s->files[slot].revision : 0;
    return mb_store_begin_revision(s,p,n,length,revision,job);
}

mb_store_error mb_store_append(mb_store *s, uint32_t job, size_t offset,
    const uint8_t *data, size_t n) {
    mb_store_error e = job_valid(s, job);
    if (e) return e;
    if (s->state != MB_WRITE_RECEIVING) return MB_STORE_STATE;
    if (offset != s->received) return MB_STORE_ORDER;
    if ((!data && n) || n > MB_FILE_CHUNK || n > (size_t)(s->expected - s->received)) return MB_STORE_SIZE;
    if (n) memcpy(s->staging + offset, data, n);
    s->received += (uint16_t)n;
    return MB_STORE_OK;
}
mb_store_error mb_store_finish(mb_store *s, uint32_t job) {
    mb_store_error e = job_valid(s, job);
    if (e) return e;
    if (s->state != MB_WRITE_RECEIVING) return MB_STORE_STATE;
    if (s->received != s->expected) return MB_STORE_SIZE;
    s->state = MB_WRITE_READY;
    return MB_STORE_OK;
}
mb_store_error mb_store_cancel(mb_store *s, uint32_t job) {
    mb_store_error e = job_valid(s, job);
    if (e) return e;
    if (!busy(s)) return MB_STORE_STATE;
    memset(s->staging, 0, sizeof(s->staging));
    s->state = MB_WRITE_CANCELLED;
    return MB_STORE_OK;
}
mb_store_error mb_store_job(const mb_store *s, uint32_t job, mb_write_state *state) {
    mb_store_error e = job_valid(s, job);
    if (e) return e;
    if (!state) return MB_STORE_STATE;
    *state = s->state;
    return MB_STORE_OK;
}
bool mb_store_poll(mb_store *s) {
    if (s->state != MB_WRITE_READY) return false;
    mb_ram_file *f = &s->files[s->slot];
    /* All callers must serialize on the store owner. Recheck before committing
       so even a future backend mutation cannot silently overwrite a revision. */
    bool matches = s->expected_revision ? f->present && f->revision == s->expected_revision &&
        !strcmp(f->path,s->path) : !f->present;
    if (!matches || s->revision_counter == MB_FILE_REFERENCE_MAX) {
        s->job_error = matches ? MB_STORE_EXHAUSTED : MB_STORE_CONFLICT;
        memset(s->staging,0,sizeof(s->staging));
        s->state = MB_WRITE_FAILED;
        return true;
    }
    memcpy(f->data, s->staging, s->expected);
    memset(f->data + s->expected, 0, MB_FILE_BYTES - s->expected);
    memcpy(f->path, s->path, sizeof(f->path));
    f->length = s->expected; f->present = true;
    f->revision = ++s->revision_counter;
    memset(s->staging, 0, sizeof(s->staging));
    s->state = MB_WRITE_DONE;
    return true;
}
void mb_store_stop(mb_store *s) {
    if (busy(s)) (void)mb_store_cancel(s, s->generation);
}
mb_store_error mb_store_view(const mb_store *s, const char *p, size_t n, const mb_ram_file **file) {
    mb_store_error e = mb_store_path(p, n);
    if (e) return e;
    int slot = find(s, p, n);
    if (slot < 0) return MB_STORE_NOT_FOUND;
    if (!file) return MB_STORE_STATE;
    *file = &s->files[slot];
    return MB_STORE_OK;
}
mb_store_error mb_store_read(const mb_store *s, const char *p, size_t n,
    size_t offset, uint8_t *out, size_t length) {
    const mb_ram_file *f;
    mb_store_error e = mb_store_view(s, p, n, &f);
    if (e) return e;
    if (length > MB_FILE_CHUNK || offset > f->length || length > f->length - offset || (!out && length)) return MB_STORE_SIZE;
    if (length) memcpy(out, f->data + offset, length);
    return MB_STORE_OK;
}
mb_store_error mb_store_read_revision(const mb_store *s, const char *p, size_t n,
    uint32_t revision, size_t offset, uint8_t *out, size_t length) {
    const mb_ram_file *f;
    mb_store_error e = mb_store_view(s,p,n,&f);
    if (e) return e;
    if (!revision || revision != f->revision) return MB_STORE_CONFLICT;
    return mb_store_read(s,p,n,offset,out,length);
}
mb_store_error mb_store_delete(mb_store *s, const char *p, size_t n) {
    mb_store_error e = mb_store_path(p, n);
    if (e) return e;
    if (busy(s)) return MB_STORE_BUSY;
    int slot = find(s, p, n);
    if (slot < 0) return MB_STORE_NOT_FOUND;
    memset(&s->files[slot], 0, sizeof(s->files[slot]));
    return MB_STORE_OK;
}
size_t mb_store_used(const mb_store *s) {
    size_t bytes = 0;
    for (unsigned i = 0; i < MB_FILE_COUNT; i++) if (s->files[i].present) bytes += s->files[i].length;
    return bytes;
}
unsigned mb_store_count(const mb_store *s) {
    unsigned count = 0;
    for (unsigned i = 0; i < MB_FILE_COUNT; i++) count += s->files[i].present;
    return count;
}
const char *mb_store_error_text(mb_store_error e) {
    static const char *const text[] = {"OK", "Use a safe /RAM/file path", "Storage backend unavailable",
        "File not found", "File exists: choose replace explicitly", "No free file slots or job references",
        "File or chunk size out of range", "A file write is already pending", "Expired write reference",
        "Write is not in the required state", "Write chunks must be sequential", "File is not UTF-8 text without NUL",
        "File changed: reopen its current revision", "File revision limit reached"};
    return (unsigned)e < sizeof(text)/sizeof(text[0]) ? text[e] : "Unknown storage error";
}
const char *mb_store_state_text(mb_write_state state) {
    static const char *const text[] = {"idle", "receiving", "ready", "done", "cancelled", "failed"};
    return (unsigned)state < sizeof(text)/sizeof(text[0]) ? text[state] : "invalid";
}
