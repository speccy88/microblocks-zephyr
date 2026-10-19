/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

#ifndef P2_BOARD_H
#define P2_BOARD_H

#define P2_FIRST_USER_PIN 0
#define P2_LAST_NON_BOOT_PIN 57

#if defined(P2_EVAL_BOARD)
	#define P2_BOARD_NAME "Parallax P2 Eval Rev C"
	#define P2_USER_PIN_COUNT 58
	#define P2_USER_LED_PIN 56
	#define P2_USER_LED_ACTIVE_LOW 1
#elif defined(P2_EDGE_BOARD)
	#define P2_BOARD_NAME "Parallax P2 Edge"
	#define P2_USER_PIN_COUNT 58
	#define P2_USER_LED_PIN 56
	#define P2_USER_LED_ACTIVE_LOW 0
#elif defined(P2_EDGE32MB_BOARD)
	#define P2_BOARD_NAME "Parallax P2 Edge 32MB"
	#define P2_USER_PIN_COUNT 40
	#define P2_USER_LED_PIN 38
	#define P2_USER_LED_ACTIVE_LOW 0
#else
	#error Select a supported Parallax P2 board variant
#endif

#define P2_LAST_USER_PIN (P2_USER_PIN_COUNT - 1)

#endif
