/* SPDX-License-Identifier: MIT */
/* Exact pinned TFLM reference-kernel allocation/invoke probe; no desktop delegate. */
#include <tensorflow/lite/micro/micro_interpreter.h>
#include <tensorflow/lite/micro/micro_mutable_op_resolver.h>
#include <tensorflow/lite/schema/schema_generated.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>
int main(int argc,char **argv) {
    if(argc!=5) return 2;
    std::ifstream f(argv[1],std::ios::binary),input(argv[2],std::ios::binary);
    std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(f)),{});
    std::vector<int8_t> data((std::istreambuf_iterator<char>(input)),{});
    if(bytes.empty() || data.empty() || data.size()%4720) return 3;
    flatbuffers::Verifier verifier(bytes.data(),bytes.size());
    if(!tflite::VerifyModelBuffer(verifier))return 4;
    auto model=tflite::GetModel(bytes.data());
    unsigned arena_size=std::strtoul(argv[4],nullptr,10);
    if(arena_size>1024*1024 || !arena_size)return 5;
    void *arena=nullptr;if(posix_memalign(&arena,16,arena_size))return 5;
    tflite::MicroMutableOpResolver<8> resolver;
    if(resolver.AddConv2D()!=kTfLiteOk || resolver.AddDepthwiseConv2D()!=kTfLiteOk ||
       resolver.AddAveragePool2D()!=kTfLiteOk || resolver.AddFullyConnected()!=kTfLiteOk ||
       resolver.AddReshape()!=kTfLiteOk || resolver.AddSoftmax()!=kTfLiteOk ||
       resolver.AddMul()!=kTfLiteOk || resolver.AddQuantize()!=kTfLiteOk)return 6;
    tflite::MicroInterpreter interpreter(model,resolver,(uint8_t *)arena,arena_size);
    if(interpreter.AllocateTensors()!=kTfLiteOk)return 7;
    auto in=interpreter.input(0),out=interpreter.output(0);
    if(in->type!=kTfLiteInt8 || in->bytes!=4720 || out->type!=kTfLiteInt8 || out->bytes!=10)return 8;
    std::ofstream output(argv[3],std::ios::binary);std::vector<double> times;
    for(size_t offset=0;offset<data.size();offset+=4720) {
        memcpy(in->data.int8,data.data()+offset,4720);
        auto start=std::chrono::steady_clock::now();
        if(interpreter.Invoke()!=kTfLiteOk)return 9;
        auto stop=std::chrono::steady_clock::now();
        times.push_back(std::chrono::duration<double,std::micro>(stop-start).count());
        output.write((char *)out->data.int8,10);
    }
    printf("{\"runtime\":\"pinned host TFLM reference kernels\",\"arena_reserved_bytes\":%u,\"arena_used_bytes\":%zu,\"invocations\":%zu,\"invoke_us\":[",arena_size,interpreter.arena_used_bytes(),times.size());
    for(size_t i=0;i<times.size();i++)printf("%s%.3f",i?",":"",times[i]);
    printf("]}\n");free(arena);
}
