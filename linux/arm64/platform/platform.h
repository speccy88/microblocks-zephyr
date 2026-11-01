/* SPDX-License-Identifier: MPL-2.0 */
#ifndef SMALLVM_LINUX_PLATFORM_H
#define SMALLVM_LINUX_PLATFORM_H
#include <stdint.h>
int linuxPlatformOpen(const char *data_dir, const char *pty_info);
void linuxPlatformClose(void);
int linuxPlatformSlave(void);
int linuxPlatformMaster(void);
const char *linuxPlatformPty(void);
const char *linuxPlatformInfo(void);
void linuxPlatformFatal(const char *reason);
int linuxPlatformSelfTest(void);
#endif
