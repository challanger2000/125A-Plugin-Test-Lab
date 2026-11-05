cmake_minimum_required(VERSION 3.25)
project(PluginTestLab125A VERSION 0.1.0 LANGUAGES CXX)

if(NOT WIN32)
  message(FATAL_ERROR "125A Plugin Test Lab P01 supports Windows x64 only")
endif()

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF CACHE BOOL "" FORCE)
set(SMTG_RUN_VST_VALIDATOR OFF CACHE BOOL "" FORCE)
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)

include(FetchContent)
# Keep aligned with the established 125A Plugin Tester; do not float to master.
FetchContent_Declare(vst3sdk
    GIT_REPOSITORY https://github.com/steinbergmedia/vst3sdk.git
    GIT_TAG v3.8.1_build_84
    GIT_SHALLOW TRUE
    GIT_SUBMODULES_RECURSE TRUE)
FetchContent_MakeAvailable(vst3sdk)

# The pinned Steinberg Windows module still uses u8string() as std::string.
# In C++20+ u8string() returns std::u8string. Compile ONLY this SDK translation
# unit as C++17; keep all original 125A code at C++23.
add_library(Vst3WinModule OBJECT
    "${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/hosting/module_win32.cpp")
set_target_properties(Vst3WinModule PROPERTIES
    CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
target_link_libraries(Vst3WinModule PRIVATE sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(Vst3WinModule PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)

add_executable(TestLabHost src/main.cpp)
set_target_properties(TestLabHost PROPERTIES OUTPUT_NAME "125A_Test_Lab_Host")
target_link_libraries(TestLabHost PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabHost PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabHost PRIVATE /W4 /permissive- /utf-8)
endif()

enable_testing()
add_test(NAME transport_selftest COMMAND $<TARGET_FILE:TestLabHost> --selftest)
add_test(NAME invalid_plugin_rejected COMMAND $<TARGET_FILE:TestLabHost> --render .\\invalid.vst3 .\\invalid.wav)
set_tests_properties(invalid_plugin_rejected PROPERTIES WILL_FAIL TRUE)

# CI-only VST3s: one renders known musical impulses, the second injects
# nonfinite audio. These are NEVER bundled with the public host artifact.
set(SMTG_PLUGIN_TARGET_PATH "${CMAKE_BINARY_DIR}/QA-VST3" CACHE PATH "" FORCE)

smtg_add_vst3plugin(QASignalGood
    PACKAGE_NAME "125A_QA_SignalGood"
    SOURCES_LIST tests/signal_fixture.cpp)
target_link_libraries(QASignalGood PRIVATE sdk)
target_compile_definitions(QASignalGood PRIVATE NOMINMAX QA_DELIBERATE_NAN=0)

smtg_add_vst3plugin(QASignalBad
    PACKAGE_NAME "125A_QA_SignalBad"
    SOURCES_LIST tests/signal_fixture.cpp)
target_link_libraries(QASignalBad PRIVATE sdk)
target_compile_definitions(QASignalBad PRIVATE NOMINMAX QA_DELIBERATE_NAN=1)

# P04: native Win32 editor host; real mouse-to-VST3-parameter assertion is
# verified by two independent, source-built synthetic UI fixtures in Actions.
add_executable(TestLabGUI src/gui_host.cpp)
set_target_properties(TestLabGUI PROPERTIES OUTPUT_NAME "125A_Test_Lab_GUI")
target_link_libraries(TestLabGUI PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces user32 gdi32 ole32 shell32)
target_compile_definitions(TestLabGUI PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabGUI PRIVATE /W4 /permissive- /utf-8)
  target_compile_options(TestLabGUI PRIVATE /FI${CMAKE_CURRENT_SOURCE_DIR}/src/p15_dropfiles.h) # P15 isolated DROPFILES layout
endif()

smtg_add_vst3plugin(QAGuiClick
    PACKAGE_NAME "125A_QA_GUI_Click"
    SOURCES_LIST tests/gui_fixture.cpp)
target_link_libraries(QAGuiClick PRIVATE sdk user32 gdi32)
target_compile_definitions(QAGuiClick PRIVATE NOMINMAX QA_GUI_INERT=0)

smtg_add_vst3plugin(QAGuiInert
    PACKAGE_NAME "125A_QA_GUI_Inert"
    SOURCES_LIST tests/gui_fixture.cpp)
target_link_libraries(QAGuiInert PRIVATE sdk user32 gdi32)
target_compile_definitions(QAGuiInert PRIVATE NOMINMAX QA_GUI_INERT=1)

# P25-P27: native VST3 concurrency host and deliberately defective production-API fixtures.
add_executable(TestLabStateStress src/state_stress.cpp)
set_target_properties(TestLabStateStress PROPERTIES OUTPUT_NAME "125A_Test_Lab_State_Stress")
target_link_libraries(TestLabStateStress PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabStateStress PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabStateStress PRIVATE /W4 /permissive- /utf-8)
endif()
foreach(mode RANGE 0 3)
  smtg_add_vst3plugin(QAStateMode${mode}
      PACKAGE_NAME "125A_QA_State_${mode}"
      SOURCES_LIST tests/state_race_fixture.cpp)
  target_link_libraries(QAStateMode${mode} PRIVATE sdk)
  target_compile_definitions(QAStateMode${mode} PRIVATE NOMINMAX QA_STATE_MODE=${mode})
endforeach()

# P26: real native VST3 failed-state rollback and successful recovery, with
# expected state and PCM outcomes supplied by an external Python adapter.
add_executable(TestLabRecovery src/state_recovery.cpp)
set_target_properties(TestLabRecovery PROPERTIES OUTPUT_NAME "125A_Test_Lab_Recovery")
target_link_libraries(TestLabRecovery PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabRecovery PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabRecovery PRIVATE /W4 /permissive- /utf-8)
endif()
foreach(mode RANGE 4 5)
  smtg_add_vst3plugin(QAStateMode${mode}
      PACKAGE_NAME "125A_QA_State_${mode}"
      SOURCES_LIST tests/state_race_fixture.cpp)
  target_link_libraries(QAStateMode${mode} PRIVATE sdk)
  target_compile_definitions(QAStateMode${mode} PRIVATE NOMINMAX QA_STATE_MODE=${mode})
endforeach()

# P27: product-independent time/partition PCM recorder and known-bad
# block-dependent VST3 synthetic DSP. Expected math remains external.
add_executable(TestLabRateBlock src/rate_block.cpp)
set_target_properties(TestLabRateBlock PROPERTIES OUTPUT_NAME "125A_Test_Lab_Rate_Block")
target_link_libraries(TestLabRateBlock PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabRateBlock PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabRateBlock PRIVATE /W4 /permissive- /utf-8)
endif()
smtg_add_vst3plugin(QAStateMode6
    PACKAGE_NAME "125A_QA_State_6"
    SOURCES_LIST tests/state_race_fixture.cpp)
target_link_libraries(QAStateMode6 PRIVATE sdk)
target_compile_definitions(QAStateMode6 PRIVATE NOMINMAX QA_STATE_MODE=6)

# P28: intentionally illegal blocking VST3 callback to prove timing gate.
smtg_add_vst3plugin(QAStateMode7
    PACKAGE_NAME "125A_QA_State_7"
    SOURCES_LIST tests/state_race_fixture.cpp)
target_link_libraries(QAStateMode7 PRIVATE sdk)
target_compile_definitions(QAStateMode7 PRIVATE NOMINMAX QA_STATE_MODE=7)

# P29 universal MIDI instrument playback/save/recall test, three VST3 fixtures.
add_executable(TestLabVoiceStress src/voice_stress.cpp)
set_target_properties(TestLabVoiceStress PROPERTIES OUTPUT_NAME "125A_Test_Lab_Voice_Stress")
target_link_libraries(TestLabVoiceStress PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabVoiceStress PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabVoiceStress PRIVATE /W4 /permissive- /utf-8)
endif()
foreach(mode RANGE 0 2)
  smtg_add_vst3plugin(QAVoiceMode${mode}
      PACKAGE_NAME "125A_QA_Voice_${mode}"
      SOURCES_LIST tests/voice_fixture.cpp)
  target_link_libraries(QAVoiceMode${mode} PRIVATE sdk)
  target_compile_definitions(QAVoiceMode${mode} PRIVATE NOMINMAX QA_VOICE_MODE=${mode})
endforeach()

# P30 universal native processor/controller reconnection and stale-state fixture.
add_executable(TestLabControllerRecovery src/controller_recovery.cpp)
set_target_properties(TestLabControllerRecovery PROPERTIES OUTPUT_NAME "125A_Test_Lab_Controller_Recovery")
target_link_libraries(TestLabControllerRecovery PRIVATE Vst3WinModule sdk_hosting sdk_common base pluginterfaces)
target_compile_definitions(TestLabControllerRecovery PRIVATE NOMINMAX _CRT_SECURE_NO_WARNINGS)
if(MSVC)
  target_compile_options(TestLabControllerRecovery PRIVATE /W4 /permissive- /utf-8)
endif()
foreach(mode RANGE 0 1)
  smtg_add_vst3plugin(QAControllerMode${mode}
      PACKAGE_NAME "125A_QA_Controller_${mode}"
      SOURCES_LIST tests/controller_recovery_fixture.cpp)
  target_link_libraries(QAControllerMode${mode} PRIVATE sdk)
  target_compile_definitions(QAControllerMode${mode} PRIVATE NOMINMAX P30_MODE=${mode})
endforeach()
