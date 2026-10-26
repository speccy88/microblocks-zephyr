/* SPDX-License-Identifier: MIT */
/* Portable register adapters, inspired by SparkFun's discovery/measurement
 * separation. No Arduino library, initialization/reset or config writes. */
#include "discovery.h"
#include <string.h>
static bool stopped(const discovery_bus *b){return b->stop && b->stop(b->context);}
static int reg(const discovery_bus *b,unsigned a,unsigned r,unsigned width,unsigned bytes,unsigned *v)
{
 uint8_t data[2];if(stopped(b))return DISC_CANCELLED;
 if(!b->read || bytes<1 || bytes>2 || b->read(b->context,a,r,width,data,bytes))return DISC_IO;
 *v=bytes==1?data[0]:((unsigned)data[0]<<8)|data[1];return DISC_OK;
}
static unsigned candidate(unsigned a)
{
 if(a>=0x48 && a<=0x4b)return DISC_TMP117;
 if(a==0x10)return DISC_IMX219;
 if(a==0x36)return DISC_OV5647;
 if(a==0x18)return DISC_ES8311;
 return DISC_UNKNOWN;
}
static int identity(const discovery_bus *b,const discovery_device *d)
{
 unsigned v=0,w=0;int e;
 switch(d->kind){
 case DISC_TMP117:e=reg(b,d->address,0x0f,1,2,&v);if(e)return e;return (v&0xfff)==0x117?DISC_OK:DISC_REPLACED;
 case DISC_IMX219:e=reg(b,d->address,0,2,2,&v);if(e)return e;return v==0x219?DISC_OK:DISC_REPLACED;
 case DISC_OV5647:e=reg(b,d->address,0x300a,2,2,&v);if(e)return e;return v==0x5647?DISC_OK:DISC_REPLACED;
 case DISC_ES8311:e=reg(b,d->address,0xfd,1,1,&v);if(e)return e;e=reg(b,d->address,0xfe,1,1,&w);if(e)return e;return ((v<<8)|w)==0x8311?DISC_OK:DISC_REPLACED;
 default:return DISC_UNSUPPORTED;
 }
}
void discovery_scan(const discovery_bus *b,bool identify,discovery_results *out)
{
 memset(out,0,sizeof(*out));
 if(!b || !b->probe){out->error=DISC_UNSUPPORTED;return;}
 for(unsigned a=8;a<0x78;a++){
  if(stopped(b)){out->error=DISC_CANCELLED;break;}
  out->visited++;if(b->probe(b->context,a))continue;
  if(out->count==DISCOVERY_LIMIT){out->error=DISC_FULL;break;}
  discovery_device d={(uint8_t)a,(uint8_t)candidate(a),DISC_ADDRESS};
  if(d.kind)d.confidence=DISC_CANDIDATE;
  if(identify && d.kind && identity(b,&d)==DISC_OK)d.confidence=DISC_CONFIRMED;
  out->devices[out->count++]=d;
 }
}
const char *discovery_name(const discovery_device *d)
{
 if(d->confidence!=DISC_CONFIRMED)return d->confidence==DISC_CANDIDATE?"unconfirmed candidate":"unknown device";
 static const char *names[]={"unknown device","TMP117","IMX219 camera","OV5647 camera","ES8311 audio codec"};
 return d->kind<=DISC_ES8311?names[d->kind]:names[0];
}
const char *discovery_confidence_name(const discovery_device *d)
{return d->confidence==DISC_CONFIRMED?"confirmed ID":d->confidence==DISC_CANDIDATE?"candidate only":"address only";}
unsigned discovery_measurement_count(const discovery_device *d)
{return d->confidence==DISC_CONFIRMED?(d->kind==DISC_IMX219?3:d->kind==DISC_TMP117?2:1):0;}
const char *discovery_measurement(const discovery_device *d,unsigned index)
{
 if(index>=discovery_measurement_count(d))return "";
 if(!index)return "device ID";
 if(d->kind==DISC_TMP117)return "temperature";
 return index==1?"exposure lines":"analog gain code";
}
discovery_reading discovery_read(const discovery_bus *b,const discovery_device *d,const char *measurement)
{
 discovery_reading out={0,1,"",DISC_UNSUPPORTED};unsigned m;
 for(m=0;m<discovery_measurement_count(d);m++)if(!strcmp(measurement,discovery_measurement(d,m)))break;
 if(m==discovery_measurement_count(d))return out; /* no bus traffic */
 out.error=identity(b,d);if(out.error)return out;
 unsigned v=0;out.error=DISC_OK;
 if(m==0){static const int ids[]={0,0x117,0x219,0x5647,0x8311};out.value=ids[d->kind];out.unit="ID";return out;}
 if(d->kind==DISC_TMP117){
  out.error=reg(b,d->address,1,1,2,&v);if(out.error)return out;
  if((v&0xc00)==0x400){out.error=DISC_SHUTDOWN;return out;}
  if(!(v&0x2000)){out.error=DISC_NOT_READY;return out;}
  out.error=reg(b,d->address,0,1,2,&v);if(out.error)return out;
  if(v==0x8000){out.error=DISC_NOT_READY;return out;}
  int32_t raw=(int16_t)v;out.value=(raw*1000+(raw>=0?64:-64))/128;
  out.unit="milli-degrees C";out.scale=1000;return out;
 }
 out.error=reg(b,d->address,m==1?0x015a:0x0157,2,m==1?2:1,&v);
 out.value=(int32_t)v;out.unit=m==1?"lines":"register code";return out;
}
const char *discovery_error_name(int e)
{
 static const char *s[]={"ready","I2C read failed","measurement unsupported","sample not ready","sensor in shutdown","sensor identity changed","cancelled","scan deadline exceeded","result limit reached"};
 return e>=0 && e<=DISC_FULL?s[e]:"unavailable";
}
