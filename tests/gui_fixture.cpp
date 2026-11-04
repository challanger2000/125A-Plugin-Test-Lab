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

#include <cstring>
using namespace Steinberg;
using namespace Steinberg::Vst;

#ifndef QA_GUI_INERT
#define QA_GUI_INERT 0
#endif

namespace {
constexpr ParamID kClickParam = 9001;
#if QA_GUI_INERT
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
    explicit ClickView(Controller* owner) : CPluginView(&kBounds), owner_(owner) {}
    tresult PLUGIN_API isPlatformTypeSupported(FIDString type) override {
        return type && std::strcmp(type, kPlatformTypeHWND) == 0 ? kResultTrue : kResultFalse;
    }
    tresult PLUGIN_API attached(void* parent, FIDString type) override;
    tresult PLUGIN_API removed() override;
private:
    static constexpr ViewRect kBounds{0,0,320,180};
    static LRESULT CALLBACK clickProc(HWND hwnd, UINT message, WPARAM w, LPARAM l);
    Controller* owner_{};
    HWND clickWindow_{};
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
    IPlugView* PLUGIN_API createView(FIDString type) override {
        if (!type || std::strcmp(type, ViewType::kEditor) != 0) return nullptr;
        return new ClickView(this);
    }
    void clicked() {
#if !QA_GUI_INERT
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
    if (message == WM_LBUTTONUP && self && self->owner_) {
        self->owner_->clicked();
        InvalidateRect(hwnd, nullptr, TRUE);
        return 0;
    }
    if (message == WM_PAINT) {
        PAINTSTRUCT ps{};
        const HDC dc = BeginPaint(hwnd, &ps);
        RECT rect{};
        GetClientRect(hwnd, &rect);
        const HBRUSH fill = CreateSolidBrush(RGB(30, 36, 48));
        FillRect(dc, &rect, fill);
        DeleteObject(fill);
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(240, 192, 110));
        const wchar_t* label = L"P04 CLICK TEST";
        DrawTextW(dc, label, -1, &rect, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
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
    wc.hCursor = LoadCursorW(nullptr, IDC_HAND);
    if (!RegisterClassW(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        return kResultFalse;
    clickWindow_ = CreateWindowExW(0, className, L"P04", WS_CHILD | WS_VISIBLE,
                                   0, 0, 320, 180, static_cast<HWND>(parent), nullptr,
                                   GetModuleHandleW(nullptr), this);
    return clickWindow_ ? kResultTrue : kResultFalse;
}
tresult PLUGIN_API ClickView::removed() {
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
