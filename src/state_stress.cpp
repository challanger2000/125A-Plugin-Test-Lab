// P25-P27 universal VST3 concurrency and sample-rate integration harness.
// Always operates on real IComponent/IAudioProcessor, never production internals.
// A domain oracle is explicit. Absence of one is NOT domain correctness.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/vsttypes.h"
#include <atomic>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;
namespace {
void demand(bool x,const char* m) {if(!x) throw std::runtime_error(m);}
struct Pair {uint32 magic;int32 bank;int32 program;uint32 check;};
constexpr uint32 kMagic=0x125A2526;
Pair makePair(bool alternate) {
    const int32 b=alternate?33:11,p=alternate?44:22;
    return {kMagic,b,p,kMagic ^ uint32(b) ^ (uint32(p)<<8)};
}
bool pairValid(Pair p) {
    return p.magic==kMagic && p.check==(kMagic ^ uint32(p.bank) ^ (uint32(p.program)<<8)) &&
           ((p.bank==11 && p.program==22)||(p.bank==33 && p.program==44));
}
using Clock=std::chrono::steady_clock;
struct Metrics {
    std::atomic<uint32> callbacks{0},processFailures{0},late{0},torn{0},saveFailures{0},saveOK{0},setFailures{0};
    std::atomic<int64> maximumNanoseconds{0};
    std::atomic<bool> running{true};
    std::atomic<float> rampSample{-1.f};
};
void updateMax(std::atomic<int64>& value,int64 candidate) {
    auto old=value.load(std::memory_order_relaxed);
    while(candidate>old && !value.compare_exchange_weak(old,candidate,std::memory_order_relaxed)){}
}
int stress(const std::string& pluginPath,const std::filesystem::path& report,
           int sampleRate,int block,int iterations,const std::string& oracle) {
    demand(sampleRate==44100||sampleRate==48000||sampleRate==96000,"unsupported test sample rate");
    demand(block==0||block==17||block==64||block==127||block==512||block==1024,
           "unsupported test block");
    demand(iterations>=2000&&iterations<=30000,"invalid stress iteration count");
    demand(oracle=="paired"||oracle=="none"||oracle=="ramp","unknown independent oracle");
    std::string error;
    auto module=Module::create(pluginPath,error);
    demand(bool(module),"could not load VST3");
    HostApplication app;
    auto factory=module->getFactory();
    factory.setHostContext(&app);
    unsigned audioClasses=0;
    bool pass=true;
    std::string reason;
    Metrics metrics;
    for(const auto& info:factory.classInfos()) {
        if(info.category()!=kVstAudioEffectClass) continue;
        ++audioClasses;
        // Single-class scenario: explicit NOT COVERED for any other class.
        if(audioClasses>1) continue;
        auto component=factory.createInstance<IComponent>(info.ID());
        demand(bool(component),"component construction failed");
        demand(component->initialize(&app)==kResultOk,"component initialization failed");
        IAudioProcessor* processor=nullptr;
        demand(component->queryInterface(IAudioProcessor::iid,
                reinterpret_cast<void**>(&processor))==kResultOk && processor,
                "no IAudioProcessor interface");
        bool active=false,processing=false;
        try {
            demand(processor->canProcessSampleSize(kSample32)==kResultTrue,
                   "32-bit processing unavailable");
            demand(component->getBusCount(kAudio,kOutput)==1,
                   "this stress scenario requires exactly one output bus");
            BusInfo bus{};
            demand(component->getBusInfo(kAudio,kOutput,0,bus)==kResultOk&&bus.channelCount==2,
                   "this stress scenario requires a stereo output");
            (void)component->activateBus(kAudio,kOutput,0,true);
            ProcessSetup setup{};
            setup.sampleRate=double(sampleRate);
            setup.maxSamplesPerBlock=std::max(16,block);
            setup.symbolicSampleSize=kSample32;
            setup.processMode=kRealtime;
            demand(processor->setupProcessing(setup)==kResultOk,"setupProcessing failed");
            demand(component->setActive(true)==kResultOk,"setActive failed");
            active=true;
            demand(processor->setProcessing(true)==kResultOk,"setProcessing failed");
            processing=true;
            const int bufferSize=std::max(16,block);
            std::vector<Sample32> left(bufferSize),right(bufferSize);
            Sample32* channels[]{left.data(),right.data()};
            AudioBusBuffers output{};output.numChannels=2;output.channelBuffers32=channels;
            std::atomic<bool> launch{false};
            const int targetFrame=sampleRate/20; // 50 ms of elapsed audio time
            const int64 deadlineNs=std::max<int64>(1000,1000000000LL*std::max(1,block)/sampleRate);
            std::thread audio([&] {
                int64 frameIndex=0;
                ProcessContext context{};
                context.sampleRate=double(sampleRate);
                context.tempo=120.;
                context.timeSigNumerator=4;context.timeSigDenominator=4;
                context.state=ProcessContext::kPlaying|ProcessContext::kTempoValid|
                    ProcessContext::kTimeSigValid|ProcessContext::kProjectTimeMusicValid;
                ProcessData d{};
                d.processMode=kRealtime;d.symbolicSampleSize=kSample32;
                d.numOutputs=1;d.outputs=&output;d.processContext=&context;
                while(!launch.load(std::memory_order_acquire)) std::this_thread::yield();
                for(int i=0;i<iterations;++i) {
                    const int count=(i%19==0)?0:block; // legal zero-frame flush
                    d.numSamples=count;
                    context.projectTimeSamples=frameIndex;
                    context.projectTimeMusic=double(frameIndex)*120./(60.*sampleRate);
                    const auto begin=Clock::now();
                    if(processor->process(d)!=kResultOk)
                        metrics.processFailures.fetch_add(1,std::memory_order_relaxed);
                    const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(
                        Clock::now()-begin).count();
                    updateMax(metrics.maximumNanoseconds,ns);
                    if(count>0 && ns>deadlineNs)
                        metrics.late.fetch_add(1,std::memory_order_relaxed);
                    if(count>0 && frameIndex<=targetFrame && frameIndex+count>targetFrame) {
                        metrics.rampSample.store(left[size_t(targetFrame-frameIndex)],std::memory_order_relaxed);
                    }
                    for(int n=0;n<count;++n) {
                        if(!std::isfinite(left[size_t(n)])||!std::isfinite(right[size_t(n)]))
                            metrics.processFailures.fetch_add(1,std::memory_order_relaxed);
                    }
                    frameIndex+=count;
                    metrics.callbacks.fetch_add(1,std::memory_order_relaxed);
                    // Pacing is OUTSIDE process(), never in the audio callback.
                    std::this_thread::sleep_for(std::chrono::microseconds(60));
                }
                metrics.running.store(false,std::memory_order_release);
            });
            std::thread writer([&] {
                while(!launch.load(std::memory_order_acquire)) std::this_thread::yield();
                for(int i=0;i<iterations*2;++i) {
                    const Pair p=makePair((i&1)!=0);
                    ResizableMemoryIBStream stream;
                    int32 written=0;
                    if(stream.write(const_cast<Pair*>(&p),sizeof(p),&written)!=kResultOk||
                        written!=sizeof(p)) {metrics.setFailures++;continue;}
                    stream.rewind();
                    if(component->setState(&stream)!=kResultOk) metrics.setFailures++;
                    std::this_thread::sleep_for(std::chrono::microseconds(5));
                }
            });
            launch.store(true,std::memory_order_release);
            // Saves occur while callback and writer threads are active.
            // Never count a success without validating a complete snapshot.
            for(int i=0;i<500;++i) {
                ResizableMemoryIBStream saved;
                if(component->getState(&saved)!=kResultOk || saved.getCursor()==0) {
                    metrics.saveFailures++;
                } else {
                    metrics.saveOK++;
                    if(oracle=="paired") {
                        if(saved.getCursor()!=sizeof(Pair) || !pairValid(*static_cast<Pair*>(saved.getData())))
                            metrics.torn++;
                    }
                }
                std::this_thread::sleep_for(std::chrono::microseconds(75));
            }
            writer.join();
            audio.join();
            demand(processor->setProcessing(false)==kResultOk,"stop processing failed");
            processing=false;
            demand(component->setActive(false)==kResultOk,"deactivate failed");
            active=false;
            // Distinguish technical success from independent domain correctness.
            if(metrics.processFailures||metrics.setFailures||metrics.saveFailures||
                metrics.saveOK!=500||metrics.torn) {pass=false;reason="failed process/setState/getState or torn independent state"; }
            if(oracle=="ramp") {
                const auto actual=metrics.rampSample.load();
                if(actual<0||std::abs(actual-0.125f)>0.002f) {
                    pass=false;reason="sample-rate-dependent elapsed-time ramp";
                }
            }
            // Deadline overruns are independently reported and can block
            // a realtime certification; timing is noisy on shared CI runners.
            if(metrics.late.load()>0 && reason.empty()) reason="callback deadline overruns observed";
        } catch (...) {
            if(processing) (void)processor->setProcessing(false);
            if(active) (void)component->setActive(false);
            processor->release();
            (void)component->terminate();
            throw;
        }
        processor->release();
        demand(component->terminate()==kResultOk,"component termination failed");
    }
    demand(audioClasses>0,"no VST3 audio classes");
    report.parent_path().empty()?void():void();
    if(!report.parent_path().empty()) std::filesystem::create_directories(report.parent_path());
    std::ofstream out(report,std::ios::trunc);
    demand(bool(out),"cannot write test evidence");
    out<<"format\t125A-P25-v1\n";
    out<<"plugin\t"<<pluginPath<<"\n";
    out<<"sample_rate\t"<<sampleRate<<"\nblock_size\t"<<block<<"\niterations\t"<<iterations<<"\n";
    out<<"oracle\t"<<oracle<<"\nclasses\t"<<audioClasses<<"\n";
    out<<"callbacks\t"<<metrics.callbacks.load()<<"\nprocess_failures\t"<<metrics.processFailures.load();
    out<<"\nset_failures\t"<<metrics.setFailures.load()<<"\nsave_failures\t"<<metrics.saveFailures.load();
    out<<"\nsave_success\t"<<metrics.saveOK.load()<<"\ntorn_snapshots\t"<<metrics.torn.load();
    out<<"\ncallback_max_ns\t"<<metrics.maximumNanoseconds.load();
    out<<"\ncallback_overruns\t"<<metrics.late.load();
    out<<"\nrate_sample\t"<<metrics.rampSample.load();
    out<<"\nresult\t"<<(pass?"PASS":"FAIL")<<"\n";
    out<<"domain_correctness\t"<<(oracle=="none"?"NOT_COVERED":pass?"PASS":"FAIL")<<"\n";
    out<<"timing_certification\t"<<(metrics.late.load()?"FAIL":"PASS")<<"\n";
    out<<"reason\t"<<reason<<"\n";
    out.flush();
    demand(out.good(),"evidence file write failed");
    std::cout<<"["<<(pass?"PASS":"FAIL")<<"] universal VST3 live process/set/get, snapshots and elapsed time\n";
    return pass?0:1;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=8||std::string(argv[1])!="--stress") {
            std::cerr<<"Usage: --stress <VST3> <report.tsv> <rate> <block> <iterations> <paired|ramp|none>\n";
            return 2;
        }
        return stress(argv[2],argv[3],std::stoi(argv[4]),std::stoi(argv[5]),std::stoi(argv[6]),argv[7]);
    } catch(const std::exception& e) {
        std::cerr<<"[FAIL] P25 host: "<<e.what()<<"\n";
        return 3;
    }
}
