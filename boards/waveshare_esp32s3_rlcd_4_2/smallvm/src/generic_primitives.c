/* SPDX-License-Identifier: MPL-2.0 */
/* Native opcode contracts follow the verified v417 ioPrims/sensorPrims.
 * Zephyr-facing operations are separate so this exact adapter can be tested
 * with the real 32-bit VM object representation and simulated drivers. */
#include "vm/interp.h"
#include "generic_io.h"
#include <string.h>

OBJ primI2cGet(OBJ *args)
{
    if (!isInt(args[0]) || !isInt(args[1])) return fail(needsIntegerError);
    int address=obj2int(args[0]), reg=obj2int(args[1]);
    if (address<0 || address>127) return fail(i2cDeviceIDOutOfRange);
    if (reg<0 || reg>255) return fail(i2cRegisterIDOutOfRange);
    uint8_t value;
    return rlcd_io_i2c_get(address,reg,&value) ? fail(i2cTransferFailed) : int2obj(value);
}

OBJ primI2cSet(OBJ *args)
{
    if (!isInt(args[0]) || !isInt(args[1]) || !isInt(args[2])) return fail(needsIntegerError);
    int address=obj2int(args[0]), reg=obj2int(args[1]), value=obj2int(args[2]);
    if (address<0 || address>127) return fail(i2cDeviceIDOutOfRange);
    if (reg<0 || reg>255) return fail(i2cRegisterIDOutOfRange);
    if (value<0 || value>255) return fail(i2cValueOutOfRange);
    return rlcd_io_i2c_set(address,reg,value) ? fail(i2cTransferFailed) : falseObj;
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
    return rlcd_io_spi_transfer(data,NULL,count) ? fail(primitiveNotImplemented) : falseObj;
}

OBJ primSPIRecv(OBJ *args)
{
    (void)args;
    uint8_t zero=0, value;
    return rlcd_io_spi_transfer(&zero,&value,1) ? fail(primitiveNotImplemented) : int2obj(value);
}

OBJ primAnalogRead(int argc, OBJ *args)
{
    if (argc<1 || argc>2) return fail(notEnoughArguments);
    if (!isInt(args[0])) return fail(needsIntegerError);
    int pin=obj2int(args[0]);
    if (pin<0 || pin>1) return fail(badPinError);
    unsigned mode=0;
    if (argc==2) {
        if (args[1]==trueObj) mode=1;
        else if (IS_TYPE(args[1],StringType)) {
            if (!strcmp(obj2str(args[1]),"up")) mode=1;
            else if (!strcmp(obj2str(args[1]),"down")) mode=2;
        }
    }
    int value;
    return rlcd_io_analog_read(pin,mode,&value) ? fail(primitiveNotImplemented) : int2obj(value);
}

void primAnalogWrite(OBJ *args)
{
    if (!isInt(args[0]) || !isInt(args[1])) { fail(needsIntegerError);return; }
    if (obj2int(args[0])!=2) { fail(badPinError);return; }
    int value=obj2int(args[1]);
    if (value<0) value=0;
    if (value>1023) value=1023;
    if (rlcd_io_pwm_write(2,value)) fail(primitiveNotImplemented);
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
    return rlcd_io_spi_setup(hz,mode,lsb) ? fail(primitiveNotImplemented) : falseObj;
}

static OBJ spi_exchange(int argc, OBJ *args)
{
    if (argc!=1) return fail(notEnoughArguments);
    if (!IS_TYPE(args[0],ByteArrayType)) return fail(needsByteArray);
    size_t count=BYTES(args[0]);
    if (count>256) return fail(indexOutOfRangeError);
    if (!count) return falseObj;
    uint8_t *data=(uint8_t *)&FIELD(args[0],0);
    return rlcd_io_spi_transfer(data,data,count) ? fail(primitiveNotImplemented) : falseObj;
}

static PrimEntry generic_sensor_entries[] = {
    {"spiSetup",spi_setup}, {"spiExchange",spi_exchange}
};

void addSensorPrims(void)
{
    addPrimitiveSet(SensorPrims,"sensors",sizeof(generic_sensor_entries)/sizeof(generic_sensor_entries[0]),generic_sensor_entries);
}
