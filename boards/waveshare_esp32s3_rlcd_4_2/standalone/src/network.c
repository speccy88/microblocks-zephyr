/* SPDX-License-Identifier: MIT */
#include "server.h"
#include "device_secrets.h"
#include "rlcd_board.h"
#include <zephyr/kernel.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4_server.h>
#include <zephyr/sys/printk.h>
#include <stdio.h>
#include <string.h>

char board_ip[NET_IPV4_ADDR_LEN] = "192.168.4.1";
const char *mb_network_ip(void) { return board_ip; }

static void ap_status_work(struct k_work *work)
{
    ARG_UNUSED(work);
    struct net_if *iface = net_if_get_wifi_sap();
    struct wifi_iface_status status = {0};
    int err = net_mgmt(NET_REQUEST_WIFI_IFACE_STATUS, iface, &status, sizeof(status));
    printk("MicroBlocks AP status: result=%d up=%d carrier=%d dormant=%d state=%d mode=%d ssid_match=%d\n",
        err, net_if_is_up(iface), net_if_is_carrier_ok(iface), net_if_is_dormant(iface),
        status.state, status.iface_mode, !strcmp(status.ssid, MB_DEVICE_SSID));
    if (k_uptime_get() < 90000) k_work_reschedule(k_work_delayable_from_work(work), K_SECONDS(5));
}
K_WORK_DELAYABLE_DEFINE(ap_status, ap_status_work);

int mb_fallback_start(void)
{
    struct net_if *iface = net_if_get_wifi_sap();
    if (!iface) return -ENODEV;
    struct net_in_addr addr, mask;
    net_addr_pton(NET_AF_INET, board_ip, &addr);
    net_addr_pton(NET_AF_INET, "255.255.255.0", &mask);
    if (!net_if_ipv4_addr_add(iface, &addr, NET_ADDR_MANUAL, 0)) return -EIO;
    net_if_ipv4_set_gw(iface, &addr);
    if (!net_if_ipv4_set_netmask_by_addr(iface, &addr, &mask)) return -EIO;
    struct wifi_connect_req_params config = {
        .ssid = (const uint8_t *)MB_DEVICE_SSID,
        .ssid_length = sizeof(MB_DEVICE_SSID) - 1,
        .psk = (const uint8_t *)MB_DEVICE_PSK,
        .psk_length = sizeof(MB_DEVICE_PSK) - 1,
        .channel = 6,
        .band = WIFI_FREQ_BAND_2_4_GHZ,
        .security = WIFI_SECURITY_TYPE_PSK,
    };
    int err = net_mgmt(NET_REQUEST_WIFI_AP_ENABLE, iface, &config, sizeof(config));
    if (err) return err;
    net_if_up(iface);
    printk("MicroBlocks AP interface: %u up=%d\n", net_if_get_by_iface(iface), net_if_is_up(iface));
    addr.s4_addr[3] = 10;
    err = net_dhcpv4_server_start(iface, &addr);
    if (err) return err;
    char screen[384];
    snprintf(screen, sizeof(screen),
             "MicroBlocks\nWireless IDE\n\nWi-Fi network:\n%s\nPassword:\n%s\n\nhttp://%s\n\nProgram in your browser",
             MB_DEVICE_SSID, MB_DEVICE_PSK, board_ip);
    err = rlcd_display_text(screen);
    printk("MicroBlocks LCD status transfer: %d\n", err);
    printk("MicroBlocks fallback AP ready at http://%s\n", board_ip);
    k_work_reschedule(&ap_status, K_SECONDS(3));
    return 0;
}
