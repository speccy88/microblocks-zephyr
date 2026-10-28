/* SPDX-License-Identifier: MIT */
#include "probe.h"
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/printk.h>
#include <inttypes.h>
BUILD_ASSERT(DT_NODE_HAS_STATUS(DT_NODELABEL(sdhc0),okay),"SD slot 0 required");
BUILD_ASSERT(!DT_NODE_HAS_STATUS(DT_NODELABEL(sdhc1),okay),"Isolated probe excludes C6 slot 1");
int main(void)
{
 const struct device *uart=DEVICE_DT_GET(DT_CHOSEN(zephyr_console));
 if(!device_is_ready(uart))return -ENODEV;
 printk("P4 SD read-only diagnostic; NOT MicroBlocks. Send T for one probe.\n");
 for(;;){
  unsigned char command;
  if(uart_poll_in(uart,&command)==0 && command=='T'){
   struct p4_sd_probe_result r;int e=p4_sd_readonly_probe(&r);
   printk("SDRO error=%d card_bytes=%" PRIu64 " free_available=%u free_error=%d free=%" PRIu64 " entries=%u files=%u dirs=%u truncated=%u close=%d unmount=%d\n",
    e,r.card_bytes,(unsigned)r.free_space_available,r.free_space_error,r.free_bytes,r.entries,r.files,r.directories,(unsigned)r.truncated,r.close_error,r.unmount_error);
  }
  k_sleep(K_MSEC(20));
 }
}
