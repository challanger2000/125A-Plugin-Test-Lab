// P58: real Windows ASIO-driver callback to real VST3 process() adapter.
// Steinberg ASIO headers are supplied separately at build time; never vendored.
// No simulation mode is exposed by this executable.
// Hardware proof is strictly bounded, callback-derived, and never a DAW approval.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include <bcrypt.h>
#include "iasiodrv.h"

#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;

namespace {
void ensure(bool valid, const char* reason) {
    if (!valid) throw std::runtime_error(reason);
}
void checkASIO(ASIOError code, const char* reason) {
    ensure(code == ASE_OK || code == ASE_SUCCESS, reason);
}
std::string requireArg(int argc, char** argv, const char* key) {
    for (int i = 1; i + 1 < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
    throw std::runtime_error(std::string("missing ASIO argument: ") + key);
}
int parseInteger(const std::string& value, int min, int max) {
    const auto number = std::stoll(value);
    ensure(number >= min && number <= max &&
           std::to_string(number) == value, "ASIO numeric option out of range");
    return static_cast<int>(number);
}
std::string hashFile(const std::filesystem::path& file) {
    BCRYPT_ALG_HANDLE alg{};
    BCRYPT_HASH_HANDLE hash{};
    auto close = [&] { if (hash) BCryptDestroyHash(hash); if (alg) BCryptCloseAlgorithmProvider(alg, 0); };
    ensure(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0,
           "Cannot open SHA256 provider");
    try {
        ensure(BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0) >= 0,
               "Cannot initialize SHA256");
        std::ifstream source(file, std::ios::binary);
        ensure(source.good(), "Cannot open binary for SHA256");
        std::array<char, 65536> buffer{};
        while (source) {
            source.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
            auto bytes = source.gcount();
            if (bytes > 0) {
                ensure(BCryptHashData(hash, reinterpret_cast<PUCHAR>(buffer.data()),
                                      static_cast<ULONG>(bytes), 0) >= 0,
                       "SHA256 hash update failed");
            }
        }
        ensure(source.eof(), "SHA256 input read failed");
        std::array<unsigned char, 32> result{};
        ensure(BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) >= 0,
               "SHA256 finalization failed");
        std::ostringstream out;
        out << std::hex << std::setfill('0');
        for (auto b : result) out << std::setw(2) << static_cast<unsigned>(b);
        close();
        return out.str();
    } catch (...) { close(); throw; }
}
std::filesystem::path selfPath() {
    std::array<wchar_t, 32768> path{};
    const auto chars = GetModuleFileNameW(nullptr, path.data(),
                                          static_cast<DWORD>(path.size()));
    ensure(chars != 0 && chars < path.size(), "Could not identify the native executor image");
    return std::filesystem::path(std::wstring(path.data(), chars));
}
std::wstring widen(const std::string& value) {
    const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                                         value.data(), static_cast<int>(value.size()),
                                         nullptr, 0);
    ensure(count > 0, "Invalid UTF-8 ASIO driver name or CLSID");
    std::wstring result(static_cast<size_t>(count), L'\0');
    ensure(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS,
                              value.data(), static_cast<int>(value.size()),
                              result.data(), count) == count, "UTF-8 conversion failed");
    return result;
}
void verifyRegisteredDriver(const std::string& name, const std::wstring& clsid) {
    ensure(!name.empty() && name.size() <= 128 &&
           name.find_first_of("\\\r\n/") == std::string::npos,
           "Invalid registered ASIO driver name");
    const auto key = L"SOFTWARE\\ASIO\\" + widen(name);
    std::array<wchar_t, 128> found{};
    DWORD count = static_cast<DWORD>(found.size() * sizeof(wchar_t));
    DWORD type = 0;
    ensure(RegGetValueW(HKEY_LOCAL_MACHINE, key.c_str(), L"CLSID", RRF_RT_REG_SZ,
                        &type, found.data(), &count) == ERROR_SUCCESS,
           "Physical ASIO driver registry key missing");
    ensure(_wcsicmp(found.data(), clsid.c_str()) == 0,
           "Physical ASIO driver CLSID differs from approved Windows registry");
}
std::string escapeJSON(const std::string& value) {
    std::ostringstream out;
    for (const unsigned char c : value) {
        if (c == '\\' || c == '"') {out << '\\' << static_cast<char>(c);}
        else if (c < 32) out << '?';
        else out << static_cast<char>(c);
    }
    return out.str();
}

struct NativeBus {
    std::vector<std::vector<Sample32>> channels;
    std::vector<Sample32*> ptrs;
    AudioBusBuffers api{};
};
struct Processing {
    std::vector<NativeBus> inputs, outputs;
    std::vector<AudioBusBuffers> inputBuses, outputBuses;
    ProcessContext context{};
    ProcessData data{};

    void prepare(IComponent* component, int frames, double rate) {
        auto build = [&](BusDirection direction, std::vector<NativeBus>& buses,
                         std::vector<AudioBusBuffers>& descriptors) {
            const auto count = component->getBusCount(kAudio, direction);
            ensure(count >= 0 && count <= 16, "unsupported VST3 audio bus count");
            buses.resize(static_cast<size_t>(count));
            for (int32 i = 0; i < count; ++i) {
                BusInfo info{};
                ensure(component->getBusInfo(kAudio, direction, i, info) == kResultOk &&
                       info.channelCount >= 0 && info.channelCount <= 16,
                       "unsupported VST3 audio bus");
                (void)component->activateBus(kAudio, direction, i, true);
                auto& bus = buses[static_cast<size_t>(i)];
                bus.channels.resize(static_cast<size_t>(info.channelCount));
                for (auto& channel : bus.channels)
                    channel.assign(static_cast<size_t>(frames), 0.0f);
                bus.ptrs.reserve(bus.channels.size());
                for (auto& channel : bus.channels) bus.ptrs.push_back(channel.data());
                bus.api.numChannels = info.channelCount;
                bus.api.channelBuffers32 = bus.ptrs.empty() ? nullptr : bus.ptrs.data();
                bus.api.silenceFlags = 0;
            }
            descriptors.reserve(buses.size());
            for (auto& bus : buses) descriptors.push_back(bus.api);
        };
        build(kInput, inputs, inputBuses);
        build(kOutput, outputs, outputBuses);
        ensure(!outputs.empty() && outputs[0].channels.size() >= 2,
               "P58 requires a stereo main VST3 output bus");
        context.state = ProcessContext::kPlaying |
                        ProcessContext::kTempoValid |
                        ProcessContext::kTimeSigValid;
        context.sampleRate = rate;
        context.tempo = 120.;
        context.timeSigNumerator = 4;
        context.timeSigDenominator = 4;
        data.processMode = kRealtime;
        data.symbolicSampleSize = kSample32;
        data.numSamples = frames;
        data.numInputs = static_cast<int32>(inputBuses.size());
        data.numOutputs = static_cast<int32>(outputBuses.size());
        data.inputs = inputBuses.empty() ? nullptr : inputBuses.data();
        data.outputs = outputBuses.empty() ? nullptr : outputBuses.data();
        data.processContext = &context;
    }
};

// Actual device formats: reject unsupported layouts rather than writing
// 32-bit words into non-32-bit driver buffers.
int asioBytesPerSample(ASIOSampleType type) {
    switch (type) {
        case ASIOSTFloat32LSB: case ASIOSTInt32LSB:
        case ASIOSTInt32LSB24: return 4;
        case ASIOSTInt24LSB: return 3;
        case ASIOSTInt16LSB: return 2;
        default: return 0;
    }
}
void writeAsioSamples(void* target, ASIOSampleType type, const Sample32* source,
                      int frames, bool& ok, double outputCeiling = 1.) noexcept {
    for (int i = 0; i < frames; ++i) {
        const float raw = source[i];
        if (!std::isfinite(raw)) { ok = false; return; }
        const double value = std::clamp(static_cast<double>(raw), -outputCeiling, outputCeiling);
        switch (type) {
            case ASIOSTFloat32LSB:
                static_cast<float*>(target)[i] = static_cast<float>(value);
                break;
            case ASIOSTInt32LSB:
                static_cast<int32_t*>(target)[i] = static_cast<int32_t>(value * 2147483647.);
                break;
            case ASIOSTInt32LSB24:
                static_cast<int32_t*>(target)[i] = static_cast<int32_t>(value * 8388607.);
                break;
            case ASIOSTInt16LSB:
                static_cast<int16_t*>(target)[i] = static_cast<int16_t>(value * 32767.);
                break;
            case ASIOSTInt24LSB: {
                const auto value24 = static_cast<uint32_t>(
                    static_cast<int32_t>(value * 8388607.));
                auto* bytes = static_cast<unsigned char*>(target) + static_cast<size_t>(i) * 3U;
                bytes[0] = static_cast<unsigned char>(value24 & 255U);
                bytes[1] = static_cast<unsigned char>((value24 >> 8) & 255U);
                bytes[2] = static_cast<unsigned char>((value24 >> 16) & 255U);
                break;
            }
            default: ok = false; return;
        }
    }
}

#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
float readAsioSample(const void* base, ASIOSampleType type, int n, bool& ok) noexcept {
    if (!base || n < 0) { ok = false; return 0.f; }
    switch (type) {
    case ASIOSTFloat32LSB: {
        float v{};
        std::memcpy(&v, static_cast<const unsigned char*>(base) + 4 * n, 4);
        if (!std::isfinite(v)) { ok = false; return 0.f; }
        return v;
    }
    case ASIOSTInt32LSB: {
        int32_t v{};
        std::memcpy(&v, static_cast<const unsigned char*>(base) + 4 * n, 4);
        return static_cast<float>(static_cast<double>(v) / 2147483648.);
    }
    case ASIOSTInt32LSB24: {
        int32_t v{};
        std::memcpy(&v, static_cast<const unsigned char*>(base) + 4 * n, 4);
        return static_cast<float>(static_cast<double>(v) / 8388608.);
    }
    case ASIOSTInt16LSB: {
        int16_t v{};
        std::memcpy(&v, static_cast<const unsigned char*>(base) + 2 * n, 2);
        return static_cast<float>(static_cast<double>(v) / 32768.);
    }
    case ASIOSTInt24LSB: {
        const auto* b = static_cast<const unsigned char*>(base) + 3 * n;
        int32_t raw = static_cast<int32_t>(uint32_t(b[0]) |
                         (uint32_t(b[1]) << 8) | (uint32_t(b[2]) << 16));
        if (raw & 0x800000) raw |= static_cast<int32_t>(0xff000000u);
        return static_cast<float>(static_cast<double>(raw) / 8388608.);
    }
    default: ok = false; return 0.f;
    }
}
#endif

// CI-only sample-format conversion check; cannot produce hardware evidence.
int formatSelfTest() {
    const std::array<float, 3> values{0.0f, 0.5f, -1.0f};
    for (const auto type : {ASIOSTFloat32LSB, ASIOSTInt32LSB,
                            ASIOSTInt32LSB24, ASIOSTInt24LSB, ASIOSTInt16LSB}) {
        std::array<unsigned char, 64> bytes{};
        bytes.fill(0x5a);
        bool ok = true;
        writeAsioSamples(bytes.data(), type, values.data(), 3, ok);
        ensure(ok && bytes[3 * asioBytesPerSample(type)] == 0x5a,
               "ASIO output format conversion overran sample buffer");
        if (type == ASIOSTInt24LSB)
            ensure(bytes[3] == 255 && bytes[4] == 255 && bytes[5] == 63,
                   "ASIO little-endian 24-bit midpoint conversion wrong");
        if (type == ASIOSTInt16LSB)
            ensure(bytes[2] == 255 && bytes[3] == 63,
                   "ASIO little-endian 16-bit midpoint conversion wrong");
        if (type == ASIOSTFloat32LSB) {
            float middle{};
            std::memcpy(&middle, bytes.data() + sizeof(float), sizeof(float));
            ensure(middle == .5f, "ASIO float32 sample conversion wrong");
        }
    }
    std::array<unsigned char, 32> limited{};
    bool limitedOkay = true;
    writeAsioSamples(limited.data(), ASIOSTFloat32LSB,
                     values.data(), 3, limitedOkay, 0.10);
    float capped{};
    std::memcpy(&capped, limited.data() + sizeof(float), sizeof(float));
    ensure(limitedOkay && std::abs(capped - .10f) < 0.000001f,
           "P59 hardware-output safety ceiling ineffective");
    std::array<unsigned char, 32> buffer{};
    const std::array<float, 1> invalid{std::numeric_limits<float>::quiet_NaN()};
    bool good = true;
    writeAsioSamples(buffer.data(), ASIOSTFloat32LSB, invalid.data(), 1, good);
    ensure(!good, "ASIO converter did not reject non-finite PCM");
    std::cout << "[PASS] P58 independent sample-format conversions; ASIO hardware NOT RUN\n";
    return 0;
}

struct Engine {
    IASIO* driver{};
    IAudioProcessor* processor{};
    Processing* processing{};
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
    std::array<ASIOBufferInfo, 4> asioBuffers{};
    std::array<ASIOSampleType, 4> sampleTypes{};
    std::vector<float> loopbackTrace; // preallocated before ASIO callback start
    uint64_t maxRecordedFrames{};
#else
    std::array<ASIOBufferInfo, 2> asioBuffers{};
    std::array<ASIOSampleType, 2> sampleTypes{};
#endif
    int frames{}, rate{};
    std::atomic<uint64_t> asioCallbacks{0};
    std::atomic<uint64_t> processedCallbacks{0};
    std::atomic<uint64_t> deadlineMisses{0};
    std::atomic<uint64_t> xruns{0};
    std::atomic<uint64_t> processFailures{0};
    std::atomic<uint64_t> sampleRateChanges{0};
    uint64_t lastEndNs{};
    uint64_t framePosition{};
    int64_t qpcFrequency{};

    void callback(long index) noexcept {
        asioCallbacks.fetch_add(1, std::memory_order_relaxed);
        const LARGE_INTEGER started = [&]{ LARGE_INTEGER v{}; QueryPerformanceCounter(&v); return v;}();
        const auto budgetNs = static_cast<uint64_t>(
            1'000'000'000.0 * static_cast<double>(frames) / rate);
        const auto startNs = static_cast<uint64_t>(
            started.QuadPart * 1'000'000'000.0 / static_cast<double>(qpcFrequency));
        // A late callback is a host-observed scheduling anomaly, not proof
        // of physical hardware XRUN. Hardware overloads are counted separately.
        if (lastEndNs && startNs > lastEndNs + 2 * budgetNs)
            deadlineMisses.fetch_add(1, std::memory_order_relaxed);
        lastEndNs = startNs;
        bool ok = false;
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
        ok = true;
#endif
        try {
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
            // Input is sampled before output to preserve actual driver timing.
            // Four interleaved floats/frame: emitted L,R then captured L,R.
            if (framePosition + static_cast<uint64_t>(frames) > maxRecordedFrames)
                throw std::runtime_error("P95 trace buffer capacity exhausted");
            for (size_t ch = 0; ch < 2; ++ch) {
                const void* input = asioBuffers[ch + 2].buffers[index];
                if (!input) throw std::runtime_error("P95 ASIO input buffer absent");
                for (int n = 0; n < frames; ++n) {
                    const float v = readAsioSample(input, sampleTypes[ch + 2], n, ok);
                    // readAsioSample sets ok=false on failure; start true.
                    if (!ok) throw std::runtime_error("P95 corrupt ASIO input format");
                    loopbackTrace[static_cast<size_t>((framePosition + n) * 4 + 2 + ch)] = v;
                }
            }
#endif
            auto& p = *processing;
            // Deterministic low-level stimulus for insert effects; each
            // buffer stays preallocated, so this code does not allocate.
            for (auto& bus : p.inputs)
                for (auto& channel : bus.channels)
                    for (int n = 0; n < frames; ++n)
                        channel[static_cast<size_t>(n)] = 0.025f *
                            std::sin(2.0 * 3.14159265358979323846 * 220.0 *
                                     static_cast<double>(framePosition + n) / rate);
            for (auto& bus : p.outputs)
                for (auto& channel : bus.channels)
                    std::fill(channel.begin(), channel.end(), 0.0f);
            p.context.projectTimeSamples = static_cast<int64>(framePosition);
            p.context.projectTimeMusic = static_cast<double>(framePosition) *
                                         120. / (60. * rate);
            ok = processor->process(p.data) == kResultOk;
            if (ok) for (size_t ch = 0; ch < 2; ++ch) {
                auto* target = asioBuffers[ch].buffers[index];
                ensure(target != nullptr, "ASIO output buffer unavailable");
                const auto& samples = p.outputs[0].channels[ch];
                writeAsioSamples(target, sampleTypes[ch],
                                 samples.data(), frames, ok, 0.10); // -20 dBFS safety ceiling
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
                if (ok) for (int n = 0; n < frames; ++n)
                    loopbackTrace[static_cast<size_t>((framePosition + n) * 4 + ch)] =
                        std::clamp(samples[static_cast<size_t>(n)], -0.10f, 0.10f);
#endif
            }
        } catch (...) { ok = false; }
        if (ok) processedCallbacks.fetch_add(1, std::memory_order_relaxed);
        else processFailures.fetch_add(1, std::memory_order_relaxed);
        if (!ok) for (size_t ch = 0; ch < 2; ++ch) {
            if (asioBuffers[ch].buffers[index])
                std::memset(asioBuffers[ch].buffers[index], 0,
                            static_cast<size_t>(frames) *
                            static_cast<size_t>(asioBytesPerSample(sampleTypes[ch])));
        }
        framePosition += static_cast<uint64_t>(frames);
        LARGE_INTEGER done{};
        QueryPerformanceCounter(&done);
        if (done.QuadPart - started.QuadPart >
            static_cast<int64_t>(frames) * qpcFrequency / rate)
            deadlineMisses.fetch_add(1, std::memory_order_relaxed);
    }
};
std::atomic<Engine*> activeEngine{nullptr};

void onBuffer(long index, ASIOBool) {
    Engine* engine = activeEngine.load(std::memory_order_acquire);
    if (engine && index >= 0 && index <= 1) engine->callback(index);
}
void onSampleRate(ASIOSampleRate) {
    if (auto* engine = activeEngine.load(std::memory_order_relaxed))
        engine->sampleRateChanges.fetch_add(1, std::memory_order_relaxed);
}
long onMessage(long selector, long value, void*, double*) {
    if (selector == kAsioSelectorSupported) {
        return value == kAsioEngineVersion || value == kAsioOverload ||
               value == kAsioResetRequest || value == kAsioResyncRequest;
    }
    if (selector == kAsioEngineVersion) return 2;
    if (selector == kAsioOverload || selector == kAsioResyncRequest ||
        selector == kAsioResetRequest) {
        if (auto* engine = activeEngine.load(std::memory_order_relaxed))
            engine->xruns.fetch_add(1, std::memory_order_relaxed);
        return 0;
    }
    return 0;
}
ASIOTime* onTimeInfo(ASIOTime* info, long index, ASIOBool direct) {
    onBuffer(index, direct);
    return info;
}
struct Arguments {
    std::filesystem::path plugin, output;
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
    std::filesystem::path pcm;
#endif
    std::string name, clsid, nonce;
    int rate{}, frames{}, callbacks{};
};
Arguments parse(int argc, char** argv) {
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
    ensure(argc >= 2 && std::strcmp(argv[1], "--virtual-asio-loopback") == 0,
           "P95 only accepts the explicit virtual ASIO loopback command");
#else
    ensure(argc >= 2 && std::strcmp(argv[1], "--physical-asio-probe") == 0,
           "P58 only accepts --physical-asio-probe");
#endif
    Arguments args;
    args.plugin = std::filesystem::u8path(requireArg(argc, argv, "--plugin"));
    args.output = std::filesystem::u8path(requireArg(argc, argv, "--out"));
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
    args.pcm = std::filesystem::u8path(requireArg(argc, argv, "--pcm"));
    ensure(args.pcm != args.output && !args.pcm.empty(),
           "P95 separate native PCM trace required");
#endif
    args.name = requireArg(argc, argv, "--driver-name");
    args.clsid = requireArg(argc, argv, "--driver-clsid");
    args.nonce = requireArg(argc, argv, "--nonce");
    args.rate = parseInteger(requireArg(argc, argv, "--rate"), 44100, 96000);
    args.frames = parseInteger(requireArg(argc, argv, "--frames"), 64, 1024);
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
    args.callbacks = parseInteger(requireArg(argc, argv, "--callbacks"), 200, 1000);
#else
    args.callbacks = parseInteger(requireArg(argc, argv, "--callbacks"), 100, 200000);
#endif
    ensure(args.rate == 44100 || args.rate == 48000 || args.rate == 96000,
           "unsupported ASIO sample rate");
    ensure(args.frames == 64 || args.frames == 128 || args.frames == 256 ||
           args.frames == 512 || args.frames == 1024,
           "unsupported ASIO frames");
    ensure(args.nonce.size() == 48 &&
           std::all_of(args.nonce.begin(), args.nonce.end(), [](char c) {
               return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
           }), "invalid P56 session nonce");
    ensure(std::filesystem::is_regular_file(args.plugin) &&
           args.plugin.extension() == ".vst3", "physical test requires exact .vst3 DLL");
    return args;
}

#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
void writeLoopbackTrace(const Arguments& args, const Engine& engine) {
    ensure(engine.framePosition <= engine.maxRecordedFrames,
           "P95 loopback trace contains more samples than preallocated");
    ensure(engine.framePosition >= static_cast<uint64_t>(args.frames) * 200,
           "P95 not enough actual virtual ASIO samples for independent PCM");
    std::ofstream out(args.pcm, std::ios::binary | std::ios::trunc);
    ensure(out.good(), "P95 cannot create independently analyzable PCM trace");
    const std::array<char,8> magic{'1','2','5','A','L','B','0','1'};
    out.write(magic.data(), magic.size());
    const std::array<uint32_t, 4> header{
        static_cast<uint32_t>(args.rate),
        static_cast<uint32_t>(engine.framePosition),
        static_cast<uint32_t>(args.frames), 4u
    };
    out.write(reinterpret_cast<const char*>(header.data()), sizeof(header));
    const auto values = static_cast<size_t>(engine.framePosition) * 4;
    out.write(reinterpret_cast<const char*>(engine.loopbackTrace.data()),
              static_cast<std::streamsize>(values * sizeof(float)));
    out.flush();
    ensure(out.good(), "P95 complete native ASIO capture trace not written");
}
#endif

void proof(const Arguments& args, const Engine& engine, const std::string& dllHash,
           const std::string& exeHash) {
    // Never write reports on the device audio callback thread.
    std::ofstream out(args.output, std::ios::binary | std::ios::trunc);
    ensure(out.good(), "Cannot write native ASIO evidence");
    out << "{\n"
        << "  \"schema\": \"125a-physical-asio-native-evidence-v1\",\n"
        << "  \"nonce\": \"" << args.nonce << "\",\n"
        << "  \"product_sha256\": \"" << dllHash << "\",\n"
        << "  \"executor_sha256\": \"" << exeHash << "\",\n"
        << "  \"asio_driver_name\": \"" << escapeJSON(args.name) << "\",\n"
        << "  \"asio_driver_clsid\": \"" << escapeJSON(args.clsid) << "\",\n"
        << "  \"sample_rate\": " << args.rate << ",\n"
        << "  \"buffer_frames\": " << args.frames << ",\n"
        << "  \"completed_callbacks\": " << engine.processedCallbacks.load() << ",\n"
        << "  \"asio_callbacks\": " << engine.asioCallbacks.load() << ",\n"
        << "  \"deadline_misses\": " << engine.deadlineMisses.load() << ",\n"
        << "  \"xruns\": " << engine.xruns.load() << ",\n"
        << "  \"process_failures\": " << engine.processFailures.load() + engine.sampleRateChanges.load() << ",\n"
        << "  \"error_code\": 0\n"
        << "}\n";
    out.flush();
    ensure(out.good(), "Native ASIO evidence incomplete");
}

int run(const Arguments& a) {
    const std::string moduleHash = hashFile(a.plugin);
    const std::string executorHash = hashFile(selfPath());
    const auto wideClsid = widen(a.clsid);
    GUID classId{};
    ensure(SUCCEEDED(CLSIDFromString(wideClsid.c_str(), &classId)),
           "Driver CLSID is not a valid COM class ID");
    verifyRegisteredDriver(a.name, wideClsid);
    const HRESULT co = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    ensure(SUCCEEDED(co), "COM apartment cannot initialize for ASIO");
    IASIO* driver = nullptr;
    try {
        // ASIO SDK's Windows host uses the registered CLSID as IID.
        ensure(SUCCEEDED(CoCreateInstance(classId, nullptr, CLSCTX_INPROC_SERVER,
                                           classId, reinterpret_cast<void**>(&driver))) &&
               driver, "Cannot instantiate actual registered physical ASIO driver");
        ensure(driver->init(GetConsoleWindow()) == ASIOTrue,
               "Actual ASIO hardware driver failed initialization");
        long inputCount{}, outputCount{}, minimum{}, maximum{}, preferred{}, granularity{};
        checkASIO(driver->getChannels(&inputCount, &outputCount),
                  "Actual ASIO channel inventory failed");
        ensure(outputCount >= 2, "Physical ASIO hardware has fewer than 2 outputs");
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
        ensure(inputCount >= 2,
               "P95 ASIO4ALL did not expose two selected virtual recording inputs");
#endif
        checkASIO(driver->getBufferSize(&minimum, &maximum, &preferred, &granularity),
                  "Physical ASIO buffer capability query failed");
        ensure(a.frames >= minimum && a.frames <= maximum &&
               (granularity == -1 ? ((a.frames & (a.frames - 1)) == 0) :
                (granularity == 0 ? a.frames == preferred :
                 (granularity > 0 && ((a.frames - minimum) % granularity == 0)))),
               "Requested ASIO buffer size not supported by physical driver");
        checkASIO(driver->canSampleRate(static_cast<double>(a.rate)),
                  "Physical ASIO hardware rejects requested sample rate");
        checkASIO(driver->setSampleRate(static_cast<double>(a.rate)),
                  "Cannot set physical ASIO hardware sample rate");
        double actualRate{};
        checkASIO(driver->getSampleRate(&actualRate),
                  "Physical ASIO driver did not return actual sample rate");
        ensure(std::abs(actualRate - a.rate) < 0.1, "Actual ASIO rate differs from plan");

        std::string error;
        auto module = Module::create(a.plugin.string(), error);
        ensure(bool(module), "Cannot load real VST3 component into ASIO host");
        HostApplication host;
        auto factory = module->getFactory();
        factory.setHostContext(&host);
        int pluginCount = 0;
        for (const auto& cls : factory.classInfos()) {
            if (cls.category() != kVstAudioEffectClass) continue;
            ++pluginCount;
        }
        ensure(pluginCount == 1, "ASIO hardware test requires one unambiguous VST3 audio class");

        for (const auto& cls : factory.classInfos()) {
            if (cls.category() != kVstAudioEffectClass) continue;
            auto component = factory.createInstance<IComponent>(cls.ID());
            ensure(bool(component) && component->initialize(&host) == kResultOk,
                   "ASIO host cannot initialize VST3 component");
            IAudioProcessor* processor{};
            bool active = false, processing = false, buffers = false, started = false;
            try {
                ensure(component->queryInterface(IAudioProcessor::iid,
                       reinterpret_cast<void**>(&processor)) == kResultOk && processor,
                       "VST3 component has no audio processor");
                ensure(processor->canProcessSampleSize(kSample32) == kResultTrue,
                       "VST3 cannot process 32-bit floating point");
                Processing audio;
                audio.prepare(component.get(), a.frames, static_cast<double>(a.rate));
                ProcessSetup config{};
                config.processMode = kRealtime;
                config.symbolicSampleSize = kSample32;
                config.maxSamplesPerBlock = a.frames;
                config.sampleRate = a.rate;
                ensure(processor->setupProcessing(config) == kResultOk,
                       "VST3 realtime setupProcessing failed");

                Engine engine{};
                engine.driver = driver;
                engine.processor = processor;
                engine.processing = &audio;
                engine.frames = a.frames;
                engine.rate = a.rate;
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
                engine.maxRecordedFrames =
                    static_cast<uint64_t>(a.callbacks + 32) * a.frames;
                engine.loopbackTrace.assign(
                    static_cast<size_t>(engine.maxRecordedFrames) * 4, 0.f);
#endif
                LARGE_INTEGER freq{};
                ensure(QueryPerformanceFrequency(&freq) && freq.QuadPart > 0,
                       "High resolution callback clock unavailable");
                engine.qpcFrequency = freq.QuadPart;
                ASIOCallbacks callbacks{};
                callbacks.bufferSwitch = onBuffer;
                callbacks.sampleRateDidChange = onSampleRate;
                callbacks.asioMessage = onMessage;
                callbacks.bufferSwitchTimeInfo = onTimeInfo;
                for (size_t ch = 0; ch < 2; ++ch) {
                    ASIOChannelInfo info{};
                    info.isInput = ASIOFalse;
                    info.channel = static_cast<long>(ch);
                    checkASIO(driver->getChannelInfo(&info),
                              "Cannot identify physical ASIO output format");
                    ensure(asioBytesPerSample(info.type) != 0,
                           "Physical output sample layout not supported");
                    engine.sampleTypes[ch] = info.type;
                    engine.asioBuffers[ch].isInput = ASIOFalse;
                    engine.asioBuffers[ch].channelNum = static_cast<long>(ch);
                }
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
                for (size_t ch = 0; ch < 2; ++ch) {
                    ASIOChannelInfo info{};
                    info.isInput = ASIOTrue;
                    info.channel = static_cast<long>(ch);
                    checkASIO(driver->getChannelInfo(&info),
                              "P95 cannot inspect selected virtual ASIO recording channel");
                    ensure(asioBytesPerSample(info.type) != 0,
                           "P95 unsupported incoming ASIO PCM format");
                    engine.sampleTypes[ch + 2] = info.type;
                    engine.asioBuffers[ch + 2].isInput = ASIOTrue;
                    engine.asioBuffers[ch + 2].channelNum = static_cast<long>(ch);
                }
#endif
                checkASIO(driver->createBuffers(engine.asioBuffers.data(),
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
                    4,
#else
                    2,
#endif
                    a.frames,
                                                &callbacks), "Actual ASIO buffer allocation failed");
                buffers = true;
                ensure(component->setActive(true) == kResultOk, "VST3 setActive failed");
                active = true;
                ensure(processor->setProcessing(true) == kResultOk,
                       "VST3 setProcessing failed");
                processing = true;
                activeEngine.store(&engine, std::memory_order_release);
                checkASIO(driver->start(), "Actual ASIO hardware streaming failed");
                started = true;

                const auto deadline = std::chrono::steady_clock::now() +
                    std::chrono::seconds(std::min(600, std::max(20,
                        static_cast<int>(a.callbacks * static_cast<double>(a.frames) / a.rate * 3 + 10))));
                while (engine.asioCallbacks.load() < static_cast<uint64_t>(a.callbacks) &&
                       std::chrono::steady_clock::now() < deadline)
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                checkASIO(driver->stop(), "Actual ASIO hardware stop failed");
                started = false;
                activeEngine.store(nullptr, std::memory_order_release);
                checkASIO(driver->disposeBuffers(), "Cannot dispose ASIO hardware buffers");
                buffers = false;
                ensure(processor->setProcessing(false) == kResultOk,
                       "VST3 setProcessing(false) failed");
                processing = false;
                ensure(component->setActive(false) == kResultOk,
                       "VST3 setActive(false) failed");
                active = false;

                ensure(engine.asioCallbacks.load() >= static_cast<uint64_t>(a.callbacks),
                       "Actual physical ASIO callback threshold not reached");
                // Count strict process successes, no partial/undercounted callbacks.
                ensure(engine.asioCallbacks.load() == engine.processedCallbacks.load() &&
                       engine.deadlineMisses.load() == 0 &&
                       engine.xruns.load() == 0 &&
                       engine.processFailures.load() == 0 &&
                       engine.sampleRateChanges.load() == 0,
                       "Physical ASIO real callback timing or DSP errors observed");
                ensure(hashFile(a.plugin) == moduleHash &&
                       hashFile(selfPath()) == executorHash,
                       "ASIO plugin/executor changed during real callback processing");
#if defined(QA_ASIO_VIRTUAL_LOOPBACK)
                writeLoopbackTrace(a, engine);
#endif
                proof(a, engine, moduleHash, executorHash);
            } catch (...) {
                activeEngine.store(nullptr, std::memory_order_release);
                if (started) (void)driver->stop();
                if (buffers) (void)driver->disposeBuffers();
                if (processing) (void)processor->setProcessing(false);
                if (active) (void)component->setActive(false);
                if (processor) processor->release();
                (void)component->terminate();
                throw;
            }
            processor->release();
            ensure(component->terminate() == kResultOk,
                   "VST3 terminate failed after ASIO callbacks");
        }
        driver->Release();
        CoUninitialize();
        return 0;
    } catch (...) {
        if (driver) driver->Release();
        CoUninitialize();
        throw;
    }
}
} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::strcmp(argv[1], "--sample-format-selftest") == 0)
            return formatSelfTest();
        return run(parse(argc, argv));
    } catch (const std::exception& ex) {
        std::cerr << "[P58 HARDWARE NO-GO] " << ex.what() << "\n";
        return 1;
    }
}
