// P02 deterministic fixtures: deliberately minimal plugins for validating the test host.
// Good: 16 exact stereo pulses, each 128 samples at 0.25 amplitude, driven ONLY
// by incoming sample-accurate MIDI NoteOn events. Bad: inject a NaN on first block.
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include <algorithm>
#include <cmath>
#include <limits>

using namespace Steinberg;
using namespace Steinberg::Vst;

#ifndef QA_DELIBERATE_NAN
#define QA_DELIBERATE_NAN 0
#endif

namespace {
#if QA_DELIBERATE_NAN
const FUID kProcessorUID(0x125A3022, 0x20261104, 0x00000002, 0x00000002);
constexpr const char* kName = "125A QA Signal Bad NaN";
#else
const FUID kProcessorUID(0x125A3021, 0x20261104, 0x00000001, 0x00000001);
constexpr const char* kName = "125A QA Signal Good";
#endif

class QAProcessor : public AudioEffect {
public:
    static FUnknown* createInstance(void*) {
        return static_cast<IAudioProcessor*>(new QAProcessor());
    }

    tresult PLUGIN_API initialize(FUnknown* context) override {
        const auto result = AudioEffect::initialize(context);
        if (result != kResultOk) return result;
        addAudioOutput(STR16("Stereo Out"), SpeakerArr::kStereo);
        addEventInput(STR16("MIDI In"), 1);
        return kResultOk;
    }

    tresult PLUGIN_API setActive(TBool state) override {
        if (state) {
            framesProcessed_ = 0;
            remainingPulseSamples_ = 0;
        }
        return AudioEffect::setActive(state);
    }

    tresult PLUGIN_API process(ProcessData& data) override {
        if (data.symbolicSampleSize != kSample32 || data.numSamples < 1 ||
            data.numSamples > 512 || data.numOutputs < 1 || !data.outputs ||
            !data.outputs[0].channelBuffers32 || data.outputs[0].numChannels != 2 ||
            !data.processContext || !data.inputEvents)
            return kResultFalse;

        const auto& context = *data.processContext;
        constexpr uint32 flags = ProcessContext::kPlaying | ProcessContext::kTempoValid |
            ProcessContext::kTimeSigValid | ProcessContext::kProjectTimeMusicValid;
        if ((context.state & flags) != flags ||
            context.projectTimeSamples != framesProcessed_ ||
            std::abs(context.sampleRate - 44100.) > 0.01 ||
            std::abs(context.tempo - 120.) > 0.01 ||
            context.timeSigNumerator != 4 || context.timeSigDenominator != 4 ||
            std::abs(context.projectTimeMusic -
                     double(framesProcessed_) / 22050.) > 1.0e-7)
            return kResultFalse;

        auto* left = data.outputs[0].channelBuffers32[0];
        auto* right = data.outputs[0].channelBuffers32[1];
        if (!left || !right) return kResultFalse;
        auto& events = *data.inputEvents;
        const int32 count = events.getEventCount();
        int32 lastOffset = -1;
        for (int32 i = 0; i < count; ++i) {
            Event event{};
            if (events.getEvent(i, event) != kResultOk ||
                event.sampleOffset < 0 || event.sampleOffset >= data.numSamples ||
                event.sampleOffset < lastOffset)
                return kResultFalse;
            lastOffset = event.sampleOffset;
        }

        int32 eventIndex = 0;
        for (int32 n = 0; n < data.numSamples; ++n) {
            while (eventIndex < count) {
                Event event{};
                if (events.getEvent(eventIndex, event) != kResultOk)
                    return kResultFalse;
                if (event.sampleOffset != n) break;
                if (event.type == Event::kNoteOnEvent) {
                    if (event.noteOn.pitch != 36 || event.noteOn.channel != 0 ||
                        std::abs(event.noteOn.velocity - 0.8f) > 1.e-5f)
                        return kResultFalse;
                    remainingPulseSamples_ = 128;
                } else if (event.type != Event::kNoteOffEvent) {
                    return kResultFalse;
                }
                ++eventIndex;
            }

            const Sample32 value = remainingPulseSamples_ > 0 ? 0.25f : 0.f;
            if (remainingPulseSamples_ > 0) --remainingPulseSamples_;
            left[n] = value;
            right[n] = value;
        }
#if QA_DELIBERATE_NAN
        if (framesProcessed_ == 0)
            left[0] = std::numeric_limits<Sample32>::quiet_NaN();
#endif
        data.outputs[0].silenceFlags = 0;
        framesProcessed_ += data.numSamples;
        return kResultOk;
    }
private:
    int64 framesProcessed_ = 0;
    int32 remainingPulseSamples_ = 0;
};
} // namespace

BEGIN_FACTORY_DEF("125A Internal Test Infrastructure",
                  "https://github.com/challanger2000",
                  "qa@125a.invalid")

DEF_CLASS2(INLINE_UID_FROM_FUID(kProcessorUID),
           PClassInfo::kManyInstances,
           kVstAudioEffectClass,
           kName,
           Vst::kDistributable,
           "Instrument",
           "0.1.0",
           kVstVersionString,
           QAProcessor::createInstance)

END_FACTORY
