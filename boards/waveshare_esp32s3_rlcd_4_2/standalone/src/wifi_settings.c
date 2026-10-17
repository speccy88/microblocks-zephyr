/* SPDX-License-Identifier: MIT */
#include "server.h"
#include "device_secrets.h"
#include "rlcd_board.h"
#include <zephyr/kernel.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/net/dhcpv4.h>
#include <zephyr/settings/settings.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/printk.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>

extern char board_ip[NET_IPV4_ADDR_LEN];
extern int mb_fallback_start(void);
static struct { char ssid[33], psk[65]; } credentials;
static struct net_mgmt_event_callback wifi_events;
K_SEM_DEFINE(connected, 0, 1);
static int connect_result;

static int read_settings(const char *name, size_t len, settings_read_cb read, void *arg)
{
    if (strcmp(name, "credentials")) return -ENOENT;
    if (len != sizeof(credentials)) return -EINVAL;
    int n = read(arg, &credentials, sizeof(credentials));
    if (n != sizeof(credentials) || !memchr(credentials.ssid, 0, sizeof(credentials.ssid)) ||
        !memchr(credentials.psk, 0, sizeof(credentials.psk))) {
        memset(&credentials, 0, sizeof(credentials)); return -EINVAL;
    }
    return 0;
}
SETTINGS_STATIC_HANDLER_DEFINE(mb_wifi, "mbwifi", NULL, read_settings, NULL, NULL);

static void reboot_work(struct k_work *work) { ARG_UNUSED(work); sys_reboot(SYS_REBOOT_COLD); }
K_WORK_DELAYABLE_DEFINE(reboot_request, reboot_work);

int mb_network_save(const char *ssid, const char *password)
{
    size_t sn = strlen(ssid), pn = strlen(password);
    if (!sn || sn > 32 || pn > 63 || (pn && pn < 8) || strchr(ssid, '\n') || strchr(password, '\n')) return -EINVAL;
    memset(&credentials, 0, sizeof(credentials));
    memcpy(credentials.ssid, ssid, sn); memcpy(credentials.psk, password, pn);
    int err = settings_save_one("mbwifi/credentials", &credentials, sizeof(credentials));
    if (!err) k_work_reschedule(&reboot_request, K_SECONDS(2));
    return err;
}

bool mb_same_origin(const struct http_request_ctx *request)
{
    char expected[64]; snprintf(expected, sizeof(expected), "http://%s", board_ip);
    for (size_t i = 0; i < request->header_count; ++i)
        if (!strcasecmp(request->headers[i].name, "Origin") &&
            !strcmp(request->headers[i].value, expected)) return true;
    return false;
}

static void wifi_event(struct net_mgmt_event_callback *cb, uint64_t event, struct net_if *iface)
{
    ARG_UNUSED(iface);
    const struct wifi_status *status = cb->info;
    if (event == NET_EVENT_WIFI_CONNECT_RESULT) {
        connect_result = status ? status->status : -EIO;
        k_sem_give(&connected);
    } else if (event == NET_EVENT_WIFI_AP_ENABLE_RESULT) {
        printk("MicroBlocks AP enable result: %d\n", status ? status->status : -EIO);
    } else if (event == NET_EVENT_WIFI_AP_STA_CONNECTED) {
        printk("MicroBlocks AP client connected\n");
    } else if (event == NET_EVENT_WIFI_AP_STA_DISCONNECTED) {
        printk("MicroBlocks AP client disconnected\n");
    }
}

static int station_start(void)
{
    struct net_if *iface = net_if_get_wifi_sta();
    if (!iface) return -ENODEV;
    struct wifi_connect_req_params config = {
        .ssid=(const uint8_t *)credentials.ssid, .ssid_length=strlen(credentials.ssid),
        .psk=(const uint8_t *)credentials.psk, .psk_length=strlen(credentials.psk),
        .security=credentials.psk[0] ? WIFI_SECURITY_TYPE_PSK : WIFI_SECURITY_TYPE_NONE,
        .band=WIFI_FREQ_BAND_2_4_GHZ, .channel=WIFI_CHANNEL_ANY, .timeout=20,
    };
    k_sem_reset(&connected); net_if_up(iface);
    int err = net_mgmt(NET_REQUEST_WIFI_CONNECT, iface, &config, sizeof(config));
    if (err) return err;
    if (k_sem_take(&connected, K_SECONDS(22))) return -ETIMEDOUT;
    if (connect_result) return -ECONNREFUSED;
    net_dhcpv4_start(iface);
    for (int i = 0; i < 100; ++i) {
        struct net_in_addr *address = net_if_ipv4_get_global_addr(iface, NET_ADDR_PREFERRED);
        if (address && address->s_addr) {
            net_addr_ntop(NET_AF_INET, address, board_ip, NET_IPV4_ADDR_LEN);
            char screen[320];
            snprintf(screen, sizeof(screen), "MicroBlocks\nWireless IDE\n\nConnected to Wi-Fi\n\nhttp://%s\n\nPairing code:\n%s\n\nKEY at boot: recovery AP", board_ip, MB_DEVICE_PAIR);
            printk("MicroBlocks LCD status transfer: %d\n", rlcd_display_text(screen));
            printk("MicroBlocks Wi-Fi ready at http://%s\n", board_ip);
            return 0;
        }
        k_sleep(K_MSEC(200));
    }
    net_dhcpv4_stop(iface);
    net_mgmt(NET_REQUEST_WIFI_DISCONNECT, iface, NULL, 0);
    return -ETIMEDOUT;
}

int mb_network_start(void)
{
    int err = settings_subsys_init();
    if (err) return err;
    settings_load_subtree("mbwifi");
    net_mgmt_init_event_callback(&wifi_events, wifi_event,
        NET_EVENT_WIFI_CONNECT_RESULT | NET_EVENT_WIFI_AP_ENABLE_RESULT |
        NET_EVENT_WIFI_AP_STA_CONNECTED | NET_EVENT_WIFI_AP_STA_DISCONNECTED);
    net_mgmt_add_event_callback(&wifi_events);
    /* KEY held during startup selects recovery AP without deleting credentials. */
    if (credentials.ssid[0] && !rlcd_button_pressed(1)) {
        err = station_start();
        printk("MicroBlocks saved network connection result: %d\n", err);
        if (!err) return 0;
    }
    return mb_fallback_start();
}
