// P29 self-contained VST3 MIDI instrument fixtures, independent of products.
// QA_VOICE_MODE 0 = correct, 1 = getState refuses normal playback saves,
// QA_VOICE_MODE 2 = silently loses voices above four.
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstevents.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
using namespace Steinberg;
using namespace Steinberg::Vst;
#ifndef QA_VOICE_MODE
#define QA_VOICE_MODE 0
#endif
namespace {
constexpr uint32 kMagic=0x125A2900;
constexpr int kMaxVoices=32;
const FUID classId(0x125A2901,0x20261105,0x00290000+QA_VOICE_MODE,
                   0xABCDEF00+QA_VOICE_MODE);
struct State {
    uint32 magic;
    uint32 voices;
    uint32 checksum;
};
State stateFor(uint32 voices) {return {kMagic,voices,kMagic ^ voices ^ 0x5A5AA5A5u};}
bool valid(const State& s) {return s.magic==kMagic &&
    s.voices<=kMaxVoices && s.checksum==(kMagic ^ s.voices ^ 0x5A5AA5A5u);}
class Instrument final : public AudioEffect {
public:
    static FUnknown* createInstance(void*) {return static_cast<IAudioProcessor*>(new Instrument);}
    tresult PLUGIN_API initialize(FUnknown* context) override {
        if(AudioEffect::initialize(context)!=kResultOk)return kResultFalse;
        addEventInput(STR16("MIDI"),1);
        addAudioOutput(STR16("Stereo"),SpeakerArr::kStereo);
        return kResultOk;
    }
    tresult PLUGIN_API setupProcessing(ProcessSetup& setup) override {
        if(setup.sampleRate<40000||setup.sampleRate>192000)return kResultFalse;
        return AudioEffect::setupProcessing(setup);
    }
    tresult PLUGIN_API setActive(TBool active) override {
        active_.store(active!=0,std::memory_order_release);
        return AudioEffect::setActive(active);
    }
    tresult PLUGIN_API setProcessing(TBool) override {return kResultOk;}
    tresult PLUGIN_API setState(IBStream* stream) override {
        if(!stream)return kInvalidArgument;
        State s{};int32 count=0;
        if(stream->read(&s,sizeof(s),&count)!=kResultOk ||
           count!=sizeof(s) || !valid(s))return kResultFalse;
        voices_.store(s.voices,std::memory_order_release);
        return kResultOk;
    }
    tresult PLUGIN_API getState(IBStream* stream) override {
        if(!stream)return kInvalidArgument;
#if QA_VOICE_MODE==1
        if(active_.load(std::memory_order_acquire) &&
           (++saveAttempts_ % 5)==0)return kResultFalse;
#endif
        const State s=stateFor(voices_.load(std::memory_order_acquire));
        int32 count=0;
        return stream->write(const_cast<State*>(&s),sizeof(s),&count)==kResultOk &&
               count==sizeof(s)?kResultOk:kResultFalse;
    }
    tresult PLUGIN_API process(ProcessData& d) override {
        if(d.symbolicSampleSize!=kSample32 || d.numSamples<0 ||
           d.numOutputs!=1||!d.outputs||d.outputs[0].numChannels!=2||
           !d.outputs[0].channelBuffers32)return kResultFalse;
        if(d.inputEvents) {
            const int32 count=d.inputEvents->getEventCount();
            for(int32 i=0;i<count;++i) {
                Event ev{};
                if(d.inputEvents->getEvent(i,ev)!=kResultOk)return kResultFalse;
                if(ev.type==Event::kNoteOnEvent) {
                    const uint32 before=voices_.load(std::memory_order_relaxed);
#if QA_VOICE_MODE==2
                    if(before<4) voices_.store(before+1,std::memory_order_release);
#else
                    if(before<kMaxVoices) voices_.store(before+1,std::memory_order_release);
#endif
                } else if(ev.type==Event::kNoteOffEvent) {
                    const auto before=voices_.load(std::memory_order_relaxed);
                    if(before>0) voices_.store(before-1,std::memory_order_release);
                }
            }
        }
        const auto voices=voices_.load(std::memory_order_acquire);
        const auto amplitude=Sample32(0.01f*static_cast<float>(voices));
        auto* left=d.outputs[0].channelBuffers32[0];
        auto* right=d.outputs[0].channelBuffers32[1];
        if(!left||!right)return kResultFalse;
        for(int32 i=0;i<d.numSamples;++i) {
            left[i]=amplitude;
            right[i]=amplitude;
        }
        d.outputs[0].silenceFlags=voices?0:3;
        return kResultOk;
    }
private:
    std::atomic<uint32> voices_{0};
    std::atomic<uint32> saveAttempts_{0};
    std::atomic<bool> active_{false};
};
#if QA_VOICE_MODE==0
constexpr const char* name="125A QA Polyphonic Playback Good";
#elif QA_VOICE_MODE==1
constexpr const char* name="125A QA Polyphonic Playback Broken Save";
#else
constexpr const char* name="125A QA Polyphonic Playback Broken Voice Limit";
#endif
}
BEGIN_FACTORY_DEF("125A Universal QA","https://github.com/challanger2000","qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(classId),PClassInfo::kManyInstances,
           kVstAudioEffectClass,name,Vst::kDistributable,"Instrument","0.1",
           kVstVersionString,Instrument::createInstance)
END_FACTORY
