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
  target_compile_options(TestLabGUI PRIVATE /FIshlobj.h) # P15 DROPFILES Windows Shell SDK
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
