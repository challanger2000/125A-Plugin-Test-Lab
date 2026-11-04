// P08 standalone real Drumator WAV export implementation probe.
// The product checkout is READ ONLY. Independent verification is in Python.
// WAV fixtures are synthetic, signed PCM16 stereo: L +0.25, R -0.5.
#include "core/OfflineWavExport.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using namespace drumator;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void u16(std::vector<std::uint8_t>& dest, std::uint16_t v) {
    dest.push_back(static_cast<std::uint8_t>(v));
    dest.push_back(static_cast<std::uint8_t>(v >> 8));
}
void u32(std::vector<std::uint8_t>& dest, std::uint32_t v) {
    for (int i = 0; i < 4; ++i)
        dest.push_back(static_cast<std::uint8_t>(v >> (8 * i)));
}
void marker(std::vector<std::uint8_t>& dest, const char* tag) {
    for (int i = 0; i < 4; ++i)
        dest.push_back(static_cast<std::uint8_t>(tag[i]));
}
std::vector<std::uint8_t> createSample() {
    constexpr unsigned rate = 44100;
    constexpr unsigned frames = 1024;
    constexpr unsigned channels = 2;
    constexpr unsigned sampleBytes = 2;
    const unsigned length = frames * channels * sampleBytes;
    std::vector<std::uint8_t> wav;
    wav.reserve(length + 44);
    marker(wav, "RIFF");
    u32(wav, 36 + length);
    marker(wav, "WAVE");
    marker(wav, "fmt ");
    u32(wav, 16);
    u16(wav, 1); // PCM
    u16(wav, channels);
    u32(wav, rate);
    u32(wav, rate * channels * sampleBytes);
    u16(wav, channels * sampleBytes);
    u16(wav, 16);
    marker(wav, "data");
    u32(wav, length);
    for (unsigned frame = 0; frame < frames; ++frame) {
        u16(wav, 8192);   // left: +0.25
        u16(wav, static_cast<std::uint16_t>(-16384)); // right: -0.5
    }
    require(wav.size() == length + 44, "Synthetic source WAV size mismatch");
    return wav;
}

KitState scenario(unsigned swing) {
    KitState state{};
    state.selected = 0;
    state.visible = 8;
    state.patternLengths.fill(16);
    state.grid.fill(0);
    state.grid[2] = 110;    // A/Kick row0/offbeat step3
    state.names[0] = "P08-synthetic-stereo.wav";
    state.wav[0] = createSample();
    state.swing = static_cast<std::uint8_t>(swing);
    state.humanize = 0;
    state.masterVolume = 100;
    state.limiter = 0;
    state.songEnabled = 1;
    require(state.chain.setCount(3), "Cannot form synthetic song");
    require(state.chain.configure(0, 0, 16) &&
            state.chain.configure(1, SongChain::kRest, 16) &&
            state.chain.configure(2, 0, 16),
            "Cannot configure synthetic A/REST/A song");
    require(KitCodec::valid(state, true), "Synthetic PCM16 kit rejected by product codec");
    return state;
}

void rejectInvalid(const std::filesystem::path& folder) {
    auto source = scenario(0);
    auto wrongTempo = folder / "bad-zero-tempo.wav";
    require(!OfflineWavExport::render(source, false, 0., wrongTempo),
            "Invalid zero tempo accepted");
    require(!std::filesystem::exists(wrongTempo),
            "Failed export incorrectly produced WAV at invalid tempo");

    source.pitch[0] = 60; // range 0..48
    auto wrongPitch = folder / "bad-pitch.wav";
    require(!OfflineWavExport::render(source, false, 120., wrongPitch),
            "Out-of-range pitch accepted");
    require(!std::filesystem::exists(wrongPitch),
            "Failed export incorrectly produced WAV for invalid pitch");

    std::cout << "[PASS] P08 export rejects invalid tempo and invalid kit without output\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: 125A_Drumator_WAV_Probe <output-directory>");
        std::filesystem::path directory = argv[1];
        std::filesystem::create_directories(directory);
        require(std::filesystem::is_directory(directory), "P08 output unavailable");
        unsigned count = 0;
        for (unsigned bpm : {90U, 120U, 150U}) {
            for (unsigned swing : {0U, 25U, 50U}) {
                auto state = scenario(swing);
                for (bool song : {false, true}) {
                    const std::string mode = song ? "song" : "pattern";
                    auto path = directory / (mode + "-bpm" + std::to_string(bpm) +
                                             "-swing" + std::to_string(swing) + ".wav");
                    require(OfflineWavExport::render(state, song, bpm, path),
                            "Actual Drumator OfflineWavExport::render failed");
                    require(std::filesystem::is_regular_file(path) &&
                            std::filesystem::file_size(path) >= 44,
                            "Actual WAV export is missing or truncated");
                    std::cout << "[INFO] " << path.filename().string()
                              << " bytes=" << std::filesystem::file_size(path) << '\n';
                    ++count;
                }
            }
        }
        require(count == 18, "Wrong number of rendered WAV export scenarios");
        rejectInvalid(directory);
        std::cout << "[PASS] P08: 18 actual WAV exports via product renderer and "
                     "transactional file writer, plus two invalid-input cases\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] P08 real WAV export probe: " << error.what() << '\n';
        return 1;
    }
}
