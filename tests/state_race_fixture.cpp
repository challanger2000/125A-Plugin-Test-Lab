// P25/P26 independently specified VST3 state/RT fixtures.
// No production-plugin code. GOOD uses one atomic transaction. BROKEN uses
// independently published related fields or arbitrarily refuses playback saves.
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "pluginterfaces/base/ibstream.h"
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <thread>
using namespace Steinberg;
using namespace Steinberg::Vst;
#ifndef QA_STATE_MODE
#define QA_STATE_MODE 0
#endif
namespace {
const FUID uid(0x125A3525,0x20261105,0x00002500 + QA_STATE_MODE,0xA5000000 + QA_STATE_MODE);
constexpr int32 kA=11, kB=22, kC=33, kD=44;
struct State {uint32 magic; int32 bank; int32 program; uint32 check;};
constexpr uint32 magic=0x125A2526;
#if QA_STATE_MODE==8
// Deliberate multi-instance defect: shared state among independent instances.
std::atomic<uint64> globalPair{(uint64(kA)<<32)|uint32(kB)};
#endif
void badFixtureWindow() {
    // Deliberately incorrect realtime writer publishes two fields apart.
    // High-resolution delay avoids the 1-16 ms Windows Sleep quantum.
    const auto until=std::chrono::steady_clock::now()+std::chrono::microseconds(20);
    while(std::chrono::steady_clock::now()<until)
        std::atomic_signal_fence(std::memory_order_seq_cst);
}

State pack(int32 bank,int32 program) {
    return {magic,bank,program,magic ^ uint32(bank) ^ (uint32(program)<<8)};
}
bool valid(State s) {
    return s.magic==magic && s.check==(magic ^ uint32(s.bank) ^ (uint32(s.program)<<8)) &&
        ((s.bank==kA && s.program==kB)||(s.bank==kC && s.program==kD));
}
class Fixture final : public AudioEffect {
public:
    static FUnknown* createInstance(void*) {return static_cast<IAudioProcessor*>(new Fixture);}
    tresult PLUGIN_API initialize(FUnknown* c) override {
        if (AudioEffect::initialize(c)!=kResultOk) return kResultFalse;
#if QA_STATE_MODE==10
        // Real audio-in/audio-out insert: the independent P25 host must
        // supply a stereo input bus or this fixture rejects process().
        addAudioInput(STR16("Stereo In"),SpeakerArr::kStereo);
#endif
        addAudioOutput(STR16("Stereo Out"),SpeakerArr::kStereo);
        return kResultOk;
    }
    tresult PLUGIN_API setupProcessing(ProcessSetup& setup) override {
        rate_=setup.sampleRate;
        if (rate_<40000.||rate_>192000.) return kResultFalse;
        return AudioEffect::setupProcessing(setup);
    }
    tresult PLUGIN_API setActive(TBool active) override {
        if (active) {samples_=0; blocks_=0;}
        active_.store(active!=0,std::memory_order_release);
        return AudioEffect::setActive(active);
    }
    tresult PLUGIN_API setProcessing(TBool) override {return kResultOk;}
    tresult PLUGIN_API setState(IBStream* stream) override {
        if (!stream) return kInvalidArgument;
#if QA_STATE_MODE==9
        // Deliberate real state-replay defect: valid project-state loads
        // are rejected once playback has started.
        if(active_.load(std::memory_order_acquire)) return kResultFalse;
#endif
        State s{}; int32 n=0;
        if (stream->read(&s,sizeof(s),&n)!=kResultOk||n!=sizeof(s)||!valid(s)) {
#if QA_STATE_MODE==5
            // Defect: report rejection but change the previously valid state.
            pair_.store((uint64(uint32(kC))<<32)|uint32(kD),std::memory_order_release);
#endif
            return kResultFalse;
        }
#if QA_STATE_MODE==8
        globalPair.store((uint64(uint32(s.bank))<<32)|uint32(s.program),std::memory_order_release);
#elif QA_STATE_MODE==1
        bank_.store(s.bank,std::memory_order_relaxed);
        badFixtureWindow();
        program_.store(s.program,std::memory_order_relaxed);
#else
        pair_.store((uint64(uint32(s.bank))<<32)|uint32(s.program),std::memory_order_release);
#endif
        return kResultOk;
    }
    tresult PLUGIN_API getState(IBStream* stream) override {
        if (!stream) return kInvalidArgument;
#if QA_STATE_MODE==2
        if (active_.load(std::memory_order_acquire) &&
            (++saves_ % 5)==0) return kResultFalse;
#endif
        int32 b,p;
#if QA_STATE_MODE==8
        const auto pair=globalPair.load(std::memory_order_acquire);
        b=int32(pair>>32);p=int32(uint32(pair));
#elif QA_STATE_MODE==1
        b=bank_.load(std::memory_order_relaxed);
        std::this_thread::yield();
        p=program_.load(std::memory_order_relaxed);
#else
        const auto pair=pair_.load(std::memory_order_acquire);
        b=int32(pair>>32);p=int32(uint32(pair));
#endif
        const State s=pack(b,p);
        int32 n=0;
        return stream->write(const_cast<State*>(&s),sizeof(s),&n)==kResultOk &&
            n==sizeof(s) ? kResultOk : kResultFalse;
    }
    tresult PLUGIN_API process(ProcessData& d) override {
        if (d.symbolicSampleSize!=kSample32||d.numSamples<0||d.numSamples>2048||
            d.numOutputs!=1||!d.outputs||d.outputs[0].numChannels!=2||
            !d.outputs[0].channelBuffers32) return kResultFalse;
#if QA_STATE_MODE==10
        if (d.numInputs!=1||!d.inputs||d.inputs[0].numChannels!=2||
            !d.inputs[0].channelBuffers32||!d.inputs[0].channelBuffers32[0]||
            !d.inputs[0].channelBuffers32[1]) return kResultFalse;
#endif
#if QA_STATE_MODE==7
        // Deliberately invalid realtime behavior: sleeps inside process().
        // Periodic delay stays over a 512-frame 44.1-kHz deadline while
        // keeping this negative CI case bounded in total runtime.
        if(d.numSamples>0 && (++slowBlocks_ % 128)==0)
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
#endif
        // Deliberate concurrent WRITE from the audio callback, not just READ.
#if QA_STATE_MODE!=4 && QA_STATE_MODE!=5 && QA_STATE_MODE!=8
        if ((++blocks_ & 3)==0) {
            const bool alternate=(blocks_ & 4)!=0;
            const int32 bank=alternate?kC:kA, program=alternate?kD:kB;
#if QA_STATE_MODE==1
            bank_.store(bank,std::memory_order_relaxed);
            std::this_thread::yield();
            program_.store(program,std::memory_order_relaxed);
#else
            pair_.store((uint64(uint32(bank))<<32)|uint32(program),std::memory_order_release);
#endif
        }
#endif
        auto* left=d.outputs[0].channelBuffers32[0];
        auto* right=d.outputs[0].channelBuffers32[1];
        if (!left||!right) return kResultFalse;
        const double denominator = 0.1 *
#if QA_STATE_MODE==3
            44100.0;
#else
            rate_;
#endif
#if QA_STATE_MODE==10
        // Non-silent, channel-identified audio oracle independent of state:
        // a valid stereo insert MUST be given both real input buffers.
        const auto* sourceL=d.inputs[0].channelBuffers32[0];
        const auto* sourceR=d.inputs[0].channelBuffers32[1];
        for(int i=0;i<d.numSamples;++i) {
            // Independent physical-signal bounds, deliberately NOT
            // copied from the host's exact excitation equation.
            // Detect zeroed, swapped, crosswired, nonfinite or fully
            // disconnected inputs even if the host supplied two valid
            // pointers. A pointer-only assertion is not audio evidence.
            const auto l=sourceL[i],r=sourceR[i];
            if(!std::isfinite(l)||!std::isfinite(r)||
               l<0.105f||l>0.155f||r<-.12f||r>-.06f)
                return kResultFalse;
            left[i]=0.7f*l;
            right[i]=0.4f*r;
            ++samples_;
        }
#else
        for(int i=0;i<d.numSamples;++i) {
#if QA_STATE_MODE==6
            // Broken DSP: advances envelope by one fixed amount per host
            // callback, not per sample. Zero-frame callbacks also perturb it.
            const Sample32 v=Sample32(0.25 * std::min(1.0,
                double(blocks_ * 64) / (0.1 * rate_)));
            ++samples_;
#elif QA_STATE_MODE==4 || QA_STATE_MODE==5 || QA_STATE_MODE==8
#if QA_STATE_MODE==8
            const auto pair=globalPair.load(std::memory_order_acquire);
#else
            const auto pair=pair_.load(std::memory_order_acquire);
#endif
            const auto bank=int32(pair>>32);
            const auto program=int32(uint32(pair));
            const Sample32 v=bank==kA && program==kB ? 0.25f :
                             bank==kC && program==kD ? 0.125f : 0.f;
            ++samples_;
#else
            const auto v=Sample32(0.25*std::min(1.,double(samples_++)/denominator));
#endif
            left[i]=v;right[i]=v;
        }
#endif
        d.outputs[0].silenceFlags=0;
        return kResultOk;
    }
private:
    std::atomic<uint64> pair_{(uint64(kA)<<32)|uint32(kB)};
    std::atomic<int32> bank_{kA}, program_{kB};
    std::atomic<bool> active_{false};
    std::atomic<int> saves_{0};
    double rate_=44100.;
    int64 samples_=0;
    uint64 blocks_=0;
    uint64 slowBlocks_=0;
};
#if QA_STATE_MODE==0
constexpr const char* name="125A QA Concurrency Good";
#elif QA_STATE_MODE==1
constexpr const char* name="125A QA Concurrency Torn State";
#elif QA_STATE_MODE==2
constexpr const char* name="125A QA Concurrency Save Refusal";
#elif QA_STATE_MODE==3
constexpr const char* name="125A QA Concurrency Wrong Rate";
#elif QA_STATE_MODE==4
constexpr const char* name="125A QA Recovery Good";
#elif QA_STATE_MODE==5
constexpr const char* name="125A QA Recovery Broken Rollback";
#elif QA_STATE_MODE==6
constexpr const char* name="125A QA Wrong Host Block Partition";
#elif QA_STATE_MODE==7
constexpr const char* name="125A QA Blocking Audio Callback";
#elif QA_STATE_MODE==8
constexpr const char* name="125A QA Broken Multi Instance Global State";
#elif QA_STATE_MODE==9
constexpr const char* name="125A QA Broken Live State Replay Rejection";
#elif QA_STATE_MODE==10
constexpr const char* name="125A QA P98 Stereo Audio Effect";
#endif
}
BEGIN_FACTORY_DEF("125A Universal QA","https://github.com/challanger2000","qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(uid),PClassInfo::kManyInstances,
           kVstAudioEffectClass,name,Vst::kDistributable,"Fx","0.1",kVstVersionString,
           Fixture::createInstance)
END_FACTORY
