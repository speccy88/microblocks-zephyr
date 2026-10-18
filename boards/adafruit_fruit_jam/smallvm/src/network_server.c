/* SPDX-License-Identifier: MIT */
#include "network_server.h"
#include "http_protocol.h"
#include "airlift_socket.h"
#include "airlift.h"
#include "network_transport.h"
#include "fruit_jam.h"
#include <zephyr/kernel.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>

enum {FREE,REQUEST,HTTP_SEND,WS_UPGRADE,WS_STREAM};
struct client {
    unsigned state;uint8_t socket;bool owns_vm,fragment;
    uint8_t input[2200],output[2052];size_t input_size,output_size,output_pos,message_size;
    char header[1024],dynamic[1024];size_t header_size,header_pos;
    const uint8_t *body;size_t body_size,body_pos;
    int64_t deadline,state_checked,input_started;
};
static struct client clients[5];
static char board_ip[24];
static int listener=-1,last_error;
static unsigned completed,aborted,sessions,ws_errors,accepted_clients;
/* No output is printed to USB. Inspect these non-secret values via status. */
volatile unsigned fruit_jam_network_started;

static void close_client(struct client *c,bool success)
{
    if(c->owns_vm)fj_ws_close();
    int err=fj_socket_close(c->socket);if(err)last_error=err;
    if(success)++completed;else ++aborted;
    memset(c,0,sizeof(*c));
}
static void response(struct client *c,unsigned code,const char *type,const uint8_t *body,size_t size,bool gzip)
{
    const char *reason=code==200?"OK":code==404?"Not Found":code==503?"Service Unavailable":"Bad Request";
    int n=snprintf(c->header,sizeof(c->header),
      "HTTP/1.1 %u %s\r\nContent-Type: %s\r\nContent-Length: %zu\r\nConnection: close\r\n%s"
      "Cache-Control: no-cache\r\nCross-Origin-Opener-Policy: same-origin\r\nCross-Origin-Embedder-Policy: require-corp\r\n"
      "X-Content-Type-Options: nosniff\r\nReferrer-Policy: no-referrer\r\n"
      "Content-Security-Policy: default-src 'self' data: blob:; connect-src 'self' ws://%s; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'\r\n\r\n",
      code,reason,type,size,gzip?"Content-Encoding: gzip\r\n":"",board_ip);
    if(n<0||(size_t)n>=sizeof(c->header)){close_client(c,false);return;}
    c->header_size=n;c->header_pos=0;c->body=body;c->body_size=size;c->body_pos=0;
    c->state=HTTP_SEND;c->input_size=0;c->deadline=k_uptime_get()+10000;
}
static void status_response(struct client *c)
{
    char status[512];if(fj_airlift_status(status,sizeof(status)))strcpy(status,"{}");
    int n=snprintf(c->dynamic,sizeof(c->dynamic),
       "{\"board\":\"Adafruit Fruit Jam\",\"vm\":417,\"ide\":\"2.5.8\",\"saved_generation\":%u,"
       "\"network\":{\"listener\":%d,\"port\":80,\"accepted\":%u,\"completed\":%u,\"aborted\":%u,\"sessions\":%u,\"ws_errors\":%u,\"last_error\":%d,\"chunk_bytes\":2048},\"airlift\":%s}",
       mb_store_generation(),listener,accepted_clients,completed,aborted,sessions,ws_errors,last_error,status);
    if(n<0||(size_t)n>=sizeof(c->dynamic)){close_client(c,false);return;}
    response(c,200,"application/json",(const uint8_t *)c->dynamic,n,false);
}
static void handle_request(struct client *c)
{
    if(c->input_size>2048){response(c,400,"text/plain",(const uint8_t *)"Header too large",16,false);return;}
    c->input[c->input_size]=0;
    char *end=strstr((char *)c->input,"\r\n\r\n");if(!end)return;
    size_t header_size=(size_t)(end-(char *)c->input)+4;
    struct fj_http_request request;
    if(header_size!=c->input_size||fj_http_parse((char *)c->input,header_size,board_ip,&request)){
        response(c,400,"text/plain",(const uint8_t *)"Invalid request",15,false);return;
    }
    if(request.websocket){
        if(fj_ws_request()){response(c,503,"text/plain",(const uint8_t *)"Controller busy",15,false);return;}
        c->owns_vm=true;char accept[29];
        if(fj_ws_accept(request.key,accept)){close_client(c,false);return;}
        int n=snprintf(c->header,sizeof(c->header),"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n",accept);
        c->header_size=n;c->header_pos=0;c->state=WS_UPGRADE;c->input_size=0;c->deadline=k_uptime_get()+1000;return;
    }
    unsigned transfers=0;for(unsigned i=0;i<5;++i)if(clients[i].state==HTTP_SEND)++transfers;
    if(transfers>=4){response(c,503,"text/plain",(const uint8_t *)"Server busy",11,false);return;}
    if(!strcmp(request.path,"/api/status")){status_response(c);return;}
    const char *path=!strcmp(request.path,"/")?"/microblocks.html":request.path;
    for(unsigned i=0;i<fj_web_asset_count;++i){
        const struct fj_web_asset *asset=fj_web_assets+i;
        if(!strcmp(path,asset->path)){response(c,200,asset->type,asset->data,asset->size,asset->gzip);return;}
    }
    response(c,404,"text/plain",(const uint8_t *)"Not found",9,false);
}
static int write_partial(struct client *c,const uint8_t *data,size_t *position,size_t size)
{
    size_t count=size-*position;if(count>2048)count=2048;
    if(!count)return 0;
    int n=fj_socket_write(c->socket,data+*position,count);
    if(n>0){*position+=n;c->deadline=k_uptime_get()+10000;}
    return n;
}
static void queue_frame(struct client *c,unsigned opcode,const uint8_t *data,size_t size)
{
    size_t n=fj_ws_header(c->output,opcode,size);memcpy(c->output+n,data,size);
    c->output_size=n+size;c->output_pos=0;
}
static bool websocket_step(struct client *c)
{
    if(!fj_ws_connected())return false;
    if(c->output_pos<c->output_size){
        int n=write_partial(c,c->output,&c->output_pos,c->output_size);
        if(n<0){last_error=n;return false;}
        if(c->output_pos<c->output_size)return true;
        c->output_pos=c->output_size=0;c->deadline=k_uptime_get()+60000;
    }
    if(c->input_size){
        uint8_t opcode,*payload;bool final;size_t length;
        int n=fj_ws_decode(c->input,c->input_size,&opcode,&final,&payload,&length);
        if(n<0){last_error=n;++ws_errors;return false;}
        if(n){
            if(opcode==8){ /* Reply with a bounded normal closure, no arbitrary echo. */
                uint8_t frame[]={0x88,2,3,0xe8};size_t pos=0;
                (void)write_partial(c,frame,&pos,sizeof(frame));return false;
            }
            if(opcode==9)queue_frame(c,10,payload,length);
            else if(opcode<8){
                if((opcode==0&&!c->fragment)||(opcode==2&&c->fragment)||c->message_size+length>8192){++ws_errors;return false;}
                c->message_size+=length;
                int put=fj_ws_input(payload,length);
                if(put!=(int)length){last_error=put;++ws_errors;return false;}
                c->fragment=!final;if(final)c->message_size=0;
            }
            memmove(c->input,c->input+n,c->input_size-n);c->input_size-=n;
        }
    }
    if(!c->output_size){
        int n=fj_ws_output(c->output+4,2048);
        if(n){size_t header=fj_ws_header(c->output,2,n);if(header!=4)memmove(c->output+header,c->output+4,n);c->output_size=header+n;c->output_pos=0;}
    }
    return true;
}
static void client_step(struct client *c)
{
    if(k_uptime_get()>c->deadline){last_error=-ETIMEDOUT;close_client(c,false);return;}
    if(c->state==WS_STREAM&&c->input_size&&k_uptime_get()-c->input_started>5000){last_error=-ETIMEDOUT;close_client(c,false);return;}
    if(c->state==HTTP_SEND||c->state==WS_UPGRADE){
        if(c->state==WS_UPGRADE&&!fj_ws_connected())return;
        int n=write_partial(c,(const uint8_t *)c->header,&c->header_pos,c->header_size);
        if(n<0){last_error=n;close_client(c,false);return;}
        if(c->header_pos<c->header_size)return;
        if(c->state==WS_UPGRADE){c->state=WS_STREAM;++sessions;queue_frame(c,1,(const uint8_t *)"ready",5);c->deadline=k_uptime_get()+60000;return;}
        n=write_partial(c,c->body,&c->body_pos,c->body_size);
        if(n<0){last_error=n;close_client(c,false);return;}
        if(c->body_pos==c->body_size)close_client(c,true);
        return;
    }
    if(c->state==WS_STREAM&&!websocket_step(c)){close_client(c,false);return;}
    int available=fj_socket_available(c->socket);
    if(available<0){last_error=available;close_client(c,false);return;}
    if(available){
        size_t capacity=sizeof(c->input)-1-c->input_size;
        if(!capacity){last_error=-EMSGSIZE;close_client(c,false);return;}
        size_t count=available;if(count>512)count=512;if(count>capacity)count=capacity;
        if(!c->input_size)c->input_started=k_uptime_get();
        int n=fj_socket_read(c->socket,c->input+c->input_size,count);
        if(n<0){last_error=n;close_client(c,false);return;}
        c->input_size+=n;
        if(n)c->deadline=k_uptime_get()+(c->state==WS_STREAM?60000:5000);
        if(c->state==REQUEST)handle_request(c);
    }else if(k_uptime_get()-c->state_checked>1000){
        c->state_checked=k_uptime_get();int state=fj_socket_state(c->socket);
        if(state<0||state==0||state==7){if(state<0)last_error=state;close_client(c,false);}
    }
}
static void network_worker(void *a,void *b,void *d)
{
    (void)a;(void)b;(void)d;
    for(;;){
        if(!fj_airlift_network_ready(board_ip,sizeof(board_ip))){k_sleep(K_MSEC(25));continue;}
        if(listener<0){
            listener=fj_socket_allocate();
            if(listener>=0){int err=fj_socket_listen(listener,80);if(err){last_error=err;fj_socket_close(listener);listener=-1;}}
            if(listener<0){last_error=listener;k_sleep(K_MSEC(500));continue;}
            fruit_jam_network_started=1;
        }
        struct client *free_client=NULL;for(unsigned i=0;i<5;++i)if(!clients[i].state){free_client=clients+i;break;}
        if(free_client){
            int socket=fj_socket_accept(listener);
            if(socket>=0){
                bool duplicate=socket==listener;for(unsigned i=0;i<5;++i)if(clients[i].state&&clients[i].socket==socket)duplicate=true;
                if(duplicate){last_error=-EPROTO;k_sleep(K_MSEC(100));}
                else{*free_client=(struct client){.state=REQUEST,.socket=socket,.deadline=k_uptime_get()+5000};++accepted_clients;}
            }else if(socket!=-EAGAIN)last_error=socket;
        }
        for(unsigned i=0;i<5;++i)if(clients[i].state)client_step(clients+i);
        k_sleep(K_MSEC(1));
    }
}
K_THREAD_DEFINE(fruit_jam_network_thread,8192,network_worker,NULL,NULL,NULL,7,0,0);
