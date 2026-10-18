/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdint.h>
#include <stddef.h>
int fj_socket_allocate(void);
int fj_socket_listen(uint8_t socket,uint16_t port);
int fj_socket_accept(uint8_t listener);
int fj_socket_available(uint8_t socket);
int fj_socket_state(uint8_t socket);
int fj_socket_server_state(uint8_t socket);
int fj_socket_read(uint8_t socket,uint8_t *dst,size_t size);
int fj_socket_write(uint8_t socket,const uint8_t *src,size_t size);
int fj_socket_close(uint8_t socket);
