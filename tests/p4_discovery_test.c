/* SPDX-License-Identifier: MIT */
#include "discovery.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
typedef struct {unsigned probes,reads,stop_after;bool all,wrong,io;unsigned config,temp;} fixture;
static int probe(void *p,uint8_t a){fixture *f=p;assert(a>=8&&a<0x78);f->probes++;return f->all||a==0x10||a==0x18||a==0x48||a==0x55?0:-1;}
static int read_reg(void *p,uint8_t a,uint16_t r,unsigned width,uint8_t *out,unsigned n)
{
 fixture *f=p;f->reads++;assert(a!=0x55);assert(n>=1&&n<=2);unsigned v=0;
 if(f->io)return -1;
 if(a==0x10){assert(width==2);v=r==0?0x219:r==0x15a?800:128;}
 else if(a==0x18){assert(width==1);v=r==0xfd?0x83:0x11;}
 else if(a==0x48){assert(width==1);v=r==0xf?(f->wrong?0x116:0x1117):r==1?f->config:f->temp;}
 else return -1;
 out[0]=n==2?v>>8:v;if(n==2)out[1]=v;return 0;
}
static bool stop(void *p){fixture *f=p;return f->stop_after&&f->probes>=f->stop_after;}
int main(void)
{
 fixture f={.config=0x2220,.temp=3008};discovery_bus b={&f,probe,read_reg,stop};discovery_results s;
 discovery_scan(&b,false,&s);assert(s.error==DISC_OK&&s.count==4&&s.visited==112&&f.reads==0);
 assert(s.devices[0].confidence==DISC_CANDIDATE&&s.devices[3].confidence==DISC_ADDRESS);
 assert(!discovery_measurement_count(&s.devices[0]));
 discovery_scan(&b,true,&s);assert(s.count==4&&s.devices[0].confidence==DISC_CONFIRMED&&s.devices[1].confidence==DISC_CONFIRMED&&s.devices[2].confidence==DISC_CONFIRMED);
 assert(!strcmp(discovery_name(&s.devices[2]),"TMP117"));assert(!discovery_measurement_count(&s.devices[3]));
 discovery_reading v=discovery_read(&b,&s.devices[2],"temperature");assert(v.error==DISC_OK&&v.value==23500&&v.scale==1000);
 f.temp=(uint16_t)-1280;v=discovery_read(&b,&s.devices[2],"temperature");assert(v.error==DISC_OK&&v.value==-10000);
 f.temp=0x8000;assert(discovery_read(&b,&s.devices[2],"temperature").error==DISC_NOT_READY);
 f.temp=3008;f.config=0x220;assert(discovery_read(&b,&s.devices[2],"temperature").error==DISC_NOT_READY);
 f.config=0x2620;assert(discovery_read(&b,&s.devices[2],"temperature").error==DISC_SHUTDOWN);f.config=0x2220;
 unsigned reads=f.reads;assert(discovery_read(&b,&s.devices[3],"temperature").error==DISC_UNSUPPORTED&&f.reads==reads);
 assert(discovery_read(&b,&s.devices[0],"temperature").error==DISC_UNSUPPORTED&&f.reads==reads);
 assert(discovery_read(&b,&s.devices[0],"exposure lines").value==800);
 assert(discovery_read(&b,&s.devices[0],"analog gain code").value==128);
 f.wrong=true;assert(discovery_read(&b,&s.devices[2],"temperature").error==DISC_REPLACED);
 discovery_scan(&b,true,&s);assert(s.devices[2].confidence==DISC_CANDIDATE);
 f.wrong=false;f.io=true;discovery_scan(&b,true,&s);assert(s.devices[2].confidence==DISC_CANDIDATE);f.io=false;
 f.all=true;discovery_scan(&b,false,&s);assert(s.count==DISCOVERY_LIMIT&&s.error==DISC_FULL);
 f.all=false;f.probes=0;f.stop_after=16;discovery_scan(&b,false,&s);assert(s.visited==16&&s.error==DISC_CANCELLED);
 puts("{\"result\":\"PASS\",\"scope\":\"portable C fixtures; no physical sensor claim\",\"checks\":[\"address-only has zero register reads\",\"confirmed and candidate IDs\",\"unknown devices never decoded\",\"temperature signed and scaled\",\"ready/shutdown/reset sentinel\",\"unsupported reads have no bus traffic\",\"camera configuration reads\",\"hot swap\",\"I2C errors\",\"bounded results\",\"cancellation\",\"reserved address exclusion\"]}");
}
