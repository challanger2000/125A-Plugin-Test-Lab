cmake_minimum_required(VERSION 3.25)
project(125ADrumatorMidiExportProbe LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "P06 probes are Windows-only")
endif()
if(NOT DEFINED DRUMATOR_SOURCE_ROOT OR NOT EXISTS "${DRUMATOR_SOURCE_ROOT}/src/core/MidiExport.h")
    message(FATAL_ERROR "DRUMATOR_SOURCE_ROOT must contain a read-only Drumator checkout")
endif()
add_executable(DrumatorMidiProbe ../drumator_midi_probe.cpp)
set_target_properties(DrumatorMidiProbe PROPERTIES
    CXX_STANDARD 23 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO
    OUTPUT_NAME "125A_Drumator_MIDI_Probe")
target_include_directories(DrumatorMidiProbe PRIVATE "${DRUMATOR_SOURCE_ROOT}/src")
target_compile_definitions(DrumatorMidiProbe PRIVATE NOMINMAX)
if(MSVC)
    target_compile_options(DrumatorMidiProbe PRIVATE /W4 /permissive- /utf-8)
endif()

add_executable(DrumatorBeatCreatorProbe ../drumator_beat_probe.cpp)
set_target_properties(DrumatorBeatCreatorProbe PROPERTIES
    CXX_STANDARD 23 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO
    OUTPUT_NAME "125A_Drumator_Beat_Probe")
target_include_directories(DrumatorBeatCreatorProbe PRIVATE "${DRUMATOR_SOURCE_ROOT}/src")
target_compile_definitions(DrumatorBeatCreatorProbe PRIVATE NOMINMAX)
if(MSVC)
    target_compile_options(DrumatorBeatCreatorProbe PRIVATE /W4 /permissive- /utf-8)
endif()

add_executable(DrumatorWavExportProbe ../drumator_wav_probe.cpp)
set_target_properties(DrumatorWavExportProbe PROPERTIES
    CXX_STANDARD 23 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO
    OUTPUT_NAME "125A_Drumator_WAV_Probe")
target_include_directories(DrumatorWavExportProbe PRIVATE "${DRUMATOR_SOURCE_ROOT}/src")
target_compile_definitions(DrumatorWavExportProbe PRIVATE NOMINMAX)
if(MSVC)
    target_compile_options(DrumatorWavExportProbe PRIVATE /W4 /permissive- /utf-8)
endif()
