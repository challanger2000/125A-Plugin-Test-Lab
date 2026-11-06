// Two actual VST3 instances in ONE Windows host process, with different
// user-state snapshots. Detects accidental static/global bank or voice state.
// State/PCM expectations live outside this native host (independent Python).
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include <array>
#include <cmath>
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
void check(bool ok,const char* message) {
    if(!ok) throw std::runtime_error(message);
}
std::vector<char> readState(const std::filesystem::path& file) {
    std::ifstream in(file,std::ios::binary|std::ios::ate);
    check(in.good(),"state file could not be opened");
    const auto length=in.tellg();
    check(length>0&&length<128*1024*1024,"state file is empty/too large");
    std::vector<char> bytes(static_cast<size_t>(length));
    in.seekg(0);
    in.read(bytes.data(),static_cast<std::streamsize>(bytes.size()));
    check(in.good(),"state file truncated");
    return bytes;
}
void saveState(IComponent* component,const std::filesystem::path& file) {
    ResizableMemoryIBStream data;
    check(component->getState(&data)==kResultOk,
          "live instance getState failed");
    const auto size=data.getCursor();
    check(size>0&&size<128*1024*1024,
          "live instance returned invalid state");
    std::ofstream out(file,std::ios::binary|std::ios::trunc);
    check(out.good(),"cannot open saved instance state");
    out.write(static_cast<const char*>(data.getData()),
              static_cast<std::streamsize>(size));
    check(out.good(),"failed writing instance state");
}
struct Instance {
    IPtr<IComponent> component;
    IAudioProcessor* processor=nullptr;
    bool active=false;
    bool processing=false;
    Instance()=default;
    Instance(const Instance&)=delete;
    Instance& operator=(const Instance&)=delete;
    ~Instance() {
        if(processor) {
            if(processing) (void)processor->setProcessing(false);
            if(active) (void)component->setActive(false);
            processor->release();
        }
        if(component) (void)component->terminate();
    }
};
template<class Factory,class Id>
void start(Instance& instance,Factory& factory,
           const Id& classID,HostApplication& host,
           const std::vector<char>& state) {
    instance.component=factory.createInstance<IComponent>(classID);
    check(bool(instance.component),"cannot create second independent VST3 processor");
    check(instance.component->initialize(&host)==kResultOk,
          "VST3 component initialize failed");
    check(instance.component->queryInterface(
        IAudioProcessor::iid,reinterpret_cast<void**>(&instance.processor))==kResultOk
        &&instance.processor,"missing VST3 processor interface");
    check(instance.processor->canProcessSampleSize(kSample32)==kResultTrue,
          "32-bit VST3 processing unsupported");
    check(instance.component->getBusCount(kAudio,kOutput)==1,
          "dual-instance case needs one audio output bus");
    BusInfo info{};
    check(instance.component->getBusInfo(kAudio,kOutput,0,info)==kResultOk &&
          info.channelCount==2,"dual-instance case needs stereo output");
    (void)instance.component->activateBus(kAudio,kOutput,0,true);
    ProcessSetup setup{};
    setup.processMode=kRealtime;
    setup.symbolicSampleSize=kSample32;
    setup.sampleRate=44100.;
    setup.maxSamplesPerBlock=64;
    check(instance.processor->setupProcessing(setup)==kResultOk,
          "dual-instance setupProcessing failed");
    ResizableMemoryIBStream stream(state.size());
    int32 count=0;
    check(stream.write(const_cast<char*>(state.data()),
          static_cast<int32>(state.size()),&count)==kResultOk &&
          count==static_cast<int32>(state.size()),
          "cannot write user state for independent VST3 instance");
    stream.rewind();
    check(instance.component->setState(&stream)==kResultOk,
          "one of two different user VST3 project states was rejected");
    check(instance.component->setActive(true)==kResultOk,
          "instance setActive failed");
    instance.active=true;
    check(instance.processor->setProcessing(true)==kResultOk,
          "instance setProcessing failed");
    instance.processing=true;
}
float sample(Instance& instance,int step) {
    std::array<Sample32,64> left{},right{};
    Sample32* channels[]{left.data(),right.data()};
    AudioBusBuffers output{};
    output.numChannels=2;
    output.channelBuffers32=channels;
    ProcessContext context{};
    context.state=ProcessContext::kPlaying|ProcessContext::kTempoValid|
                  ProcessContext::kTimeSigValid|ProcessContext::kProjectTimeMusicValid;
    context.sampleRate=44100.;
    context.tempo=120.;
    context.timeSigNumerator=4;
    context.timeSigDenominator=4;
    context.projectTimeSamples=static_cast<int64>(step)*64;
    context.projectTimeMusic=step*64.*120./(60.*44100.);
    ProcessData d{};
    d.processMode=kRealtime;
    d.symbolicSampleSize=kSample32;
    d.numSamples=64;
    d.numOutputs=1;
    d.outputs=&output;
    d.processContext=&context;
    check(instance.processor->process(d)==kResultOk,
          "one of the two independent VST3 instances failed processing");
    check(std::isfinite(left[0])&&std::isfinite(right[0]),
          "VST3 emitted nonfinite multi-instance audio");
    return 0.5f*(left[0]+right[0]);
}
int run(const std::string& pluginPath,const std::filesystem::path& a,
        const std::filesystem::path& b,const std::filesystem::path& dest) {
    auto stateA=readState(a),stateB=readState(b);
    check(stateA!=stateB,"dual-instance test requires distinct user states");
    std::string error;
    auto module=Module::create(pluginPath,error);
    check(bool(module),"could not load dual-instance VST3 module");
    HostApplication host;
    auto factory=module->getFactory();
    factory.setHostContext(&host);
    int found=0;
    for(const auto& cls:factory.classInfos()) {
        if(cls.category()!=kVstAudioEffectClass) continue;
        ++found;
    }
    check(found==1,"multi-class plugin needs explicit class selection (INCONCLUSIVE)");
    std::filesystem::create_directories(dest);
    // Keep both instances alive simultaneously, in the same loaded module.
    for(const auto& cls:factory.classInfos()) {
        if(cls.category()!=kVstAudioEffectClass) continue;
        Instance first,second;
        start(first,factory,cls.ID(),host,stateA);
        start(second,factory,cls.ID(),host,stateB);
        const float a0=sample(first,0),b0=sample(second,0);
        const float b1=sample(second,1),a1=sample(first,1);
        saveState(first.component.get(),dest/"A-after.bin");
        saveState(second.component.get(),dest/"B-after.bin");
        std::ofstream out(dest/"MULTI-INSTANCE.tsv",std::ios::trunc);
        check(out.good(),"cannot create multi-instance evidence");
        out.precision(9);
        out<<"format\t125A-DUAL-INSTANCE-v1\n";
        out<<"same_process_instances\t2\n";
        out<<"process_callbacks\t4\n";
        out<<"A_first_pcm\t"<<a0<<"\n";
        out<<"B_first_pcm\t"<<b0<<"\n";
        out<<"B_second_pcm\t"<<b1<<"\n";
        out<<"A_second_pcm\t"<<a1<<"\n";
        out.flush();
        check(out.good(),"could not save dual-instance test result");
        std::cout<<"[PASS] two real VST3 instances processed in same host process\n";
        return 0;
    }
    return 2;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=6||std::string(argv[1])!="--dual-state") {
            std::cerr<<"Usage: --dual-state <plugin.vst3> <A.bin> <B.bin> <out-dir>\n";
            return 2;
        }
        return run(argv[2],argv[3],argv[4],argv[5]);
    } catch(const std::exception& ex) {
        std::cerr<<"[FAIL] native dual-instance VST3 test: "<<ex.what()<<"\n";
        return 1;
    }
}
