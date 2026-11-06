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
#include <cstring>
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

namespace {
constexpr ParamID kClickParam = 9001;
#if QA_GUI_PAINTED_ONLY
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
};

class Controller final : public EditController {
public:
    static FUnknown* createInstance(void*) {return static_cast<IEditController*>(new Controller);}
    tresult PLUGIN_API initialize(FUnknown* context) override {
        if (EditController::initialize(context) != kResultOk) return kResultFalse;
        parameters.addParameter(STR16("Clicked"), nullptr, 1, 0.,
                                ParameterInfo::kCanAutomate, kClickParam);
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
    void clicked() {
#if QA_GUI_HOVER
        // A hover effect is not a button click: do not change any state.
        (void)0;
#elif QA_GUI_TOGGLE || QA_GUI_NESTED
        const auto current = getParamNormalized(kClickParam);
        (void)setParamNormalized(kClickParam, current >= 0.5 ? 0.0 : 1.0);
#elif !QA_GUI_INERT
        (void)setParamNormalized(kClickParam, 1.0);
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
        const wchar_t* label = L"P04 CLICK TEST";
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
