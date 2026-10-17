/* SPDX-License-Identifier: MPL-2.0
 * Two alternating snapshots; commit the header only after writing the payload.
 * Called exclusively by the VM thread. Program records persist; live variable
 * values and task stacks do not. */
#include <zephyr/kernel.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/sys/crc.h>
#include <zephyr/sys/printk.h>
#include <string.h>

extern unsigned char *smallvmCodeData(void);
extern unsigned smallvmCodeSize(void);
#define SLOT_SIZE 0x20000u
#define DATA_OFFSET 4096u
#define MAGIC 0x4d425a31u
struct snapshot_header { uint32_t magic, version, generation, size, crc, reserved[3]; };
static const struct flash_area *area;
static uint32_t generation, saved_crc, observed_crc;
static int active = -1;
static int64_t next_check, changed_at;
static bool baseline;

static bool valid_records(const unsigned char *data, unsigned size)
{
    const uint32_t *words = (const uint32_t *)data;
    if (size < 8 || (words[0] >> 24) != 'S') return false;
    unsigned pos = 1;
    /* v417 uses one cycle-counter word on this platform. */
    while (pos < size / 4) {
        if (words[pos] == UINT32_MAX) return true;
        if ((words[pos] >> 24) != 'R' || pos + 1 >= size / 4) return false;
        uint32_t length = words[pos + 1];
        if (length > size / 4 - pos - 2) return false;
        pos += length + 2;
    }
    return pos == size / 4;
}

int mb_store_load(void)
{
    int err = flash_area_open(FIXED_PARTITION_ID(vmstore), &area);
    if (err) return err;
    if (area->fa_size < 2 * SLOT_SIZE || smallvmCodeSize() > SLOT_SIZE - DATA_OFFSET) return -EFBIG;
    struct snapshot_header h[2];
    bool valid[2] = {false, false};
    for (int i = 0; i < 2; ++i) {
        err = flash_area_read(area, i * SLOT_SIZE, &h[i], sizeof(h[i]));
        valid[i] = !err && h[i].magic == MAGIC && h[i].version == 1 && h[i].size == smallvmCodeSize();
    }
    int first = valid[1] && (!valid[0] || (int32_t)(h[1].generation - h[0].generation) > 0) ? 1 : 0;
    for (int n = 0; n < 2; ++n) {
        int i = first ^ n;
        if (!valid[i]) continue;
        err = flash_area_read(area, i * SLOT_SIZE + DATA_OFFSET, smallvmCodeData(), smallvmCodeSize());
        if (!err && crc32_ieee(smallvmCodeData(), smallvmCodeSize()) == h[i].crc &&
            valid_records(smallvmCodeData(), smallvmCodeSize())) {
            active = i; generation = h[i].generation; saved_crc = observed_crc = h[i].crc;
            baseline = true;
            printk("MicroBlocks program restored: generation %u\n", generation);
            return 0;
        }
    }
    memset(smallvmCodeData(), 0, smallvmCodeSize());
    return -ENOENT;
}

void mb_store_poll(void)
{
    int64_t now = k_uptime_get();
    if (!area || now < next_check) return;
    next_check = now + 1000;
    uint32_t crc = crc32_ieee(smallvmCodeData(), smallvmCodeSize());
    if (!baseline) { saved_crc = observed_crc = crc; baseline = true; return; }
    if (crc != observed_crc) { observed_crc = crc; changed_at = now; return; }
    if (crc == saved_crc || now - changed_at < 2000 || !valid_records(smallvmCodeData(), smallvmCodeSize())) return;
    int slot = active == 0 ? 1 : 0;
    struct snapshot_header h = { .magic = MAGIC, .version = 1, .generation = generation + 1,
        .size = smallvmCodeSize(), .crc = crc };
    int err = flash_area_erase(area, slot * SLOT_SIZE, DATA_OFFSET + smallvmCodeSize());
    if (!err) err = flash_area_write(area, slot * SLOT_SIZE + DATA_OFFSET, smallvmCodeData(), smallvmCodeSize());
    if (!err) err = flash_area_write(area, slot * SLOT_SIZE, &h, sizeof(h));
    if (!err) { active = slot; generation = h.generation; saved_crc = crc; }
    else next_check = now + 10000;
    printk("MicroBlocks program save: %d generation %u\n", err, generation);
}

unsigned mb_store_generation(void) { return generation; }
