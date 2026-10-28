/* SPDX-License-Identifier: MIT */
#pragma once
#include <stdbool.h>
#include <errno.h>
struct p4_latency_policy {
 bool attempted,complete,set_requested,confirmed;
 int before_enabled,before_mode,set_error,after_enabled,after_mode,error;
};
/* A volatile policy attempt is never replayed, including after a lost ACK.
 * The read after a setter error observes state; it never resends the setter. */
static inline int p4_latency_policy_run(struct p4_latency_policy *p,void *context,
 int (*read_state)(void *,int *,int *),int (*disable)(void *))
{
 if(p->attempted)return p->error;
 *p=(struct p4_latency_policy){.attempted=true,.before_enabled=-1,.before_mode=-1,.after_enabled=-1,.after_mode=-1};
 int error=read_state(context,&p->before_enabled,&p->before_mode);
 if(error){p->error=error;p->complete=true;return error;}
 if(!p->before_enabled){p->after_enabled=0;p->after_mode=p->before_mode;p->confirmed=p->complete=true;return 0;}
 p->set_requested=true;p->set_error=disable(context);
 error=read_state(context,&p->after_enabled,&p->after_mode);
 p->confirmed=!error&&!p->after_enabled;
 p->error=p->confirmed?0:error?error:p->set_error?p->set_error:-EIO;
 p->complete=true;return p->error;
}
