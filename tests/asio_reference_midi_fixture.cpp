// P182: independent single-oscillator MIDI VST3 reference instrument.
// Note 48 ON starts 220Hz stereo sine, OFF silences it. No sound without MIDI.
// Deliberately minimal and independently compiled; not an AWE emulator.
// For same-physical-ASIO-driver A/B startup timing diagnosis ONLY.
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "pluginterfaces/vst/ivstevents.h"
#include <cmath>
#include <algorithm>
#include <cstdint>

using namespace Steinberg;
using namespace Steinberg::Vst;

#ifndef QA_REFERENCE_BROKEN_PROCESSING
#define QA_REFERENCE_BROKEN_PROCESSING 0
#endif

namespace {
#if QA_REFERENCE_BROKEN_PROCESSING
const FUID kProcessorUID(0x125A2026, 0x11070183, 0xA125A183, 0xB125A184);
const FUID kControllerUID(0x125A2026, 0x11070183, 0xA125A185, 0xB125A186);
constexpr const char* kName = "125A QA ASIO Reference MIDI Broken Processing";
#else
const FUID kProcessorUID(0x125A2026, 0x11070182, 0xA125A182, 0xB125A182);
const FUID kControllerUID(0x125A2026, 0x11070182, 0xA125A183, 0xB125A183);
constexpr const char* kName = "125A QA ASIO Reference MIDI Tone";
#endif
constexpr double pi = 3.14159265358979323846;

class MidiTone final : public AudioEffect {
public:
    MidiTone() { setControllerClass(kControllerUID); }
    static FUnknown* createInstance(void*) {
        return static_cast<IAudioProcessor*>(new MidiTone);
    }

    tresult PLUGIN_API initialize(FUnknown* context) override {
        const auto r = AudioEffect::initialize(context);
        if (r != kResultOk) return r;
        addAudioOutput(STR16("Stereo Out"), SpeakerArr::kStereo);
        addEventInput(STR16("MIDI Input"), 1);
        return kResultOk;
    }

    tresult PLUGIN_API setActive(TBool state) override {
        if (state) { gate_ = false; phase_ = 0.0; }
        return AudioEffect::setActive(state);
    }

    // P183: AudioEffect's default setProcessing() is not guaranteed to return
    // kResultOk. The native ASIO host correctly treats non-OK as NO-GO.
    // The instrument has no resources to allocate during this transition.
    tresult PLUGIN_API setProcessing(TBool /*state*/) override {
#if QA_REFERENCE_BROKEN_PROCESSING
        return kResultFalse; // P183 adversarial regression: must fail at start.
#else
        return kResultOk;
#endif
    }

    tresult PLUGIN_API canProcessSampleSize(int32 size) override {
        return size == kSample32 ? kResultTrue : kResultFalse;
    }

    tresult PLUGIN_API process(ProcessData& data) override {
        if (data.numSamples <= 0 || data.symbolicSampleSize != kSample32 ||
            data.numOutputs < 1 || !data.outputs ||
            data.outputs[0].numChannels != 2 ||
            !data.outputs[0].channelBuffers32 ||
            !data.outputs[0].channelBuffers32[0] ||
            !data.outputs[0].channelBuffers32[1]) return kResultFalse;

        const auto rate = processSetup.sampleRate;
        if (!(rate >= 44100.0 && rate <= 192000.0))
            return kResultFalse;
        const double increment = 2.0 * pi * 220.0 / rate;
        auto* left = data.outputs[0].channelBuffers32[0];
        auto* right = data.outputs[0].channelBuffers32[1];
        int32 next = 0;
        const int32 count = data.inputEvents ? data.inputEvents->getEventCount() : 0;
        for (int32 sample = 0; sample < data.numSamples; ++sample) {
            while (next < count) {
                Event evt{};
                if (data.inputEvents->getEvent(next, evt) != kResultOk)
                    return kResultFalse;
                if (evt.sampleOffset > sample) break;
                if (evt.sampleOffset < 0 || evt.sampleOffset >= data.numSamples)
                    return kResultFalse;
                if (evt.type == Event::kNoteOnEvent && evt.noteOn.pitch == 48) {
                    gate_ = evt.noteOn.velocity > 0.0f;
                } else if (evt.type == Event::kNoteOffEvent &&
                           evt.noteOff.pitch == 48) {
                    gate_ = false;
                }
                ++next;
            }
            const Sample32 value = gate_
                ? static_cast<Sample32>(0.05 * std::sin(phase_)) : 0.f;
            left[sample] = value;
            right[sample] = value;
            if (gate_) {
                phase_ += increment;
                if (phase_ >= 2.0 * pi) phase_ -= 2.0 * pi;
            }
        }
        data.outputs[0].silenceFlags = 0;
        return kResultOk;
    }

private:
    bool gate_ = false;
    double phase_ = 0.;
};
class MidiToneController final : public EditController {
public:
    static FUnknown* createInstance(void*) {
        return static_cast<IEditController*>(new MidiToneController);
    }
};
} // namespace

BEGIN_FACTORY_DEF("125A Internal Test Infrastructure",
                  "https://github.com/challanger2000",
                  "qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(kProcessorUID), PClassInfo::kManyInstances,
           kVstAudioEffectClass, kName, Vst::kDistributable,
           "Instrument", "0.1.0", kVstVersionString,
           MidiTone::createInstance)
DEF_CLASS2(INLINE_UID_FROM_FUID(kControllerUID), PClassInfo::kManyInstances,
           kVstComponentControllerClass, "125A QA ASIO Reference MIDI Controller",
           0, "", "0.1.0", kVstVersionString,
           MidiToneController::createInstance)
END_FACTORY
