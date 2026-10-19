/* SPDX-License-Identifier: MPL-2.0 */
/* Adapted from the Waveshare port; board source remains independent.
 * Native opcode contracts follow the verified v417 ioPrims/sensorPrims.
 * Zephyr-facing operations are separate so this exact adapter can be tested
 * with the real 32-bit VM object representation and simulated drivers. */
#include "vm/interp.h"
#include "generic_io.h"
#include <string.h>

static OBJ i2c_failure(int error)
{
    xrp_io_i2c_cancel();
    return fail(error);
}

OBJ primI2cGet(OBJ *args)
{
    xrp_io_i2c_cancel();
    if (!isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
    int address=obj2int(args[0]), reg=obj2int(args[1]);
    if (address<0 || address>127) return fail(i2cDeviceIDOutOfRange);
    if (reg<0 || reg>255) return fail(i2cRegisterIDOutOfRange);
    uint8_t value;
    return xrp_io_i2c_get(address,reg,&value) ? fail(i2cTransferFailed) : int2obj(value);
}

OBJ primI2cSet(OBJ *args)
{
    xrp_io_i2c_cancel();
    if (!isInt(args[0]) || !isInt(args[1]) || !isInt(args[2])) return fail(needsIntegerError);
    int address=obj2int(args[0]), reg=obj2int(args[1]), value=obj2int(args[2]);
    if (address<0 || address>127) return fail(i2cDeviceIDOutOfRange);
    if (reg<0 || reg>255) return fail(i2cRegisterIDOutOfRange);
    if (value<0 || value>255) return fail(i2cValueOutOfRange);
    return xrp_io_i2c_set(address,reg,value) ? fail(i2cTransferFailed) : falseObj;
}

OBJ primSPISend(OBJ *args)
{
    uint8_t byte;
    const uint8_t *data;
    size_t count;
    if (isInt(args[0])) {
        int value=obj2int(args[0]);
        if (value<0 || value>255) return fail(i2cValueOutOfRange);
        byte=value;data=&byte;count=1;
    } else if (IS_TYPE(args[0],ByteArrayType)) {
        data=(const uint8_t *)&FIELD(args[0],0);count=BYTES(args[0]);
        if (count>256) return fail(indexOutOfRangeError);
    } else return fail(needsIntegerError);
    if (!count) return falseObj;
    return xrp_io_spi_transfer(data,NULL,count) ? fail(primitiveNotImplemented) : falseObj;
}

OBJ primSPIRecv(OBJ *args)
{
    (void)args;
    uint8_t zero=0, value;
    return xrp_io_spi_transfer(&zero,&value,1) ? fail(primitiveNotImplemented) : int2obj(value);
}

OBJ primAnalogRead(int argc, OBJ *args)
{
    if (argc<1 || argc>2) return fail(notEnoughArguments);
    if (!isInt(args[0])) return fail(needsIntegerError);
    int pin=obj2int(args[0]);
    if (pin<40 || pin>46) return fail(badPinError);
    unsigned mode=0;
    if (argc==2) {
        if (args[1]==trueObj) mode=1;
        else if (IS_TYPE(args[1],StringType)) {
            if (!strcmp(obj2str(args[1]),"up")) mode=1;
            else if (!strcmp(obj2str(args[1]),"down")) mode=2;
        }
    }
    int value;
    return xrp_io_analog_read(pin,mode,&value) ? fail(primitiveNotImplemented) : int2obj(value);
}

void primAnalogWrite(OBJ *args)
{
    if (!isInt(args[0]) || !isInt(args[1])) { fail(needsIntegerError);return; }
    if (obj2int(args[0])<0 || obj2int(args[0])>=48) { fail(badPinError);return; }
    int value=obj2int(args[1]);
    if (value<0) value=0;
    if (value>1023) value=1023;
    if (xrp_io_pwm_write(obj2int(args[0]),value)) fail(primitiveNotImplemented);
}

static OBJ spi_setup(int argc, OBJ *args)
{
    if (argc<1 || argc>4) return fail(notEnoughArguments);
    if (!isInt(args[0]) || (argc>1 && !isInt(args[1])) || (argc>2 && !isInt(args[2])))
        return fail(needsIntegerError);
    int hz=obj2int(args[0]),mode=argc>1 ? obj2int(args[1]) : 0;
    if (hz<10000 || hz>8000000 || mode<0 || mode>3) return fail(indexOutOfRangeError);
    if (argc>2 && obj2int(args[2])!=0) return fail(badPinError);
    bool lsb=false;
    if (argc>3) {
        if (!IS_TYPE(args[3],StringType)) return fail(needsStringError);
        if (!strcmp(obj2str(args[3]),"LSB")) lsb=true;
        else if (strcmp(obj2str(args[3]),"MSB")) return fail(indexOutOfRangeError);
    }
    return xrp_io_spi_setup(hz,mode,lsb) ? fail(primitiveNotImplemented) : falseObj;
}

static OBJ spi_exchange(int argc, OBJ *args)
{
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],ByteArrayType)) return fail(needsByteArray);
    size_t count=BYTES(args[0]);
    if (count>256) return fail(indexOutOfRangeError);
    if (!count) return falseObj;
    uint8_t *data=(uint8_t *)&FIELD(args[0],0);
    return xrp_io_spi_transfer(data,data,count) ? fail(primitiveNotImplemented) : falseObj;
}

/* List storage includes a tagged logical count followed by its elements. */
static int list_count(OBJ list)
{
    if (!WORDS(list) || !isInt(FIELD(list,0))) return -1;
    int count=obj2int(FIELD(list,0));
    return count<0 || count>=WORDS(list) ? -1 : count;
}

static OBJ i2c_exists(int argc, OBJ *args)
{
    xrp_io_i2c_cancel();
    if (argc<1 || !isInt(args[0])) return falseObj;
    int address=obj2int(args[0]);
    if (address<0 || address>127) return falseObj;
    return xrp_io_i2c_exists(address) ? falseObj : trueObj;
}

static OBJ i2c_read(int argc, OBJ *args)
{
    if (argc<2 || !isInt(args[0])) { xrp_io_i2c_cancel();return zeroObj; }
    int address=obj2int(args[0]);
    if (address<0 || address>127) return i2c_failure(i2cDeviceIDOutOfRange);
    OBJ target=args[1];
    bool list=IS_TYPE(target,ListType);
    int count;
    if (list) count=list_count(target);
    else if (IS_TYPE(target,ByteArrayType)) count=BYTES(target);
    else return i2c_failure(needsByteArray);
    if (count<0) return i2c_failure(indexOutOfRangeError);
    if (!count) return zeroObj;
    if (count>32) count=32;
    uint8_t data[32];
    /* Preserve v417's bounded-count/255-fill contract on failed reads. */
    if (xrp_io_i2c_read(address,data,count)) memset(data,255,count);
    if (list) {
        for (int i=0;i<count;++i) FIELD(target,i+1)=int2obj(data[i]);
    } else memcpy(&FIELD(target,0),data,count);
    return int2obj(count);
}

static OBJ i2c_write(int argc, OBJ *args)
{
    if (argc<2 || !isInt(args[0])) { xrp_io_i2c_cancel();return zeroObj; }
    int address=obj2int(args[0]);
    if (address<0 || address>127) return i2c_failure(i2cDeviceIDOutOfRange);
    OBJ source=args[1];
    uint8_t data[32];
    int count;
    if (isInt(source)) {
        int value=obj2int(source);
        if (value<0 || value>255) return i2c_failure(i2cValueOutOfRange);
        data[0]=value;count=1;
    } else if (IS_TYPE(source,ListType)) {
        count=list_count(source);
        if (count<0 || count>32) return i2c_failure(indexOutOfRangeError);
        for (int i=0;i<count;++i) {
            OBJ item=FIELD(source,i+1);
            if (!isInt(item) || obj2int(item)<0 || obj2int(item)>255) return i2c_failure(i2cValueOutOfRange);
            data[i]=obj2int(item);
        }
    } else if (IS_TYPE(source,ByteArrayType) || IS_TYPE(source,StringType)) {
        count=IS_TYPE(source,ByteArrayType) ? BYTES(source) : strlen(obj2str(source));
        if (count>32) return i2c_failure(indexOutOfRangeError);
        memcpy(data,&FIELD(source,0),count);
    } else return i2c_failure(needsByteArray);
    if (!count) { xrp_io_i2c_cancel();return falseObj; }
    bool stop=argc<3 || args[2]==trueObj;
    return xrp_io_i2c_write(address,data,count,stop) ? i2c_failure(i2cTransferFailed) : falseObj;
}

OBJ xrp_capture_start(int,OBJ *);
OBJ xrp_capture_count(int,OBJ *);
OBJ xrp_capture_end(int,OBJ *);
static PrimEntry generic_sensor_entries[] = {
    {"captureStart",xrp_capture_start}, {"captureCount",xrp_capture_count}, {"captureEnd",xrp_capture_end},
    {"spiSetup",spi_setup}, {"spiExchange",spi_exchange},
    {"i2cExists",i2c_exists}, {"i2cRead",i2c_read}, {"i2cWrite",i2c_write}
};

void addSensorPrims(void)
{
    addPrimitiveSet(SensorPrims,"sensors",sizeof(generic_sensor_entries)/sizeof(generic_sensor_entries[0]),generic_sensor_entries);
}
