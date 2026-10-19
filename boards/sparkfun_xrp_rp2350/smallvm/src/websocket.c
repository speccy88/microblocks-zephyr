/* SPDX-License-Identifier: MPL-2.0
 * Bounded Zephyr WebSocket worker adapted from the existing Waveshare port.
 * The XRP USB/WS arbiter owns VM queues; this worker never touches VM state. */
#include "server.h"
#include "network_transport.h"
#include <zephyr/net/websocket.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>

K_SEM_DEFINE(client_ready,0,1);
static atomic_t busy;
static int client_socket=-1;
static void worker(void *a,void *b,void *c)
{
    ARG_UNUSED(a);ARG_UNUSED(b);ARG_UNUSED(c);
    uint8_t input[1024],output[1024];
    for(;;){
        k_sem_take(&client_ready,K_FOREVER);
        int fd=client_socket;
        int64_t deadline=k_uptime_get()+1000;
        while(!xrp_ws_connected() && k_uptime_get()<deadline)k_sleep(K_MSEC(1));
        bool valid=xrp_ws_connected();
        if(valid)valid=websocket_send_msg(fd,(const uint8_t *)"ready",5,
            WEBSOCKET_OPCODE_DATA_TEXT,false,true,1000)==5;
        size_t message_bytes=0;bool binary=false;
        while(valid && xrp_ws_connected()){
            uint32_t type=0;uint64_t remaining=0;
            int n=websocket_recv_msg(fd,input,sizeof(input),&type,&remaining,10);
            if(n==-EAGAIN)n=0;
            else if(n<0 || (type&WEBSOCKET_FLAG_CLOSE))break;
            if(n>0){
                if(type&WEBSOCKET_FLAG_PING){
                    if(websocket_send_msg(fd,input,n,WEBSOCKET_OPCODE_PONG,false,true,500)!=n)break;
                    continue;
                }
                if(type&WEBSOCKET_FLAG_BINARY)binary=true;
                if(!binary || (type&WEBSOCKET_FLAG_TEXT) || message_bytes+(size_t)n+remaining>8192)break;
                message_bytes+=n;
                deadline=k_uptime_get()+500;
                int result;
                do{
                    result=xrp_ws_input(input,n);
                    if(result==-ENOBUFS)k_sleep(K_MSEC(1));
                }while(result==-ENOBUFS && k_uptime_get()<deadline);
                if(result!=n)break;
                if((type&WEBSOCKET_FLAG_FINAL) && !remaining){message_bytes=0;binary=false;}
            }
            int count=xrp_ws_output(output,sizeof(output));
            if(count && websocket_send_msg(fd,output,count,WEBSOCKET_OPCODE_DATA_BINARY,false,true,1000)!=count)break;
        }
        xrp_ws_close();websocket_unregister(fd);client_socket=-1;atomic_clear(&busy);
    }
}
K_THREAD_DEFINE(ws_worker,4096,worker,NULL,NULL,NULL,7,0,0);
int mb_ws_setup(int fd,struct http_request_ctx *req,void *user)
{
    ARG_UNUSED(user);
    if(!mb_same_origin(req) || !atomic_cas(&busy,0,1))return -EACCES;
    int e=xrp_ws_request();if(e){atomic_clear(&busy);return e;}
    client_socket=fd;k_sem_give(&client_ready);return 0;
}
