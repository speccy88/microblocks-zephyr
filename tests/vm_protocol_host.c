/* SPDX-License-Identifier: MPL-2.0
 * Execute the real 32-bit interpreter with simulated transport and peripherals.
 * Framing examples derive from the existing UNO Q interpreter harness. */
#include "vm/interp.h"
#include "vm/persist.h"
#include "rlcd_board.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8 rx[4096], tx[32768];
static int rx_count, tx_count;
static uint32 now = 1000;
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
int pinCount(void) { return 3; }
OBJ primDigitalPins(OBJ *a) { (void)a; return int2obj(3); }
OBJ primAnalogPins(OBJ *a) { (void)a; return int2obj(0); }
OBJ primDigitalRead(int n, OBJ *a) { (void)n; (void)a; return falseObj; }
void primDigitalWrite(OBJ *a) { (void)a; }
void primDigitalSet(int p, int s) { (void)p; (void)s; }
bool rlcd_button_pressed(unsigned n) { return n == 1; }
int rlcd_environment_read(struct rlcd_environment *out) { out->temp_milli_c=21500; out->humidity_milli_pct=47000; return 0; }
int rlcd_battery_read(int32_t *raw, int32_t *mv) { *raw=1200; if(mv)*mv=4000; return 0; }
int rlcd_display_checkerboard(void) { return 0; }
int rlcd_display_text(const char *text) { return text ? 0 : -1; }
int rlcd_display_clear(bool white) { (void)white;return 0; }
int rlcd_rtc_read(char *text, unsigned size) { snprintf(text,size,"2026-10-17T12:00:00");return 0; }

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
    OBJ value=doPrimitiveCall(IOPrims,"temperatureMilliC",0,NULL); assert(isInt(value)&&obj2int(value)==21500);
    value=doPrimitiveCall(IOPrims,"humidityMilliPct",0,NULL); assert(isInt(value)&&obj2int(value)==47000);
    OBJ button=int2obj(1); assert(doPrimitiveCall(IOPrims,"buttonPressed",1,&button)==trueObj);
    button=int2obj(2); doPrimitiveCall(IOPrims,"buttonPressed",1,&button); assert(failure()); fail(0);
    vars[0]=zeroObj; vars[1]=int2obj(499);
    const uint16 streaming[]={OP(6,1),OP(2,3),OP(8,0),OP(6,0),OP(78,1),(uint16)OP(26,-5),0};
    upload(3,streaming,7); startTaskForChunk(3);
    for(int i=0;i<200&&taskCount;++i){inject(ping,3);pump(1000);}
    for(int i=0,last=-1;i<200&&last!=tx_count;++i){last=tx_count;pump(5000);}
    assert(!taskCount&&!failure());
    assert(obj2int(vars[0])==500);
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
    assert(outputs==500);
    printf("{\"result\":\"PASS\",\"architecture\":\"wasm32\",\"scope\":\"real SmallVM v417; simulated transport/peripherals\",\"reporter_runs\":10,\"arithmetic\":12,\"fragmented_message_bytes\":1019,\"partial_output_max\":7,\"ordered_stream_outputs\":500,\"stream_bytes\":%d,\"timeout_recovery\":true,\"invalid_length_recovery\":true,\"named_primitives\":true}\n",tx_count);
    return 0;
}
