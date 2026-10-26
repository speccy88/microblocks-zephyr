/* SPDX-License-Identifier: MPL-2.0 */
#include "neural_backend.h"
#include "nn_contract.h"
#include "neural_builtin.h"
#include <zephyr/kernel.h>
#include <zephyr/multi_heap/shared_multi_heap.h>
#include <zephyr/sys/atomic.h>
#include <psa/crypto.h>
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/micro/micro_mutable_op_resolver.h>
#include <tensorflow/lite/schema/schema_generated.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <new>

namespace {
constexpr unsigned STACK_BYTES=32768;
K_MUTEX_DEFINE(lock);
K_SEM_DEFINE(requested,0,1);
static struct {K_KERNEL_STACK_MEMBER(stack,STACK_BYTES);} memory __attribute__((section(".ext_ram.bss.nn_stack")));
static struct k_thread thread;
static atomic_t cancelled;
enum Job {NONE,LOAD,RUN,UNLOAD};
static Job job;
static bool initialized,busy,loaded,result_ready,unload_requested,model_owned;
static uint32_t generation,token,upload_token,upload_received,last_upload;
static uint8_t *upload,*arena;
static const uint8_t *model_data;
static unsigned model_bytes,arena_bytes,repeats=1,elapsed_us,completed,arena_used,stack_unused,macs;
static unsigned input_count;
static uint8_t supplied[(NN_MAX_ELEMENTS+7)/8];
static nn_tensor_desc input_desc,output_desc;
static char id[33],license[49],source[121],digest_hex[65],source_hex[65];
static uint8_t expected_digest[32],source_digest[32];
static unsigned source_format;
static const char *phase="idle",*message="no model loaded";
static tflite::MicroMutableOpResolver<1> resolver;
alignas(tflite::MicroInterpreter) static uint8_t interpreter_memory[sizeof(tflite::MicroInterpreter)];
static tflite::MicroInterpreter *interpreter;
static TfLiteTensor *input,*output;

static void *allocate(size_t n){return shared_multi_heap_aligned_alloc(SMH_REG_ATTR_EXTERNAL,16,n);}
static void release(void *p){if(p)shared_multi_heap_free(p);}
static void wipe(void *p,size_t n){if(p)memset(p,0,n);}
static uint32_t next_token(){return generation<0x1fffffffu?++generation:0;}
static void hex(const uint8_t *p,char *out){static const char digits[]="0123456789abcdef";for(unsigned i=0;i<32;i++){out[2*i]=digits[p[i]>>4];out[2*i+1]=digits[p[i]&15];}out[64]=0;}
static bool active(uint32_t t){return t&&t==token&&loaded&&!busy;}
static unsigned dtype(tflite::TensorType t){return t==tflite::TensorType_FLOAT32?NN_FLOAT32:t==tflite::TensorType_INT8?NN_INT8:t==tflite::TensorType_INT32?NN_INT32:0;}
static const char *type_name(unsigned t){return t==NN_FLOAT32?"float32":t==NN_INT8?"int8":"int32";}
static bool describe(const tflite::Tensor *t,nn_tensor_desc &out,bool io)
{
 if(!t||!t->shape()||!nn_shape_check(dtype(t->type()),t->shape()->size(),t->shape()->data(),&out))return false;
 if(t->is_variable()||t->sparsity())return false;
 if(t->shape_signature()){
  if(t->shape_signature()->size()!=t->shape()->size())return false;
  for(unsigned i=0;i<t->shape()->size();i++)if(t->shape_signature()->Get(i)!=t->shape()->Get(i))return false;
 }
 auto q=t->quantization();
 if(t->type()==tflite::TensorType_INT8){
  if(!q||!q->scale()||!q->zero_point()||!q->scale()->size()||!q->zero_point()->size())return false;
  if(io&&(q->scale()->size()!=1||q->zero_point()->size()!=1))return false;
  for(float scale:*q->scale())if(!std::isfinite(scale)||scale<1e-12f||scale>1e6f)return false;
  for(int64_t zero:*q->zero_point())if(zero < -128||zero>127)return false;
  out.scale=q->scale()->Get(0);out.zero_point=q->zero_point()->Get(0);
 }
 return true;
}
static const char *validate(const tflite::Model **mapped)
{
 if(model_bytes<32||model_bytes>NN_MAX_MODEL_BYTES)return "artifact size outside bounds";
 uint8_t digest[32];size_t n=0;
 if(psa_hash_compute(PSA_ALG_SHA_256,model_data,model_bytes,digest,sizeof(digest),&n)!=PSA_SUCCESS||n!=32)return "SHA-256 unavailable";
 hex(digest,digest_hex);hex(source_digest,source_hex);
 if(memcmp(digest,expected_digest,32))return "artifact SHA-256 mismatch";
 flatbuffers::Verifier verifier(model_data,model_bytes,16,2048);
 if(!tflite::VerifyModelBuffer(verifier))return "invalid TFLite FlatBuffer";
 auto model=tflite::GetModel(model_data);
 if(model->version()!=TFLITE_SCHEMA_VERSION)return "unsupported TFLite schema version";
 if(!model->subgraphs()||model->subgraphs()->size()!=1||!model->buffers()||!model->operator_codes()||!model->operator_codes()->size()||model->operator_codes()->size()>NN_MAX_OPS)return "expected one static dense graph";
 for(auto b:*model->buffers())if(!b||b->offset()||b->size())return "external model buffers unsupported";
 for(auto code:*model->operator_codes())if(!code)return "unsupported operator; expected FULLY_CONNECTED v1..4";
 auto graph=model->subgraphs()->Get(0);
 if(!graph||!graph->tensors()||!graph->tensors()->size()||graph->tensors()->size()>NN_MAX_TENSORS||!graph->operators()||!graph->operators()->size()||graph->operators()->size()>NN_MAX_OPS||!graph->inputs()||graph->inputs()->size()!=1||!graph->outputs()||graph->outputs()->size()!=1)return "graph/tensor count outside supported limits";
 unsigned count=graph->tensors()->size();nn_tensor_desc desc[NN_MAX_TENSORS];bool defined[NN_MAX_TENSORS]={};
 int in=graph->inputs()->Get(0),out=graph->outputs()->Get(0);
 if(in<0||out<0||in==out||(unsigned)in>=count||(unsigned)out>=count)return "invalid input/output tensor index";
 for(unsigned i=0;i<count;i++){
  auto t=graph->tensors()->Get(i);
  if(!describe(t,desc[i],i==(unsigned)in||i==(unsigned)out)||t->buffer()>=model->buffers()->size())return "unsupported tensor shape/type/quantization";
  auto bytes=model->buffers()->Get(t->buffer())->data();
  if(bytes&&bytes->size()){
   if(bytes->size()!=desc[i].bytes)return "constant tensor byte length mismatch";
   if(desc[i].dtype!=NN_INT8&&((uintptr_t)bytes->data()&3))return "unaligned numeric constant";
   if(desc[i].dtype==NN_FLOAT32)for(unsigned j=0;j<desc[i].elements;j++){float v;memcpy(&v,bytes->data()+4*j,4);if(!std::isfinite(v))return "non-finite model weight";}
   defined[i]=true;
  }else if(desc[i].dtype==NN_INT8){auto q=t->quantization();if(q->scale()->size()!=1||q->zero_point()->size()!=1)return "mutable tensors require per-tensor quantization";}
 }
 if(defined[in]||defined[out]||desc[in].dtype==NN_INT32||desc[out].dtype!=desc[in].dtype||desc[in].dims[0]!=1)return "expected matching float32/int8 input/output, batch one";
 defined[in]=true;macs=0;
 for(auto op:*graph->operators()){
  if(atomic_get(&cancelled))return "cancelled";
  if(!op||op->opcode_index()>=model->operator_codes()->size()||!op->inputs()||op->inputs()->size()<2||op->inputs()->size()>3||!op->outputs()||op->outputs()->size()!=1)return "invalid dense operator wiring";
  auto code=model->operator_codes()->Get(op->opcode_index());
  if(code->custom_code()||MAX((int)code->builtin_code(),(int)code->deprecated_builtin_code())!=tflite::BuiltinOperator_FULLY_CONNECTED||code->version()<1||code->version()>4)return "unsupported operator; expected FULLY_CONNECTED v1..4";
  int a=op->inputs()->Get(0),w=op->inputs()->Get(1),b=op->inputs()->size()==3?op->inputs()->Get(2):-1,y=op->outputs()->Get(0);
  if(a<0||w<0||y<0||(unsigned)a>=count||(unsigned)w>=count||(unsigned)y>=count||b < -1||(b>=0&&(unsigned)b>=count)||!defined[a]||!defined[w]||defined[y])return "cyclic or invalid tensor dependency";
  auto weights=graph->tensors()->Get(w);auto wb=model->buffers()->Get(weights->buffer())->data();
  if(!wb||!wb->size()||desc[w].rank!=2||desc[y].rank!=2||desc[y].dims[0]!=1||desc[w].dtype!=desc[a].dtype||desc[y].dtype!=desc[a].dtype||desc[w].dims[1]!=(int)desc[a].elements||desc[w].dims[0]!=(int)desc[y].elements)return "unsupported dense tensor layout";
  if(b>=0){auto bt=graph->tensors()->Get(b);auto bb=model->buffers()->Get(bt->buffer())->data();if(!defined[b]||!bb||!bb->size()||desc[b].elements!=desc[y].elements||desc[b].dtype!=(desc[a].dtype==NN_FLOAT32?NN_FLOAT32:NN_INT32))return "invalid dense bias";}
  if(desc[a].dtype==NN_INT8){
   auto q=weights->quantization();unsigned channels=desc[y].elements;
   if((q->scale()->size()!=1&&q->scale()->size()!=channels)||(q->zero_point()->size()!=1&&q->zero_point()->size()!=channels)||q->quantized_dimension()!=0)return "unsupported weight quantization layout";
   for(int64_t zero:*q->zero_point())if(zero)return "int8 dense weights must have zero point zero";
   for(float scale:*q->scale()){double actual=(double)desc[a].scale*scale/desc[y].scale;if(!std::isfinite(actual)||actual<=0||actual>1)return "quantized multiplier outside safe reference subset";}
   if(b>=0){auto bt=graph->tensors()->Get(b);auto bb=model->buffers()->Get(bt->buffer())->data();for(unsigned j=0;j<desc[b].elements;j++){int32_t value;memcpy(&value,bb->data()+4*j,4);int64_t magnitude=value<0?-(int64_t)value:value;if(magnitude+32768LL*desc[a].elements>INT32_MAX)return "bias and accumulation exceed int32 budget";}}
  }
  auto options=op->builtin_options_as_FullyConnectedOptions();
  if(op->builtin_options_type()!=tflite::BuiltinOptions_FullyConnectedOptions||!options||options->weights_format()!=tflite::FullyConnectedOptionsWeightsFormat_DEFAULT||options->keep_num_dims()||options->asymmetric_quantize_inputs()||(options->fused_activation_function()!=tflite::ActivationFunctionType_NONE&&options->fused_activation_function()!=tflite::ActivationFunctionType_RELU&&options->fused_activation_function()!=tflite::ActivationFunctionType_RELU6))return "unsupported dense options";
  if(desc[w].elements>NN_MAX_MACS-macs)return "model exceeds MAC budget";
  macs+=desc[w].elements;defined[y]=true;k_sleep(K_MSEC(1));
 }
 if(!defined[out])return "graph output is not produced";
 input_desc=desc[in];output_desc=desc[out];*mapped=model;return nullptr;
}
static void cleanup()
{
 if(interpreter){interpreter->~MicroInterpreter();interpreter=nullptr;}
 if(arena){wipe(arena,arena_bytes);release(arena);arena=nullptr;}
 if(model_owned&&model_data){wipe((void *)model_data,model_bytes);release((void *)model_data);}
 model_data=nullptr;model_owned=false;input=output=nullptr;arena_used=0;
}
static void worker(void *,void *,void *)
{
 for(;;){
  k_sem_take(&requested,K_FOREVER);k_mutex_lock(&lock,K_FOREVER);Job current=job;phase=current==LOAD?"loading":current==RUN?"running":"unloading";k_mutex_unlock(&lock);
  int64_t began=k_uptime_ticks();const char *error=nullptr;unsigned done=0;
  if(current==LOAD){
   const tflite::Model *model=nullptr;error=validate(&model);
   if(!error){arena=(uint8_t *)allocate(arena_bytes);if(!arena)error="PSRAM arena allocation failed; release other media";}
   if(!error){interpreter=new(interpreter_memory)tflite::MicroInterpreter(model,resolver,arena,arena_bytes);if(interpreter->AllocateTensors()!=kTfLiteOk)error="tensor allocation/kernel preparation failed";}
   if(!error){input=interpreter->input(0);output=interpreter->output(0);if(!input||!output||input->bytes!=input_desc.bytes||output->bytes!=output_desc.bytes)error="allocated tensor contract mismatch";else{arena_used=interpreter->arena_used_bytes();wipe(input->data.raw,input->bytes);memset(supplied,0,sizeof(supplied));input_count=0;}}
  }else if(current==RUN){
   for(unsigned i=0;i<repeats;i++){
    if(atomic_get(&cancelled)){error="cancelled";break;}
    if(interpreter->Invoke()!=kTfLiteOk){error="inference failed";break;}
    done++;k_sleep(K_MSEC(1));
    if(k_ticks_to_ms_floor64(k_uptime_ticks()-began)>5000){error="bounded inference deadline exceeded";break;}
   }
   if(!error&&output_desc.dtype==NN_FLOAT32)for(unsigned i=0;i<output_desc.elements;i++)if(!std::isfinite(output->data.f[i])){error="non-finite output rejected";break;}
  }
  if(atomic_get(&cancelled)&&current!=UNLOAD)error="cancelled";
  k_mutex_lock(&lock,K_FOREVER);bool discard=current==UNLOAD||unload_requested||(current==LOAD&&error);k_mutex_unlock(&lock);
  if(discard)cleanup();
  size_t unused=0;if(k_thread_stack_space_get(k_current_get(),&unused))unused=0;
  k_mutex_lock(&lock,K_FOREVER);
  elapsed_us=k_ticks_to_us_floor64(k_uptime_ticks()-began);completed=done;stack_unused=unused;
  if(discard){loaded=false;token=0;result_ready=false;phase=error?"error":"idle";message=error?error:"model and arena released";}
  else if(current==LOAD){loaded=true;phase="loaded";message="supply every input element before run";}
  else{result_ready=!error;phase=error?"error":"ready";message=error?error:"typed output ready";}
  busy=false;job=NONE;unload_requested=false;k_mutex_unlock(&lock);
 }
}
static void queue(Job j){job=j;busy=true;result_ready=false;phase="queued";atomic_clear(&cancelled);k_sem_give(&requested);}
static void mark(unsigned i){uint8_t bit=1u<<(i&7);if(!(supplied[i>>3]&bit)){supplied[i>>3]|=bit;input_count++;}}
static bool safe_text(const uint8_t *p,unsigned n){for(unsigned i=0;i<n;i++)if(p[i]<32||p[i]>126||p[i]=='"'||p[i]=='\\')return false;return n!=0;}
static bool metadata(const uint8_t *p,unsigned n)
{
 if(n<68)return false;memcpy(expected_digest,p,32);memcpy(source_digest,p+32,32);source_format=p[64];if(source_format>1)return false;
 unsigned pos=65;char *dest[]={id,license,source};unsigned limits[]={32,48,120};
 for(unsigned i=0;i<3;i++){if(pos>=n)return false;unsigned len=p[pos++];if(len>limits[i]||len>n-pos||!safe_text(p+pos,len))return false;memcpy(dest[i],p+pos,len);dest[i][len]=0;pos+=len;}
 return pos==n;
}
static void descriptor(char *out,size_t n,const nn_tensor_desc &d)
{
 char dims[80]={0};size_t used=0;for(unsigned i=0;i<d.rank;i++)used+=snprintf(dims+used,sizeof(dims)-used,"%s%d",i?",":"",(int)d.dims[i]);
 snprintf(out,n,"{\"dtype\":\"%s\",\"shape\":[%s],\"elements\":%u,\"bytes\":%u,\"scale\":%.9g,\"zero_point\":%d}",type_name(d.dtype),dims,d.elements,d.bytes,(double)d.scale,(int)d.zero_point);
}
}

extern "C" void p4_nn_init(void)
{
 if(initialized)return;
 if(resolver.AddFullyConnected()!=kTfLiteOk||psa_crypto_init()!=PSA_SUCCESS){message="native kernel/hash initialization failed";return;}
 initialized=true;k_thread_create(&thread,memory.stack,K_KERNEL_STACK_SIZEOF(memory.stack),worker,nullptr,nullptr,nullptr,8,0,K_NO_WAIT);k_thread_name_set(&thread,"p4_nn");
}
extern "C" int p4_nn_available(void){return initialized;}
extern "C" uint32_t p4_nn_builtin(const char *name)
{
 k_mutex_lock(&lock,K_FOREVER);uint32_t result=0;
 if(initialized&&!busy&&!upload&&!strcmp(name,"sine-int8-v1")){
  if(loaded&&!strcmp(id,"sine-int8-v1"))result=token;
  else if(!loaded&&(result=next_token())){
   token=result;model_data=p4_nn_builtin_start;model_bytes=p4_nn_builtin_end-p4_nn_builtin_start;model_owned=false;arena_bytes=8192;
   strcpy(id,"sine-int8-v1");strcpy(license,"Apache-2.0");strcpy(source,"zephyr:a915b2f12675b48b16d56653ea145dcd8f20cbbf:hello_world/src/model.cpp");
   memcpy(expected_digest,p4_nn_builtin_digest,32);memcpy(source_digest,p4_nn_builtin_source_digest,32);source_format=0;queue(LOAD);
  }
 }
 k_mutex_unlock(&lock);return result;
}
extern "C" int p4_nn_busy(void){k_mutex_lock(&lock,K_FOREVER);int value=busy;k_mutex_unlock(&lock);return value;}
extern "C" int p4_nn_ready(uint32_t t){k_mutex_lock(&lock,K_FOREVER);int value=active(t);k_mutex_unlock(&lock);return value;}
extern "C" uint32_t p4_nn_current(void){k_mutex_lock(&lock,K_FOREVER);uint32_t t=loaded&&!busy?token:0;k_mutex_unlock(&lock);return t;}
extern "C" int p4_nn_set_value(uint32_t t,unsigned index,int milli)
{
 k_mutex_lock(&lock,K_FOREVER);int ok=0;
 if(active(t)&&index<input_desc.elements){
  float real=(float)milli/1000.f;
  if(input_desc.dtype==NN_FLOAT32){input->data.f[index]=real;ok=1;}
  else{double q=std::round((double)real/input_desc.scale)+input_desc.zero_point;if(q>=-128&&q<=127){input->data.int8[index]=(int8_t)q;ok=1;}}
  if(ok){mark(index);result_ready=false;phase="loaded";}else message="input outside quantized range";
 }
 k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_nn_output_value(uint32_t t,unsigned index,int *value)
{
 k_mutex_lock(&lock,K_FOREVER);int ok=0;
 if(active(t)&&result_ready&&index<output_desc.elements){double real=output_desc.dtype==NN_FLOAT32?output->data.f[index]:(output->data.int8[index]-output_desc.zero_point)*(double)output_desc.scale;double scaled=std::round(real*1000);if(std::isfinite(scaled)&&scaled>=-1e9&&scaled<=1e9){*value=(int)scaled;ok=1;}}
 k_mutex_unlock(&lock);return ok;
}
extern "C" int p4_nn_run(uint32_t t,unsigned count)
{
 k_mutex_lock(&lock,K_FOREVER);int ok=active(t)&&count>0&&count<=256&&input_count==input_desc.elements;
 if(ok){repeats=count;queue(RUN);}else if(active(t))message="every input element is required; repetitions 1..256";
 k_mutex_unlock(&lock);return ok;
}
extern "C" void p4_nn_cancel(void)
{
 atomic_set(&cancelled,1);k_mutex_lock(&lock,K_FOREVER);
 if(upload){wipe(upload,model_bytes);release(upload);upload=nullptr;upload_token=0;phase="idle";message="upload cancelled";}
 k_mutex_unlock(&lock);
}
extern "C" int p4_nn_unload(uint32_t t)
{
 k_mutex_lock(&lock,K_FOREVER);int ok=t&&t==token;
 if(ok){if(busy){unload_requested=true;atomic_set(&cancelled,1);}else queue(UNLOAD);}
 k_mutex_unlock(&lock);return ok;
}
extern "C" void p4_nn_poll(void)
{
 k_mutex_lock(&lock,K_FOREVER);if(upload&&(uint32_t)(k_uptime_get_32()-last_upload)>30000){wipe(upload,model_bytes);release(upload);upload=nullptr;upload_token=0;phase="error";message="upload inactivity timeout; buffers released";}k_mutex_unlock(&lock);
}
extern "C" void p4_nn_capabilities(char *out,size_t n)
{
 snprintf(out,n,"{\"available\":%s,\"backend\":\"native Zephyr TFLM reference CPU\",\"artifact\":\"TFLite\",\"direct_onnx_runtime\":false,\"operators\":[\"FULLY_CONNECTED\"],\"types\":[\"float32\",\"int8\"],\"max_model_bytes\":%u,\"max_arena_bytes\":%u,\"max_macs\":%u,\"models\":[{\"id\":\"sine-int8-v1\",\"license\":\"Apache-2.0\",\"bytes\":2488}],\"hardware_acceleration\":false,\"cloud_fallback\":false}",initialized?"true":"false",NN_MAX_MODEL_BYTES,NN_MAX_ARENA_BYTES,NN_MAX_MACS);
}
extern "C" void p4_nn_status(char *out,size_t n)
{
 k_mutex_lock(&lock,K_FOREVER);
 snprintf(out,n,"{\"phase\":\"%s\",\"message\":\"%s\",\"busy\":%s,\"loaded\":%s,\"upload_received\":%u,\"model_ram_bytes\":%u,\"arena_reserved_bytes\":%u,\"arena_used_bytes\":%u,\"worker_stack_bytes\":%u,\"stack_unused_bytes\":%u,\"elapsed_us\":%u,\"completed_invocations\":%u,\"inputs_supplied\":%u}",phase,busy?"bounded native job active":message,busy?"true":"false",loaded?"true":"false",upload_received,busy?0:model_owned?model_bytes:upload?model_bytes:0,busy?arena_bytes:arena?arena_bytes:0,busy?0:arena_used,STACK_BYTES,busy?0:stack_unused,busy?0:elapsed_us,busy?0:completed,busy?0:input_count);
 k_mutex_unlock(&lock);
}
extern "C" void p4_nn_info(uint32_t t,char *out,size_t n)
{
 k_mutex_lock(&lock,K_FOREVER);
 if(!active(t)){snprintf(out,n,"{\"error\":\"stale model or busy\"}");k_mutex_unlock(&lock);return;}
 char in[200],result[200];descriptor(in,sizeof(in),input_desc);descriptor(result,sizeof(result),output_desc);
 snprintf(out,n,"{\"id\":\"%s\",\"license\":\"%s\",\"source\":\"%s\",\"source_format\":\"%s\",\"source_sha256\":\"%s\",\"artifact_sha256\":\"%s\",\"artifact_bytes\":%u,\"backend\":\"TFLM reference CPU\",\"input\":%s,\"output\":%s,\"macs\":%u,\"arena_used_bytes\":%u}",id,license,source,source_format?"ONNX converted offline":"TFLite",source_hex,digest_hex,model_bytes,in,result,macs,arena_used);
 k_mutex_unlock(&lock);
}
extern "C" int p4_nn_transfer(unsigned op,uint32_t *t,uint32_t offset,uint32_t arg,const uint8_t *data,unsigned count,uint8_t *out,unsigned *bytes)
{
 unsigned capacity=*bytes;*bytes=0;if(!initialized)return 3;
 if(op==0){p4_nn_capabilities((char *)out,capacity);*bytes=strlen((char *)out);return 0;}
 if(op==5){p4_nn_info(*t,(char *)out,capacity);*bytes=strlen((char *)out);return 0;}
 if(op==10){p4_nn_status((char *)out,capacity);*bytes=strlen((char *)out);return 0;}
 if(op==8){if(!count||count>32||!safe_text(data,count))return 1;char name[33]={0};memcpy(name,data,count);*t=p4_nn_builtin(name);return *t?0:2;}
 if(op==9)return p4_nn_unload(*t)?0:7;
 if(op==4){p4_nn_cancel();return 0;}
 k_mutex_lock(&lock,K_FOREVER);int error=1;
 if(op==1){
  if(busy||loaded||upload)error=2;
  else if(arg<32||arg>NN_MAX_MODEL_BYTES||offset<4096||offset>NN_MAX_ARENA_BYTES)error=4;
  else if(!metadata(data,count))error=1;
  else if(!(upload=(uint8_t *)allocate(arg)))error=6;
  else{upload_token=next_token();if(!upload_token){release(upload);upload=nullptr;error=6;}else{*t=upload_token;model_bytes=arg;arena_bytes=offset;upload_received=0;last_upload=k_uptime_get_32();phase="uploading";message="bounded local upload";error=0;}}
 }else if(op==2){
  if(!upload||*t!=upload_token)error=7;
  else if(!count||count>512||offset!=upload_received||count>model_bytes-upload_received)error=4;
  else{memcpy(upload+offset,data,count);upload_received+=count;last_upload=k_uptime_get_32();error=0;}
 }else if(op==3){
  if(!upload||*t!=upload_token)error=7;
  else if(upload_received!=model_bytes)error=9;
  else{model_data=upload;model_owned=true;upload=nullptr;token=upload_token;upload_token=0;queue(LOAD);error=0;}
 }else if(op==6||op==7){
  if(!active(*t))error=busy?2:7;
  else{
   const nn_tensor_desc &d=op==6?output_desc:input_desc;unsigned unit=d.dtype==NN_INT8?1:4;
   if(offset>d.bytes||count>d.bytes-offset||count>512||offset%unit||count%unit)error=4;
   else if(op==6){if(!result_ready)error=9;else{memcpy(out,output->data.raw+offset,count);*bytes=count;error=0;}}
   else{
    error=0;if(d.dtype==NN_FLOAT32)for(unsigned i=0;i<count;i+=4){float v;memcpy(&v,data+i,4);if(!std::isfinite(v)){error=4;break;}}
    if(!error){memcpy(input->data.raw+offset,data,count);for(unsigned i=offset/unit;i<(offset+count)/unit;i++)mark(i);result_ready=false;phase="loaded";}
   }
  }
 }
 k_mutex_unlock(&lock);return error;
}
