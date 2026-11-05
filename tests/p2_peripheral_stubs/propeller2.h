/* SPDX-License-Identifier: MIT */
#include <stdint.h>
void _pinclear(int pin);
void _pinl(int pin);
void _pinh(int pin);
void _pinf(int pin);
void _pinw(int pin,int value);
uint32_t _getus(void);
int _pinr(int pin);
void _wrpin(int pin,uint32_t mode);
void _waitus(int delay);
