// P29 universal VST3 MIDI workload: voice tiers, 500 live saves, fresh-instance recall.
// Expected voice/audio meaning is supplied by a separate fixture adapter oracle.
// A generic plugin does NOT imply musical correctness merely by accepting events.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/eventlist.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/vsttypes.h"
#include <array>
#include <atomic>
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
using Clock=std::chrono::steady_clock;
void require(bool condition,const char* message) {
    if(!condition)throw std::runtime_error(message);
}
void hostPace(int us) {
    const auto stop=Clock::now()+std::chrono::microseconds(us);
    while(Clock::now()<stop)std::atomic_signal_fence(std::memory_order_seq_cst);
}
bool writeState(IComponent* c,ResizableMemoryIBStream& out) {
    return c->getState(&out)==kResultOk && out.getCursor()>0;
}
void configure(IComponent* c,IAudioProcessor* p) {
    require(c->activateBus(kEvent,kInput,0,true)==kResultOk,"event input activation failed");
    require(c->activateBus(kAudio,kOutput,0,true)==kResultOk,"audio output activation failed");
    ProcessSetup setup{};
    setup.processMode=kRealtime;setup.symbolicSampleSize=kSample32;
    setup.sampleRate=48000.;setup.maxSamplesPerBlock=64;
    require(p->canProcessSampleSize(kSample32)==kResultTrue,"32bit processor unsupported");
    require(p->setupProcessing(setup)==kResultOk,"setupProcessing failed");
}
int run(const std::string& plugin,const std::filesystem::path& out,int voices) {
    require(voices==0||voices==1||voices==8||voices==32,"unapproved voice tier");
    std::string error;
    auto module=Module::create(plugin,error);
    require(bool(module),"VST3 binary cannot be loaded");
    HostApplication host;
    auto factory=module->getFactory();
    factory.setHostContext(&host);
    int classes=0;
    for(const auto& info:factory.classInfos()) {
        if(info.category()!=kVstAudioEffectClass)continue;
        ++classes;
        if(classes>1)continue;
        auto makeInstance=[&]() {
            auto component=factory.createInstance<IComponent>(info.ID());
            require(bool(component),"createInstance failed");
            require(component->initialize(&host)==kResultOk,"initialize failed");
            IAudioProcessor* processor=nullptr;
            require(component->queryInterface(IAudioProcessor::iid,
                reinterpret_cast<void**>(&processor))==kResultOk && processor,
                "IComponent has no audio processor");
            require(component->getBusCount(kEvent,kInput)>=1,"MIDI/event input unavailable");
            require(component->getBusCount(kAudio,kOutput)==1,"one output bus required by adapter");
            BusInfo audio{};
            require(component->getBusInfo(kAudio,kOutput,0,audio)==kResultOk &&
                    audio.channelCount==2,"stereo output required by adapter");
            configure(component.get(),processor);
            return std::pair{std::move(component),processor};
        };
        auto [component,processor]=makeInstance();
        std::atomic<int> audioCalls{0},audioFailures{0}, liveSaves{0};
        std::atomic<bool> notesReady{false}, start{false}, running{true};
        std::atomic<float> latest{-1.f};
        std::array<Sample32,64> left{},right{};
        Sample32* channelData[]{left.data(),right.data()};
        AudioBusBuffers output{};output.numChannels=2;output.channelBuffers32=channelData;
        ProcessContext context{};
        context.sampleRate=48000.;context.tempo=120.;
        context.timeSigNumerator=4;context.timeSigDenominator=4;
        context.state=ProcessContext::kPlaying|ProcessContext::kTempoValid|
            ProcessContext::kTimeSigValid|ProcessContext::kProjectTimeMusicValid;
        EventList notes(64);
        for(int n=0;n<voices;++n) {
            Event e{};e.type=Event::kNoteOnEvent;e.busIndex=0;e.sampleOffset=0;
            e.noteOn.channel=0;e.noteOn.pitch=static_cast<int16>(48+n);
            e.noteOn.velocity=.75f;e.noteOn.noteId=n;
            require(notes.addEvent(e)==kResultOk,"cannot create real VST3 MIDI event");
        }
        ProcessData data{};
        data.processMode=kRealtime;data.symbolicSampleSize=kSample32;
        data.numSamples=64;data.numInputs=0;data.numOutputs=1;
        data.outputs=&output;data.inputEvents=&notes;data.processContext=&context;
        require(component->setActive(true)==kResultOk,"setActive failed");
        require(processor->setProcessing(true)==kResultOk,"setProcessing failed");
        std::thread audio([&] {
            while(!start.load(std::memory_order_acquire))std::this_thread::yield();
            for(int i=0;i<2500;++i) {
                data.inputEvents=(i==0?static_cast<IEventList*>(&notes):nullptr);
                context.projectTimeSamples=static_cast<int64>(i)*64;
                context.projectTimeMusic=double(context.projectTimeSamples)/(48000.*.5);
                if(processor->process(data)!=kResultOk)audioFailures++;
                for(int n=0;n<64;++n) {
                    if(!std::isfinite(left[size_t(n)])||!std::isfinite(right[size_t(n)]))
                        audioFailures++;
                }
                latest.store(left[0],std::memory_order_release);
                audioCalls++;
                if(i==0)notesReady.store(true,std::memory_order_release);
                hostPace(150);
            }
            running.store(false,std::memory_order_release);
        });
        start.store(true,std::memory_order_release);
        while(!notesReady.load(std::memory_order_acquire))std::this_thread::yield();
        int success=0,failed=0,invalidPayload=0;
        for(int i=0;i<500;++i) {
            if(running.load(std::memory_order_acquire))liveSaves++;
            ResizableMemoryIBStream saved;
            if(!writeState(component.get(),saved)) {
                ++failed;
            } else {
                ++success;
                if(saved.getCursor()!=12)++invalidPayload;
            }
            hostPace(80);
        }
        audio.join();
        require(processor->setProcessing(false)==kResultOk,"stop processing failed");
        require(component->setActive(false)==kResultOk,"deactivate failed");
        ResizableMemoryIBStream stableState;
        require(writeState(component.get(),stableState),"post-playback getState failed");
        const auto stateSize=stableState.getCursor();
        require(stateSize>0&&stateSize<1024*1024,"unreasonable state size");
        std::vector<char> state(size_t(stateSize));
        std::memcpy(state.data(),stableState.getData(),state.size());
        const float priorAudio=latest.load();
        processor->release();
        require(component->terminate()==kResultOk,"terminate old instance failed");
        component=nullptr;
        // Recall via a fresh IComponent and IAudioProcessor instance.
        auto [reopened,again]=makeInstance();
        ResizableMemoryIBStream input;
        int32 written=0;
        require(input.write(state.data(),static_cast<int32>(state.size()),&written)==kResultOk &&
                written==static_cast<int32>(state.size()),"cannot prepare recall stream");
        input.rewind();
        require(reopened->setState(&input)==kResultOk,"fresh-instance setState failed");
        require(reopened->setActive(true)==kResultOk,"reactivate after restore failed");
        require(again->setProcessing(true)==kResultOk,"process after restore failed");
        notes.clear();
        data.inputEvents=nullptr;
        left.fill(0.f);right.fill(0.f);
        require(again->process(data)==kResultOk,"render after fresh-instance recall failed");
        const float recoveredAudio=left[0];
        require(again->setProcessing(false)==kResultOk,"stop recalled processing failed");
        require(reopened->setActive(false)==kResultOk,"deactivate recalled instance failed");
        again->release();
        require(reopened->terminate()==kResultOk,"terminate recalled instance failed");
        if(!out.parent_path().empty())std::filesystem::create_directories(out.parent_path());
        std::ofstream file(out,std::ios::trunc);
        require(bool(file),"cannot open oracle evidence");
        file<<"schema\t125A-P29-v1\n"
            <<"plugin\t"<<plugin<<"\n"
            <<"voices_requested\t"<<voices<<"\n"
            <<"max_voices_adapter\t32\n"
            <<"audio_calls\t"<<audioCalls.load()<<"\n"
            <<"audio_failures\t"<<audioFailures.load()<<"\n"
            <<"saves_while_playing\t"<<liveSaves.load()<<"\n"
            <<"save_attempts\t500\n"
            <<"save_success\t"<<success<<"\n"
            <<"save_failures\t"<<failed<<"\n"
            <<"invalid_state_payloads\t"<<invalidPayload<<"\n"
            <<"pre_recall_amplitude\t"<<priorAudio<<"\n"
            <<"after_fresh_recall_amplitude\t"<<recoveredAudio<<"\n"
            <<"state_bytes\t"<<stateSize<<"\n";
        require(file.good(),"cannot flush voice oracle evidence");
        std::cout<<"[PASS] P29 real VST3 MIDI and 500-save scenario recorded; "
                 <<"independent voice/state/audio oracle required\n";
        return 0;
    }
    require(classes>0,"VST3 contains no audio component");
    return 3;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=5||std::string(argv[1])!="--voices") {
            std::cerr<<"Usage: --voices <plugin.vst3> <evidence.tsv> <0|1|8|32>\n";
            return 2;
        }
        return run(argv[2],argv[3],std::stoi(argv[4]));
    }catch(const std::exception& e){
        std::cerr<<"[FAIL] P29 VST3 voice host: "<<e.what()<<"\n";
        return 1;
    }
}
