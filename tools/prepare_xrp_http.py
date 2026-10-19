#!/usr/bin/env python3
"""Generate XRP-only fair HTTP/1 response sources from the exact Zephyr commit.

The shared workspace is read-only. Only the XRP CMake target substitutes these
two generated objects; other board builds retain the unmodified Zephyr library.
Generated adaptations retain the upstream Apache-2.0 source notices.
"""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,subprocess
from pathlib import Path

REVISION='a915b2f12675b48b16d56653ea145dcd8f20cbbf'
def replace_once(source,old,new):
    if source.count(old)!=1:raise ValueError('Pinned HTTP source anchor changed: '+old[:70])
    return source.replace(old,new,1)

PENDING=r'''
/* XRP: one response chunk per writable-client turn; HTTP thread owns state. */
static struct http_client_ctx *xrp_http1_clients[CONFIG_HTTP_SERVER_MAX_CLIENTS];
bool xrp_http1_pending(struct http_client_ctx *client)
{
    for (size_t i=0;i<ARRAY_SIZE(xrp_http1_clients);++i)
        if (xrp_http1_clients[i]==client) return true;
    return false;
}
void xrp_http1_cancel(struct http_client_ctx *client)
{
    for (size_t i=0;i<ARRAY_SIZE(xrp_http1_clients);++i)
        if (xrp_http1_clients[i]==client) xrp_http1_clients[i]=NULL;
}
static int xrp_http1_defer(struct http_client_ctx *client)
{
    if (xrp_http1_pending(client)) return 0;
    for (size_t i=0;i<ARRAY_SIZE(xrp_http1_clients);++i) {
        if (!xrp_http1_clients[i]) {xrp_http1_clients[i]=client;return 0;}
    }
    return -ENOBUFS;
}
static void xrp_http1_finish(struct http_client_ctx *client)
{
    if (is_client_http10(client) || (client->parser.flags & F_CONNECTION_CLOSE))
        enter_http_done_state(client);
    else client->server_state=HTTP_SERVER_PREFACE_STATE;
}
'''

CONTINUE=r'''
int xrp_http1_continue(struct http_client_ctx *client)
{
    int ret=dynamic_get_del_opts_req(
        (struct http_resource_detail_dynamic *)client->current_detail,client);
    if (ret<0 || xrp_http1_pending(client)) return ret;
    xrp_http1_finish(client);
    return client->server_state==HTTP_SERVER_DONE_STATE ? -ENOTCONN : 0;
}

'''

POLL=r'''
            /* XRP: writable response chunks share turns with accept/requests.
             * Read no further request body while the current response is live. */
            if (i>=ctx->listen_fds &&
                xrp_http1_pending(&ctx->clients[i-ctx->listen_fds]) &&
                (ctx->fds[i].revents & ZSOCK_POLLOUT)) {
                struct http_client_ctx *client=&ctx->clients[i-ctx->listen_fds];
                ret=xrp_http1_continue(client);
                if (ret>=0 && !xrp_http1_pending(client) && client->data_len)
                    ret=handle_http_request(client);
                if (ret<0) close_h3_or_plain_client(client,ctx->fds,ARRAY_SIZE(ctx->fds));
                else ctx->fds[i].events=xrp_http1_pending(client) ? ZSOCK_POLLOUT : ZSOCK_POLLIN;
                continue;
            }

'''

def prepare(zephyr,output):
    zephyr=zephyr.resolve();output.mkdir(parents=True,exist_ok=True);sources={}
    for name in ('http_server_http1.c','http_server_core.c'):
        relative='subsys/net/lib/http/'+name
        original=subprocess.check_output(['git','-C',str(zephyr),'show',REVISION+':'+relative])
        if (zephyr/relative).read_bytes()!=original:raise ValueError('Preserve pristine pinned source: '+relative)
        sources[name]=original.decode('utf8')
    h=sources['http_server_http1.c'];anchor='static int dynamic_get_del_opts_req('
    h=replace_once(h,anchor,PENDING+'\n'+anchor)
    old='\tstatus = HTTP_SERVER_REQUEST_DATA_FINAL;\n\n\tdo {'
    new='\tstatus = HTTP_SERVER_REQUEST_DATA_FINAL;\n\t/* HTTP/1 GET does not initialize this upstream; retain it for deferred turns. */\n\tclient->current_detail = &dynamic_detail->common;\n\tif (xrp_http1_pending(client)) len=0;\n\n\tdo {'
    h=replace_once(h,old,new)
    old='\t} while (!http_response_is_final(&response_ctx, status));'
    new='\t\tif (!http_response_is_final(&response_ctx,status)) return xrp_http1_defer(client);\n\t} while (false);\n\txrp_http1_cancel(client);'
    h=replace_once(h,old,new)
    h=replace_once(h,'static int dynamic_post_put_req(',CONTINUE+'static int dynamic_post_put_req(')
    begin=h.index('\tif (client->parser_state == HTTP1_MESSAGE_COMPLETE_STATE) {',h.index('int handle_http1_request('))
    end=h.index('\n\treturn 0;\n\nerror:',begin)
    h=h[:begin]+'\tif (!xrp_http1_pending(client) && client->parser_state == HTTP1_MESSAGE_COMPLETE_STATE)\n\t\txrp_http1_finish(client);\n'+h[end:]
    c=sources['http_server_core.c']
    declaration='\nextern bool xrp_http1_pending(struct http_client_ctx *);\nextern void xrp_http1_cancel(struct http_client_ctx *);\nextern int xrp_http1_continue(struct http_client_ctx *);\n'
    c=replace_once(c,'static struct http_server_ctx server_ctx;','static struct http_server_ctx server_ctx;'+declaration)
    c=replace_once(c,'void http_server_release_client(struct http_client_ctx *client)\n{','void http_server_release_client(struct http_client_ctx *client)\n{\n\txrp_http1_cancel(client);')
    c=replace_once(c,'\t} while (ret >= 0 && client->data_len > 0);','\t} while (ret >= 0 && client->data_len > 0 && !xrp_http1_pending(client));')
    anchor='\t\t\tif (!(ctx->fds[i].revents & ZSOCK_POLLIN)) {\n\t\t\t\tcontinue;\n\t\t\t}\n\n\t\t\tif (i < ctx->listen_fds) {'
    c=replace_once(c,anchor,POLL+anchor)
    old='\t\t\thandle_http_data(ctx, i);\n'
    new=old+'\t\t\tif (xrp_http1_pending(&ctx->clients[i-ctx->listen_fds]))\n\t\t\t\tctx->fds[i].events=ZSOCK_POLLOUT;\n'
    c=replace_once(c,old,new)
    modified={'http_server_http1.c':h,'http_server_core.c':c}
    report=dict(zephyr_commit=REVISION,scope='XRP target only; fair dynamic GET/DELETE/OPTIONS chunks; no public struct ABI change; original workspace unchanged',sources={})
    for name,text in modified.items():
        (output/name).write_text(text,encoding='utf8',newline='\n')
        report['sources'][name]=dict(original_sha256=hashlib.sha256(sources[name].encode()).hexdigest(),generated_sha256=hashlib.sha256(text.encode()).hexdigest())
    (output/'provenance.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print('Prepared exact XRP-only cooperative HTTP/1 sources; original Zephyr files unchanged')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--zephyr',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();prepare(a.zephyr,a.output)
