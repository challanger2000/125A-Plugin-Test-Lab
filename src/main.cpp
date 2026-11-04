#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/eventlist.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/vsttypes.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;

namespace {
constexpr int kSampleRate = 44100;
constexpr int kBlockSize = 512;
constexpr int kBpm = 120;
constexpr int kBars = 4;
constexpr int kBeatsPerBar = 4;
constexpr int kFramesPerBeat = kSampleRate * 60 / kBpm;
constexpr int kTotalFrames = kFramesPerBeat * kBeatsPerBar * kBars;
constexpr double kPi = 3.14159265358979323846;

void require(bool okay, const char* message) {
    if (!okay) throw std::runtime_error(message);
}

double ppqAt(int64 frame) {
    return static_cast<double>(frame) * static_cast<double>(kBpm) /
           (60.0 * static_cast<double>(kSampleRate));
}

int selfTest() {
    require(kFramesPerBeat == 22050, "120 BPM quarter-note duration incorrect");
    require(kTotalFrames == 352800, "four-bar rendering length incorrect");
    require(std::abs(ppqAt(22050) - 1.0) < 1.e-12, "PPQ conversion incorrect");
    require(std::abs(ppqAt(kTotalFrames) - 16.0) < 1.e-12, "PPQ endpoint incorrect");
    for (int beat = 0; beat < 16; ++beat)
        require(ppqAt(int64(beat) * kFramesPerBeat) == beat, "beat alignment incorrect");
    std::cout << "[PASS] Transport reference: 44.1 kHz, 120 BPM, 4/4, 4 bars, "
              << kTotalFrames << " frames\n";
    return 0;
}

struct Bus {
    std::vector<std::vector<Sample32>> samples;
    std::vector<Sample32*> pointers;
    AudioBusBuffers buffers{};
};

std::vector<Bus> createBuses(IComponent* component, BusDirection direction) {
    const int32 count = component->getBusCount(kAudio, direction);
    require(count >= 0 && count <= 64, "invalid audio bus count");
    std::vector<Bus> buses(static_cast<size_t>(count));
    for (int32 i = 0; i < count; ++i) {
        BusInfo info{};
        require(component->getBusInfo(kAudio, direction, i, info) == kResultOk,
                "getBusInfo(audio) failed");
        require(info.channelCount >= 0 && info.channelCount <= 64, "invalid channel count");
        if ((info.flags & BusInfo::kDefaultActive) != 0)
            (void)component->activateBus(kAudio, direction, i, true);
        auto& bus = buses[static_cast<size_t>(i)];
        bus.samples.resize(static_cast<size_t>(info.channelCount));
        bus.pointers.resize(bus.samples.size());
        for (size_t ch = 0; ch < bus.samples.size(); ++ch) {
            bus.samples[ch].assign(kBlockSize, 0.f);
            bus.pointers[ch] = bus.samples[ch].data();
        }
        bus.buffers.numChannels = info.channelCount;
        bus.buffers.silenceFlags = 0;
        bus.buffers.channelBuffers32 = bus.pointers.empty() ? nullptr : bus.pointers.data();
    }
    return buses;
}

std::vector<AudioBusBuffers> descriptors(const std::vector<Bus>& buses) {
    std::vector<AudioBusBuffers> result;
    result.reserve(buses.size());
    for (const auto& bus : buses) result.push_back(bus.buffers);
    return result;
}

void writeU16(std::ofstream& out, uint16_t value) {
    const std::array<char, 2> bytes{
        static_cast<char>(value & 0xff), static_cast<char>((value >> 8) & 0xff)};
    out.write(bytes.data(), bytes.size());
}
void writeU32(std::ofstream& out, uint32_t value) {
    const std::array<char, 4> bytes{
        static_cast<char>(value & 0xff), static_cast<char>((value >> 8) & 0xff),
        static_cast<char>((value >> 16) & 0xff), static_cast<char>((value >> 24) & 0xff)};
    out.write(bytes.data(), bytes.size());
}

void writeWave(const std::filesystem::path& path, const std::vector<int32_t>& stereo) {
    const auto byteCount = stereo.size() * 3ULL;
    require(byteCount <= std::numeric_limits<uint32_t>::max() - 36ULL, "WAV exceeds RIFF limits");
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    require(out.good(), "cannot create WAV output");
    out.write("RIFF", 4);
    writeU32(out, static_cast<uint32_t>(36ULL + byteCount));
    out.write("WAVEfmt ", 8);
    writeU32(out, 16);
    writeU16(out, 1);  // PCM integer
    writeU16(out, 2);  // stereo
    writeU32(out, kSampleRate);
    writeU32(out, kSampleRate * 2 * 3);
    writeU16(out, 6);
    writeU16(out, 24);
    out.write("data", 4);
    writeU32(out, static_cast<uint32_t>(byteCount));
    for (const auto sample : stereo) {
        const auto v = static_cast<uint32_t>(sample) & 0x00ffffffU;
        const std::array<char, 3> bytes{
            static_cast<char>(v & 0xff), static_cast<char>((v >> 8) & 0xff),
            static_cast<char>((v >> 16) & 0xff)};
        out.write(bytes.data(), bytes.size());
    }
    require(out.good(), "WAV write failure");
}

int32_t pcm24(Sample32 input) {
    const auto clamped = std::clamp(static_cast<double>(input), -1.0, 1.0);
    return static_cast<int32_t>(std::llround(clamped * 8388607.0));
}

int render(const std::string& pluginPath, const std::filesystem::path& wavePath,
           const std::filesystem::path& statePath = {}) {
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(static_cast<bool>(module), ("Cannot load VST3 module: " + error).c_str());

    HostApplication host;
    auto factory = module->getFactory();
    factory.setHostContext(&host);
    int classCount = 0;

    for (const auto& classInfo : factory.classInfos()) {
        if (classInfo.category() != kVstAudioEffectClass) continue;
        ++classCount;
        // P01 intentionally renders one audio class. Multiclass selection is a later milestone.
        auto component = factory.createInstance<IComponent>(classInfo.ID());
        require(static_cast<bool>(component), "cannot instantiate IComponent");
        require(component->initialize(&host) == kResultOk, "IComponent::initialize failed");

        IAudioProcessor* processor = nullptr;
        if (component->queryInterface(IAudioProcessor::iid,
                                      reinterpret_cast<void**>(&processor)) != kResultOk || !processor) {
            component->terminate();
            throw std::runtime_error("IAudioProcessor unavailable");
        }

        bool active = false;
        bool processing = false;
        try {
            require(processor->canProcessSampleSize(kSample32) == kResultTrue,
                    "plugin does not support 32-bit floating point audio");

            auto inputs = createBuses(component.get(), kInput);
            auto outputs = createBuses(component.get(), kOutput);
            require(!outputs.empty() && !outputs.front().samples.empty(),
                    "plugin has no renderable audio output");
            const auto eventBusCount = component->getBusCount(kEvent, kInput);
            for (int32 i = 0; i < eventBusCount; ++i) {
                BusInfo info{};
                if (component->getBusInfo(kEvent, kInput, i, info) == kResultTrue &&
                    (info.flags & BusInfo::kDefaultActive) != 0)
                    (void)component->activateBus(kEvent, kInput, i, true);
            }

            ProcessSetup setup{};
            setup.processMode = kRealtime;
            setup.symbolicSampleSize = kSample32;
            setup.maxSamplesPerBlock = kBlockSize;
            setup.sampleRate = kSampleRate;
            require(processor->setupProcessing(setup) == kResultOk, "setupProcessing failed");
            // P03: load a deterministic drum kit as a real host-project state.
            // The processor receives the complete VST3 IBStream contract;
            // no private Drumator classes are linked into the test host.
            if (!statePath.empty()) {
                std::ifstream stateFile(statePath, std::ios::binary | std::ios::ate);
                require(stateFile.good(), "Cannot open state fixture file");
                const auto length = stateFile.tellg();
                require(length > 0 && length < 16 * 1024 * 1024,
                        "Invalid state fixture size");
                std::vector<char> bytes(static_cast<size_t>(length));
                stateFile.seekg(0);
                stateFile.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
                require(stateFile.good(), "Cannot read complete state fixture");
                ResizableMemoryIBStream stream(bytes.size());
                int32 written = 0;
                require(stream.write(bytes.data(), static_cast<int32>(bytes.size()),
                                     &written) == kResultOk &&
                        written == static_cast<int32>(bytes.size()),
                        "Cannot create state IBStream");
                stream.rewind();
                require(component->setState(&stream) == kResultOk,
                        "Plugin rejected supplied VST3 project state");
                std::cout << "[PASS] Host project state loaded: " << bytes.size()
                          << " bytes\n";
            }
            require(component->setActive(true) == kResultOk, "setActive(true) failed");
            active = true;
            require(processor->setProcessing(true) == kResultOk, "setProcessing(true) failed");
            processing = true;

            std::vector<int32_t> interleaved;
            interleaved.reserve(static_cast<size_t>(kTotalFrames) * 2U);
            double peak = 0.0;
            int64_t emittedEvents = 0;

            for (int start = 0; start < kTotalFrames; start += kBlockSize) {
                const int frames = std::min(kBlockSize, kTotalFrames - start);
                auto inputBuffers = descriptors(inputs);
                auto outputBuffers = descriptors(outputs);
                for (auto& bus : outputs)
                    for (auto& channel : bus.samples)
                        std::fill(channel.begin(), channel.end(), 0.f);

                EventList events(32);
                if (eventBusCount > 0 && statePath.empty()) {
                    for (int beat = 0; beat < kBeatsPerBar * kBars; ++beat) {
                        const int frame = beat * kFramesPerBeat;
                        const int offFrame = frame + kSampleRate / 10;
                        for (int kind = 0; kind < 2; ++kind) {
                            const int at = kind == 0 ? frame : offFrame;
                            if (at < start || at >= start + frames) continue;
                            Event event{};
                            event.busIndex = 0;
                            event.sampleOffset = at - start;
                            event.ppqPosition = ppqAt(at);
                            event.type = kind == 0 ? Event::kNoteOnEvent : Event::kNoteOffEvent;
                            if (kind == 0) {
                                event.noteOn.channel = 0;
                                event.noteOn.pitch = 36;
                                event.noteOn.velocity = 0.8f;
                                event.noteOn.noteId = beat + 1;
                            } else {
                                event.noteOff.channel = 0;
                                event.noteOff.pitch = 36;
                                event.noteOff.velocity = 0.f;
                                event.noteOff.noteId = beat + 1;
                            }
                            require(events.addEvent(event) == kResultOk, "event buffer insertion failed");
                            ++emittedEvents;
                        }
                    }
                }

                ProcessContext ctx{};
                ctx.state = ProcessContext::kPlaying |
                            ProcessContext::kTempoValid |
                            ProcessContext::kTimeSigValid |
                            ProcessContext::kProjectTimeMusicValid |
                            ProcessContext::kBarPositionValid;
                ctx.sampleRate = kSampleRate;
                ctx.projectTimeSamples = start;
                ctx.projectTimeMusic = ppqAt(start);
                ctx.barPositionMusic = 4.0 * std::floor(ctx.projectTimeMusic / 4.0);
                ctx.tempo = kBpm;
                ctx.timeSigNumerator = kBeatsPerBar;
                ctx.timeSigDenominator = 4;

                ProcessData data{};
                data.processMode = kRealtime;
                data.symbolicSampleSize = kSample32;
                data.numSamples = frames;
                data.numInputs = static_cast<int32>(inputBuffers.size());
                data.numOutputs = static_cast<int32>(outputBuffers.size());
                data.inputs = inputBuffers.empty() ? nullptr : inputBuffers.data();
                data.outputs = outputBuffers.data();
                data.inputEvents = eventBusCount > 0 && statePath.empty() ? &events : nullptr;
                data.processContext = &ctx;
                require(processor->process(data) == kResultOk, "VST3 process() failed");

                const auto& mainBus = outputs.front().samples;
                for (int n = 0; n < frames; ++n) {
                    const float left = mainBus[0][static_cast<size_t>(n)];
                    const float right = mainBus.size() > 1 ?
                        mainBus[1][static_cast<size_t>(n)] : left;
                    require(std::isfinite(left) && std::isfinite(right),
                            "nonfinite audio emitted by plugin");
                    peak = std::max({peak, std::abs(double(left)), std::abs(double(right))});
                    interleaved.push_back(pcm24(left));
                    interleaved.push_back(pcm24(right));
                }
            }

            require(processor->setProcessing(false) == kResultOk, "setProcessing(false) failed");
            processing = false;
            require(component->setActive(false) == kResultOk, "setActive(false) failed");
            active = false;
            writeWave(wavePath, interleaved);
            std::cout << "[PASS] VST3 processing: 4 bars, 120 BPM, 44.1 kHz, PCM24 stereo\n";
            std::cout << "[INFO] MIDI events emitted: " << emittedEvents << "\n";
            std::cout << "[INFO] Rendered peak: " << peak << "\n";
            if (peak < 1.e-6)
                std::cout << "[WARN] Audio is silent; no functional sound assertion is possible\n";
            std::cout << "[PASS] WAV written: " << wavePath.string() << "\n";
        } catch (...) {
            if (processing) (void)processor->setProcessing(false);
            if (active) (void)component->setActive(false);
            processor->release();
            (void)component->terminate();
            throw;
        }
        processor->release();
        require(component->terminate() == kResultOk, "IComponent::terminate failed");
        return 0;
    }

    require(classCount > 0, "no audio effect/instrument class in VST3 module");
    return 1;
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--selftest") return selfTest();
        if (argc == 4 && std::string(argv[1]) == "--render")
            return render(argv[2], std::filesystem::path(argv[3]));
        if (argc == 5 && std::string(argv[1]) == "--render-state")
            return render(argv[2], std::filesystem::path(argv[4]),
                          std::filesystem::path(argv[3]));
        std::cerr << "Usage: 125A_Test_Lab_Host --selftest\n"
                  << "       125A_Test_Lab_Host --render <plugin.vst3> <output.wav>\n"
                  << "       125A_Test_Lab_Host --render-state <plugin.vst3> <state.bin> <output.wav>\n";
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] " << error.what() << '\n';
        return 1;
    }
}
