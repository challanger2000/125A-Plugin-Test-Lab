// P04 native GUI test fixture. Entirely synthetic: no product plugin is modified.
// A real VST3 controller creates a real child HWND. Its mouse-up event changes
// the exposed VST3 parameter 9001; the broken variant deliberately ignores it.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "public.sdk/source/common/pluginview.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <string>
using namespace Steinberg;
using namespace Steinberg::Vst;

#ifndef QA_GUI_INERT
#define QA_GUI_INERT 0
#endif
#ifndef QA_GUI_STALE_PAINT
#define QA_GUI_STALE_PAINT 0
#endif
#ifndef QA_GUI_BAD_PARAM
#define QA_GUI_BAD_PARAM 0
#endif
#ifndef QA_GUI_TOGGLE
#define QA_GUI_TOGGLE 0
#endif
#ifndef QA_GUI_TEXT
#define QA_GUI_TEXT 0
#endif
#ifndef QA_GUI_BAD_TEXT
#define QA_GUI_BAD_TEXT 0
#endif
#ifndef QA_GUI_HOVER
#define QA_GUI_HOVER 0
#endif
#ifndef QA_GUI_NESTED
#define QA_GUI_NESTED 0
#endif
#ifndef QA_GUI_PAINTED_ONLY
#define QA_GUI_PAINTED_ONLY 0
#endif
#ifndef QA_GUI_ANALOG_GOOD
#define QA_GUI_ANALOG_GOOD 0
#endif
#ifndef QA_GUI_ANALOG_BAD
#define QA_GUI_ANALOG_BAD 0
#endif
#ifndef QA_GUI_EXPORT_GOOD
#define QA_GUI_EXPORT_GOOD 0
#endif
#ifndef QA_GUI_EXPORT_BAD
#define QA_GUI_EXPORT_BAD 0
#endif
#ifndef QA_GUI_EXPORT_MIDI_GOOD
#define QA_GUI_EXPORT_MIDI_GOOD 0
#endif
#ifndef QA_GUI_EXPORT_MIDI_BAD
#define QA_GUI_EXPORT_MIDI_BAD 0
#endif

namespace {
constexpr ParamID kClickParam = 9001;

// Real Win32 file side effect performed by the *VST3 editor*, not by
// the test harness. The independent Python contract must inspect the
// produced RIFF/PCM bytes and reject the deliberately broken variant.
#if QA_GUI_EXPORT_GOOD || QA_GUI_EXPORT_BAD
bool writeFixtureWav() {
    std::array<wchar_t, 4096> path{};
    const DWORD count = GetEnvironmentVariableW(
        L"QA_TEST_LAB_EXPORT_ROOT", path.data(),
        static_cast<DWORD>(path.size()));
    if (count == 0 || count >= path.size() || count > 3500) return false;
    std::wstring file(path.data(), count);
    if (!file.empty() && file.back() != L'\\' && file.back() != L'/')
        file += L'\\';
    file += L"gui-export.wav";
    const HANDLE handle = CreateFileW(file.c_str(), GENERIC_WRITE, 0, nullptr,
                                      CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) return false;
    constexpr std::array<std::int16_t, 16> samples = {
        0, 1000, -1000, 32767, -32768, 4321, -4321, 0,
        256, -256, 8192, -8192, 123, -123, 1, -1
    };
    std::array<std::uint8_t, 76> wav{};
    auto put16 = [&](int offset, std::uint16_t n) {
        wav[offset] = static_cast<std::uint8_t>(n & 255);
        wav[offset + 1] = static_cast<std::uint8_t>(n >> 8);
    };
    auto put32 = [&](int offset, std::uint32_t n) {
        put16(offset, static_cast<std::uint16_t>(n));
        put16(offset + 2, static_cast<std::uint16_t>(n >> 16));
    };
    std::memcpy(wav.data(), "RIFF", 4);
    put32(4, 68);
    std::memcpy(wav.data() + 8, "WAVEfmt ", 8);
    put32(16, 16);
    put16(20, 1);
    put16(22, 1);
    put32(24, 44100);
    put32(28, 88200);
    put16(32, 2);
    put16(34, 16);
    std::memcpy(wav.data() + 36, "data", 4);
    put32(40, 32);
    for (int i = 0; i < 16; ++i) {
        auto sample = samples[static_cast<std::size_t>(i)];
#if QA_GUI_EXPORT_BAD
        if (i == 3) sample = 0; // Valid WAV, *incorrect actual audio*
#endif
        put16(44 + i * 2, static_cast<std::uint16_t>(sample));
    }
    DWORD written = 0;
    const BOOL ok = WriteFile(handle, wav.data(), static_cast<DWORD>(wav.size()),
                              &written, nullptr);
    const BOOL flushed = FlushFileBuffers(handle);
    const BOOL closed = CloseHandle(handle);
    return ok && flushed && closed && written == wav.size();
}
#endif

#if QA_GUI_EXPORT_MIDI_GOOD || QA_GUI_EXPORT_MIDI_BAD
bool writeFixtureMidi() {
    std::array<wchar_t, 4096> path{};
    const DWORD count = GetEnvironmentVariableW(
        L"QA_TEST_LAB_EXPORT_ROOT", path.data(),
        static_cast<DWORD>(path.size()));
    if (count == 0 || count >= path.size() || count > 3500) return false;
    std::wstring file(path.data(), count);
    if (!file.empty() && file.back() != L'\\' && file.back() != L'/')
        file += L'\\';
    file += L"gui-export.mid";
    const HANDLE handle = CreateFileW(file.c_str(), GENERIC_WRITE, 0, nullptr,
                                      CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) return false;
    // Separate source-defined MIDI fixture: SMF0, PPQ 96, one note-on at
    // tick zero, note-off at tick 96, proper 12-byte track and EOT.
    std::array<std::uint8_t, 34> midi = {
        0x4d, 0x54, 0x68, 0x64, 0x00, 0x00, 0x00, 0x06,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x60,
        0x4d, 0x54, 0x72, 0x6b, 0x00, 0x00, 0x00, 0x0c,
        0x00, 0x90, 0x3c, 0x64, 0x60, 0x80, 0x3c, 0x00,
        0x00, 0xff, 0x2f, 0x00
    };
#if QA_GUI_EXPORT_MIDI_BAD
    // A syntactically valid MIDI but objectively WRONG musical note.
    midi[24] = 0x40;
    midi[28] = 0x40;
#endif
    DWORD written = 0;
    const BOOL ok = WriteFile(handle, midi.data(),
                              static_cast<DWORD>(midi.size()), &written, nullptr);
    const BOOL flushed = FlushFileBuffers(handle);
    const BOOL closed = CloseHandle(handle);
    return ok && flushed && closed && written == midi.size();
}
#endif

#if QA_GUI_ANALOG_GOOD
const FUID kProcessorCID(0x125A2026, 0x11060001, 0xA0000A11, 0xB0000A11);
const FUID kControllerCID(0x125A2026, 0x11060001, 0xA0000A12, 0xB0000A12);
constexpr const char* kName = "125A Analog GUI Continuous Control Fixture";
#elif QA_GUI_ANALOG_BAD
const FUID kProcessorCID(0x125A2026, 0x11060001, 0xA0000A21, 0xB0000A21);
const FUID kControllerCID(0x125A2026, 0x11060001, 0xA0000A22, 0xB0000A22);
constexpr const char* kName = "125A Analog GUI Quantized Defect Fixture";
#elif QA_GUI_EXPORT_MIDI_GOOD
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA00000C1, 0xB00000C1);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA00000C2, 0xB00000C2);
constexpr const char* kName = "125A GUI Export Correct MIDI Fixture";
#elif QA_GUI_EXPORT_MIDI_BAD
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA00000D1, 0xB00000D1);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA00000D2, 0xB00000D2);
constexpr const char* kName = "125A GUI Export Wrong Note MIDI Fixture";
#elif QA_GUI_EXPORT_GOOD
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA00000A1, 0xB00000A1);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA00000A2, 0xB00000A2);
constexpr const char* kName = "125A GUI Export Correct WAV Fixture";
#elif QA_GUI_EXPORT_BAD
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA00000B1, 0xB00000B1);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA00000B2, 0xB00000B2);
constexpr const char* kName = "125A GUI Export Wrong PCM Fixture";
#elif QA_GUI_PAINTED_ONLY
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000091, 0xB0000091);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000092, 0xB0000092);
constexpr const char* kName = "125A Custom Painted GUI Only Fixture";
#elif QA_GUI_NESTED
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000081, 0xB0000081);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000082, 0xB0000082);
constexpr const char* kName = "125A Nested Child HWND Button Fixture";
#elif QA_GUI_HOVER
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000071, 0xB0000071);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000072, 0xB0000072);
constexpr const char* kName = "125A GUI Hover Without Click Fixture";
#elif QA_GUI_BAD_TEXT
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000061, 0xB0000061);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000062, 0xB0000062);
constexpr const char* kName = "125A Bad VST3 Parameter Text Fixture";
#elif QA_GUI_TEXT
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000051, 0xB0000051);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000052, 0xB0000052);
constexpr const char* kName = "125A Good VST3 Parameter Text Fixture";
#elif QA_GUI_TOGGLE
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000041, 0xB0000041);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000042, 0xB0000042);
constexpr const char* kName = "125A GUI Bidirectional Toggle Fixture";
#elif QA_GUI_BAD_PARAM
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000031, 0xB0000031);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000032, 0xB0000032);
constexpr const char* kName = "125A GUI Bad Parameter API Fixture";
#elif QA_GUI_STALE_PAINT
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000011, 0xB0000011);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000012, 0xB0000012);
constexpr const char* kName = "125A GUI Stale Paint Fixture";
#elif QA_GUI_INERT
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000001, 0xB0000001);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000002, 0xB0000002);
constexpr const char* kName = "125A GUI Broken Fixture";
#else
const FUID kProcessorCID(0x125A2026, 0x11040004, 0xA0000003, 0xB0000003);
const FUID kControllerCID(0x125A2026, 0x11040004, 0xA0000004, 0xB0000004);
constexpr const char* kName = "125A GUI Click Fixture";
#endif

class Processor final : public AudioEffect {
public:
    Processor() {setControllerClass(kControllerCID);}
    static FUnknown* createInstance(void*) {return static_cast<IAudioProcessor*>(new Processor);}
    tresult PLUGIN_API initialize(FUnknown* context) override {
        const auto result = AudioEffect::initialize(context);
        if (result != kResultOk) return result;
        addAudioOutput(STR16("Stereo"), SpeakerArr::kStereo);
        return kResultOk;
    }
    tresult PLUGIN_API setProcessing(TBool) override {return kResultOk;}
    tresult PLUGIN_API process(ProcessData& data) override {
        if (data.symbolicSampleSize != kSample32) return kResultFalse;
        for (int32 b = 0; b < data.numOutputs; ++b) {
            auto& bus = data.outputs[b];
            for (int32 c = 0; c < bus.numChannels; ++c)
                if (bus.channelBuffers32 && bus.channelBuffers32[c])
                    std::fill_n(bus.channelBuffers32[c], data.numSamples, 0.f);
            bus.silenceFlags = 3;
        }
        return kResultOk;
    }
};

class Controller;
class ClickView final : public CPluginView {
public:
    explicit ClickView(Controller* owner) : CPluginView(nullptr), owner_(owner) {
        setRect(ViewRect(0, 0, 320, 180));
    }
    tresult PLUGIN_API isPlatformTypeSupported(FIDString type) override {
        return type && std::strcmp(type, kPlatformTypeHWND) == 0 ? kResultTrue : kResultFalse;
    }
    tresult PLUGIN_API attached(void* parent, FIDString type) override;
    tresult PLUGIN_API removed() override;
private:
    static LRESULT CALLBACK clickProc(HWND hwnd, UINT message, WPARAM w, LPARAM l);
    Controller* owner_{};
    HWND clickWindow_{};
    HWND nestedButton_{};
    bool hovered_{};
    bool paintedActive_{};
    bool draggingAnalog_{};
};

class Controller final : public EditController {
public:
    static FUnknown* createInstance(void*) {return static_cast<IEditController*>(new Controller);}
    tresult PLUGIN_API initialize(FUnknown* context) override {
        if (EditController::initialize(context) != kResultOk) return kResultFalse;
#if QA_GUI_ANALOG_GOOD || QA_GUI_ANALOG_BAD
        parameters.addParameter(STR16("Analog"), nullptr, 0, 0.,
                                ParameterInfo::kCanAutomate, kClickParam);
#else
        parameters.addParameter(STR16("Clicked"), nullptr, 1, 0.,
                                ParameterInfo::kCanAutomate, kClickParam);
#endif
        return kResultOk;
    }
    tresult PLUGIN_API setParamNormalized(ParamID id, ParamValue value) override {
#if QA_GUI_BAD_PARAM
        // Deliberately return success without updating an advertised
        // automatable parameter.  A simple inventory sees no fault.
        if (id == kClickParam && value > 0.5)
            return kResultTrue;
#endif
        return EditController::setParamNormalized(id, value);
    }
    tresult PLUGIN_API getParamStringByValue(
            ParamID id, ParamValue value, String128 buffer) override {
#if QA_GUI_TEXT || QA_GUI_BAD_TEXT
        if (id == kClickParam) {
            const bool on = value >= 0.5;
            buffer[0] = on ? u'O' : u'O';
            buffer[1] = on ? u'N' : u'F';
            buffer[2] = on ? 0 : u'F';
            buffer[3] = 0;
            return kResultTrue;
        }
#endif
        return EditController::getParamStringByValue(id, value, buffer);
    }
    tresult PLUGIN_API getParamValueByString(
            ParamID id, TChar* buffer, ParamValue& value) override {
#if QA_GUI_TEXT || QA_GUI_BAD_TEXT
        if (id == kClickParam) {
            const bool on = buffer && buffer[0] == u'O' &&
                            buffer[1] == u'N' && buffer[2] == 0;
            const bool off = buffer && buffer[0] == u'O' &&
                             buffer[1] == u'F' && buffer[2] == u'F' &&
                             buffer[3] == 0;
            if (!on && !off) return kResultFalse;
#if QA_GUI_BAD_TEXT
            // Deliberately maps both visible labels to the wrong state.
            // Native normalized parameter sweeps alone cannot detect this.
            value = on ? 0.0 : 1.0;
#else
            value = on ? 1.0 : 0.0;
#endif
            return kResultTrue;
        }
#endif
        return EditController::getParamValueByString(id, buffer, value);
    }
    IPlugView* PLUGIN_API createView(FIDString type) override {
        if (!type || std::strcmp(type, ViewType::kEditor) != 0) return nullptr;
        return new ClickView(this);
    }
    void analogAt(int x) {
#if QA_GUI_ANALOG_GOOD || QA_GUI_ANALOG_BAD
        const double normalized = std::clamp((static_cast<double>(x) - 40.0) / 240.0, 0.0, 1.0);
#if QA_GUI_ANALOG_BAD
        // Fault fixture deliberately discards ALL mid-range values.
        (void)setParamNormalized(kClickParam, normalized < 0.5 ? 0.0 : 1.0);
#else
        (void)setParamNormalized(kClickParam, normalized);
#endif
#else
        (void)x;
#endif
    }
    void clicked() {
#if QA_GUI_HOVER
        // A hover effect is not a button click: do not change any state.
        (void)0;
#elif QA_GUI_TOGGLE || QA_GUI_NESTED
        const auto current = getParamNormalized(kClickParam);
        (void)setParamNormalized(kClickParam, current >= 0.5 ? 0.0 : 1.0);
#elif !QA_GUI_INERT
        (void)setParamNormalized(kClickParam, 1.0);
#if QA_GUI_EXPORT_GOOD || QA_GUI_EXPORT_BAD
        // The GUI-facing controller can report the expected value
        // even when the exported PCM is wrong or the WAV is missing.
        (void)writeFixtureWav();
#elif QA_GUI_EXPORT_MIDI_GOOD || QA_GUI_EXPORT_MIDI_BAD
        (void)writeFixtureMidi();
#endif
#endif
    }
};

LRESULT CALLBACK ClickView::clickProc(HWND hwnd, UINT message, WPARAM w, LPARAM l) {
    auto* self = reinterpret_cast<ClickView*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    if (message == WM_NCCREATE) {
        auto* cs = reinterpret_cast<CREATESTRUCTW*>(l);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA,
                          reinterpret_cast<LONG_PTR>(cs->lpCreateParams));
        return TRUE;
    }
#if QA_GUI_HOVER
    if (message == WM_MOUSEMOVE && self) {
        self->hovered_ = true;
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;
    }
#endif
#if QA_GUI_NESTED
    if (message == WM_COMMAND && LOWORD(w) == 43001 &&
        HIWORD(w) == BN_CLICKED && self && self->owner_ &&
        reinterpret_cast<HWND>(l) == self->nestedButton_) {
        // P43 only the genuine Win32 BUTTON child notification may
        // change the parameter. Root-surface clicks intentionally do not.
        self->owner_->clicked();
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;
    }
#endif
    if (message == WM_KEYDOWN && (w == VK_SPACE || w == VK_RETURN) &&
        self && self->owner_) {
        // True native HWND keyboard input exercises the same semantic toggle
        // path as mouse input. The inert variant still ignores it and the
        // stale-paint variant still fails a visual oracle.
        self->owner_->clicked();
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;
    }
#if QA_GUI_ANALOG_GOOD || QA_GUI_ANALOG_BAD
    if (self && self->owner_ && message == WM_LBUTTONDOWN) {
        self->draggingAnalog_ = true;
        return 0;
    }
    if (self && self->owner_ && message == WM_MOUSEMOVE && self->draggingAnalog_
        && (w & MK_LBUTTON)) {
        self->owner_->analogAt(static_cast<short>(LOWORD(l)));
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;
    }
    if (self && self->owner_ && message == WM_LBUTTONUP) {
        if (self->draggingAnalog_) {
            self->owner_->analogAt(static_cast<short>(LOWORD(l)));
            self->draggingAnalog_ = false;
            InvalidateRect(hwnd, nullptr, TRUE);
        }
        return 0;
    }
#endif
    if (message == WM_LBUTTONUP && self && self->owner_) {
#if QA_GUI_PAINTED_ONLY
        // This genuinely custom-painted toggle exists *only* inside a
        // single HWND. It changes NO VST3 parameter or audio state.
        // P44 must detect its local pixels without inventing semantics.
        const int x = static_cast<short>(LOWORD(l));
        const int y = static_cast<short>(HIWORD(l));
        if (x >= 120 && x < 200 && y >= 65 && y < 115) {
            self->paintedActive_ = !self->paintedActive_;
            InvalidateRect(hwnd, nullptr, TRUE);
        }
#elif !QA_GUI_NESTED
        self->owner_->clicked();
        InvalidateRect(hwnd, nullptr, TRUE);
#endif
        return 0;
    }
    if (message == WM_PAINT) {
        PAINTSTRUCT ps{};
        const HDC dc = BeginPaint(hwnd, &ps);
        RECT rect{};
        GetClientRect(hwnd, &rect);
        const bool active = self && self->owner_ &&
            self->owner_->getParamNormalized(kClickParam) > 0.5;
        const HBRUSH fill = CreateSolidBrush(
            (active && !QA_GUI_STALE_PAINT) ||
            (QA_GUI_HOVER && self && self->hovered_)
                ? RGB(12, 142, 85) : RGB(30, 36, 48));
        FillRect(dc, &rect, fill);
        DeleteObject(fill);
#if QA_GUI_PAINTED_ONLY
        RECT painted{120, 65, 200, 115};
        const HBRUSH patch = CreateSolidBrush(
            self && self->paintedActive_ ? RGB(12, 142, 85) : RGB(70, 80, 90));
        FillRect(dc, &painted, patch);
        DeleteObject(patch);
#else
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(240, 192, 110));
#if QA_GUI_ANALOG_GOOD || QA_GUI_ANALOG_BAD
        const wchar_t* label = L"P52 ANALOG CONTROL";
#else
        const wchar_t* label = L"P04 CLICK TEST";
#endif
        DrawTextW(dc, label, -1, &rect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
#endif
        EndPaint(hwnd, &ps);
        return 0;
    }
    return DefWindowProcW(hwnd, message, w, l);
}

tresult PLUGIN_API ClickView::attached(void* parent, FIDString type) {
    if (isPlatformTypeSupported(type) != kResultTrue || !parent) return kResultFalse;
    if (CPluginView::attached(parent, type) != kResultTrue) return kResultFalse;
    static const wchar_t className[] = L"125A_P04_NativeClickSurface";
    WNDCLASSW wc{};
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.lpfnWndProc = &ClickView::clickProc;
    wc.lpszClassName = className;
    wc.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32649));
    if (!RegisterClassW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        return kResultFalse;
    clickWindow_ = CreateWindowExW(0, className, L"P04", WS_CHILD | WS_VISIBLE,
                                   0, 0, 320, 180, static_cast<HWND>(parent), nullptr,
                                   GetModuleHandleW(nullptr), this);
#if QA_GUI_NESTED
    if (clickWindow_) {
        // Standard native button is a child of the child-editor HWND.
        // A mouse message delivered only to the editor surface will
        // fail to operate this control: this tests true nested hit routing.
        nestedButton_ = CreateWindowExW(
            0, L"BUTTON", L"NESTED ON/OFF",
            WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
            120, 65, 80, 50, clickWindow_,
            reinterpret_cast<HMENU>(static_cast<INT_PTR>(43001)),
            GetModuleHandleW(nullptr), nullptr);
        if (!nestedButton_) {
            DestroyWindow(clickWindow_);
            clickWindow_ = nullptr;
        }
    }
#endif
    return clickWindow_ ? kResultTrue : kResultFalse;
}
tresult PLUGIN_API ClickView::removed() {
    if (nestedButton_) {
        DestroyWindow(nestedButton_);
        nestedButton_ = nullptr;
    }
    if (clickWindow_) {
        DestroyWindow(clickWindow_);
        clickWindow_ = nullptr;
    }
    return CPluginView::removed();
}
} // namespace

BEGIN_FACTORY_DEF("125A Internal Test Infrastructure",
                  "https://github.com/challanger2000",
                  "qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(kProcessorCID), PClassInfo::kManyInstances,
           kVstAudioEffectClass, kName, Vst::kDistributable,
           "Instrument", "0.1.0", kVstVersionString, Processor::createInstance)
DEF_CLASS2(INLINE_UID_FROM_FUID(kControllerCID), PClassInfo::kManyInstances,
           kVstComponentControllerClass, "125A GUI Fixture Controller",
           0, "", "0.1.0", kVstVersionString, Controller::createInstance)
END_FACTORY
