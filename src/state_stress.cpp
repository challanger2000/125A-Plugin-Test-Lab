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
void hostPaceMicroseconds(int us) {
    const auto end=Clock::now()+std::chrono::microseconds(us);
    while(Clock::now()<end) std::atomic_signal_fence(std::memory_order_seq_cst);
}

struct Metrics {
    std::atomic<uint32> callbacks{0},processFailures{0},late{0},torn{0},saveFailures{0},saveOK{0},setFailures{0},savesDuringPlayback{0},setsDuringPlayback{0},setOK{0};
    std::atomic<int64> maximumNanoseconds{0};
    std::atomic<bool> running{true};
    std::atomic<float> rampSample{-1.f};
};
void updateMax(std::atomic<int64>& value,int64 candidate) {
    auto old=value.load(std::memory_order_relaxed);
    while(candidate>old && !value.compare_exchange_weak(old,candidate,std::memory_order_relaxed)){}
}
int stress(const std::string& pluginPath,const std::filesystem::path& report,
           int sampleRate,int block,int iterations,const std::string& oracle,bool saveOnly,bool strictRealtime,bool replayValid) {
    demand(!(saveOnly && replayValid),"state replay and save-only are mutually exclusive");
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
    int64 rtP95=0,rtP99=0;
    int64 callbackBudget=0;
    int observedInputBusCount=0;
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
            // Generic VST3 stress must provide actual input buffers to
            // effect plugins that declare a stereo input. The old host
            // only passed outputs (valid for instruments), so every normal
            // audio-effect process() correctly rejecting numInputs=0 was
            // misclassified as a plugin regression.
            const auto inputBusCount=component->getBusCount(kAudio,kInput);
            observedInputBusCount=inputBusCount;
            demand(inputBusCount==0||inputBusCount==1,
                   "this stress scenario supports zero or one audio input bus");
            if(inputBusCount==1) {
                BusInfo inputInfo{};
                demand(component->getBusInfo(kAudio,kInput,0,inputInfo)==kResultOk &&
                       inputInfo.channelCount==2,
                       "this stress scenario requires a stereo input when present");
                demand(component->activateBus(kAudio,kInput,0,true)==kResultOk,
                       "activate declared stereo input bus failed");
            }
            ProcessSetup setup{};
            setup.sampleRate=double(sampleRate);
            setup.maxSamplesPerBlock=std::max(16,block);
            setup.symbolicSampleSize=kSample32;
            setup.processMode=kRealtime;
            demand(processor->setupProcessing(setup)==kResultOk,"setupProcessing failed");
            // Capture REAL plugin-owned state; arbitrary binary layouts are
            // never injected into third-party VST3s in replay mode.
            std::vector<char> validState;
            if(replayValid) {
                ResizableMemoryIBStream initial;
                demand(component->getState(&initial)==kResultOk &&
                       initial.getCursor()>0 && initial.getCursor()<128*1024*1024,
                       "cannot capture valid pre-playback plugin state for replay");
                const auto* bytes=static_cast<const char*>(initial.getData());
                validState.assign(bytes,bytes+initial.getCursor());
            }
            demand(component->setActive(true)==kResultOk,"setActive failed");
            active=true;
            demand(processor->setProcessing(true)==kResultOk,"setProcessing failed");
            processing=true;
            const int bufferSize=std::max(16,block);
            std::vector<Sample32> left(bufferSize),right(bufferSize);
            Sample32* channels[]{left.data(),right.data()};
            AudioBusBuffers output{};output.numChannels=2;output.channelBuffers32=channels;
            // Preallocated deterministic, finite stereo signal for input
            // effects. Preserve the zero-input instrument contract.
            std::vector<Sample32> sourceL(bufferSize),sourceR(bufferSize);
            for(int n=0;n<bufferSize;++n) {
                sourceL[size_t(n)]=Sample32(.025*std::sin(double(n)*.031));
                sourceR[size_t(n)]=Sample32(.023*std::cos(double(n)*.047));
            }
            Sample32* inputChannels[]{sourceL.data(),sourceR.data()};
            AudioBusBuffers input{};
            input.numChannels=2;input.channelBuffers32=inputChannels;
            // Allocation is performed before the audio thread begins.
            // Only preallocated slots are written during the callbacks.
            std::vector<int64> callbackNs(size_t(iterations),0);
            std::atomic<bool> launch{false};
            const int targetFrame=sampleRate/20; // 50 ms of elapsed audio time
            const int64 deadlineNs=std::max<int64>(1000,1000000000LL*std::max(1,block)/sampleRate);
            callbackBudget=deadlineNs;
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
                d.numInputs=inputBusCount;
                d.inputs=inputBusCount==1?&input:nullptr;
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
                    callbackNs[size_t(i)]=ns;
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
                    hostPaceMicroseconds(60);
                }
                metrics.running.store(false,std::memory_order_release);
            });
            launch.store(true,std::memory_order_release);
            // Steinberg VST3: setState/getState are serialized on one
            // control/UI thread; process() runs concurrently on audio thread.
            // Alternate save-before-write and save-after-write ordering.
            auto saveSnapshot = [&] {
                // Confirm saved state was captured while the audio thread
                // was genuinely processing, not only after playback stopped.
                const uint32 before=metrics.callbacks.load(std::memory_order_acquire);
                ResizableMemoryIBStream saved;
                const bool ok=component->getState(&saved)==kResultOk && saved.getCursor()>0;
                const uint32 after=metrics.callbacks.load(std::memory_order_acquire);
                if(ok && before>0 && after<static_cast<uint32>(iterations) &&
                   metrics.running.load(std::memory_order_acquire))
                    metrics.savesDuringPlayback.fetch_add(1,std::memory_order_relaxed);
                if(!ok) {
                    metrics.saveFailures++;
                } else {
                    metrics.saveOK++;
                    if(oracle=="paired" &&
                       (saved.getCursor()!=sizeof(Pair) ||
                        !pairValid(*static_cast<const Pair*>(saved.getData()))))
                        metrics.torn++;
                }
            };
            if(saveOnly) {
                // Normal playback: absolutely no project writes or automation.
                for(int i=0;i<500;++i) {
                    saveSnapshot();
                    hostPaceMicroseconds(75);
                }
            } else if(replayValid) {
                // 500 setState and 500 getState attempts interleaved with live
                // processing; actual pre-playback state is replayed unchanged.
                // Control writes are serialized on this thread.
                for(int i=0;i<500;++i) {
                    ResizableMemoryIBStream stream(validState.size());
                    int32 written=0;
                    if(stream.write(validState.data(),
                        static_cast<int32>(validState.size()),&written)!=kResultOk ||
                        written!=static_cast<int32>(validState.size())) {
                        metrics.setFailures++;
                    } else {
                        stream.rewind();
                        const uint32 before=metrics.callbacks.load(std::memory_order_acquire);
                        const bool ok=component->setState(&stream)==kResultOk;
                        const uint32 after=metrics.callbacks.load(std::memory_order_acquire);
                        if(ok) {
                            metrics.setOK++;
                            if(before>0 && after<static_cast<uint32>(iterations) &&
                               metrics.running.load(std::memory_order_acquire))
                                metrics.setsDuringPlayback++;
                        } else {
                            metrics.setFailures++;
                        }
                    }
                    saveSnapshot();
                    hostPaceMicroseconds(75);
                }
            } else {
                for(int i=0;i<iterations*2;++i) {
                    if(i%20==0) saveSnapshot();
                    const Pair p=makePair((i&1)!=0);
                    ResizableMemoryIBStream stream;
                    int32 written=0;
                    if(stream.write(const_cast<Pair*>(&p),sizeof(p),&written)!=kResultOk ||
                       written!=sizeof(p)) {
                        metrics.setFailures++;
                    } else {
                        stream.rewind();
                        if(component->setState(&stream)!=kResultOk) metrics.setFailures++;
                    }
                    if(i%20==10) saveSnapshot();
                    hostPaceMicroseconds(5);
                }
            }
            audio.join();
            // Statistics are computed after join; no allocation/locking in
            // the real VST3 audio callback instrumentation.
            std::vector<int64> nonZero;
            nonZero.reserve(size_t(iterations));
            for(int i=0;i<iterations;++i) if(i%19!=0) nonZero.push_back(callbackNs[size_t(i)]);
            std::sort(nonZero.begin(),nonZero.end());
            demand(!nonZero.empty(),"P28 no nonzero callbacks recorded");
            rtP95=nonZero[size_t(std::ceil(0.95*nonZero.size()))-1];
            rtP99=nonZero[size_t(std::ceil(0.99*nonZero.size()))-1];
            demand(processor->setProcessing(false)==kResultOk,"stop processing failed");
            processing=false;
            demand(component->setActive(false)==kResultOk,"deactivate failed");
            active=false;
            // Distinguish technical success from independent domain correctness.
            if(metrics.processFailures||metrics.setFailures||metrics.saveFailures||
                metrics.saveOK!=500||metrics.torn||metrics.savesDuringPlayback.load()==0||
                (replayValid && (metrics.setOK.load()!=500 ||
                                  metrics.setsDuringPlayback.load()==0))) {pass=false;reason="failed process/setState/getState or torn independent state"; }
            if(oracle=="ramp") {
                const auto actual=metrics.rampSample.load();
                if(actual<0||std::abs(actual-0.125f)>0.002f) {
                    pass=false;reason="sample-rate-dependent elapsed-time ramp";
                }
            }
            // Deadline overruns are independently reported and can block
            // a realtime certification; timing is noisy on shared CI runners.
            if(metrics.late.load()>0 && reason.empty()) reason="callback deadline overruns observed";
            if(strictRealtime && metrics.late.load()>0) {
                pass=false;
                reason="realtime callback deadline violated";
            }
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
    if(!report.parent_path().empty()) std::filesystem::create_directories(report.parent_path());
    std::ofstream out(report,std::ios::trunc);
    demand(bool(out),"cannot write test evidence");
    out<<"format\t125A-P25-v1\n";
    out<<"plugin\t"<<pluginPath<<"\n";
    out<<"sample_rate\t"<<sampleRate<<"\nblock_size\t"<<block<<"\niterations\t"<<iterations<<"\n";
    out<<"oracle\t"<<oracle<<"\nscenario\t"<<(replayValid?"replay-genuine-state":saveOnly?"playback-save-no-writes":"concurrent-writers")<<"\nclasses\t"<<audioClasses<<"\n";
    out<<"input_audio_buses\t"<<observedInputBusCount<<"\n";
    out<<"callbacks\t"<<metrics.callbacks.load()<<"\nprocess_failures\t"<<metrics.processFailures.load();
    out<<"\nset_failures\t"<<metrics.setFailures.load()<<"\nsave_failures\t"<<metrics.saveFailures.load();
    out<<"\nsaves_during_playback\t"<<metrics.savesDuringPlayback.load();
    out<<"\nset_success\t"<<metrics.setOK.load()<<"\nsets_during_playback\t"<<metrics.setsDuringPlayback.load();
    out<<"\nsave_success\t"<<metrics.saveOK.load()<<"\ntorn_snapshots\t"<<metrics.torn.load();
    out<<"\ncallback_max_ns\t"<<metrics.maximumNanoseconds.load();
    out<<"\ncallback_overruns\t"<<metrics.late.load();
    out<<"\ncallback_p95_ns\t"<<rtP95;
    out<<"\ncallback_p99_ns\t"<<rtP99;
    out<<"\ncallback_deadline_ns\t"<<callbackBudget;
    out<<"\nstrict_realtime\t"<<(strictRealtime?1:0);
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
        if(argc<8||argc>11||std::string(argv[1])!="--stress") {
            std::cerr<<"Usage: --stress <VST3> <report.tsv> <rate> <block> <iterations> <paired|ramp|none> [--save-only] [--rt-deadline] [--replay-valid-state]\n";
            return 2;
        }
        bool saveOnly=false,strictRt=false,replayValid=false;
        for(int i=8;i<argc;++i) {
            const std::string flag=argv[i];
            if(flag=="--save-only" && !saveOnly) saveOnly=true;
            else if(flag=="--rt-deadline" && !strictRt) strictRt=true;
            else if(flag=="--replay-valid-state" && !replayValid) replayValid=true;
            else {std::cerr<<"Unknown or duplicate stress flag: "<<flag<<"\n";return 2;}
        }
        return stress(argv[2],argv[3],std::stoi(argv[4]),std::stoi(argv[5]),std::stoi(argv[6]),argv[7],saveOnly,strictRt,replayValid);
    } catch(const std::exception& e) {
        std::cerr<<"[FAIL] P25 host: "<<e.what()<<"\n";
        return 3;
    }
}
