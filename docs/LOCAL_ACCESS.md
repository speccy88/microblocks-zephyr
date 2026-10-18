# Direct local access

At the user's explicit request on 2026-10-18, the editor and binary VM transport
connect without an application code or login. Every device that can reach the
board can upload and execute programs. This is the intended private-LAN mode;
do not expose the service to the Internet.

The generated private build file now contains only the existing fallback AP
SSID and Wi-Fi password. Rebuilds migrate old files while preserving those
values. Saved station credentials, WPA2 fallback AP, KEY recovery, same-origin
WebSocket/POST validation, browser CSP/isolation headers, bounded queues and
one active VM controller remain in place. No new access mechanism replaces
the removed code. Wi-Fi setup uses the same-origin page without a code field.

Fresh and existing browser sessions connect directly. The adapter removes the
obsolete stored session value during migration. Historical logs and earlier
checkpoint descriptions remain evidence of the previous behavior.
