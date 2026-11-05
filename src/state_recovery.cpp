// P26: product-neutral real VST3 state failure/rollback/recovery recorder.
// The expected state bytes/audio live ONLY in the external adapter oracle.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/vsttypes.h"
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;
namespace {
void check(bool yes,const char* msg) {if(!yes) throw std::runtime_error(msg);}
std::vector<char> load(const std::filesystem::path& path) {
    std::ifstream f(path,std::ios::binary|std::ios::ate);
    check(bool(f),"input state file unavailable");
    const auto size=f.tellg();
    check(size>0&&size<=1024*1024,"invalid state input length");
    std::vector<char> bytes(static_cast<size_t>(size));
    f.seekg(0);
    f.read(bytes.data(),static_cast<std::streamsize>(size));
    check(bool(f),"cannot read complete state");
    return bytes;
}
void dump(const std::filesystem::path& path,const void* data,size_t count) {
    std::ofstream file(path,std::ios::binary|std::ios::trunc);
    check(bool(file),"output evidence cannot be opened");
    file.write(static_cast<const char*>(data),static_cast<std::streamsize>(count));
    check(bool(file),"cannot write evidence");
}
bool setState(IComponent* c,const std::vector<char>& bytes) {
    ResizableMemoryIBStream stream;
    int32 n=0;
    check(stream.write(const_cast<char*>(bytes.data()),static_cast<int32>(bytes.size()),&n)==kResultOk &&
          n==static_cast<int32>(bytes.size()),"cannot create IBStream fixture");
    stream.rewind();
    return c->setState(&stream)==kResultOk;
}
void saveState(IComponent* c,const std::filesystem::path& path) {
    ResizableMemoryIBStream stream;
    check(c->getState(&stream)==kResultOk,"getState failed after state operation");
    const auto bytes=stream.getCursor();
    check(bytes>0&&bytes<16*1024*1024,"getState returned unreasonable payload");
    dump(path,stream.getData(),static_cast<size_t>(bytes));
}
void render(IAudioProcessor* p,const std::filesystem::path& path,int sampleRate) {
    std::array<Sample32,64> left{},right{};
    Sample32* channels[]{left.data(),right.data()};
    AudioBusBuffers output{};
    output.numChannels=2;
    output.channelBuffers32=channels;
    ProcessContext ctx{};
    ctx.sampleRate=sampleRate;
    ctx.tempo=120.;
    ctx.timeSigNumerator=4;ctx.timeSigDenominator=4;
    ctx.state=ProcessContext::kPlaying|ProcessContext::kTempoValid|
              ProcessContext::kTimeSigValid|ProcessContext::kProjectTimeMusicValid;
    ProcessData data{};
    data.processMode=kRealtime;data.symbolicSampleSize=kSample32;
    data.numSamples=64;
    data.numOutputs=1;data.outputs=&output;data.processContext=&ctx;
    check(p->process(data)==kResultOk,"real VST3 process failed after state action");
    std::array<float,128> interleaved{};
    for(size_t i=0;i<64;++i){
        interleaved[2*i]=left[i];interleaved[2*i+1]=right[i];
    }
    dump(path,interleaved.data(),sizeof(interleaved));
}
int run(const std::string& plugin,const std::filesystem::path& a,
        const std::filesystem::path& b,const std::filesystem::path& invalid,
        const std::filesystem::path& output) {
    const auto bytesA=load(a),bytesB=load(b),bytesInvalid=load(invalid);
    std::filesystem::create_directories(output);
    std::string error;
    auto module=Module::create(plugin,error);
    check(bool(module),"VST3 module load failed");
    HostApplication app;
    auto factory=module->getFactory();
    factory.setHostContext(&app);
    unsigned count=0;
    for(const auto& cls:factory.classInfos()) {
        if(cls.category()!=kVstAudioEffectClass) continue;
        ++count;
        if(count>1) continue;
        auto c=factory.createInstance<IComponent>(cls.ID());
        check(bool(c),"VST3 instantiate failed");
        check(c->initialize(&app)==kResultOk,"VST3 initialize failed");
        IAudioProcessor* p=nullptr;
        check(c->queryInterface(IAudioProcessor::iid,
            reinterpret_cast<void**>(&p))==kResultOk&&p,
            "VST3 processor interface unavailable");
        bool active=false,processing=false;
        try {
            check(p->canProcessSampleSize(kSample32)==kResultTrue,"32-bit processing unavailable");
            check(c->getBusCount(kAudio,kOutput)==1,"one output bus required by this scenario");
            BusInfo bus{};
            check(c->getBusInfo(kAudio,kOutput,0,bus)==kResultOk&&bus.channelCount==2,
                  "stereo output required by scenario");
            (void)c->activateBus(kAudio,kOutput,0,true);
            ProcessSetup setup{};
            setup.sampleRate=44100.;setup.maxSamplesPerBlock=64;
            setup.symbolicSampleSize=kSample32;setup.processMode=kRealtime;
            check(p->setupProcessing(setup)==kResultOk,"setupProcessing failed");
            check(setState(c.get(),bytesA),"valid fixture A rejected");
            check(c->setActive(true)==kResultOk,"setActive failed");active=true;
            check(p->setProcessing(true)==kResultOk,"start processing failed");processing=true;
            saveState(c.get(),output/"state-before.bin");
            render(p,output/"audio-before.f32",44100);
            const bool badAccepted=setState(c.get(),bytesInvalid);
            // A negative setState must reject the file; data consistency is
            // independently verified from the actual post-error state/audio.
            check(!badAccepted,"invalid state file accepted by VST3 component");
            saveState(c.get(),output/"state-after-error.bin");
            render(p,output/"audio-after-error.f32",44100);
            check(setState(c.get(),bytesB),"valid recovery state B rejected");
            saveState(c.get(),output/"state-after-recovery.bin");
            render(p,output/"audio-after-recovery.f32",44100);
            check(setState(c.get(),bytesA),"restoring original state A rejected");
            saveState(c.get(),output/"state-after-restore.bin");
            render(p,output/"audio-after-restore.f32",44100);
            check(p->setProcessing(false)==kResultOk,"stop processing failed");processing=false;
            check(c->setActive(false)==kResultOk,"deactivate failed");active=false;
        } catch (...) {
            if(processing) (void)p->setProcessing(false);
            if(active) (void)c->setActive(false);
            p->release();(void)c->terminate();throw;
        }
        p->release();
        check(c->terminate()==kResultOk,"component termination failed");
    }
    check(count>0,"no audio component");
    std::cout<<"[PASS] P26 real VST3 API sequence executed (semantic oracle separate)\n";
    return 0;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=7||std::string(argv[1])!="--recover") {
            std::cerr<<"Usage: --recover <VST3> <state-A.bin> <state-B.bin> <invalid.bin> <output-dir>\n";
            return 2;
        }
        return run(argv[2],argv[3],argv[4],argv[5],argv[6]);
    } catch(const std::exception& e) {
        std::cerr<<"[FAIL] P26 recovery: "<<e.what()<<"\n";
        return 1;
    }
}
