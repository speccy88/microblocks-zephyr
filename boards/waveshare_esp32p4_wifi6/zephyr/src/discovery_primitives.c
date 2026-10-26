/* SPDX-License-Identifier: MPL-2.0 */
#include "vm/interp.h"
#include "discovery_backend.h"
#include <string.h>
static OBJ string(const char *s){return newStringFromBytes(s,strlen(s));}
static bool ints(int n,OBJ *a,int count){if(n!=count){fail(notEnoughArguments);return false;}for(int i=0;i<n;i++)if(!isInt(a[i])){fail(needsIntegerError);return false;}return true;}
static bool sensor(int n,OBJ *a,discovery_device *d){if(n<1||!IS_TYPE(a[0],StringType)){fail(needsStringError);return false;}return p4_discovery_device(obj2str(a[0]),d);}
static OBJ scan(int n,OBJ *a){if(n!=2||!isInt(a[0]))return fail(needsIntegerError);return p4_discovery_scan(obj2int(a[0]),a[1]==trueObj)?trueObj:falseObj;}
static OBJ busy(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return p4_discovery_busy()?trueObj:falseObj;}
static OBJ cancel(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);p4_discovery_cancel();return falseObj;}
static OBJ status(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[128];p4_discovery_status(s,sizeof(s));return string(s);}
static OBJ count(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);return int2obj(p4_discovery_count());}
static OBJ ref(int n,OBJ *a){if(!ints(n,a,1))return falseObj;char s[20];p4_discovery_ref(obj2int(a[0]),s,sizeof(s));return string(s);}
static OBJ name(int n,OBJ *a){discovery_device d;return sensor(n,a,&d)?string(discovery_name(&d)):string("expired sensor reference");}
static OBJ confidence(int n,OBJ *a){discovery_device d;return sensor(n,a,&d)?string(discovery_confidence_name(&d)):string("expired sensor reference");}
static OBJ address(int n,OBJ *a){discovery_device d;return sensor(n,a,&d)?int2obj(d.address):falseObj;}
static OBJ bus(int n,OBJ *a){discovery_device d;return sensor(n,a,&d)?zeroObj:falseObj;}
static OBJ measurements(int n,OBJ *a){discovery_device d;return sensor(n,a,&d)?int2obj(discovery_measurement_count(&d)):zeroObj;}
static OBJ measurement(int n,OBJ *a){discovery_device d;if(n!=2||!isInt(a[1]))return fail(needsIntegerError);return sensor(n,a,&d)?string(discovery_measurement(&d,obj2int(a[1])-1)):string("");}
static OBJ read(int n,OBJ *a){if(n!=2||!IS_TYPE(a[0],StringType)||!IS_TYPE(a[1],StringType))return fail(needsStringError);return p4_discovery_read(obj2str(a[0]),obj2str(a[1]))?trueObj:falseObj;}
static OBJ value(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);discovery_reading v=p4_discovery_reading();return v.error?falseObj:int2obj(v.value);}
static OBJ unit(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);discovery_reading v=p4_discovery_reading();return string(v.error?"":v.unit);}
static OBJ scale(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);discovery_reading v=p4_discovery_reading();return v.error?falseObj:int2obj(v.scale);}
static OBJ text(int n,OBJ *a){(void)a;if(n)return fail(notEnoughArguments);char s[128];p4_discovery_read_text(s,sizeof(s));return string(s);}
static PrimEntry entries[]={
 {"scan",scan},{"busy",busy},{"cancel",cancel},{"status",status},{"count",count},{"sensorAt",ref},
 {"name",name},{"confidence",confidence},{"address",address},{"bus",bus},{"measurementCount",measurements},{"measurement",measurement},
 {"read",read},{"value",value},{"unit",unit},{"scale",scale},{"readingText",text}};
void addSensorPrims(void){addPrimitiveSet(SensorPrims,"i2cDetect",sizeof(entries)/sizeof(entries[0]),entries);}
