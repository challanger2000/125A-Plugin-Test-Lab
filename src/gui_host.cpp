// P04 minimal Win32 editor host, with observable native mouse-to-VST3
// parameter assertion. No vendor DAW dependency or product source code.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "base/source/fobject.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstmessage.h"
#include "pluginterfaces/vst/vsttypes.h"

#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>

using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;

namespace {
constexpr wchar_t kWindowClass[] = L"125A_Test_Lab_P04_EditorHost";

void require(bool value, const char* error) {
    if (!value) throw std::runtime_error(error);
}

LRESULT CALLBACK windowProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    return DefWindowProcW(hwnd, msg, wp, lp);
}

void pump(DWORD milliseconds) {
    const auto until = GetTickCount64() + milliseconds;
    MSG msg{};
    do {
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        Sleep(2);
    } while (GetTickCount64() < until);
}

class HostFrame final : public FObject, public IPlugFrame {
public:
    explicit HostFrame(HWND hwnd) : hwnd_(hwnd) {}
    tresult PLUGIN_API resizeView(IPlugView* view, ViewRect* desired) override {
        if (!view || !desired || !hwnd_ || desired->getWidth() <= 0 ||
            desired->getHeight() <= 0 || desired->getWidth() > 8192 ||
            desired->getHeight() > 8192) return kInvalidArgument;
        RECT outer{0, 0, desired->getWidth(), desired->getHeight()};
        const DWORD style = static_cast<DWORD>(GetWindowLongPtrW(hwnd_, GWL_STYLE));
        const DWORD exStyle = static_cast<DWORD>(GetWindowLongPtrW(hwnd_, GWL_EXSTYLE));
        if (!AdjustWindowRectEx(&outer, style, FALSE, exStyle)) return kResultFalse;
        if (!SetWindowPos(hwnd_, nullptr, 0, 0, outer.right - outer.left,
                          outer.bottom - outer.top,
                          SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE))
            return kResultFalse;
        return view->onSize(desired);
    }

    OBJ_METHODS(HostFrame, FObject)
    DEFINE_INTERFACES
        DEF_INTERFACE(IPlugFrame)
    END_DEFINE_INTERFACES(FObject)
    REFCOUNT_METHODS(FObject)
private:
    HWND hwnd_{};
};

class Window final {
public:
    explicit Window(ViewRect bounds) {
        WNDCLASSW wc{};
        wc.hInstance = GetModuleHandleW(nullptr);
        wc.lpfnWndProc = windowProc;
        wc.lpszClassName = kWindowClass;
        wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
        require(RegisterClassW(&wc) || GetLastError() == ERROR_CLASS_ALREADY_EXISTS,
                "Win32 class registration failed");
        require(bounds.getWidth() >= 100 && bounds.getHeight() >= 60 &&
                bounds.getWidth() <= 8192 && bounds.getHeight() <= 8192,
                "Plugin editor reports invalid window geometry");
        RECT outer{0, 0, bounds.getWidth(), bounds.getHeight()};
        require(AdjustWindowRectEx(&outer, WS_OVERLAPPEDWINDOW, FALSE, WS_EX_TOOLWINDOW) != 0,
                "Window size adjustment failed");
        hwnd_ = CreateWindowExW(WS_EX_TOOLWINDOW, kWindowClass,
                               L"125A Plugin Test Lab - P04",
                               WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
                               outer.right - outer.left, outer.bottom - outer.top,
                               nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
        require(hwnd_ != nullptr, "Failed to create real Win32 host window");
    }
    ~Window() {if (hwnd_) DestroyWindow(hwnd_);}
    Window(const Window&) = delete;
    Window& operator=(const Window&) = delete;
    HWND get() const {return hwnd_;}
private:
    HWND hwnd_{};
};

struct Controller {
    IEditController* ptr = nullptr;
    bool separate = false;
    bool connected = false;
    IConnectionPoint* componentCP = nullptr;
    IConnectionPoint* controllerCP = nullptr;

    void close() {
        if (connected) {
            if (componentCP) (void)componentCP->disconnect(controllerCP);
            if (controllerCP) (void)controllerCP->disconnect(componentCP);
        }
        connected = false;
        if (componentCP) componentCP->release();
        if (controllerCP) controllerCP->release();
        componentCP = nullptr;
        controllerCP = nullptr;
        if (ptr) {
            if (separate) (void)ptr->terminate();
            ptr->release();
            ptr = nullptr;
        }
    }
    ~Controller() {close();}
};

void acquireController(IComponent* component,
                       const PluginFactory& factory,
                       HostApplication* context,
                       Controller& dest) {
    if (component->queryInterface(IEditController::iid,
                                  reinterpret_cast<void**>(&dest.ptr)) == kResultTrue &&
        dest.ptr) return;
    TUID uid{};
    require(component->getControllerClassId(uid) == kResultTrue,
            "component has no editor controller class");
    auto separate = factory.createInstance<IEditController>(VST3::UID(uid));
    require(static_cast<bool>(separate), "cannot construct VST3 editor controller");
    dest.ptr = separate.take();
    require(dest.ptr->initialize(context) == kResultOk,
            "cannot initialize VST3 editor controller");
    dest.separate = true;
    const bool a = component->queryInterface(
        IConnectionPoint::iid, reinterpret_cast<void**>(&dest.componentCP)) == kResultTrue;
    const bool b = dest.ptr->queryInterface(
        IConnectionPoint::iid, reinterpret_cast<void**>(&dest.controllerCP)) == kResultTrue;
    if (a && b && dest.componentCP && dest.controllerCP) {
        const auto first = dest.componentCP->connect(dest.controllerCP);
        const auto second = dest.controllerCP->connect(dest.componentCP);
        if (first == kResultTrue && second == kResultTrue)
            dest.connected = true;
        else {
            if (first == kResultTrue) (void)dest.componentCP->disconnect(dest.controllerCP);
            if (second == kResultTrue) (void)dest.controllerCP->disconnect(dest.componentCP);
        }
    }
}

void runView(IEditController* controller, int cycle, bool checkClick, ParamID paramID) {
    IPlugView* view = controller->createView(ViewType::kEditor);
    if (!view) throw std::runtime_error("plugin supplies no editor view (INCONCLUSIVE)");
    bool frameSet = false;
    bool attached = false;
    HostFrame* frame = nullptr;

    try {
        ViewRect size{};
        require(view->getSize(&size) == kResultTrue, "IPlugView::getSize failed");
        require(view->isPlatformTypeSupported(kPlatformTypeHWND) == kResultTrue,
                "Plugin view does not support Win32 HWND");
        Window window(size);
        frame = new HostFrame(window.get());
        require(view->setFrame(frame) == kResultTrue, "IPlugView::setFrame failed");
        frameSet = true;
        require(view->attached(window.get(), kPlatformTypeHWND) == kResultTrue,
                "IPlugView::attached(HWND) failed");
        attached = true;
        ShowWindow(window.get(), SW_SHOWNA);
        UpdateWindow(window.get());
        pump(75);

        if (checkClick) {
            require(std::isfinite(controller->getParamNormalized(paramID)),
                    "Parameter is not supported by VST3 edit controller");
            require(controller->setParamNormalized(paramID, 0.0) == kResultTrue,
                    "Cannot initialize expected GUI parameter");
            const auto before = controller->getParamNormalized(paramID);
            require(before == 0.0, "Click parameter failed reset to zero");
            HWND child = GetWindow(window.get(), GW_CHILD);
            require(child != nullptr && IsWindow(child), "GUI has no native child HWND");
            RECT rect{};
            require(GetClientRect(child, &rect) != 0 && rect.right > 10 && rect.bottom > 10,
                    "GUI child has invalid mouse coordinates");
            const LPARAM coordinate = MAKELPARAM(rect.right / 2, rect.bottom / 2);
            // Direct native HWND messages, not a fake controller parameter write.
            SendMessageW(child, WM_MOUSEMOVE, 0, coordinate);
            SendMessageW(child, WM_LBUTTONDOWN, MK_LBUTTON, coordinate);
            SendMessageW(child, WM_LBUTTONUP, 0, coordinate);
            pump(40);
            const auto after = controller->getParamNormalized(paramID);
            require(std::isfinite(after) && after == 1.0,
                    "GUI parameter unchanged after native click");
            std::cout << "[PASS] P04 cycle " << cycle
                      << ": native click changed VST3 parameter " << paramID
                      << " from " << before << " to " << after << '\n';
        } else {
            std::cout << "[PASS] P04 cycle " << cycle
                      << ": real editor HWND attached and message pump operated; "
                      << size.getWidth() << "x" << size.getHeight() << '\n';
        }

        require(view->removed() == kResultTrue, "IPlugView::removed failed");
        attached = false;
        require(view->setFrame(nullptr) == kResultTrue, "IPlugView::setFrame(nullptr) failed");
        frameSet = false;
        frame->release();
        frame = nullptr;
        pump(10);
    } catch (...) {
        if (attached) (void)view->removed();
        if (frameSet) (void)view->setFrame(nullptr);
        if (frame) frame->release();
        view->release();
        throw;
    }
    view->release();
}

int run(const std::string& pluginPath, bool checkClick, ParamID paramID) {
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(static_cast<bool>(module), ("Cannot load VST3: " + error).c_str());

    HostApplication host;
    auto factory = module->getFactory();
    factory.setHostContext(&host);

    for (const auto& cls : factory.classInfos()) {
        if (cls.category() != kVstAudioEffectClass) continue;
        auto component = factory.createInstance<IComponent>(cls.ID());
        require(static_cast<bool>(component), "VST3 audio processor instantiation failed");
        require(component->initialize(&host) == kResultOk,
                "VST3 processor initialization failed");
        {
            Controller controller;
            acquireController(component.get(), factory, &host, controller);
            for (int cycle = 1; cycle <= 2; ++cycle)
                runView(controller.ptr, cycle, checkClick, paramID);
            controller.close();
        }
        require(component->terminate() == kResultOk,
                "VST3 component terminate failed");
        std::cout << "[PASS] P04 two actual editor attach/message/input/detach cycles\n";
        return 0;
    }
    throw std::runtime_error("No VST3 audio class found");
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 3 && std::string(argv[1]) == "--probe")
            return run(argv[2], false, 0);
        if (argc == 4 && std::string(argv[1]) == "--prove-click")
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])));
        std::cerr << "Usage: 125A_Test_Lab_GUI --probe <plugin.vst3>\n"
                  << "       125A_Test_Lab_GUI --prove-click <plugin.vst3> <param-id>\n";
        return 2;
    } catch (const std::exception& ex) {
        const std::string message = ex.what();
        if (message.find("(INCONCLUSIVE)") != std::string::npos) {
            std::cerr << "[INCONCLUSIVE] " << message << '\n';
            return 10;
        }
        std::cerr << "[FAIL] " << message << '\n';
        return 1;
    }
}
