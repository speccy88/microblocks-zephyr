/* SPDX-License-Identifier: MIT
 * Synthetic credentials and RAM flash only. No device/network access. */
#include "network_setup_store.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned checks;
#define CHECK(condition) do { ++checks; if (!(condition)) { \
    fprintf(stderr, "Network setup check failed at line %u\n", __LINE__); exit(1); } } while (0)
static const uint8_t old_ssid[] = "Synthetic old SSID", new_ssid[] = "Synthetic new SSID";
static const uint8_t old_key[] = "test-only-old-key", new_key[] = "test-only-new-key";
#define LEN(a) (sizeof(a) - 1)

static bool zeroed(const void *data, size_t size)
{
    const uint8_t *p = data;
    for (size_t i = 0; i < size; ++i) if (p[i]) return false;
    return true;
}
static size_t packet(uint8_t *out, unsigned operation, unsigned flags)
{
    memset(out, 0, MBNW_MAX_REQUEST + 1);
    memcpy(out, "MBNW", 4); out[4] = 2; out[5] = operation;
    out[6] = 0x12; out[7] = 0x34; out[8] = 0x56; out[9] = 0x78;
    if (operation != MBNW_CONNECT) return 10;
    out[10] = flags; out[11] = LEN(old_ssid); out[12] = LEN(old_key);
    memcpy(out + 13, old_ssid, LEN(old_ssid));
    memcpy(out + 13 + LEN(old_ssid), old_key, LEN(old_key));
    return 13 + LEN(old_ssid) + LEN(old_key);
}
static void protocol(void)
{
    uint8_t body[MBNW_MAX_REQUEST + 1]; struct mbnw_request r;
    size_t n = packet(body, MBNW_PROBE, 0);
    CHECK(mbnw_decode(body, n, &r) == MBNW_OK);
    CHECK(r.id == UINT32_C(0x78563412) && r.operation == MBNW_PROBE && !r.ssid);
    CHECK(mbnw_authorize(&r, false, true) == MBNW_NOT_LOCAL);
    CHECK(mbnw_authorize(&r, true, false) == MBNW_OK);
    n = packet(body, MBNW_STATUS, 0);
    CHECK(mbnw_decode(body, n, &r) == MBNW_OK);
    CHECK(mbnw_authorize(&r, true, false) == MBNW_OK);
    n = packet(body, MBNW_CONNECT, 0);
    CHECK(mbnw_decode(body, n, &r) == MBNW_OK);
    CHECK(r.ssid_length == LEN(old_ssid) && r.key_length == LEN(old_key));
    CHECK(!memcmp(r.ssid, old_ssid, r.ssid_length));
    CHECK(mbnw_authorize(&r, true, false) == MBNW_OK);
    CHECK(mbnw_authorize(&r, false, true) == MBNW_NOT_LOCAL);
    n = packet(body, MBNW_CONNECT, MBNW_REMEMBER);
    CHECK(mbnw_decode(body, n, &r) == MBNW_OK);
    CHECK(mbnw_authorize(&r, true, false) == MBNW_UNSUPPORTED);
    CHECK(mbnw_authorize(&r, true, true) == MBNW_OK);
    for (size_t size = 0; size <= MBNW_MAX_REQUEST + 1; ++size) {
        if (size == n) continue;
        memset(&r, 0xa5, sizeof(r));
        CHECK(mbnw_decode(body, size, &r) != MBNW_OK);
        CHECK(zeroed(&r, sizeof(r)));
    }
    for (unsigned flags = 2; flags < 256; ++flags) {
        packet(body, MBNW_CONNECT, flags);
        CHECK(mbnw_decode(body, n, &r) == MBNW_FORMAT);
        CHECK(zeroed(&r, sizeof(r)));
    }
    n = packet(body, MBNW_CONNECT, 0); body[0] ^= 1;
    CHECK(mbnw_decode(body, n, &r) == MBNW_FORMAT);
    packet(body, MBNW_CONNECT, 0); body[4] = 3;
    CHECK(mbnw_decode(body, n, &r) == MBNW_FORMAT);
    packet(body, MBNW_CONNECT, 0); memset(body + 6, 0, 4);
    CHECK(mbnw_decode(body, n, &r) == MBNW_FORMAT);
    packet(body, 99, 0); CHECK(mbnw_decode(body, 10, &r) == MBNW_UNSUPPORTED);
    CHECK(mbnw_decode(NULL, 10, &r) == MBNW_FORMAT);
    CHECK(mbnw_decode(body, 10, NULL) == MBNW_FORMAT);
    CHECK(mbnw_authorize(NULL, true, true) == MBNW_FORMAT);
    uint8_t ssid[33], key[65]; memset(ssid, 's', sizeof(ssid)); memset(key, 'a', sizeof(key));
    CHECK(mbnw_credentials_valid(ssid, 32, key, 64)); key[63] = 'g';
    CHECK(!mbnw_credentials_valid(ssid, 32, key, 64));
    CHECK(mbnw_credentials_valid(ssid, 1, key, 8));
    CHECK(!mbnw_credentials_valid(ssid, 0, key, 8));
    CHECK(!mbnw_credentials_valid(ssid, 33, key, 8));
    CHECK(!mbnw_credentials_valid(ssid, 1, key, 7));
    CHECK(!mbnw_credentials_valid(ssid, 1, key, 65));
    key[2] = 0; CHECK(!mbnw_credentials_valid(ssid, 1, key, 8));
    key[2] = 'a'; ssid[0] = 0; CHECK(!mbnw_credentials_valid(ssid, 1, key, 8));
    memset(body, 0xa5, sizeof(body)); mbnw_clear(body, sizeof(body)); CHECK(zeroed(body, sizeof(body)));
}

struct flash {
    uint8_t slots[2][4096];
    int budget, read_error_slot;
    bool erase_error, corrupt_write;
    unsigned erases, writes;
};
static void fresh(struct flash *f)
{
    memset(f, 0, sizeof(*f)); memset(f->slots, 0xff, sizeof(f->slots));
    f->budget = -1; f->read_error_slot = -1;
}
static int read_slot(void *context, unsigned slot, size_t offset, void *data, size_t size)
{
    struct flash *f = context;
    if (slot > 1 || offset > 4096 || size > 4096 - offset || (int)slot == f->read_error_slot) return -1;
    memcpy(data, f->slots[slot] + offset, size); return 0;
}
static int erase_slot(void *context, unsigned slot)
{
    struct flash *f = context;
    if (slot > 1) return -1;
    ++f->erases;
    memset(f->slots[slot], 0xff, f->erase_error ? 2048 : 4096);
    return f->erase_error ? -1 : 0;
}
static int write_slot(void *context, unsigned slot, size_t offset, const void *data, size_t size)
{
    struct flash *f = context; const uint8_t *src = data;
    if (slot > 1 || offset > 4096 || size > 4096 - offset) return -1;
    ++f->writes;
    for (size_t i = 0; i < size; ++i) {
        if (f->budget == 0 || (f->slots[slot][offset + i] & src[i]) != src[i]) return -1;
        f->slots[slot][offset + i] = src[i];
        if (f->budget > 0) --f->budget;
    }
    if (f->corrupt_write) f->slots[slot][offset] ^= 1;
    return 0;
}
static struct mbnw_store backend(struct flash *f)
{
    return (struct mbnw_store){f, read_slot, erase_slot, write_slot};
}
static int old_save(const struct mbnw_store *s)
{
    return mbnw_store_save(s, old_ssid, LEN(old_ssid), old_key, LEN(old_key));
}
static int new_save(const struct mbnw_store *s)
{
    return mbnw_store_save(s, new_ssid, LEN(new_ssid), new_key, LEN(new_key));
}
static void expect(const struct mbnw_store *s, bool is_new, uint32_t generation, unsigned selected)
{
    struct mbnw_credentials c; unsigned slot = 9;
    CHECK(mbnw_store_load(s, &c, &slot) == MBNW_OK);
    CHECK(c.generation == generation && slot == selected);
    CHECK(c.ssid_length == (is_new ? LEN(new_ssid) : LEN(old_ssid)));
    CHECK(!memcmp(c.ssid, is_new ? new_ssid : old_ssid, c.ssid_length));
    CHECK(!memcmp(c.key, is_new ? new_key : old_key, c.key_length));
    mbnw_clear(&c, sizeof(c)); CHECK(zeroed(&c, sizeof(c)));
}
/* Fixture helper, not the implementation's private CRC routine. */
static void fixture_generation(uint8_t *r, uint32_t generation)
{
    for (unsigned i = 0; i < 4; ++i) r[8 + i] = generation >> (8 * i);
    uint32_t crc = UINT32_MAX;
    for (unsigned i = 0; i < 108; ++i) {
        crc ^= r[i];
        for (unsigned bit = 0; bit < 8; ++bit) crc = crc & 1 ? (crc >> 1) ^ UINT32_C(0xedb88320) : crc >> 1;
    }
    crc = ~crc;
    for (unsigned i = 0; i < 4; ++i) r[108 + i] = crc >> (8 * i);
}
static void storage(void)
{
    struct flash baseline, f; fresh(&baseline);
    struct mbnw_store base = backend(&baseline), s = backend(&f);
    struct mbnw_credentials c; unsigned slot;
    memset(&c, 0xa5, sizeof(c));
    CHECK(mbnw_store_load(&base, &c, &slot) == MBNW_EMPTY); CHECK(zeroed(&c, sizeof(c)));
    CHECK(old_save(&base) == MBNW_OK); expect(&base, false, 1, 0);
    for (int cut = 0; cut <= (int)MBNW_RECORD_SIZE; ++cut) {
        f = baseline; f.budget = cut;
        CHECK(new_save(&s) == (cut == (int)MBNW_RECORD_SIZE ? MBNW_OK : MBNW_IO));
        CHECK(!memcmp(f.slots[0], baseline.slots[0], sizeof(f.slots[0])));
        expect(&s, cut == (int)MBNW_RECORD_SIZE, cut == (int)MBNW_RECORD_SIZE ? 2 : 1,
               cut == (int)MBNW_RECORD_SIZE ? 1 : 0);
    }
    f = baseline; CHECK(new_save(&s) == MBNW_OK);
    struct flash completed = f;
    for (unsigned byte = 0; byte < MBNW_RECORD_SIZE; ++byte) {
        for (unsigned bit = 0; bit < 8; ++bit) {
            f = completed; f.slots[1][byte] ^= 1u << bit;
            expect(&s, false, 1, 0);
        }
    }
    f = baseline; f.erase_error = true;
    CHECK(new_save(&s) == MBNW_IO); expect(&s, false, 1, 0);
    f = baseline; f.corrupt_write = true;
    CHECK(new_save(&s) == MBNW_IO); expect(&s, false, 1, 0);
    for (int bad_slot = 0; bad_slot < 2; ++bad_slot) {
        f = baseline; f.read_error_slot = bad_slot; unsigned erases = f.erases;
        CHECK(new_save(&s) == MBNW_IO); CHECK(f.erases == erases);
        memset(&c, 0xa5, sizeof(c));
        CHECK(mbnw_store_load(&s, &c, &slot) == MBNW_IO); CHECK(zeroed(&c, sizeof(c)));
    }
    f = baseline; fixture_generation(f.slots[0], UINT32_MAX);
    expect(&s, false, UINT32_MAX, 0); CHECK(new_save(&s) == MBNW_OK); expect(&s, true, 1, 1);
    CHECK(old_save(&s) == MBNW_OK); expect(&s, false, 2, 0);
    CHECK(mbnw_store_save(&s, NULL, 0, old_key, LEN(old_key)) == MBNW_CREDENTIALS);
    CHECK(mbnw_store_load(NULL, &c, NULL) == MBNW_FORMAT); CHECK(zeroed(&c, sizeof(c)));
    CHECK(mbnw_store_load(&s, NULL, NULL) == MBNW_FORMAT);
}
int main(void)
{
    protocol(); storage();
    printf("{\"result\":\"PASS\",\"checks\":%u,\"partial_write_cuts\":117,"
           "\"corrupt_new_record_bit_flips\":928,\"hardware\":false,"
           "\"credential_fixture\":\"synthetic public strings only\"}\n", checks);
    return 0;
}
