/* SPDX-License-Identifier: MPL-2.0 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
/* All access is serialized by network_backend's state_lock. Budget is never
 * refilled on success: repeated link flaps remain bounded for the whole boot. */
struct p4_wifi_retry {unsigned used;bool active,pending;int64_t due;};
static inline bool p4_retry_schedule(struct p4_wifi_retry *r,int64_t now)
{
 static const unsigned delays[]={5000,15000,45000};
 if(r->used>=3){r->active=r->pending=false;return false;}
 r->active=r->pending=true;r->due=now+delays[r->used];return true;
}
static inline bool p4_retry_claim(struct p4_wifi_retry *r,int64_t now)
{
 if(!r->active||!r->pending||now<r->due)return false;
 r->pending=false;r->used++;return true;
}
static inline void p4_retry_halt(struct p4_wifi_retry *r)
{r->active=r->pending=false;}
