// P07: read-only product Beat Creator stress vectors for an independent
// verifier. The checker is not based on BeatCreator.cpp internals.
#include "core/BeatCreatorTransaction.h"
#include "vst3/UiBeatCreatorDialog.h"

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using namespace drumator;
void require(bool ok, const char* text) {
    if (!ok) throw std::runtime_error(text);
}

void verifyUiStepping() {
    using U = UiBeatCreatorDialog;
    for (int complexity = 0; complexity <= 100; complexity += 5) {
        const auto v = static_cast<std::uint8_t>(complexity);
        const auto next = U::steppedComplexity(v, +1);
        const auto prev = U::steppedComplexity(v, -1);
        require(next == static_cast<unsigned>(std::min(100, complexity + 5)),
                "Beat Creator + button does not adjust in exact 5-point steps");
        require(prev == static_cast<unsigned>(std::max(0, complexity - 5)),
                "Beat Creator - button does not adjust in exact 5-point steps");
    }
    std::uint8_t parsed = 0;
    require(U::parseComplexity("37", parsed) && parsed == 37,
            "Direct complexity value is not accepted");
    require(U::parseComplexity("100%", parsed) && parsed == 100,
            "Percent complexity value not accepted");
    require(!U::parseComplexity("101", parsed) &&
            !U::parseComplexity("-5", parsed) &&
            !U::parseComplexity("35x", parsed),
            "Invalid direct complexity value accepted");
    std::cout << "[PASS] P07 UI complexity control: +/- five points, clipping, direct entry\n";
}

void verifyTransactions() {
    const BeatCreatorSettings s{BeatStyle::EBM, 35, 16};
    const BeatCreatorPreview preview = BeatCreator::preview(s, 57);
    require(preview.valid, "Cannot generate valid core preview");
    BeatTriple previous{};
    previous[0][8 * kSteps] = 109;   // User's hidden row 9, never erased
    BeatLengths originalLengths{32, 32, 32};
    const auto rejected = BeatCreatorTransaction::prepare(
        preview, previous, originalLengths, false);
    require(!rejected.valid && rejected.occupied != 0,
            "Existing user pattern overwritten without approval");
    const auto allowed = BeatCreatorTransaction::prepare(
        preview, previous, originalLengths, true);
    require(allowed.valid, "Explicitly confirmed creator transaction was rejected");
    require(allowed.before == previous &&
            allowed.oldLengths == originalLengths,
            "Undo snapshot lost existing notes/lengths");
    require(allowed.after[0][8 * kSteps] == 109,
            "Creator changed protected hidden user row 9");
    for (auto length : allowed.newLengths)
        require(length == 16, "Creator failed to install chosen one-bar length");
    BeatCreatorPreview invalid = preview;
    invalid.a[8 * kSteps] = 127;       // Generator may never fill hidden rows
    require(!BeatCreatorTransaction::prepare(
                invalid, previous, originalLengths, true).valid,
            "Invalid generator preview with hidden notes accepted");
    std::cout << "[PASS] P07 transactional protection, explicit overwrite and undo snapshot\n";
}

void writeVector(const std::filesystem::path& path, unsigned style,
                 unsigned complexity, unsigned steps,
                 const BeatCreatorPreview& data) {
    require(data.valid && data.steps == steps, "Invalid Beat Creator vector");
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    require(out.good(), "Cannot write generator test vector");
    out.write("125ABC01", 8);
    const std::array<char, 4> header{
        static_cast<char>(style), static_cast<char>(complexity),
        static_cast<char>(steps), 0};
    out.write(header.data(), static_cast<std::streamsize>(header.size()));
    out.write(reinterpret_cast<const char*>(data.a.data()), data.a.size());
    out.write(reinterpret_cast<const char*>(data.b.data()), data.b.size());
    out.write(reinterpret_cast<const char*>(data.c.data()), data.c.size());
    require(out.good(), "Incomplete generator vector write");
}

void generate(const std::filesystem::path& directory) {
    std::filesystem::create_directories(directory);
    require(std::filesystem::is_directory(directory), "Missing P07 output directory");
    unsigned count = 0;
    for (unsigned style = 0; style < 10; ++style) {
        for (unsigned steps : {16U, 32U}) {
            for (unsigned complexity : {35U, 100U}) {
                for (unsigned seed = 0; seed < 32; ++seed) {
                    BeatCreatorSettings settings{
                        static_cast<BeatStyle>(style),
                        static_cast<std::uint8_t>(complexity),
                        static_cast<std::uint8_t>(steps)};
                    const auto first = BeatCreator::preview(settings, seed);
                    const auto second = BeatCreator::preview(settings, seed);
                    require(first.valid && second.valid &&
                            first.a == second.a && first.b == second.b &&
                            first.c == second.c,
                            "Beat Creator generated nondeterministic A/B/C");
                    const auto filename =
                        "style" + std::to_string(style) + "-steps" +
                        std::to_string(steps) + "-complexity" +
                        std::to_string(complexity) + "-seed" +
                        std::to_string(seed) + ".abc";
                    writeVector(directory / filename, style, complexity, steps, first);
                    ++count;
                }
            }
        }
    }
    require(count == 1280, "Wrong Beat Creator vector count");
    std::cout << "[PASS] P07: emitted " << count
              << " real Beat Creator A/B/C vectors across ten styles, "
                 "two lengths, two complexities and 32 seeds\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        require(argc == 2, "Usage: 125A_Drumator_Beat_Probe <output-directory>");
        verifyUiStepping();
        verifyTransactions();
        generate(std::filesystem::path(argv[1]));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "[FAIL] P07 Beat Creator probe: " << error.what() << '\n';
        return 1;
    }
}
