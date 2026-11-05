// P27 universal actual VST3 PCM recorder with different host block partitions.
// Independent reference waveform and cross-partition oracle are in Python.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/vsttypes.h"
#include <algorithm>
#include <cmath>
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
void require(bool b,const char* msg) {if(!b) throw std::runtime_error(msg);}
int run(const std::string& plugin,const std::filesystem::path& file,int rate,int block) {
    require(rate==44100||rate==48000||rate==96000,"unsupported sample rate");
    require(block==17||block==127||block==512,"unsupported block size");
    std::string error;
    auto module=Module::create(plugin,error);
    require(bool(module),"cannot load real VST3 module");
    HostApplication host;
    auto factory=module->getFactory();
    factory.setHostContext(&host);
    unsigned classes=0;
    const int total=rate/4; // 250 ms time domain, not fixed samples
    for(const auto& info:factory.classInfos()) {
        if(info.category()!=kVstAudioEffectClass) continue;
        ++classes;
        if(classes>1)continue; // Other classes explicitly NOT COVERED in scenario.
        auto component=factory.createInstance<IComponent>(info.ID());
        require(bool(component),"cannot instantiate IComponent");
        require(component->initialize(&host)==kResultOk,"initialize failed");
        IAudioProcessor* proc=nullptr;
        require(component->queryInterface(IAudioProcessor::iid,
                reinterpret_cast<void**>(&proc))==kResultOk&&proc,"processor unavailable");
        bool active=false,processing=false;
        try {
            require(proc->canProcessSampleSize(kSample32)==kResultTrue,"32-bit processing unavailable");
            require(component->getBusCount(kAudio,kOutput)==1,"single-output-bus scenario only");
            BusInfo bus{};
            require(component->getBusInfo(kAudio,kOutput,0,bus)==kResultOk&&bus.channelCount==2,
                    "stereo output required");
            (void)component->activateBus(kAudio,kOutput,0,true);
            ProcessSetup setup{};setup.processMode=kRealtime;
            setup.sampleRate=double(rate);setup.symbolicSampleSize=kSample32;
            setup.maxSamplesPerBlock=block;
            require(proc->setupProcessing(setup)==kResultOk,"setupProcessing failed");
            require(component->setActive(true)==kResultOk,"setActive failed");active=true;
            require(proc->setProcessing(true)==kResultOk,"setProcessing failed");processing=true;
            std::vector<Sample32> left(size_t(block),0.f),right(size_t(block),0.f);
            Sample32* channel[]{left.data(),right.data()};
            AudioBusBuffers outputs{};outputs.numChannels=2;outputs.channelBuffers32=channel;
            ProcessData d{};
            d.processMode=kRealtime;d.symbolicSampleSize=kSample32;
            d.numOutputs=1;d.outputs=&outputs;
            ProcessContext ctx{};
            ctx.sampleRate=double(rate);ctx.tempo=120.;
            ctx.timeSigNumerator=4;ctx.timeSigDenominator=4;
            ctx.state=ProcessContext::kPlaying|ProcessContext::kTempoValid|
                ProcessContext::kTimeSigValid|ProcessContext::kProjectTimeMusicValid;
            d.processContext=&ctx;
            std::vector<float> result;
            result.reserve(size_t(total)*2);
            unsigned calls=0,zero=0;
            for(int frame=0;frame<total;) {
                ctx.projectTimeSamples=frame;
                ctx.projectTimeMusic=double(frame)*120./(60.*rate);
                if(calls%11==0) {
                    d.numSamples=0;
                    require(proc->process(d)==kResultOk,"zero-frame process rejected");
                    ++zero;
                }
                const int count=std::min(block,total-frame);
                d.numSamples=count;
                require(proc->process(d)==kResultOk,"VST3 process callback failed");
                for(int n=0;n<count;++n) {
                    require(std::isfinite(left[size_t(n)])&&std::isfinite(right[size_t(n)]),
                            "NaN or Inf audio emitted");
                    result.push_back(left[size_t(n)]);
                    result.push_back(right[size_t(n)]);
                }
                frame+=count;
                ++calls;
            }
            require(result.size()==size_t(total)*2,"truncated frames");
            require(proc->setProcessing(false)==kResultOk,"stop processing failed");processing=false;
            require(component->setActive(false)==kResultOk,"deactivate failed");active=false;
            if(!file.parent_path().empty())std::filesystem::create_directories(file.parent_path());
            std::ofstream f(file,std::ios::binary|std::ios::trunc);
            require(bool(f),"unable to create PCM evidence");
            f.write(reinterpret_cast<const char*>(result.data()),
                    static_cast<std::streamsize>(result.size()*sizeof(float)));
            require(bool(f),"unable to save complete PCM evidence");
            std::cout<<"[PASS] P27 real VST3 250ms PCM: rate="<<rate
                     <<" block="<<block<<" frames="<<total<<" zero-frame calls="<<zero<<"\n";
        }catch(...) {
            if(processing)(void)proc->setProcessing(false);
            if(active)(void)component->setActive(false);
            proc->release();(void)component->terminate();throw;
        }
        proc->release();
        require(component->terminate()==kResultOk,"terminate failed");
    }
    require(classes>0,"no VST3 audio classes");
    return 0;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=6||std::string(argv[1])!="--pcm") {
            std::cerr<<"Usage: --pcm <plugin.vst3> <out-f32> <samplerate> <block-size>\n";return 2;
        }
        return run(argv[2],argv[3],std::stoi(argv[4]),std::stoi(argv[5]));
    }catch(const std::exception& error){
        std::cerr<<"[FAIL] P27 real VST3 host: "<<error.what()<<"\n";return 1;
    }
}
