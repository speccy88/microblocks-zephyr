/* SPDX-License-Identifier: MPL-2.0
 * Execute the real 32-bit interpreter with simulated transport and peripherals.
 * Fruit Jam adaptation of the existing Waveshare/UNO Q interpreter harness. */
#include "vm/interp.h"
#include "vm/persist.h"
#include "fruit_jam.h"
#include "generic_io.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8 rx[4096], tx[32768];
static int rx_count, tx_count;
static uint32 now = 1000;
static unsigned digital_calls;
extern void smallvmResetTransport(void);
uint32 microsecs(void) { return now; }
uint32 millisecs(void) { return now / 1000; }
uint64 totalMicrosecs(void) { return now; }
uint32 seconds(void) { return now / 1000000; }
void handleMicosecondClockWrap(void) {}
void smallvmDelay(unsigned long n) { now += n * 1000; }
void lightSleep(int n) { now += n * 1000; }
void deepSleep(int n) { (void)n; }
void hardwareInit(void) { initTasks(); }
void turnOffPins(void) {}
int pinCount(void) { return 9; }
OBJ primDigitalPins(OBJ *a) { (void)a; return int2obj(9); }
OBJ primAnalogPins(OBJ *a) { (void)a; return int2obj(6); }
OBJ primDigitalRead(int n, OBJ *a) { ++digital_calls; (void)n; (void)a; return falseObj; }
void primDigitalWrite(OBJ *a) { ++digital_calls; (void)a; }
void primDigitalSet(int p, int s) { (void)p; (void)s; }
int fj_button(unsigned n) { return n < 3 ? n == 1 : -22; }

static int io_calls, io_error, io_pin, io_mode, io_value, io_count;
static unsigned io_hz, io_spi_mode;
static bool io_lsb;
static bool io_stop;
static uint8 io_bytes[256];
int fj_io_i2c_get(unsigned address,unsigned reg,uint8_t *value)
{ ++io_calls;io_pin=address;io_mode=reg;*value=0x83;return io_error; }
int fj_io_i2c_set(unsigned address,unsigned reg,uint8_t value)
{ ++io_calls;io_pin=address;io_mode=reg;io_value=value;return io_error; }
void fj_io_i2c_cancel(void) {}
int fj_io_i2c_exists(unsigned address)
{ ++io_calls;io_pin=address;return io_error; }
int fj_io_i2c_read(unsigned address,uint8_t *data,size_t count)
{ ++io_calls;assert(count<=32);io_pin=address;io_count=count;
  for(size_t i=0;i<count;++i)data[i]=128+i;return io_error; }
int fj_io_i2c_write(unsigned address,const uint8_t *data,size_t count,bool stop)
{ ++io_calls;assert(count<=32);io_pin=address;io_count=count;io_stop=stop;memcpy(io_bytes,data,count);return io_error; }
int fj_io_spi_setup(unsigned hz,unsigned mode,bool lsb)
{ (void)hz;(void)mode;(void)lsb;return -95; }
int fj_io_spi_transfer(const uint8_t *txdata,uint8_t *rxdata,size_t count)
{ (void)txdata;(void)rxdata;(void)count;return -95; }

int fj_io_analog_read(unsigned pin,unsigned mode,int *value)
{ ++io_calls;io_pin=pin;io_mode=mode;*value=511;return mode ? -95 : io_error; }
int fj_io_pwm_write(unsigned pin,unsigned value)
{ ++io_calls;io_pin=pin;io_value=value;return io_error; }
void fj_io_pwm_stop(void) {}
void fj_io_prepare_gpio(unsigned pin) { (void)pin; }
int fj_io_info(char *dst,unsigned size) { snprintf(dst,size,"{}");return 0; }
/* New board primitives are dispatch-tested with these simulated devices;
 * native sensor CRC and PIO timing require their own tests. */
int fj_sht4x_read(int *t,int *h) { *t=25000;*h=44000;return 0; }
int fj_sht4x_status(char *dst,unsigned size)
{ return snprintf(dst,size,"{\"simulated\":true,\"heater\":false}"); }
int fj_pixels_set(unsigned index,unsigned r,unsigned g,unsigned b)
{ return index<5 && r<=255 && g<=255 && b<=255 ? 0 : -22; }
int fj_pixels_off(void) { return 0; }

int recvBytes(uint8 *p, int count)
{
    int n = count < rx_count ? count : rx_count;
    memcpy(p, rx, n); memmove(rx, rx+n, rx_count-n); rx_count -= n; return n;
}
int sendBytes(uint8 *p, int start, int end)
{
    int n = end-start; if (n > 7) n=7; /* Force partial output writes. */
    assert(tx_count+n <= sizeof(tx)); memcpy(tx+tx_count,p+start,n); tx_count+=n; return n;
}
static void inject(const uint8 *p, int n)
{
    assert(rx_count+n <= sizeof(rx)); memcpy(rx+rx_count,p,n); rx_count+=n;
}
static void pump(int n) { for(int i=0;i<n;++i){now+=100;vmSlice(1);} }
static int ping_seen(int id)
{
    for(int i=0;i+2<tx_count;++i)if(tx[i]==250&&tx[i+1]==26&&tx[i+2]==id)return 1;
    return 0;
}
static void upload(int id, const uint16 *ops, int words)
{
    uint8 p[1024]={251,32,(uint8)id,0,0,1}; int length=2+2*words;
    p[3]=length&255; p[4]=length>>8; memcpy(p+6,ops,2*words); p[6+2*words]=254;
    inject(p,7+2*words); pump(1000); assert(chunks[id].code); tx_count=0;
}

static unsigned io_checks;
/* Test-only accessor appended to the prepared interpreter, never firmware. */
extern unsigned smallvm_test_error(void);
#define CHECK_IO(condition) do { assert(condition); ++io_checks; } while(0)
static void io_failed(int expected)
{
    if (smallvm_test_error()!=expected) fprintf(stderr,"I/O check %u: expected error %d, got %u\n",io_checks,expected,smallvm_test_error());
    CHECK_IO(smallvm_test_error()==expected);fail(0);
}

static void generic_contracts(void)
{
    OBJ args[4]={int2obj(24),int2obj(253),int2obj(37),falseObj};
    CHECK_IO(obj2int(primI2cGet(args))==0x83 && io_pin==24 && io_mode==253);
    CHECK_IO(primI2cSet(args)==falseObj && io_value==37);
    int before=io_calls;
    args[0]=int2obj(-1);primI2cGet(args);io_failed(21);
    args[0]=int2obj(128);primI2cSet(args);io_failed(21);
    args[0]=int2obj(24);args[1]=int2obj(256);primI2cGet(args);io_failed(22);
    args[1]=int2obj(0);args[2]=int2obj(-1);primI2cSet(args);io_failed(23);
    args[0]=trueObj;primI2cGet(args);io_failed(13);
    CHECK_IO(io_calls==before);
    args[0]=int2obj(24);io_error=-5;primI2cGet(args);io_failed(35);io_error=0;

    args[0]=int2obj(165);primSPISend(args);io_failed(27);
    primSPIRecv(NULL);io_failed(27);
    args[0]=int2obj(1000000);doPrimitiveCall(SensorPrims,"spiSetup",1,args);io_failed(27);
    for (int pin=0;pin<6;++pin) {
        args[0]=int2obj(pin);CHECK_IO(obj2int(primAnalogRead(1,args))==511&&io_pin==pin);
    }
    args[1]=trueObj;primAnalogRead(2,args);io_failed(27);CHECK_IO(io_mode==1);
    args[1]=newStringFromBytes("down",4);primAnalogRead(2,args);io_failed(27);CHECK_IO(io_mode==2);
    before=io_calls;args[0]=int2obj(6);primAnalogRead(1,args);io_failed(57);CHECK_IO(io_calls==before);
    args[0]=falseObj;primAnalogRead(1,args);io_failed(13);
    for (int pin=0;pin<9;++pin) {
        args[0]=int2obj(pin);args[1]=int2obj(500);primAnalogWrite(args);
        CHECK_IO(io_pin==pin&&io_value==500);
    }
    args[0]=int2obj(8);args[1]=int2obj(-1);primAnalogWrite(args);CHECK_IO(io_value==0);
    args[1]=int2obj(2000);primAnalogWrite(args);CHECK_IO(io_value==1023);
    before=io_calls;args[0]=int2obj(9);primAnalogWrite(args);io_failed(57);CHECK_IO(io_calls==before);
    args[0]=int2obj(8);args[1]=trueObj;primAnalogWrite(args);io_failed(13);

    /* Execute malformed arities in the actual interpreter, not only adapters. */
    const uint8 cases[][2]={{86,0},{87,1},{95,2},{96,0},{97,0},{98,1},{88,0},{89,1},{88,3},{89,3}};
    unsigned digital_before=digital_calls;
    for(unsigned c=0;c<sizeof(cases)/sizeof(cases[0]);++c) {
        uint16 code[12]={OP(9,0)};int n=1;
        for(int a=0;a<cases[c][1];++a)code[n++]=OP(2,1);
        code[n++]=OP(cases[c][0],cases[c][1]);code[n++]=OP(35,0);code[n++]=OP(127,0);
        if(n&1)++n;
        upload(4,code,n);startTaskForChunk(4);pump(1000);
        int found=0;
        for(int i=0;i+6<tx_count;++i)
            if(tx[i]==251 && tx[i+1]==19 && tx[i+2]==4 && tx[i+5]==28)found=1;
        CHECK_IO(found);fail(0);tx_count=0;
    }
    CHECK_IO(digital_calls==digital_before);
    /* A literal ByteArray uses opcode 5, not the huge-integer opcode 4. */
    const uint16 oversized_literal[140]={OP(9,0),OP(5,0),6,OP(97,1),OP(2,0),OP(35,0),OP(127,0),0,1043,0};
    before=io_calls;upload(4,oversized_literal,140);startTaskForChunk(4);pump(1000);
    int found=0;
    for(int i=0;i+6<tx_count;++i)
        if(tx[i]==251&&tx[i+1]==19&&tx[i+2]==4&&tx[i+5]==18)found=1;
    CHECK_IO(found&&io_calls==before);fail(0);tx_count=0;
}

static unsigned i2c_bulk_checks;
static void i2c_bulk_contracts(void)
{
    unsigned initial=io_checks;
    OBJ args[3]={int2obj(24),falseObj,trueObj};
    int before=io_calls;
    CHECK_IO(doPrimitiveCall(SensorPrims,"i2cExists",0,args)==falseObj);
    args[0]=trueObj;CHECK_IO(doPrimitiveCall(SensorPrims,"i2cExists",1,args)==falseObj);
    args[0]=int2obj(128);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cExists",1,args)==falseObj&&io_calls==before);
    args[0]=int2obj(24);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cExists",1,args)==trueObj&&io_pin==24);
    io_error=-5;CHECK_IO(doPrimitiveCall(SensorPrims,"i2cExists",1,args)==falseObj);io_error=0;

    OBJ list=newObj(ListType,4,zeroObj);FIELD(list,0)=int2obj(3);args[1]=list;
    CHECK_IO(obj2int(doPrimitiveCall(SensorPrims,"i2cRead",2,args))==3&&io_count==3&&obj2int(FIELD(list,1))==128&&obj2int(FIELD(list,3))==130);
    OBJ bytes=newObj(ByteArrayType,9,zeroObj);setByteCountAdjust(bytes,35);
    uint8 *data=(uint8 *)&FIELD(bytes,0);memset(data,42,35);args[1]=bytes;
    CHECK_IO(obj2int(doPrimitiveCall(SensorPrims,"i2cRead",2,args))==32&&io_count==32&&data[0]==128&&data[31]==159&&data[32]==42);
    io_error=-5;CHECK_IO(obj2int(doPrimitiveCall(SensorPrims,"i2cRead",2,args))==32&&data[0]==255&&data[31]==255&&data[32]==42);io_error=0;
    OBJ longlist=newObj(ListType,36,zeroObj);FIELD(longlist,0)=int2obj(35);args[1]=longlist;
    CHECK_IO(obj2int(doPrimitiveCall(SensorPrims,"i2cRead",2,args))==32&&FIELD(longlist,33)==zeroObj);
    OBJ empty=newObj(ByteArrayType,0,zeroObj);args[1]=empty;before=io_calls;
    CHECK_IO(doPrimitiveCall(SensorPrims,"i2cRead",2,args)==zeroObj&&io_calls==before);
    CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",2,args)==falseObj&&io_calls==before);
    args[1]=trueObj;doPrimitiveCall(SensorPrims,"i2cRead",2,args);io_failed(36);
    args[0]=int2obj(-1);doPrimitiveCall(SensorPrims,"i2cRead",2,args);io_failed(21);
    args[0]=trueObj;CHECK_IO(doPrimitiveCall(SensorPrims,"i2cRead",2,args)==zeroObj);
    args[0]=int2obj(24);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cRead",1,args)==zeroObj);
    FIELD(list,0)=int2obj(4);args[1]=list;doPrimitiveCall(SensorPrims,"i2cRead",2,args);io_failed(18);FIELD(list,0)=int2obj(3);
    CHECK_IO(io_calls==before);

    args[1]=int2obj(253);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",2,args)==falseObj&&io_count==1&&io_bytes[0]==253&&io_stop);
    args[2]=falseObj;CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",3,args)==falseObj&&!io_stop);
    FIELD(list,1)=int2obj(1);FIELD(list,2)=int2obj(2);FIELD(list,3)=int2obj(255);args[1]=list;
    CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",2,args)==falseObj&&io_count==3&&io_bytes[2]==255);
    args[1]=newStringFromBytes("abc",3);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",2,args)==falseObj&&io_count==3&&io_bytes[0]=='a');
    args[1]=newObj(ByteArrayType,8,zeroObj);CHECK_IO(doPrimitiveCall(SensorPrims,"i2cWrite",2,args)==falseObj&&io_count==32);
    before=io_calls;args[1]=bytes;doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(18);
    args[1]=longlist;doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(18);
    args[1]=int2obj(256);doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(23);
    args[1]=int2obj(-1);doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(23);
    FIELD(list,3)=trueObj;args[1]=list;doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(23);
    FIELD(list,3)=int2obj(300);doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(23);
    args[1]=trueObj;doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(36);
    args[0]=int2obj(128);doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(21);
    CHECK_IO(io_calls==before);
    args[0]=int2obj(24);args[1]=int2obj(5);io_error=-5;doPrimitiveCall(SensorPrims,"i2cWrite",2,args);io_failed(35);io_error=0;
    i2c_bulk_checks=io_checks-initial;
}

int main(void)
{
    hardwareInit(); memInit(); primsInit(); restoreScripts(); pump(100); tx_count=0;
    const uint8 ping[]={250,26,73}; inject(ping,3); pump(100); assert(ping_seen(73)); tx_count=0;
    const uint8 reporter[]={251,32,0,22,0,2,9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0,254};
    const uint8 result[]={251,18,0,5,0,1,12,0,0,0};
    for(int repeat=0;repeat<10;++repeat){
        const uint8 reset[]={250,14,1,250,15,0}; inject(reset,sizeof(reset)); pump(100); assert(!failure()); tx_count=0;
        inject(reporter,sizeof(reporter)); pump(100); const uint8 start[]={250,3,0}; inject(start,3); pump(1000);
        int found=0; for(int i=0;i+sizeof(result)<=tx_count;++i)if(!memcmp(tx+i,result,sizeof(result)))found=1;
        assert(found&&!failure()); tx_count=0;
    }
    uint16 straight[506]={0}; for(int i=0;i<500;++i)straight[i]=OP(21,0);
    straight[500]=OP(2,85); straight[501]=OP(7,2);
    uint8 packet[1019]={251,32,2,246,3,1}; memcpy(packet+6,straight,1012); packet[1018]=254;
    for(int pos=0;pos<1019;pos+=192){int n=1019-pos;if(n>192)n=192;inject(packet+pos,n);pump(100);now+=30000;}
    pump(100); assert(chunks[2].code); startTaskForChunk(2); pump(1); assert(taskCount==1); pump(10); assert(obj2int(vars[2])==42); tx_count=0;
    const uint8 partial[]={251,32,7,100,0,1}; inject(partial,6); pump(100); now+=300000;
    inject(ping,3); pump(100); assert(ping_seen(73)); tx_count=0;
    const uint8 malformed[]={251,32,8,0,0,250,26,73}; inject(malformed,sizeof(malformed)); pump(1000);
    if(!ping_seen(73)){fprintf(stderr,"invalid-length reply:");for(int i=0;i<tx_count;++i)fprintf(stderr,"%02x",tx[i]);fprintf(stderr," error=%d\n",failure());}
    assert(ping_seen(73)); tx_count=0;
    OBJ button=int2obj(2);assert(doPrimitiveCall(IOPrims,"buttonPressed",1,&button)==trueObj);
    button=int2obj(1);assert(doPrimitiveCall(IOPrims,"buttonPressed",1,&button)==falseObj);
    button=int2obj(4);doPrimitiveCall(IOPrims,"buttonPressed",1,&button);assert(failure());fail(0);
    assert(primButtonA(NULL)==trueObj&&primButtonB(NULL)==falseObj);
    generic_contracts();
    i2c_bulk_contracts();
    vars[0]=zeroObj; vars[1]=int2obj(49);
    const uint16 streaming[]={OP(6,1),OP(2,3),OP(8,0),OP(6,0),OP(78,1),(uint16)OP(26,-5),0};
    upload(3,streaming,7); startTaskForChunk(3);
    for(int i=0;i<200&&taskCount;++i){inject(ping,3);pump(1000);}
    for(int i=0,last=-1;i<200&&last!=tx_count;++i){last=tx_count;pump(5000);}
    assert(!taskCount&&!failure());
    assert(obj2int(vars[0])==50);
    int outputs=0;
    for(int pos=0;pos<tx_count;){
        if(tx[pos]==250){assert(pos+3<=tx_count);pos+=3;continue;}
        if(tx[pos]!=251)fprintf(stderr,"stream offset=%d byte=%d count=%d outputs=%d\n",pos,tx[pos],tx_count,outputs);
        assert(tx[pos]==251&&pos+5<=tx_count);
        int len=tx[pos+3]+256*tx[pos+4];
        if(pos+5+len>tx_count)fprintf(stderr,"truncated at=%d len=%d total=%d outputs=%d\n",pos,len,tx_count,outputs);
        assert(pos+5+len<=tx_count);
        if(tx[pos+1]==outputValueMsg&&tx[pos+2]==254){
            assert(len>1&&len<16&&tx[pos+5]==2);char number[16];
            memcpy(number,tx+pos+6,len-1);number[len-1]=0;
            assert(atoi(number)==++outputs);
        }
        pos+=5+len;
    }
    assert(outputs==50);
    printf("{\"result\":\"PASS\",\"architecture\":\"wasm32\",\"scope\":\"real Fruit Jam SmallVM v417; simulated transport/peripherals\",\"reporter_runs\":10,\"arithmetic\":12,\"fragmented_message_bytes\":1019,\"partial_output_max\":7,\"ordered_stream_outputs\":50,\"generic_io_checks\":%u,\"i2c_bulk_checks\":%u,\"stream_bytes\":%d,\"timeout_recovery\":true,\"invalid_length_recovery\":true,\"named_primitives\":true}\n",io_checks,i2c_bulk_checks,tx_count);
    return 0;
}
