// P06 read-only integration against Drumator's actual MIDI export implementation.
// This executable is built INSIDE Test Lab from a pinned, checkout-only product
// source tree. No product changes or product-owned test assertions are imported.
// A separate Python MIDI parser is the actual behavior oracle.
#include "core/MidiExport.h"
#include "core/ExportFile.h"

#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using drumator::MidiExport;
using drumator::MidiExportConfig;
using drumator::SongChain;

namespace {
void require(bool okay, const char* msg) {
    if (!okay) throw std::runtime_error(msg);
}

MidiExportConfig kit(unsigned bpm, unsigned swing, bool song) {
    MidiExportConfig config{};
    config.patternLengths.fill(16);
    config.randomVelocity.fill(0);
    config.grid.fill(0);
    config.grid[2] = 110;                 // Kick row 0, Step 3 (eighth offbeat)
    config.selectedPattern = 0;
    config.swingPercent = static_cast<std::uint8_t>(swing);
    config.humanizePercent = 0;
    config.tempoBpm = static_cast<double>(bpm);
    config.exportSong = song;
    if (song) {
        require(config.song.setCount(3), "Cannot set synthetic song length");
        require(config.song.configure(0, 0, 16), "Cannot set song entry A");
        require(config.song.configure(1, SongChain::kRest, 16), "Cannot set REST");
        require(config.song.configure(2, 0, 16), "Cannot set second A");
    }
    return config;
}

void write(const std::filesystem::path& path, const std::vector<std::uint8_t>& bytes) {
    drumator::ExportFile output(path);
    require(output.open() && output.write(bytes.data(), bytes.size()) && output.finish(),
            "Actual export writer failed to commit SMF MIDI");
    require(std::filesystem::is_regular_file(path), "MIDI export output missing");
    require(std::filesystem::file_size(path) == bytes.size(), "MIDI file size mismatch");
}

void negativeCases() {
    auto baseline = kit(120, 0, false);
    std::vector<std::uint8_t> sentinel{0xDE, 0xAD, 0xBE, 0xEF};
    const auto original = sentinel;

    auto invalidTempo = baseline;
    invalidTempo.tempoBpm = 0.;
    require(!MidiExport::encode(invalidTempo, sentinel) && sentinel == original,
            "Invalid tempo accepted or destination mutated");

    auto invalidSwing = baseline;
    invalidSwing.swingPercent = 51;
    require(!MidiExport::encode(invalidSwing, sentinel) && sentinel == original,
            "Invalid swing accepted or destination mutated");

    auto invalidCell = baseline;
    invalidCell.grid[2] = 128;
    require(!MidiExport::encode(invalidCell, sentinel) && sentinel == original,
            "Invalid grid velocity accepted or destination mutated");

    auto invalidLength = baseline;
    invalidLength.patternLengths[0] = 0;
    require(!MidiExport::encode(invalidLength, sentinel) && sentinel == original,
            "Invalid pattern length accepted or destination mutated");

    std::cout << "[PASS] Actual Drumator export rejected invalid tempo, swing, "
                 "velocity and pattern length transactionally\n";
}
}  // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: 125A_Drumator_MIDI_Probe <output-directory>");
        const std::filesystem::path output = argv[1];
        std::filesystem::create_directories(output);
        require(std::filesystem::is_directory(output), "Output directory unavailable");
        unsigned cases = 0;
        for (const unsigned bpm : {90U, 120U, 150U}) {
            for (const unsigned swing : {0U, 25U, 50U}) {
                for (const bool song : {false, true}) {
                    const auto source = kit(bpm, swing, song);
                    std::vector<std::uint8_t> midi{};
                    require(MidiExport::encode(source, midi), "Actual MIDI exporter rejected good fixture");
                    require(midi.size() > 30 && midi.size() < 1'000'000,
                            "MIDI exporter returned implausible size");
                    const auto path = output /
                        (std::string(song ? "song" : "pattern") + "-bpm" +
                         std::to_string(bpm) + "-swing" + std::to_string(swing) + ".mid");
                    write(path, midi);
                    std::cout << "[INFO] " << path.filename().string()
                              << " size=" << midi.size() << " bytes\n";
                    ++cases;
                }
            }
        }
        require(cases == 18, "Wrong case count");
        negativeCases();
        std::cout << "[PASS] P06: 18 actual, disk-committed Drumator SMF exports "
                     "ready for independent parser verification\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "[FAIL] P06 actual exporter: " << ex.what() << '\n';
        return 1;
    }
}
