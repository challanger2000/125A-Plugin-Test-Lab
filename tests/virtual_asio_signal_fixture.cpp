// P95 independent source-built VST3 oracle for virtual ASIO audio loopback.
// Two deliberately different amplitude envelopes and frequencies. No MIDI,
// GUI, external samples, soundcard or DAW dependency.
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include <cmath>
#include <algorithm>
#include <cstdint>
using namespace Steinberg;
using namespace Steinberg::Vst;
namespace {
const FUID processorUID(0x125A2026, 0x20261107, 0x00000095, 0x00000095);
const FUID controllerUID(0x125A2026, 0x20261107, 0x00000095, 0x00000096);
constexpr double pi = 3.14159265358979323846;
constexpr uint32_t patternL = 0x6d4e92b5u;
constexpr uint32_t patternR = 0xb39a4d27u;

class LoopSignal final : public AudioEffect {
public:
    LoopSignal() { setControllerClass(controllerUID); }
    static FUnknown* createInstance(void*) {
        return static_cast<IAudioProcessor*>(new LoopSignal);
    }
    tresult PLUGIN_API initialize(FUnknown* ctx) override {
        if (AudioEffect::initialize(ctx) != kResultOk) return kResultFalse;
        addAudioOutput(STR16("Stereo virtual ASIO return"), SpeakerArr::kStereo);
        return kResultOk;
    }
    tresult PLUGIN_API setActive(TBool state) override {
        if (state) position_ = 0;
        return AudioEffect::setActive(state);
    }
    tresult PLUGIN_API canProcessSampleSize(int32 size) override {
        return size == kSample32 ? kResultTrue : kResultFalse;
    }
    tresult PLUGIN_API process(ProcessData& d) override {
        if (d.numSamples <= 0 || d.symbolicSampleSize != kSample32 ||
            d.numOutputs < 1 || !d.outputs ||
            d.outputs[0].numChannels != 2 ||
            !d.outputs[0].channelBuffers32 ||
            !d.outputs[0].channelBuffers32[0] ||
            !d.outputs[0].channelBuffers32[1])
            return kResultFalse;
        const auto rate = processSetup.sampleRate;
        if (!(rate >= 44100. && rate <= 96000.)) return kResultFalse;
        float* left = d.outputs[0].channelBuffers32[0];
        float* right = d.outputs[0].channelBuffers32[1];
        for (int32 i = 0; i < d.numSamples; ++i) {
            const auto time = static_cast<double>(position_ + i) / rate;
            const auto cellL = static_cast<uint32_t>(time / .061);
            const auto cellR = static_cast<uint32_t>(time / .083);
            const auto bitL = (patternL >> (cellL % 32)) & 1u;
            const auto bitR = (patternR >> (cellR % 32)) & 1u;
            const float envL = bitL ? .040f : 0.f;
            const float envR = bitR ? .055f : 0.f;
            left[i] = envL * static_cast<float>(std::sin(2. * pi * 317. * time));
            right[i] = envR * static_cast<float>(std::sin(2. * pi * 557. * time));
        }
        position_ += static_cast<uint64_t>(d.numSamples);
        d.outputs[0].silenceFlags = 0;
        return kResultOk;
    }
private:
    uint64_t position_ = 0;
};
class LoopController final : public EditController {
public:
    static FUnknown* createInstance(void*) {
        return static_cast<IEditController*>(new LoopController);
    }
};
}
BEGIN_FACTORY_DEF("125A Internal Test Infrastructure",
                  "https://github.com/challanger2000", "qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(processorUID), PClassInfo::kManyInstances,
           kVstAudioEffectClass, "125A QA Virtual ASIO Return",
           Vst::kDistributable, "Instrument", "0.1.0", kVstVersionString,
           LoopSignal::createInstance)
DEF_CLASS2(INLINE_UID_FROM_FUID(controllerUID), PClassInfo::kManyInstances,
           kVstComponentControllerClass, "125A QA Virtual ASIO Controller",
           0, "", "0.1.0", kVstVersionString,
           LoopController::createInstance)
END_FACTORY
