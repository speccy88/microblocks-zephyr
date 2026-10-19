/* SPDX-License-Identifier: MIT
 * Exercise the actual generated HTTP/1 scheduler functions with fake sends.
 * No socket, Zephyr runtime, credential or hardware access. */
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define CONFIG_HTTP_SERVER_MAX_CLIENTS 4
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define F_CONNECTION_CLOSE 1
enum { HTTP_SERVER_PREFACE_STATE=1,HTTP_SERVER_DONE_STATE=2 };
enum http_transaction_status {HTTP_SERVER_REQUEST_DATA_FINAL=1,HTTP_SERVER_TRANSACTION_COMPLETE=2};
struct http_client_ctx { char url_buffer[192];int header_capture_ctx;struct {int flags;} parser;int server_state;void *current_detail;bool http10;int chunks,goal,complete,sends;int cb_error,send_error;int param_len[8]; };
struct http_request_ctx {int parameter_length;};
struct http_response_ctx {bool final_chunk;};
struct http_resource_detail_dynamic {struct {int path_len;} common;int (*cb)(struct http_client_ctx *,enum http_transaction_status,struct http_request_ctx *,struct http_response_ctx *,void *);void *user_data;struct http_client_ctx *holder;};
static bool is_client_http10(struct http_client_ctx *c){return c->http10;}
static int enter_http_done_state(struct http_client_ctx *c){c->server_state=HTTP_SERVER_DONE_STATE;return 0;}
static void populate_request_ctx(struct http_request_ctx *r,char *p,int n,int *headers){(void)p;(void)headers;r->parameter_length=n;}
static bool http_response_is_final(struct http_response_ctx *r,enum http_transaction_status s){(void)s;return r->final_chunk;}
static int http1_dynamic_response(struct http_client_ctx *c,struct http_response_ctx *r,enum http_transaction_status s,struct http_resource_detail_dynamic *d){(void)r;(void)s;(void)d;c->sends++;return c->send_error;}
#include "http_scheduler_under_test.inc"
static unsigned checks;
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"scheduler check failed at line %d\n",__LINE__);exit(1);}} while(0)
static int callback(struct http_client_ctx *c,enum http_transaction_status s,struct http_request_ctx *req,struct http_response_ctx *rsp,void *user)
{
 (void)user;if(s==HTTP_SERVER_TRANSACTION_COMPLETE){c->complete++;return 0;}
 if(c->cb_error)return c->cb_error;
 c->param_len[c->chunks]=req->parameter_length;c->chunks++;rsp->final_chunk=c->chunks==c->goal;return 0;
}
static void init(struct http_client_ctx *c,struct http_resource_detail_dynamic *d,int count)
{
 memset(c,0,sizeof(*c));memset(d,0,sizeof(*d));strcpy(c->url_buffer,"/q");c->goal=count;
 d->common.path_len=1;d->cb=callback;d->holder=c; /* Upstream ordinary GET starts with no current_detail. */
}
int main(void)
{
 struct http_client_ctx c[5];struct http_resource_detail_dynamic d[5];
 init(&c[0],&d[0],3);
 CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==0);CHECK(c[0].chunks==1 && c[0].sends==1 && c[0].complete==0);CHECK(xrp_http1_pending(&c[0]));
 CHECK(c[0].current_detail==&d[0].common); /* Continuation must retain the real resource. */
 CHECK(xrp_http1_continue(&c[0])==0);CHECK(c[0].chunks==2 && c[0].sends==2 && c[0].complete==0);CHECK(xrp_http1_pending(&c[0]));
 CHECK(xrp_http1_continue(&c[0])==0);CHECK(c[0].chunks==3 && c[0].complete==1);CHECK(!xrp_http1_pending(&c[0]) && d[0].holder==NULL);CHECK(c[0].server_state==HTTP_SERVER_PREFACE_STATE);
 CHECK(c[0].param_len[0]==1 && c[0].param_len[1]==0 && c[0].param_len[2]==0);
 for(int mode=0;mode<2;mode++){
  init(&c[0],&d[0],2);c[0].http10=mode==0;c[0].parser.flags=mode==1 ? F_CONNECTION_CLOSE : 0;
  CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==0);CHECK(xrp_http1_continue(&c[0])==-ENOTCONN);CHECK(c[0].complete==1 && c[0].server_state==HTTP_SERVER_DONE_STATE && !xrp_http1_pending(&c[0]));
 }
 for(int i=0;i<5;i++)init(&c[i],&d[i],2);
 for(int i=0;i<4;i++){CHECK(dynamic_get_del_opts_req(&d[i],&c[i])==0);CHECK(c[i].chunks==1);}
 CHECK(dynamic_get_del_opts_req(&d[4],&c[4])==-ENOBUFS);
 xrp_http1_cancel(&c[1]);CHECK(!xrp_http1_pending(&c[1]));
 CHECK(dynamic_get_del_opts_req(&d[4],&c[4])==0);CHECK(!xrp_http1_pending(&c[4])); /* Its second chunk completes. */
 for(int i=0;i<4;i++)xrp_http1_cancel(&c[i]);
 init(&c[0],&d[0],2);CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==0);xrp_http1_cancel(&c[0]);
 init(&c[0],&d[0],1);CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==0);CHECK(c[0].complete==1 && !xrp_http1_pending(&c[0]));
 init(&c[0],&d[0],2);c[0].cb_error=-EINVAL;CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==-EINVAL);CHECK(c[0].sends==0 && !xrp_http1_pending(&c[0]));
 init(&c[0],&d[0],2);CHECK(dynamic_get_del_opts_req(&d[0],&c[0])==0);c[0].send_error=-EIO;CHECK(xrp_http1_continue(&c[0])==-EIO);xrp_http1_cancel(&c[0]);CHECK(!xrp_http1_pending(&c[0]));
 printf("{\"result\":\"PASS\",\"checks\":%u}\n",checks);return 0;
}
