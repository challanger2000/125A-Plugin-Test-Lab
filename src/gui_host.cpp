// P04 minimal Win32 editor host, with observable native mouse-to-VST3
// parameter assertion. No vendor DAW dependency or product source code.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <ole2.h>
#include <shellapi.h>
#include <objbase.h> // CoInitializeEx, COINIT_APARTMENTTHREADED, CoUninitialize
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "base/source/fobject.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstprocesscontext.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstmessage.h"
#include "pluginterfaces/vst/vsttypes.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"

#include <filesystem>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <vector>

#include <algorithm>
#include <array>
#include <cwchar>
#include <atomic>
#include <thread>
#include <memory>
#include <cstring>
#include <chrono>
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


// Windows VSTGUI uses COM-backed WIC/Direct2D resources. A real DAW normally
// creates its UI thread COM apartment before constructing plugin editors.
// The P04 synthetic HWND fixture did not need COM; the actual VSTGUI does.
class ComApartment final {
public:
    ComApartment() {
        const HRESULT result = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
        require(SUCCEEDED(result),
                "P09 COM STA initialization failed before VSTGUI editor attach");
        initialized_ = true;
        std::cout << "[INFO] GUI host initialized Win32 COM STA apartment\n";
    }
    ~ComApartment() {
        if (initialized_) CoUninitialize();
    }
    ComApartment(const ComApartment&) = delete;
    ComApartment& operator=(const ComApartment&) = delete;
private:
    bool initialized_{false};
};

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
        wc.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32512));
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
            "component has no editor controller class (INCONCLUSIVE)");
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

// Capture the pixels actually painted by the native HWND editor, not an
// approximate screenshot synthesized from controller parameter values.
void captureEditorBmp(HWND nativeChild, const std::filesystem::path& path) {
    RECT rect{};
    require(IsWindow(nativeChild) && GetClientRect(nativeChild, &rect) != 0,
            "GUI snapshot HWND or client rectangle missing");
    const int width = rect.right - rect.left;
    const int height = rect.bottom - rect.top;
    require(width > 0 && width <= 4096 && height > 0 && height <= 4096,
            "GUI snapshot dimensions invalid or excessive");
    const HDC source = GetDC(nativeChild);
    require(source != nullptr, "GUI snapshot cannot obtain native HWND DC");
    const HDC memory = CreateCompatibleDC(source);
    HBITMAP bitmap = memory ? CreateCompatibleBitmap(source, width, height) : nullptr;
    HGDIOBJ old = bitmap ? SelectObject(memory, bitmap) : nullptr;
    const bool selectionOK = old && old != HGDI_ERROR;
    const bool copied = selectionOK &&
        BitBlt(memory, 0, 0, width, height, source, 0, 0, SRCCOPY) != 0;
    if (selectionOK) (void)SelectObject(memory, old);
    BITMAPINFO info{};
    info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    info.bmiHeader.biWidth = width;
    info.bmiHeader.biHeight = -height;  // top-down, matches GUI coordinates
    info.bmiHeader.biPlanes = 1;
    info.bmiHeader.biBitCount = 32;
    info.bmiHeader.biCompression = BI_RGB;
    const auto byteCount = static_cast<std::size_t>(width) *
                           static_cast<std::size_t>(height) * 4U;
    std::vector<std::uint8_t> pixels(byteCount);
    const bool extracted = copied && GetDIBits(
        memory, bitmap, 0, static_cast<UINT>(height),
        pixels.data(), &info, DIB_RGB_COLORS) == height;
    if (bitmap) DeleteObject(bitmap);
    if (memory) DeleteDC(memory);
    ReleaseDC(nativeChild, source);
    require(extracted, "GUI snapshot real Win32 pixels unavailable");
    BITMAPFILEHEADER file{};
    file.bfType = 0x4D42;
    file.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
    file.bfSize = static_cast<DWORD>(file.bfOffBits + byteCount);
    info.bmiHeader.biSizeImage = static_cast<DWORD>(byteCount);
    if (!path.parent_path().empty())
        std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    require(out.good(), "GUI snapshot output BMP cannot be opened");
    out.write(reinterpret_cast<const char*>(&file), sizeof(file));
    out.write(reinterpret_cast<const char*>(&info.bmiHeader), sizeof(BITMAPINFOHEADER));
    out.write(reinterpret_cast<const char*>(pixels.data()),
              static_cast<std::streamsize>(pixels.size()));
    require(out.good(), "GUI snapshot BMP write failed");
    std::cout << "[PASS] real native HWND BMP captured " << width
              << "x" << height << ": " << path.string() << '\n';
}

void runView(IEditController* controller, int cycle, bool checkClick, ParamID paramID,
             int clickX = -1, int clickY = -1, double expectedValue = 1.0,
             const std::filesystem::path& screenshot = {},
             double initialNormalized = 0.0) {
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
            require(std::isfinite(initialNormalized) &&
                    initialNormalized >= 0.0 && initialNormalized <= 1.0,
                    "Invalid initial GUI parameter value");
            require(controller->setParamNormalized(paramID, initialNormalized) == kResultTrue,
                    "Cannot initialize expected GUI parameter");
            const auto before = controller->getParamNormalized(paramID);
            require(std::isfinite(before) &&
                    std::abs(before - initialNormalized) < 0.00001,
                    "Click parameter failed reset to requested initial value");
            HWND child = GetWindow(window.get(), GW_CHILD);
            require(child != nullptr && IsWindow(child), "GUI has no native child HWND");
            RECT rect{};
            require(GetClientRect(child, &rect) != 0 && rect.right > 10 && rect.bottom > 10,
                    "GUI child has invalid mouse coordinates");
            require(std::isfinite(expectedValue) && expectedValue >= 0.0 &&
                    expectedValue <= 1.0 && expectedValue != before,
                    "Invalid or non-observable expected GUI control result");
            const int x = clickX < 0 ? rect.right / 2 : clickX;
            const int y = clickY < 0 ? rect.bottom / 2 : clickY;
            require(x >= 0 && x < rect.right && y >= 0 && y < rect.bottom,
                    "GUI click location outside native editor HWND");
            const LPARAM coordinate = MAKELPARAM(x, y);
            // Direct native HWND messages, not a fake controller parameter write.
            SendMessageW(child, WM_MOUSEMOVE, 0, coordinate);
            SendMessageW(child, WM_LBUTTONDOWN, MK_LBUTTON, coordinate);
            SendMessageW(child, WM_LBUTTONUP, 0, coordinate);
            pump(40);
            const auto after = controller->getParamNormalized(paramID);
            require(std::isfinite(after) && std::abs(after - expectedValue) < 0.00001,
                    "GUI parameter unchanged after native click");
            std::cout << "[PASS] P04 cycle " << cycle
                      << ": native click changed VST3 parameter " << paramID
                      << " from " << before << " to " << after << '\n';
        } else {
            std::cout << "[PASS] P04 cycle " << cycle
                      << ": real editor HWND attached and message pump operated; "
                      << size.getWidth() << "x" << size.getHeight() << '\n';
        }

        if (!screenshot.empty() && cycle == 1) {
            HWND child = GetWindow(window.get(), GW_CHILD);
            require(child && IsWindow(child), "GUI snapshot has no painted child HWND");
            InvalidateRect(child, nullptr, TRUE);
            require(UpdateWindow(child) != FALSE,
                    "GUI snapshot failed to repaint actual child HWND");
            pump(30);
            captureEditorBmp(child, screenshot);
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

// P37: Run a declared ordered click/drag workflow in ONE actual VST3 editor
// instance.  Unlike isolated click fixtures, each action must start from the
// previous action's real controller state.  No product-specific code or
// guessed UI locations are embedded in this reusable native host.
struct WorkflowStep {
    int index{};
    bool drag{};
    int x1{}, y1{}, x2{}, y2{};
    ParamID parameter{};
    double before{}, expected{};
    bool screenshot{};
    bool visualOnly{};
    bool keyboard{};
    int keyCode{};
    int modifiers{};
};
struct WorkflowInput {
    std::vector<std::pair<ParamID, double>> initial;
    std::vector<WorkflowStep> steps;
};

std::vector<std::string> splitWorkflowRow(const std::string& input) {
    std::vector<std::string> parts;
    std::istringstream stream(input);
    std::string part;
    while (std::getline(stream, part, '\t')) parts.push_back(part);
    // Do not silently discard trailing empty fields.
    if (!input.empty() && input.back() == '\t') parts.emplace_back();
    return parts;
}
int workflowInt(const std::string& data, int max) {
    require(!data.empty() && data.size() <= 12 &&
            std::all_of(data.begin(), data.end(), [](char c) {
                return c >= '0' && c <= '9';
            }), "invalid workflow unsigned integer");
    const auto value = std::stoull(data);
    require(value <= static_cast<unsigned long long>(max),
            "out-of-range workflow integer");
    return static_cast<int>(value);
}
ParamID workflowParam(const std::string& data) {
    require(!data.empty() && data.size() <= 10 &&
            std::all_of(data.begin(), data.end(), [](char c) {
                return c >= '0' && c <= '9';
            }), "invalid workflow parameter ID");
    const auto value = std::stoull(data);
    require(value <= 4294967295ULL, "out-of-range workflow parameter ID");
    return static_cast<ParamID>(value);
}
double workflowValue(const std::string& data) {
    require(!data.empty() && data.size() <= 32, "workflow value missing");
    std::size_t length{};
    const auto value = std::stod(data, &length);
    require(length == data.size() && std::isfinite(value) &&
            value >= 0.0 && value <= 1.0,
            "invalid workflow normalized parameter value");
    return value;
}
WorkflowInput parseWorkflow(const std::filesystem::path& path) {
    std::ifstream input(path);
    require(bool(input), "cannot open approved GUI workflow");
    auto row = [&]() {
        std::string line;
        require(bool(std::getline(input, line)), "truncated GUI workflow");
        if (!line.empty() && line.back() == '\r') line.pop_back();
        require(line.size() <= 512, "oversized GUI workflow row");
        return splitWorkflowRow(line);
    };
    require(row() == std::vector<std::string>{"format", "125A-GUI-WORKFLOW-v1"},
            "unrecognized workflow schema");
    auto head = row();
    require(head.size() == 2 && head[0] == "init_count",
            "missing exact workflow initial-state count");
    const int initCount = workflowInt(head[1], 64);
    WorkflowInput workflow;
    for (int n = 0; n < initCount; ++n) {
        auto parts = row();
        require(parts.size() == 3 && parts[0] == "init", "malformed workflow initial state");
        const auto id = workflowParam(parts[1]);
        require(std::none_of(workflow.initial.begin(), workflow.initial.end(),
                             [id](const auto& v) { return v.first == id; }),
                "duplicate workflow initial parameter");
        workflow.initial.emplace_back(id, workflowValue(parts[2]));
    }
    head = row();
    require(head.size() == 2 && head[0] == "step_count",
            "missing workflow action count");
    const int count = workflowInt(head[1], 64);
    require(count >= 1, "GUI workflow requires actions");
    int screenshots = 0;
    for (int i = 0; i < count; ++i) {
        const auto parts = row();
        require(parts.size() == 11 && parts[0] == "step",
                "malformed GUI workflow action");
        WorkflowStep step;
        step.index = workflowInt(parts[1], 63);
        require(step.index == i, "missing, duplicated or out-of-order workflow action");
        require(parts[2] == "click" || parts[2] == "drag" || parts[2] == "key",
                "unsupported GUI workflow action");
        step.drag = parts[2] == "drag";
        step.keyboard = parts[2] == "key";
        step.x1 = workflowInt(parts[3], 8191);
        step.y1 = workflowInt(parts[4], 8191);
        step.x2 = workflowInt(parts[5], 8191);
        step.y2 = workflowInt(parts[6], 8191);
        if (step.keyboard) {
            // For key actions, payload columns 5/6 carry the virtual-key
            // and modifier bitmask rather than pointer destination.
            step.keyCode = step.x2;
            step.modifiers = step.y2;
            require(step.keyCode >= 8 && step.keyCode <= 255 &&
                    step.modifiers <= 7 &&
                    step.keyCode != VK_LWIN && step.keyCode != VK_RWIN,
                    "invalid or system-level GUI workflow key");
        } else if (!step.drag) {
            require(step.x1 == step.x2 && step.y1 == step.y2,
                    "click workflow action has different endpoints");
        }
        step.visualOnly = parts[7] == "-";
        if (step.visualOnly) {
            require(parts[8] == "-" && parts[9] == "-",
                    "visual-only GUI action cannot invent VST3 controller values");
        } else {
            step.parameter = workflowParam(parts[7]);
            step.before = workflowValue(parts[8]);
            step.expected = workflowValue(parts[9]);
            require(std::abs(step.before - step.expected) > 0.00001,
                    "GUI workflow requires an observable controller transition");
        }
        step.screenshot = workflowInt(parts[10], 1) == 1;
        require(!step.visualOnly || step.screenshot,
                "visual-only GUI action requires before and after native pixels");
        if (step.screenshot) ++screenshots;
        workflow.steps.push_back(step);
    }
    require(screenshots <= 16, "too many GUI workflow screenshots");
    std::string extra;
    require(!std::getline(input, extra), "unexpected extra GUI workflow actions");
    return workflow;
}

// P41: Blind, bounded observation of ONE actual native UI click in a
// disposable plugin instance.  The result is evidence for later control
// mapping, never proof that a product's undocumented buttons work correctly.
// One click per process ensures independent initial controller/UI state.
int exploreOneGuiClick(const std::string& pluginPath, int clickX, int clickY,
                       bool performClick, const std::filesystem::path& evidence,
                       const std::filesystem::path& baselineFirst,
                       const std::filesystem::path& baselineSecond,
                       const std::filesystem::path& observed) {
    require(clickX >= 0 && clickX <= 8191 && clickY >= 0 && clickY <= 8191,
            "P41 unsafe click coordinates");
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(bool(module), "P41 could not load real VST3 module");
    HostApplication app;
    auto factory = module->getFactory();
    factory.setHostContext(&app);
    int classes = 0;
    for (const auto& cls : factory.classInfos()) {
        if (cls.category() != kVstAudioEffectClass) continue;
        ++classes;
        require(classes == 1,
                "P41 multiple audio classes require explicit selection (INCONCLUSIVE)");
        auto component = factory.createInstance<IComponent>(cls.ID());
        require(bool(component) && component->initialize(&app) == kResultOk,
                "P41 cannot initialize real VST3 processor");
        {
            Controller controller;
            acquireController(component.get(), factory, &app, controller);
            const int32 count = controller.ptr->getParameterCount();
            require(count >= 0 && count <= 8192,
                    "P41 invalid controller parameter count");
            struct ValueRow {
                int32 index;
                ParamID id;
                double initial;
                double observed;
            };
            std::vector<ValueRow> rows;
            rows.reserve(static_cast<std::size_t>(count));
            std::vector<ParamID> seen;
            seen.reserve(static_cast<std::size_t>(count));
            for (int32 i = 0; i < count; ++i) {
                ParameterInfo info{};
                require(controller.ptr->getParameterInfo(i, info) == kResultTrue,
                        "P41 cannot enumerate all VST3 controller metadata");
                require(std::find(seen.begin(), seen.end(), info.id) == seen.end(),
                        "P41 controller returned duplicate parameter ID");
                seen.push_back(info.id);
                const auto value = controller.ptr->getParamNormalized(info.id);
                require(std::isfinite(value) && value >= 0.0 && value <= 1.0,
                        "P41 initial parameter value invalid");
                rows.push_back({i, info.id, value, -1.0});
            }
            IPlugView* view = controller.ptr->createView(ViewType::kEditor);
            require(view != nullptr, "P41 VST3 supplies no GUI editor (INCONCLUSIVE)");
            HostFrame* frame = nullptr;
            bool frameSet = false, attached = false;
            try {
                ViewRect size{};
                require(view->getSize(&size) == kResultTrue,
                        "P41 editor cannot report dimensions");
                require(view->isPlatformTypeSupported(kPlatformTypeHWND) == kResultTrue,
                        "P41 editor does not support Windows HWND (INCONCLUSIVE)");
                Window window(size);
                frame = new HostFrame(window.get());
                require(view->setFrame(frame) == kResultTrue,
                        "P41 cannot set real editor frame");
                frameSet = true;
                require(view->attached(window.get(), kPlatformTypeHWND) == kResultTrue,
                        "P41 cannot attach real VST3 editor");
                attached = true;
                ShowWindow(window.get(), SW_SHOWNA);
                UpdateWindow(window.get());
                pump(100);
                const HWND child = GetWindow(window.get(), GW_CHILD);
                require(child && IsWindow(child),
                        "P41 real plugin editor child HWND missing");
                RECT rect{};
                require(GetClientRect(child, &rect) && rect.right > 0 &&
                        rect.bottom > 0 && rect.right <= 4096 &&
                        rect.bottom <= 4096, "P41 invalid real editor geometry");
                require(clickX < rect.right && clickY < rect.bottom,
                        "P41 click would fall outside real editor");
                InvalidateRect(child, nullptr, TRUE);
                (void)UpdateWindow(child);
                pump(40);
                captureEditorBmp(child, baselineFirst);
                pump(80);
                captureEditorBmp(child, baselineSecond);
                // Send the SAME mouse motion to both modes: a hover
                // highlight must NOT be misattributed to a click. Only
                // the real-click run receives button down/up. Both modes
                // keep exactly the same dwell and repaint timing.
                const LPARAM point = MAKELPARAM(clickX, clickY);
                SendMessageW(child, WM_MOUSEMOVE, 0, point);
                if (performClick) {
                    SendMessageW(child, WM_LBUTTONDOWN, MK_LBUTTON, point);
                    SendMessageW(child, WM_LBUTTONUP, 0, point);
                }
                pump(100);
                InvalidateRect(child, nullptr, TRUE);
                (void)UpdateWindow(child);
                pump(50);
                captureEditorBmp(child, observed);
                for (auto& row : rows) {
                    row.observed = controller.ptr->getParamNormalized(row.id);
                    require(std::isfinite(row.observed) && row.observed >= 0.0 &&
                            row.observed <= 1.0,
                            "P41 observed invalid VST3 parameter after GUI click");
                }
                if (!evidence.parent_path().empty())
                    std::filesystem::create_directories(evidence.parent_path());
                std::ofstream out(evidence, std::ios::trunc);
                require(bool(out), "P41 cannot create native UI exploration evidence");
                out << std::setprecision(17);
                out << "format\t125A-GUI-EXPLORE-v2\n"
                    << "mode\t" << (performClick ? "click" : "sham") << "\n"
                    << "coordinate\t" << clickX << "\t" << clickY << "\n"
                    << "canvas\t" << rect.right << "\t" << rect.bottom << "\n"
                    << "param_count\t" << rows.size() << "\n";
                for (const auto& row : rows)
                    out << "param\t" << row.index << "\t" << row.id << "\t"
                        << row.initial << "\t" << row.observed << "\n";
                out << "end\tCOMPLETE\n";
                out.flush();
                require(out.good(), "P41 incomplete real native exploration evidence");
                require(view->removed() == kResultTrue, "P41 editor remove failed");
                attached = false;
                require(view->setFrame(nullptr) == kResultTrue,
                        "P41 clear editor frame failed");
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
            controller.close();
        }
        require(component->terminate() == kResultOk,
                "P41 real VST3 processor could not terminate");
        std::cout << "[OBSERVED] P42 disposable VST3 GUI "
                  << (performClick ? "click" : "sham no-click") << " at "
                  << clickX << "," << clickY << ", no product approval\n";
        return 0;
    }
    throw std::runtime_error("P41 no VST3 audio class (INCONCLUSIVE)");
}

int runGuiWorkflow(const std::string& pluginPath,
                   const std::filesystem::path& approvedActions,
                   const std::filesystem::path& report,
                   const std::filesystem::path& screenshots) {
    const auto input = parseWorkflow(approvedActions);
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(bool(module), "GUI workflow could not load actual VST3 module");
    HostApplication host;
    auto factory = module->getFactory();
    factory.setHostContext(&host);
    int classes = 0;
    for (const auto& cls : factory.classInfos()) {
        if (cls.category() != kVstAudioEffectClass) continue;
        ++classes;
        require(classes == 1, "GUI workflow requires a unique VST3 processor (INCONCLUSIVE)");
        auto component = factory.createInstance<IComponent>(cls.ID());
        require(bool(component) && component->initialize(&host) == kResultOk,
                "GUI workflow processor initialization failed");
        {
            Controller controller;
            acquireController(component.get(), factory, &host, controller);
            for (const auto& initial : input.initial) {
                require(controller.ptr->setParamNormalized(initial.first, initial.second) ==
                        kResultTrue, "GUI workflow cannot set declared initial parameter");
                const auto actual = controller.ptr->getParamNormalized(initial.first);
                require(std::isfinite(actual) &&
                        std::abs(actual - initial.second) <= 0.00001,
                        "GUI workflow initial-state parameter mismatch");
            }
            IPlugView* view = controller.ptr->createView(ViewType::kEditor);
            require(view != nullptr, "GUI workflow plugin has no editor (INCONCLUSIVE)");
            HostFrame* frame = nullptr;
            bool frameSet = false, attached = false;
            try {
                ViewRect size{};
                require(view->getSize(&size) == kResultTrue, "workflow editor getSize failed");
                require(view->isPlatformTypeSupported(kPlatformTypeHWND) == kResultTrue,
                        "workflow editor has no native HWND");
                Window window(size);
                frame = new HostFrame(window.get());
                require(view->setFrame(frame) == kResultTrue, "workflow setFrame failed");
                frameSet = true;
                require(view->attached(window.get(), kPlatformTypeHWND) == kResultTrue,
                        "workflow real editor attach failed");
                attached = true;
                ShowWindow(window.get(), SW_SHOWNA);
                UpdateWindow(window.get());
                pump(90);
                const HWND child = GetWindow(window.get(), GW_CHILD);
                require(child && IsWindow(child), "workflow cannot locate real editor child");
                RECT client{};
                require(GetClientRect(child, &client) && client.right > 0 && client.bottom > 0,
                        "GUI workflow invalid client dimensions");
                if (!report.parent_path().empty())
                    std::filesystem::create_directories(report.parent_path());
                std::ofstream out(report, std::ios::trunc);
                require(bool(out), "workflow result cannot be created");
                out << std::setprecision(17);
                out << "format\t125A-GUI-WORKFLOW-RESULT-v1\n"
                    << "step_count\t" << input.steps.size() << "\n";
                for (const auto& step : input.steps) {
                    require(step.x1 < client.right && step.y1 < client.bottom &&
                            (step.keyboard || (step.x2 < client.right &&
                                               step.y2 < client.bottom)),
                            "approved GUI workflow coordinates are outside actual HWND");
                    double before = 0.0;
                    if (step.visualOnly) {
                        // Without VST3 ParamID, only the independently supplied
                        // BEFORE and AFTER real painted pixels can assert meaning.
                        InvalidateRect(child, nullptr, TRUE);
                        (void)UpdateWindow(child);
                        pump(20);
                        captureEditorBmp(child, screenshots /
                                         (std::to_string(step.index) + ".before.bmp"));
                    } else {
                        before = controller.ptr->getParamNormalized(step.parameter);
                        require(std::isfinite(before) &&
                                std::abs(before - step.before) <= 0.00001,
                                "GUI workflow precondition mismatches previous action");
                    }
                    if (step.keyboard) {
                        // Send actual Win32 key down/up messages to the
                        // attached plugin HWND, not just edit a controller
                        // value. The test oracle still checks the result.
                        SetFocus(child);
                        SendMessageW(child, WM_MOUSEMOVE, 0,
                                     MAKELPARAM(step.x1, step.y1));
                        if (step.modifiers & 1)
                            SendMessageW(child, WM_KEYDOWN, VK_CONTROL, 0);
                        if (step.modifiers & 2)
                            SendMessageW(child, WM_KEYDOWN, VK_SHIFT, 0);
                        if (step.modifiers & 4)
                            SendMessageW(child, WM_SYSKEYDOWN, VK_MENU, 0);
                        const UINT down = (step.modifiers & 4) ?
                                          WM_SYSKEYDOWN : WM_KEYDOWN;
                        const UINT up = (step.modifiers & 4) ?
                                        WM_SYSKEYUP : WM_KEYUP;
                        SendMessageW(child, down,
                                     static_cast<WPARAM>(step.keyCode), 0);
                        SendMessageW(child, up,
                                     static_cast<WPARAM>(step.keyCode), 0);
                        if (step.modifiers & 4)
                            SendMessageW(child, WM_SYSKEYUP, VK_MENU, 0);
                        if (step.modifiers & 2)
                            SendMessageW(child, WM_KEYUP, VK_SHIFT, 0);
                        if (step.modifiers & 1)
                            SendMessageW(child, WM_KEYUP, VK_CONTROL, 0);
                    } else {
                        const LPARAM start = MAKELPARAM(step.x1, step.y1);
                        const LPARAM end = MAKELPARAM(step.x2, step.y2);
                        SendMessageW(child, WM_MOUSEMOVE, 0, start);
                        SendMessageW(child, WM_LBUTTONDOWN, MK_LBUTTON, start);
                        if (step.drag) {
                            SendMessageW(child, WM_MOUSEMOVE, MK_LBUTTON, end);
                            pump(10);
                        }
                        SendMessageW(child, WM_LBUTTONUP, 0, end);
                    }
                    pump(50);
                    if (step.screenshot) {
                        InvalidateRect(child, nullptr, TRUE);
                        (void)UpdateWindow(child);
                        pump(20);
                        const auto name = std::to_string(step.index) + ".bmp";
                        captureEditorBmp(child, screenshots / name);
                    }
                    const auto after = step.visualOnly ? 0.0 :
                                       controller.ptr->getParamNormalized(step.parameter);
                    const bool passed = step.visualOnly ||
                                        (std::isfinite(after) &&
                                         std::abs(after - step.expected) <= 0.00001);
                    out << "step\t" << step.index << "\t";
                    if (step.visualOnly) {
                        out << "-\t-\t-\tPASS\n";
                    } else {
                        out << step.parameter << "\t" << before << "\t"
                            << after << "\t" << (passed ? "PASS" : "FAIL") << "\n";
                    }
                    out.flush();
                    require(out.good(), "GUI workflow step evidence could not be written");
                    require(passed, "real GUI workflow control produced wrong value");
                }
                out << "end\tPASS\n";
                out.flush();
                require(out.good(), "GUI workflow final evidence unavailable");
                require(view->removed() == kResultTrue, "GUI workflow editor remove failed");
                attached = false;
                require(view->setFrame(nullptr) == kResultTrue,
                        "GUI workflow editor setFrame(nullptr) failed");
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
            controller.close();
        }
        require(component->terminate() == kResultOk,
                "GUI workflow processor terminate failed");
        std::cout << "[PASS] native GUI workflow checked " << input.steps.size()
                  << " ordered actions in one real VST3 editor\n";
        return 0;
    }
    throw std::runtime_error("GUI workflow no VST3 audio class (INCONCLUSIVE)");
}

int run(const std::string& pluginPath, bool checkClick, ParamID paramID,
        int clickX = -1, int clickY = -1, double expectedValue = 1.0,
        const std::filesystem::path& screenshot = {},
        double initialNormalized = 0.0) {
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
                runView(controller.ptr, cycle, checkClick, paramID,
                        clickX, clickY, expectedValue, screenshot,
                        initialNormalized);
            controller.close();
        }
        require(component->terminate() == kResultOk,
                "VST3 component terminate failed");
        std::cout << "[PASS] P04 two actual editor attach/message/input/detach cycles\n";
        return 0;
    }
    throw std::runtime_error("No VST3 audio class found");
}


// Non-destructive audit of every advertised VST3 controller parameter.
// This inventory does not infer corresponding physical GUI control locations.
int inventoryParameters(const std::string& pluginPath,
                        const std::filesystem::path& reportPath) {
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(bool(module), "Parameter inventory could not load VST3");
    HostApplication app;
    auto factory = module->getFactory();
    factory.setHostContext(&app);
    int audioClasses = 0;
    for(const auto& info : factory.classInfos()) {
        if(info.category() != kVstAudioEffectClass) continue;
        ++audioClasses;
        require(audioClasses == 1, "Multiple audio classes need explicit selection (INCONCLUSIVE)");
        auto component = factory.createInstance<IComponent>(info.ID());
        require(bool(component) && component->initialize(&app) == kResultOk,
                "Parameter inventory cannot initialize processor");
        {
            Controller controller;
            acquireController(component.get(), factory, &app, controller);
            const int32 count = controller.ptr->getParameterCount();
            require(count >= 0 && count <= 8192,
                    "VST3 controller returned invalid/oversized parameter count");
            struct Row {int32 index; ParamID id; int32 steps; double defaultValue;
                        double current; int32 flags;};
            std::vector<Row> rows;
            std::vector<ParamID> identifiers;
            rows.reserve(static_cast<size_t>(count));
            identifiers.reserve(static_cast<size_t>(count));
            for(int32 index=0; index<count; ++index) {
                ParameterInfo info{};
                require(controller.ptr->getParameterInfo(index, info) == kResultTrue,
                        "VST3 getParameterInfo failed for advertised index");
                require(info.stepCount >= 0 &&
                        std::isfinite(info.defaultNormalizedValue) &&
                        info.defaultNormalizedValue >= 0.0 &&
                        info.defaultNormalizedValue <= 1.0,
                        "Invalid VST3 parameter steps/default normalized value");
                require(std::find(identifiers.begin(),identifiers.end(),info.id)
                        == identifiers.end(), "Duplicate VST3 parameter ID");
                const auto current=controller.ptr->getParamNormalized(info.id);
                require(std::isfinite(current) && current >= 0.0 && current <= 1.0,
                        "Invalid current normalized VST3 parameter value");
                identifiers.push_back(info.id);
                rows.push_back({index,info.id,info.stepCount,
                                info.defaultNormalizedValue,current,info.flags});
            }
            if(!reportPath.parent_path().empty())
                std::filesystem::create_directories(reportPath.parent_path());
            std::ofstream out(reportPath,std::ios::trunc);
            require(bool(out),"Parameter inventory report file cannot be created");
            out.precision(17);
            out<<"format\t125A-GUI-PARAMS-v1\n";
            out<<"param_count\t"<<count<<"\n";
            for(const auto& row:rows)
                out<<"param\t"<<row.index<<"\t"<<row.id<<"\t"
                   <<row.steps<<"\t"<<row.defaultValue<<"\t"
                   <<row.current<<"\t"<<row.flags<<"\n";
            out.flush();
            require(out.good(),"Parameter inventory cannot write verified output");
            controller.close();
            std::cout<<"[PASS] VST3 parameter inventory verified "
                     <<count<<" unique parameters\n";
        }
        require(component->terminate()==kResultOk,
                "Parameter inventory component termination failed");
    }
    require(audioClasses == 1, "No unique VST3 processor class for inventory");
    return 0;
}

// Generic controller parameter sweep.  This probes *only* declared writable
// VST3 parameters in a disposable test instance.  It never guesses editor
// coordinates or asserts a relation between controller values and audio.
int sweepParameters(const std::string& pluginPath,
                    const std::filesystem::path& reportPath) {
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(bool(module), "Controller sweep could not load VST3");
    HostApplication app;
    auto factory = module->getFactory();
    factory.setHostContext(&app);
    int audioClasses = 0;
    for (const auto& cls : factory.classInfos()) {
        if (cls.category() != kVstAudioEffectClass) continue;
        ++audioClasses;
        require(audioClasses == 1,
                "Multiple audio classes require explicit selection (INCONCLUSIVE)");
        auto component = factory.createInstance<IComponent>(cls.ID());
        require(bool(component) && component->initialize(&app) == kResultOk,
                "Controller sweep cannot initialize processor");
        int tested = 0, skipped = 0, failed = 0, observations = 0;
        struct Observation {
            double requested{};
            double actual{};
            int result{};
        };
        struct Row {
            int32 index{};
            ParamID id{};
            int32 steps{};
            int32 flags{};
            double initial{};
            bool eligible{};
            bool restored{};
            bool passed{};
            std::vector<Observation> observations;
        };
        std::vector<Row> rows;
        {
            Controller controller;
            acquireController(component.get(), factory, &app, controller);
            const int32 count = controller.ptr->getParameterCount();
            require(count >= 0 && count <= 8192,
                    "Controller sweep reports invalid parameter count");
            rows.reserve(static_cast<size_t>(count));
            std::vector<ParamID> ids;
            ids.reserve(static_cast<size_t>(count));
            for (int32 index = 0; index < count; ++index) {
                ParameterInfo p{};
                require(controller.ptr->getParameterInfo(index, p) == kResultTrue,
                        "Controller sweep cannot read parameter info");
                require(p.stepCount >= 0 &&
                        std::isfinite(p.defaultNormalizedValue) &&
                        p.defaultNormalizedValue >= 0.0 &&
                        p.defaultNormalizedValue <= 1.0 &&
                        std::find(ids.begin(), ids.end(), p.id) == ids.end(),
                        "Controller sweep invalid or duplicate parameter metadata");
                ids.push_back(p.id);
                const double initial = controller.ptr->getParamNormalized(p.id);
                require(std::isfinite(initial) && initial >= 0.0 && initial <= 1.0,
                        "Controller sweep initial normalized value invalid");
                Row row;
                row.index = index;
                row.id = p.id;
                row.steps = p.stepCount;
                row.flags = p.flags;
                row.initial = initial;
                row.eligible = (p.flags & ParameterInfo::kCanAutomate) != 0 &&
                               (p.flags & ParameterInfo::kIsReadOnly) == 0;
                row.restored = true;
                row.passed = true;
                if (row.eligible) {
                    ++tested;
                    // Probe endpoints and quartiles.  For discrete parameters
                    // use actual integral step positions, not invalid half steps.
                    for (int i = 0; i <= 4; ++i) {
                        double requested = static_cast<double>(i) / 4.0;
                        if (p.stepCount > 0)
                            requested = std::round(requested * p.stepCount) /
                                        static_cast<double>(p.stepCount);
                        if (!row.observations.empty() &&
                            std::abs(row.observations.back().requested - requested) < 1e-12)
                            continue;
                        const auto rc = controller.ptr->setParamNormalized(p.id, requested);
                        const double actual = controller.ptr->getParamNormalized(p.id);
                        const bool ok = rc == kResultTrue && std::isfinite(actual) &&
                                        actual >= 0.0 && actual <= 1.0 &&
                                        std::abs(actual - requested) <= 1e-5;
                        row.observations.push_back({requested, actual, ok ? 1 : 0});
                        row.passed = row.passed && ok;
                        ++observations;
                    }
                    const auto rc = controller.ptr->setParamNormalized(p.id, initial);
                    const auto restored = controller.ptr->getParamNormalized(p.id);
                    row.restored = rc == kResultTrue && std::isfinite(restored) &&
                                   std::abs(restored - initial) <= 1e-5;
                    row.passed = row.passed && row.restored;
                    if (!row.passed) ++failed;
                } else {
                    ++skipped;
                }
                rows.push_back(std::move(row));
            }
            controller.close();
        }
        require(component->terminate() == kResultOk,
                "Controller sweep component termination failed");
        if (!reportPath.parent_path().empty())
            std::filesystem::create_directories(reportPath.parent_path());
        std::ofstream out(reportPath, std::ios::trunc);
        require(bool(out), "Controller sweep cannot create report");
        out << std::setprecision(17);
        out << "format\t125A-GUI-SWEEP-v1\n"
            << "param_count\t" << rows.size() << "\n"
            << "tested\t" << tested << "\n"
            << "skipped\t" << skipped << "\n"
            << "failed\t" << failed << "\n"
            << "observations\t" << observations << "\n";
        for (const auto& row : rows) {
            out << "param\t" << row.index << "\t" << row.id << "\t"
                << row.steps << "\t" << row.flags << "\t" << row.initial << "\t"
                << (row.eligible ? (row.passed ? "PASS" : "FAIL") : "SKIP")
                << "\t" << (row.restored ? 1 : 0) << "\n";
            for (const auto& x : row.observations)
                out << "probe\t" << row.index << "\t" << row.id << "\t"
                    << x.requested << "\t" << x.actual << "\t" << x.result << "\n";
        }
        out.flush();
        require(out.good(), "Controller sweep cannot write full evidence");
        std::cout << (failed ? "[FAIL]" : "[PASS]")
                  << " VST3 controller boundary sweep: " << tested
                  << " writable parameters, " << observations
                  << " checked values, " << failed << " failed\n";
        return failed ? 1 : 0;
    }
    require(audioClasses == 1, "No unique audio processor class for controller sweep");
    return 10;
}

// P40: Verify the VST3 controller's independent textual value mapping.
// A normalized parameter value is not the same as a displayed label.  Not all
// plugins implement reverse text parsing; absence is explicitly NOT COVERED.
std::string parameterTextHex(const TChar* data) {
    constexpr char hex[] = "0123456789abcdef";
    std::string result;
    for (int i = 0; i < 128; ++i) {
        const auto value = static_cast<unsigned int>(data[i]);
        if (!value) return result;
        require(value <= 65535, "VST3 parameter text contains non-UTF16 code unit");
        for (int shift : {12, 8, 4, 0})
            result.push_back(hex[(value >> shift) & 15]);
    }
    throw std::runtime_error("VST3 parameter text lacks terminator");
}

int verifyParameterText(const std::string& pluginPath,
                        const std::filesystem::path& reportPath) {
    std::string error;
    auto module = Module::create(pluginPath, error);
    require(bool(module), "Parameter text probe could not load real VST3");
    HostApplication app;
    auto factory = module->getFactory();
    factory.setHostContext(&app);
    int audioClasses = 0;
    for (const auto& cls : factory.classInfos()) {
        if (cls.category() != kVstAudioEffectClass) continue;
        ++audioClasses;
        require(audioClasses == 1,
                "Multiple audio classes need explicit selection (INCONCLUSIVE)");
        auto component = factory.createInstance<IComponent>(cls.ID());
        require(bool(component) && component->initialize(&app) == kResultOk,
                "Parameter text probe cannot initialize processor");
        int tested = 0, skipped = 0, failed = 0;
        int observations = 0, readable = 0, reversible = 0;
        std::ostringstream body;
        body << std::setprecision(17);
        {
            Controller controller;
            acquireController(component.get(), factory, &app, controller);
            const int32 count = controller.ptr->getParameterCount();
            require(count >= 0 && count <= 8192,
                    "Parameter text probe invalid controller count");
            std::vector<ParamID> identifiers;
            identifiers.reserve(static_cast<std::size_t>(count));
            for (int32 index = 0; index < count; ++index) {
                ParameterInfo p{};
                require(controller.ptr->getParameterInfo(index, p) == kResultTrue,
                        "Parameter text probe missing controller metadata");
                require(p.stepCount >= 0 &&
                        std::isfinite(p.defaultNormalizedValue) &&
                        p.defaultNormalizedValue >= 0.0 &&
                        p.defaultNormalizedValue <= 1.0 &&
                        std::find(identifiers.begin(), identifiers.end(), p.id)
                            == identifiers.end(),
                        "Parameter text probe invalid or duplicate metadata");
                identifiers.push_back(p.id);
                const bool eligible =
                    (p.flags & ParameterInfo::kCanAutomate) != 0 &&
                    (p.flags & ParameterInfo::kIsReadOnly) == 0;
                bool bad = false, hasText = false;
                std::ostringstream probes;
                probes << std::setprecision(17);
                if (eligible) {
                    ++tested;
                    double previous = -1.0;
                    for (int point = 0; point < 5; ++point) {
                        double target = static_cast<double>(point) / 4.0;
                        if (p.stepCount > 0)
                            target = std::round(target * p.stepCount) /
                                     static_cast<double>(p.stepCount);
                        if (std::abs(previous - target) < 1e-12) continue;
                        previous = target;
                        ++observations;
                        String128 text{};
                        const auto rc = controller.ptr->getParamStringByValue(
                            p.id, target, text);
                        const bool textSupported = rc == kResultTrue;
                        std::string encoded = "-";
                        std::string canonical = "-";
                        std::string reverseState = "-";
                        double parsed = -1.0;
                        bool good = true;
                        if (textSupported) {
                            hasText = true;
                            ++readable;
                            encoded = parameterTextHex(text);
                            good = !encoded.empty();
                            reverseState = "N";
                            ParamValue reverse = -1.0;
                            const auto fromText = controller.ptr->getParamValueByString(
                                p.id, text, reverse);
                            if (fromText == kResultTrue) {
                                reverseState = "R";
                                ++reversible;
                                parsed = reverse;
                                const bool validReverse =
                                    std::isfinite(parsed) && parsed >= 0.0 &&
                                    parsed <= 1.0;
                                good = good && validReverse;
                                if (validReverse) {
                                    // Text formatting can legitimately round
                                    // continuous values; require semantic
                                    // textual stability, not exact 0.25.
                                    String128 roundtrip{};
                                    const auto canonicalResult =
                                        controller.ptr->getParamStringByValue(
                                            p.id, parsed, roundtrip);
                                    if (canonicalResult == kResultTrue)
                                        canonical = parameterTextHex(roundtrip);
                                    good = good && canonicalResult == kResultTrue &&
                                           canonical == encoded;
                                    if (p.stepCount > 0)
                                        good = good &&
                                               std::abs(parsed - target) <= 1e-5;
                                }
                            }
                        }
                        if (!good) bad = true;
                        probes << "text\t" << index << "\t" << p.id << "\t"
                               << target << "\t" << encoded << "\t"
                               << reverseState << "\t";
                        if (reverseState == "R") probes << parsed;
                        else probes << "-";
                        probes << "\t" << canonical << "\t"
                               << (!textSupported ? "NOT_COVERED" :
                                   (good ? "PASS" : "FAIL")) << "\n";
                    }
                } else {
                    ++skipped;
                }
                const char* status = !eligible ? "SKIP" :
                                     (bad ? "FAIL" :
                                      (hasText ? "PASS" : "NOT_COVERED"));
                if (bad) ++failed;
                body << "param\t" << index << "\t" << p.id << "\t"
                     << p.stepCount << "\t" << p.flags << "\t"
                     << status << "\n";
                body << probes.str();
            }
            controller.close();
            if (!reportPath.parent_path().empty())
                std::filesystem::create_directories(reportPath.parent_path());
            std::ofstream output(reportPath, std::ios::trunc);
            require(bool(output), "Parameter text probe cannot create evidence file");
            output << "format\t125A-GUI-TEXT-v1\n"
                   << "param_count\t" << count << "\n"
                   << "tested\t" << tested << "\n"
                   << "skipped\t" << skipped << "\n"
                   << "failed\t" << failed << "\n"
                   << "observations\t" << observations << "\n"
                   << "readable\t" << readable << "\n"
                   << "reversible\t" << reversible << "\n"
                   << body.str();
            output.flush();
            require(output.good(), "Parameter text probe evidence write incomplete");
        }
        require(component->terminate() == kResultOk,
                "Parameter text probe component termination failed");
        std::cout << (failed ? "[FAIL]" : "[PASS]")
                  << " VST3 parameter text mapping: " << readable
                  << " labels, " << reversible
                  << " reverse values, " << failed << " invalid controls\n";
        return failed ? 1 : 0;
    }
    require(audioClasses == 1, "No unique VST3 audio class for parameter text probe");
    return 10;
}

std::vector<std::uint8_t> captureActualComponentState(IComponent* component) {
    ResizableMemoryIBStream stream;
    require(component->getState(&stream) == kResultOk,
            "P09 cannot read live VST3 component state");
    const auto bytes = stream.getCursor();
    require(bytes > 64 && bytes < 128 * 1024 * 1024,
            "P09 live project state has invalid size");
    const auto* begin = static_cast<const std::uint8_t*>(stream.getData());
    require(begin != nullptr, "P09 live project state has no bytes");
    return {begin, begin + bytes};
}

void saveActualComponentState(IComponent* component, const std::filesystem::path& path) {
    ResizableMemoryIBStream stream;
    require(component->getState(&stream) == kResultOk,
            "Drumator component getState failed during GUI test");
    const auto size = stream.getCursor();
    require(size >= 64 && size < 128 * 1024 * 1024,
            "Drumator GUI state size is invalid");
    std::ofstream dump(path, std::ios::binary | std::ios::trunc);
    require(dump.good(), "Cannot create P09 GUI state evidence file");
    dump.write(static_cast<const char*>(stream.getData()),
               static_cast<std::streamsize>(size));
    require(dump.good(), "Cannot save P09 GUI state evidence");
}

HWND getRealVstGuiWindow(HWND parent) {
    const auto child = GetWindow(parent, GW_CHILD);
    require(child && IsWindow(child),
            "P09 real Drumator GUI has no native child HWND");
    RECT dims{};
    require(GetClientRect(child, &dims) != 0 &&
            dims.right >= 700 && dims.bottom >= 250,
            "P09 Drumator native HWND is too small for real controls");
    return child;
}

void clickRealDrumatorGui(HWND surface, double x, double y,
                          const char* action) {
    // UI geometry is normalized to Drumator's 1280-pixel logical viewport.
    // No production header or object is imported into the test host.
    RECT rect{};
    require(GetClientRect(surface, &rect) != 0, "No GUI click surface");
    const double scale = static_cast<double>(rect.right) / 1280.0;
    require(scale >= 0.45 && scale <= 2.5,
            "Unsupported P09 product GUI scale; do not guess coordinates");
    const int px = static_cast<int>(std::lround(x * scale));
    const int py = static_cast<int>(std::lround(y * scale));
    require(px > 0 && px < rect.right && py > 0 && py < rect.bottom,
            "P09 click outside actual product window");
    const LPARAM at = MAKELPARAM(px, py);
    (void)SendMessageW(surface, WM_MOUSEMOVE, 0, at);
    (void)SendMessageW(surface, WM_LBUTTONDOWN, MK_LBUTTON, at);
    (void)SendMessageW(surface, WM_LBUTTONUP, 0, at);
    pump(110);
    std::cout << "[INFO] P09 actual HWND mouse action: " << action
              << " at " << px << "," << py << '\n';
}


// P10: Find the *actual OS-owned Shell save dialog*, never infer its existence
// from a GUI click. Cancel it from a second thread because IFileDialog::Show
// runs a synchronous modal COM event loop on the UI thread.
struct SaveDialogSearch {
    DWORD processId{};
    std::wstring caption;
    HWND window{};
};
BOOL CALLBACK findExportDialog(HWND window, LPARAM payload) {
    auto* q = reinterpret_cast<SaveDialogSearch*>(payload);
    if (!IsWindowVisible(window)) return TRUE;
    DWORD process{};
    (void)GetWindowThreadProcessId(window, &process);
    if (process != q->processId) return TRUE;
    wchar_t kind[64]{};
    if (!GetClassNameW(window, kind, 64) || wcscmp(kind, L"#32770"))
        return TRUE;
    wchar_t title[512]{};
    (void)GetWindowTextW(window, title, 512);
    if (std::wstring(title).find(q->caption) == std::wstring::npos)
        return TRUE;
    q->window = window;
    return FALSE;
}
bool cancelNativeSaveDialog(const std::wstring& title) {
    const ULONGLONG deadline = GetTickCount64() + 9000;
    while (GetTickCount64() < deadline) {
        SaveDialogSearch query{GetCurrentProcessId(), title, nullptr};
        EnumWindows(findExportDialog, reinterpret_cast<LPARAM>(&query));
        if (query.window) {
            std::wcout << L"[INFO] P10 verified native Windows Shell Save dialog: "
                       << title << L"\n";
            if (!PostMessageW(query.window, WM_CLOSE, 0, 0))
                return false;
            for (unsigned i = 0; i < 30; ++i) {
                if (!IsWindow(query.window)) return true;
                Sleep(80);
            }
            return false;
        }
        Sleep(35);
    }
    return false;
}
void runNativeExportDialogCancel(
    HWND child, IComponent* component, double logicalHeight,
    const std::filesystem::path& evidenceFolder) {
    std::filesystem::create_directories(evidenceFolder);
    const auto baseline = captureActualComponentState(component);
    const std::array<const wchar_t*, 4> dialogTitles{
        L"125A Drumator - Export PATTERN",
        L"125A Drumator - Export PATTERN",
        L"125A Drumator - Export SONG",
        L"125A Drumator - Export SONG"
    };
    const std::array<const char*, 4> actionNames{
        "PATTERN MIDI", "PATTERN WAV", "SONG MIDI", "SONG WAV"
    };
    for (int option = 0; option < 4; ++option) {
        // Popup bound by product's fixed 1280px layout: footer EXPORT is
        // x910..1005, y=height-48+10..35. Four 26px menu rows sit above.
        clickRealDrumatorGui(child, 957.0, logicalHeight - 26.,
                             "OPEN native EXPORT popup");
        std::atomic<bool> cancelObserved{false};
        std::thread closer([&]() {
            cancelObserved.store(cancelNativeSaveDialog(dialogTitles[option]),
                                 std::memory_order_release);
        });
        try {
            clickRealDrumatorGui(child, 900., logicalHeight - 149. + 26. * option,
                                 actionNames[option]);
        } catch (...) {
            closer.join();
            throw;
        }
        closer.join();
        require(cancelObserved.load(std::memory_order_acquire),
                "P10 selected export did not open/close expected native Windows Save dialog");
        pump(80);
        const auto after = captureActualComponentState(component);
        require(after == baseline,
                "P10 CANCEL corrupted actual processor state");
        const auto stem = std::string("cancel-") + std::to_string(option);
        std::ofstream proof(evidenceFolder / (stem + ".ok"),
                            std::ios::binary | std::ios::trunc);
        require(proof.good(), "P10 cannot create scenario evidence");
        proof << actionNames[option] << ": OS modal opened and canceled; "
              << "component state byte-identical\n";
        require(proof.good(), "P10 scenario evidence write failed");
        std::cout << "[PASS] P10 actual native Save dialog "
                  << actionNames[option]
                  << ": opened, canceled, state unchanged\n";
    }
    for (const auto& entry : std::filesystem::directory_iterator(evidenceFolder)) {
        const auto ext = entry.path().extension().string();
        require(ext != ".mid" && ext != ".wav",
                "P10 CANCEL unexpectedly produced MIDI/WAV file");
    }
    std::cout << "[PASS] P10: all four actual Drumator GUI export choices "
                 "opened native Win32 Save dialog; CANCEL non-destructive\n";
}


// P11: real VST3 processor time context and real product project-state
// restoration. No tempo is injected into Drumator private objects.
class ProductGuiClock {
public:
    ProductGuiClock(IComponent* component, IEditController* controller,
                    const std::filesystem::path& statePath)
        : component_(component) {
        require(component_->queryInterface(IAudioProcessor::iid,
                    reinterpret_cast<void**>(&processor_)) == kResultTrue &&
                    processor_, "P11 GUI product has no real IAudioProcessor");
        ProcessSetup setup{};
        setup.processMode = kRealtime;
        setup.symbolicSampleSize = kSample32;
        setup.maxSamplesPerBlock = 512;
        setup.sampleRate = 44100.0;
        require(processor_->setupProcessing(setup) == kResultOk,
                "P11 cannot configure host processing");
        std::ifstream source(statePath, std::ios::binary | std::ios::ate);
        require(source.good(), "P11 synthetic product project state missing");
        const auto len = source.tellg();
        require(len > 0 && len < 128 * 1024 * 1024,
                "P11 synthetic state has invalid length");
        std::vector<char> bytes(static_cast<size_t>(len));
        source.seekg(0);
        source.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
        require(source.good(), "P11 failed to read product state");
        auto transfer = [&](IBStream* output) {
            int32 done{};
            require(output->write(bytes.data(),
                    static_cast<int32>(bytes.size()), &done) == kResultOk &&
                    done == static_cast<int32>(bytes.size()),
                    "P11 cannot prepare IBStream project bytes");
            require(output->seek(0, IBStream::kIBSeekSet, nullptr) == kResultOk,
                    "P11 IBStream rewind failed");
        };
        ResizableMemoryIBStream processorState(bytes.size());
        transfer(&processorState);
        require(component_->setState(&processorState) == kResultOk,
                "P11 processor rejected rights-free state");
        ResizableMemoryIBStream controllerState(bytes.size());
        transfer(&controllerState);
        require(controller->setComponentState(&controllerState) == kResultOk,
                "P11 VST3 controller refused synchronized product state");
        require(component_->setActive(true) == kResultOk,
                "P11 VST3 product activation rejected");
        active_ = true;
        require(processor_->setProcessing(true) == kResultOk,
                "P11 VST3 product processing rejected");
        processing_ = true;
        publishTempo();
        std::cout << "[INFO] P11 real processor/controller state synchronized "
                     "with 120 BPM host transport\n";
    }
    ~ProductGuiClock() {
        if (processing_) (void)processor_->setProcessing(false);
        if (active_) (void)component_->setActive(false);
        if (processor_) processor_->release();
    }
    void publishTempo() {
        // The product explicitly accepts zero-frame host callbacks. Tempo
        // is conveyed via VST3 ProcessContext and confirmed by the
        // controller's normal MeterSnapshot request/response path.
        ProcessContext context{};
        context.state = ProcessContext::kPlaying | ProcessContext::kTempoValid |
                        ProcessContext::kTimeSigValid |
                        ProcessContext::kProjectTimeMusicValid;
        context.sampleRate = 44100.0;
        context.projectTimeMusic = 0.;
        context.projectTimeSamples = 0;
        context.tempo = 120.;
        context.timeSigNumerator = 4;
        context.timeSigDenominator = 4;
        ProcessData data{};
        data.processMode = kRealtime;
        data.symbolicSampleSize = kSample32;
        data.numSamples = 0;
        data.processContext = &context;
        require(processor_->process(data) == kResultOk,
                "P11 product rejected sample-exact host tempo observation");
    }
private:
    IComponent* component_{};
    IAudioProcessor* processor_{};
    bool active_{false};
    bool processing_{false};
};

// File dialogs are system COM objects. Observe and interact with their
// *real* HWND child controls, not a test-replacement IFileDialog.
struct GuiFileNameControl {
    HWND preferred{};
    HWND fallback{};
    unsigned candidates{};
};
BOOL CALLBACK findSaveFilenameEdit(HWND h, LPARAM arg) {
    auto* v = reinterpret_cast<GuiFileNameControl*>(arg);
    wchar_t className[64]{};
    if (!GetClassNameW(h, className, 64) || wcscmp(className, L"Edit"))
        return TRUE;
    ++v->candidates;
    if (!v->fallback) v->fallback = h;
    const int id = GetDlgCtrlID(h);
    if (id == 1001 || id == 1152) v->preferred = h;
    std::wcout << L"[INFO] P11 native dialog Edit id=" << id
               << L" hwnd=" << static_cast<void*>(h) << L"\n";
    return TRUE;
}
struct GuiSaveButton {
    HWND choice{};
};
BOOL CALLBACK findSaveButton(HWND h, LPARAM arg) {
    auto* v = reinterpret_cast<GuiSaveButton*>(arg);
    wchar_t className[64]{};
    if (!GetClassNameW(h, className, 64) ||
        wcscmp(className, L"Button")) return TRUE;
    const int id = GetDlgCtrlID(h);
    wchar_t caption[96]{};
    (void)GetWindowTextW(h, caption, 96);
    if (id == IDOK || wcscmp(caption, L"Save") == 0 ||
        wcscmp(caption, L"&Save") == 0) v->choice = h;
    return TRUE;
}
bool saveNativeShellDialog(const std::wstring& title,
                           const std::filesystem::path& target) {
    const ULONGLONG deadline = GetTickCount64() + 9000;
    while (GetTickCount64() < deadline) {
        SaveDialogSearch query{GetCurrentProcessId(), title, nullptr};
        EnumWindows(findExportDialog, reinterpret_cast<LPARAM>(&query));
        if (query.window) {
            GuiFileNameControl filename{};
            EnumChildWindows(query.window, findSaveFilenameEdit,
                             reinterpret_cast<LPARAM>(&filename));
            const HWND edit = filename.preferred ? filename.preferred : filename.fallback;
            if (!edit) {
                (void)PostMessageW(query.window, WM_CLOSE, 0, 0);
                std::cerr << "[FAIL] P11 FileSaveDialog has no accessible "
                             "native filename edit control\n";
                return false;
            }
            const auto native = std::filesystem::absolute(target).wstring();
            if (!SendMessageW(edit, WM_SETTEXT, 0,
                              reinterpret_cast<LPARAM>(native.c_str()))) {
                (void)PostMessageW(query.window, WM_CLOSE, 0, 0);
                return false;
            }
            GuiSaveButton button{};
            EnumChildWindows(query.window, findSaveButton,
                             reinterpret_cast<LPARAM>(&button));
            std::wcout << L"[INFO] P11 entered real Save As filename: "
                       << native << L"\n";
            if (button.choice)
                (void)PostMessageW(button.choice, BM_CLICK, 0, 0);
            else
                (void)PostMessageW(query.window, WM_COMMAND,
                                   MAKEWPARAM(IDOK, BN_CLICKED), 0);
            for (unsigned i = 0; i < 35; ++i) {
                if (!IsWindow(query.window)) {
                    std::wcout << L"[INFO] P11 Windows Save As dialog accepted\n";
                    return true;
                }
                Sleep(100);
            }
            (void)PostMessageW(query.window, WM_CLOSE, 0, 0);
            return false;
        }
        Sleep(40);
    }
    return false;
}
void runNativeGuiExportSave(HWND child, IComponent* component,
                            ProductGuiClock& clock, double logicalHeight,
                            const std::filesystem::path& folder) {
    std::filesystem::create_directories(folder);
    const auto unchanged = captureActualComponentState(component);
    const std::array<const wchar_t*, 4> titles{
        L"125A Drumator - Export PATTERN",
        L"125A Drumator - Export PATTERN",
        L"125A Drumator - Export SONG",
        L"125A Drumator - Export SONG"
    };
    const std::array<const char*, 4> labels{
        "PATTERN MIDI", "PATTERN WAV", "SONG MIDI", "SONG WAV"
    };
    const std::array<const wchar_t*, 4> filenames{
        L"pattern-midi.mid", L"pattern-wav.wav",
        L"song-midi.mid", L"song-wav.wav"
    };
    for (size_t option = 0; option < labels.size(); ++option) {
        const auto dest = folder / filenames[option];
        require(!std::filesystem::exists(dest),
                "P11 must never overwrite an existing export");
        clock.publishTempo();
        pump(200);
        clickRealDrumatorGui(child, 957., logicalHeight - 26.,
                             "OPEN actual EXPORT popup");
        std::atomic<bool> accepted{false};
        std::thread saver([&] {
            accepted.store(saveNativeShellDialog(titles[option], dest),
                           std::memory_order_release);
        });
        try {
            clickRealDrumatorGui(child, 900.,
                                 logicalHeight - 149. + 26. * option,
                                 labels[option]);
        } catch (...) {
            saver.join();
            throw;
        }
        saver.join();
        require(accepted.load(std::memory_order_acquire),
                "P11 real Windows Save As control was not accepted");
        pump(80);
        require(std::filesystem::is_regular_file(dest) &&
                std::filesystem::file_size(dest) > 128,
                "P11 GUI Save As returned without writing a real export file");
        require(captureActualComponentState(component) == unchanged,
                "P11 exporting unexpectedly mutated plugin project state");
        std::cout << "[PASS] P11 real GUI Save As " << labels[option]
                  << ": saved " << std::filesystem::file_size(dest)
                  << " bytes, project state preserved\n";
    }
    std::cout << "[PASS] P11 four actual product GUI file exports written "
                 "via native Windows Shell Save dialog\n";
}


// P13: real COM/OLE IDropTarget registered on a separate visible Win32
// host window. A product VSTGUI drag must deliver CF_HDROP *through Windows
// OLE*, not an imitation payload or an exporter called directly.
class NativeFileDropTarget final : public IDropTarget {
public:
    explicit NativeFileDropTarget(std::filesystem::path folder)
        : folder_(std::move(folder)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != IID_IUnknown && iid != IID_IDropTarget)
            return E_NOINTERFACE;
        *out = static_cast<IDropTarget*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override {
        return refs_.fetch_add(1, std::memory_order_relaxed) + 1;
    }
    ULONG STDMETHODCALLTYPE Release() override {
        const auto count = refs_.fetch_sub(1, std::memory_order_acq_rel) - 1;
        if (!count) delete this;
        return count;
    }
    HRESULT STDMETHODCALLTYPE DragEnter(IDataObject* data, DWORD, POINTL,
                                        DWORD* effect) override {
        if (!effect) return E_POINTER;
        *effect = DROPEFFECT_NONE;
        FORMATETC fmt{CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
        if (!data || FAILED(data->QueryGetData(&fmt))) return S_OK;
        *effect = DROPEFFECT_COPY;
        ++entered_;
        std::cout << "[INFO] P13 OLE receiver saw actual CF_HDROP package\n";
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE DragOver(DWORD, POINTL, DWORD* effect) override {
        if (!effect) return E_POINTER;
        *effect = DROPEFFECT_COPY;
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE DragLeave() override { return S_OK; }
    HRESULT STDMETHODCALLTYPE Drop(IDataObject* data, DWORD, POINTL,
                                   DWORD* effect) override {
        if (!effect) return E_POINTER;
        *effect = DROPEFFECT_NONE;
        if (!data) return E_INVALIDARG;
        FORMATETC fmt{CF_HDROP, nullptr, DVASPECT_CONTENT, -1, TYMED_HGLOBAL};
        STGMEDIUM storage{};
        if (FAILED(data->GetData(&fmt, &storage))) return DV_E_FORMATETC;
        std::filesystem::path copied;
        do {
            if (storage.tymed != TYMED_HGLOBAL) break;
            auto dropped = static_cast<HDROP>(storage.hGlobal);
            if (DragQueryFileW(dropped, 0xFFFFFFFF, nullptr, 0) != 1)
                break;
            wchar_t path[32768]{};
            const UINT n = DragQueryFileW(dropped, 0, path, 32768);
            if (!n || n >= 32768) break;
            const std::filesystem::path original(path);
            if (!std::filesystem::is_regular_file(original) ||
                std::filesystem::file_size(original) <= 128) break;
            const std::wstring sourceName = original.filename().wstring();
            if (sourceName != expectedSource_) break;
            copied = folder_ / expectedDestination_;
            if (std::filesystem::exists(copied)) break;
            std::filesystem::copy_file(original, copied,
                                        std::filesystem::copy_options::none);
            if (!std::filesystem::is_regular_file(copied)) break;
            lastSource_ = original;
            accepted_.fetch_add(1, std::memory_order_release);
            *effect = DROPEFFECT_COPY;
            std::wcout << L"[PASS] P13 real OLE CF_HDROP from " <<
                original.wstring() << L" received and copied\n";
        } while (false);
        ReleaseStgMedium(&storage);
        return copied.empty() ? E_FAIL : S_OK;
    }
    void setExpected(const wchar_t* name, const wchar_t* dest) {
        expectedSource_ = name;
        expectedDestination_ = dest;
        lastSource_.clear();
    }
    unsigned accepted() const { return accepted_.load(std::memory_order_acquire); }
    unsigned entered() const { return entered_.load(std::memory_order_acquire); }
    const std::filesystem::path& source() const { return lastSource_; }
private:
    std::atomic<ULONG> refs_{1};
    std::atomic<unsigned> accepted_{0}, entered_{0};
    std::filesystem::path folder_,lastSource_;
    std::wstring expectedSource_,expectedDestination_;
};

// P15: fully unattended receiver CONTRACT test. Direct callback invocation
// is deliberately not presented as a real shell DoDragDrop or DAW acceptance.
class ContractFileDataObject final : public IDataObject {
public:
    explicit ContractFileDataObject(std::wstring path) : path_(std::move(path)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != IID_IUnknown && iid != IID_IDataObject) return E_NOINTERFACE;
        *out = static_cast<IDataObject*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++refs_; }
    ULONG STDMETHODCALLTYPE Release() override {
        const ULONG n = --refs_;
        if (!n) delete this;
        return n;
    }
    HRESULT STDMETHODCALLTYPE QueryGetData(FORMATETC* format) override {
        if (!format) return E_POINTER;
        return format->cfFormat == CF_HDROP &&
            (format->tymed & TYMED_HGLOBAL) &&
            format->dwAspect == DVASPECT_CONTENT ? S_OK : DV_E_FORMATETC;
    }
    HRESULT STDMETHODCALLTYPE GetData(FORMATETC* format, STGMEDIUM* medium) override {
        if (!medium) return E_POINTER;
        *medium = {};
        if (FAILED(QueryGetData(format))) return DV_E_FORMATETC;
        const SIZE_T bytes = sizeof(DROPFILES) +
            (path_.size() + 2) * sizeof(wchar_t);
        HGLOBAL h = GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, bytes);
        if (!h) return E_OUTOFMEMORY;
        auto* p = static_cast<BYTE*>(GlobalLock(h));
        if (!p) { GlobalFree(h); return E_OUTOFMEMORY; }
        auto* drop = reinterpret_cast<DROPFILES*>(p);
        drop->pFiles = sizeof(DROPFILES);
        drop->fWide = TRUE;
        std::memcpy(p + sizeof(DROPFILES), path_.c_str(),
                    (path_.size() + 1) * sizeof(wchar_t));
        GlobalUnlock(h);
        medium->tymed = TYMED_HGLOBAL;
        medium->hGlobal = h;
        medium->pUnkForRelease = nullptr;
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE GetDataHere(FORMATETC*, STGMEDIUM*) override {
        return DATA_E_FORMATETC;
    }
    HRESULT STDMETHODCALLTYPE GetCanonicalFormatEtc(FORMATETC*,FORMATETC* out) override {
        if (out) out->ptd = nullptr;
        return DATA_S_SAMEFORMATETC;
    }
    HRESULT STDMETHODCALLTYPE SetData(FORMATETC*,STGMEDIUM*,BOOL) override {
        return E_NOTIMPL;
    }
    HRESULT STDMETHODCALLTYPE EnumFormatEtc(DWORD,IEnumFORMATETC**) override {
        return E_NOTIMPL;
    }
    HRESULT STDMETHODCALLTYPE DAdvise(FORMATETC*,DWORD,IAdviseSink*,DWORD*) override {
        return OLE_E_ADVISENOTSUPPORTED;
    }
    HRESULT STDMETHODCALLTYPE DUnadvise(DWORD) override {
        return OLE_E_ADVISENOTSUPPORTED;
    }
    HRESULT STDMETHODCALLTYPE EnumDAdvise(IEnumSTATDATA**) override {
        return OLE_E_ADVISENOTSUPPORTED;
    }
private:
    std::atomic<ULONG> refs_{1};
    std::wstring path_;
};

void runOleReceiverContract(const std::filesystem::path& base) {
    std::filesystem::create_directories(base);
    const auto input = base / "sources";
    const auto output = base / "received";
    std::filesystem::create_directories(input);
    std::filesystem::create_directories(output);
    NativeFileDropTarget target(output);
    const std::array<const wchar_t*,4> from{
        L"125A Drumator Pattern.mid", L"125A Drumator Pattern.wav",
        L"125A Drumator Song.mid", L"125A Drumator Song.wav"};
    const std::array<const wchar_t*,4> to{
        L"pattern-midi.mid", L"pattern-wav.wav",
        L"song-midi.mid", L"song-wav.wav"};
    for (size_t i = 0; i < from.size(); ++i) {
        const auto original = input / from[i];
        {
            std::ofstream file(original, std::ios::binary);
            require(file.good(), "P15 cannot create synthetic source fixture");
            const std::array<char,256> fixture{};
            file.write(fixture.data(), fixture.size());
            require(file.good(), "P15 fixture write failed");
        }
        target.setExpected(from[i],to[i]);
        auto* data = new ContractFileDataObject(original.wstring());
        FORMATETC unsupported{CF_UNICODETEXT,nullptr,DVASPECT_CONTENT,-1,TYMED_HGLOBAL};
        require(data->QueryGetData(&unsupported) == DV_E_FORMATETC,
                "P15 receiver fixture did not reject unsupported format");
        DWORD effect = DROPEFFECT_COPY;
        POINTL point{};
        require(target.DragEnter(data,0,point,&effect) == S_OK &&
                effect == DROPEFFECT_COPY,"P15 CF_HDROP DragEnter rejected");
        effect = DROPEFFECT_COPY;
        require(target.Drop(data,0,point,&effect) == S_OK &&
                effect == DROPEFFECT_COPY,"P15 CF_HDROP Drop rejected");
        data->Release();
        require(std::filesystem::file_size(output/to[i]) == 256,
                "P15 received file differs from synthetic source");
        require(target.accepted() == i+1 && target.entered() == i+1,
                "P15 expected OLE receiver callbacks not recorded");
    }
    std::cout << "[PASS] P15 four native IDropTarget contract callbacks and "
                 "four independent CF_HDROP copies (NOT a system DoDragDrop)\n";
}

class NativeDropWindow final {
public:
    explicit NativeDropWindow(const std::filesystem::path& folder) {
        // An actual external DAW uses another STA with its own message loop.
        // A drop target registered on the drag SOURCE thread is not a
        // representative interapplication OLE test and can be starved by
        // the synchronous DoDragDrop nested pump on that same thread.
        receiverThread_ = std::thread([this, folder] {
            const HRESULT ole = OleInitialize(nullptr);
            if (FAILED(ole)) {
                failed_.store(true,std::memory_order_release);
                ready_.store(true,std::memory_order_release);
                return;
            }
            NativeFileDropTarget* target = new NativeFileDropTarget(folder);
            HWND w = CreateWindowExW(WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                L"STATIC", L"125A Lab CF_HDROP Receiver", WS_POPUP | WS_VISIBLE,
                35, 35, 280, 140, nullptr, nullptr,
                GetModuleHandleW(nullptr), nullptr);
            const bool ok = w != nullptr && RegisterDragDrop(w,target) == S_OK;
            if (ok) {
                ShowWindow(w,SW_SHOWNORMAL);
                UpdateWindow(w);
                target_.store(target,std::memory_order_release);
                window_.store(w,std::memory_order_release);
            } else {
                failed_.store(true,std::memory_order_release);
            }
            ready_.store(true,std::memory_order_release);
            if (ok) {
                MSG msg{};
                while (!stop_.load(std::memory_order_acquire)) {
                    while (PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)) {
                        TranslateMessage(&msg);
                        DispatchMessageW(&msg);
                    }
                    Sleep(6);
                }
                (void)RevokeDragDrop(w);
            }
            if (w) DestroyWindow(w);
            target->Release();
            OleUninitialize();
        });
        for (unsigned t=0;t<300 && !ready_.load(std::memory_order_acquire);++t)
            Sleep(10);
        if (!ready_.load(std::memory_order_acquire) ||
            failed_.load(std::memory_order_acquire)) {
            stop_.store(true,std::memory_order_release);
            if (receiverThread_.joinable()) receiverThread_.join();
            throw std::runtime_error(
                "P13 independent COM/STA receiver thread or HWND failed to start");
        }
        std::cout << "[INFO] P13 independent drop receiver ready on "
                     "separate Win32 STA + message loop\n";
    }
    ~NativeDropWindow() {
        stop_.store(true,std::memory_order_release);
        if (receiverThread_.joinable()) receiverThread_.join();
    }
    NativeFileDropTarget& target() {
        auto* v=target_.load(std::memory_order_acquire);
        require(v!=nullptr,"P13 independent receiver has no IDropTarget");
        return *v;
    }
    HWND get() const { return window_.load(std::memory_order_acquire); }
private:
    std::thread receiverThread_;
    std::atomic<HWND> window_{nullptr};
    std::atomic<NativeFileDropTarget*> target_{nullptr};
    std::atomic<bool> ready_{false}, failed_{false}, stop_{false};
};

void injectButton(DWORD flags) {
    INPUT e{};
    e.type = INPUT_MOUSE;
    e.mi.dwFlags = flags;
    require(SendInput(1, &e, sizeof(e)) == 1,
            "P13 Windows mouse input injection failed");
}
void runActualOleDragDrop(HWND nativeChild, HWND hostWindow,
                          IComponent* processorComponent,
                          ProductGuiClock& tempo,
                          double logicalHeight,
                          const std::filesystem::path& folder) {
    std::filesystem::create_directories(folder);
    // The VST3 editor may be wider than the Windows runner's actual
    // virtual desktop. GUI SendMessage tests tolerate that, but OLE
    // DoDragDrop requires a real on-screen cursor over source + target.
    // Move the *host window*, not the plugin view, so the source menu
    // remains at its tested logical coordinates and its zoom is unchanged.
    RECT hostBounds{}, childBounds{};
    require(GetWindowRect(hostWindow, &hostBounds)!=0 &&
            GetClientRect(nativeChild, &childBounds)!=0,
            "P13 cannot position visible physical drag source");
    const double layoutScale = childBounds.right / 1280.0;
    POINT screenSource{static_cast<LONG>(900.*layoutScale),
                       static_cast<LONG>((logicalHeight-149.)*layoutScale)};
    require(ClientToScreen(nativeChild, &screenSource)!=0,
            "P13 cannot locate on-screen native source");
    const int desktopW = GetSystemMetrics(SM_CXSCREEN);
    const int desktopH = GetSystemMetrics(SM_CYSCREEN);
    require(desktopW >= 640 && desktopH >= 480,
            "P13 runner has no usable interactive Windows desktop");
    const int desiredX = std::max(360, desktopW/2);
    const int desiredY = std::min(desktopH-180,desktopH*2/3);
    const int dx = desiredX - screenSource.x;
    const int dy = desiredY - screenSource.y;
    require(SetWindowPos(hostWindow,nullptr,
                         hostBounds.left+dx,hostBounds.top+dy,0,0,
                         SWP_NOSIZE|SWP_NOZORDER|SWP_NOACTIVATE)!=0,
            "P13 unable to position large VSTGUI popup on visible desktop");
    pump(80);
    std::cout << "[INFO] P13 visible desktop " << desktopW << "x" << desktopH
              << " product host moved dx=" << dx << " dy=" << dy << "\n";
    // OleInitialize is required on the source STA that invokes DoDragDrop.
    // The receiving window owns its *own* distinct OLE STA.
    const HRESULT sourceOle=OleInitialize(nullptr);
    require(SUCCEEDED(sourceOle),"P13 source OLE apartment init failed");
    struct SourceOleScope { ~SourceOleScope(){OleUninitialize();} } sourceScope;
    NativeDropWindow drop(folder);
    const auto unchanged = captureActualComponentState(processorComponent);
    const std::array<const wchar_t*, 4> originalNames{
        L"125A Drumator Pattern.mid", L"125A Drumator Pattern.wav",
        L"125A Drumator Song.mid", L"125A Drumator Song.wav"
    };
    const std::array<const wchar_t*, 4> outputNames{
        L"pattern-midi.mid", L"pattern-wav.wav",
        L"song-midi.mid", L"song-wav.wav"
    };
    ShowWindow(hostWindow, SW_SHOWNORMAL);
    SetForegroundWindow(hostWindow);
    for (size_t i = 0; i < originalNames.size(); ++i) {
        tempo.publishTempo();
        pump(250);
        clickRealDrumatorGui(nativeChild, 957., logicalHeight-26.,
                             "P13 OPEN EXPORT popup");
        RECT rect{};
        require(GetClientRect(nativeChild,&rect)!=0,
                "P13 cannot obtain plugin child dimensions");
        const double scale = rect.right/1280.0;
        POINT source{static_cast<LONG>(900.*scale),
                     static_cast<LONG>((logicalHeight - 149. + 26.*i)*scale)};
        POINT moved{source.x + static_cast<LONG>(45.*scale),
                    source.y - static_cast<LONG>(17.*scale)};
        POINT screen = source;
        require(ClientToScreen(nativeChild,&screen)!=0,
                "P13 cannot translate source to actual monitor location");
        require(SetCursorPos(screen.x,screen.y)!=0,
                "P13 source pointer position refused");
        // Match the P13 verified source-side gesture: VSTGUI must receive
        // a hover over the popup item BEFORE the left-button press.
        // Without it, onMouseMoved returns and no OLE drag ever starts.
        const LPARAM hoverAt = MAKELPARAM(source.x,source.y);
        (void)SendMessageW(nativeChild, WM_MOUSEMOVE, 0, hoverAt);
        pump(70);
        drop.target().setExpected(originalNames[i], outputNames[i]);
        const unsigned previous = drop.target().accepted();
        // OLE QueryContinueDrag inspects the *real* Windows keyboard state.
        // Synthetic SendMessage(WM_LBUTTONDOWN) alone cannot establish a
        // physical button hold. Use genuine SendInput + cursor movements.
        pump(110);
        injectButton(MOUSEEVENTF_LEFTDOWN);
        pump(90);
        // P16 runs in an actual logged-in RDP desktop. SendInput already
        // dispatches WM_LBUTTONDOWN. A second synthetic WM_LBUTTONDOWN
        // would click the popup item twice and cancel the drag source.
        const LPARAM to = MAKELPARAM(moved.x,moved.y);
        const auto hoveredSource = WindowFromPoint(screen);
        std::cout << "[INFO] P16 actual physical button held; source HWND hit="
                  << (hoveredSource == nativeChild) << " foreground-host="
                  << (GetForegroundWindow() == hostWindow) << "\n";
        POINT screenMoved = moved;
        require(ClientToScreen(nativeChild,&screenMoved)!=0,
                "P13 cannot translate OS drag origin");
        std::cout << "[INFO] P13 physical down="
                  << ((GetAsyncKeyState(VK_LBUTTON)&0x8000)!=0)
                  << " source screen=" << screen.x << "," << screen.y
                  << " -> gesture=" << screenMoved.x << ","
                  << screenMoved.y << "\n";
        // The dragging session enters synchronous DoDragDrop. A worker
        // operates the independent OS cursor while OLE pumps the STA.
        std::thread mover([&] {
            Sleep(750);
            RECT target{};
            (void)GetWindowRect(drop.get(),&target);
            for (int step=1;step<=7;++step) {
                const int x = screen.x+(target.left+140-screen.x)*step/7;
                const int y = screen.y+(target.top+70-screen.y)*step/7;
                (void)SetCursorPos(x,y);
                INPUT motion{};
                motion.type=INPUT_MOUSE;
                motion.mi.dwFlags=MOUSEEVENTF_MOVE;
                motion.mi.dx=1;
                (void)SendInput(1,&motion,sizeof(motion));
                Sleep(110);
            }
            POINT cursor{};
            (void)GetCursorPos(&cursor);
            const HWND hovered=WindowFromPoint(cursor);
            std::cout << "[INFO] P13 OS cursor at " << cursor.x << ","
                      << cursor.y << " target-window-hover="
                      << (hovered==drop.get()) << " OLE-entered="
                      << drop.target().entered() << "\n";
            INPUT up{};
            up.type = INPUT_MOUSE;
            up.mi.dwFlags = MOUSEEVENTF_LEFTUP;
            (void)SendInput(1,&up,sizeof(up));
            Sleep(200);
            // Send an ESC fallback to prevent indefinite OLE modal hanging.
            INPUT esc[2]{};
            esc[0].type=INPUT_KEYBOARD;esc[0].ki.wVk=VK_ESCAPE;
            esc[1].type=INPUT_KEYBOARD;esc[1].ki.wVk=VK_ESCAPE;
            esc[1].ki.dwFlags=KEYEVENTF_KEYUP;
            (void)SendInput(2,esc,sizeof(INPUT));
        });
        std::atomic<bool> dragReturned{false};
        // OLE drag sessions can hang on non-interactive CI desktops.
        // Do not spend 45 minutes stuck inside a native COM modal loop.
        std::thread watchdog([&] {
            for (unsigned t=0;t<90;++t) {
                if (dragReturned.load(std::memory_order_acquire)) return;
                Sleep(100);
            }
            std::cerr << "[FAIL] P13 OLE modal drag failed to return "
                         "within 9 seconds; Windows runner cannot complete drop\n";
            TerminateProcess(GetCurrentProcess(), 14);
        });
        try {
            require(SetCursorPos(screenMoved.x, screenMoved.y)!=0,
                    "P13 physical drag motion failed");
            std::cout << "[INFO] P13 requesting live VSTGUI/OLE drag start\n";
            (void)SendMessageW(nativeChild, WM_MOUSEMOVE, MK_LBUTTON, to);
            std::cout << "[INFO] P13 live VSTGUI/OLE drag returned\n";
            pump(230);
        } catch (...) {
            dragReturned.store(true, std::memory_order_release);
            watchdog.join();
            mover.join();
            throw;
        }
        dragReturned.store(true, std::memory_order_release);
        watchdog.join();
        mover.join();
        pump(100);
        std::cout << "[INFO] P13 OLE receiver entered="
                  << drop.target().entered() << " accepted="
                  << drop.target().accepted() << " expected="
                  << previous+1 << " held="
                  << ((GetAsyncKeyState(VK_LBUTTON)&0x8000)!=0) << "\n";
        const auto root = std::filesystem::temp_directory_path();
        unsigned exported=0;
        for(const auto& ent:std::filesystem::directory_iterator(root)) {
            if (ent.path().filename().wstring().find(L"125A-Drumator-Drag-")==0) {
                ++exported;
                if(exported<=5)
                    std::wcout << L"[INFO] P13 temporary drag folder: "
                               << ent.path().wstring() << L"\n";
            }
        }
        std::cout << "[INFO] P13 temporary drag folder count=" << exported << "\n";
        require(drop.target().accepted() == previous + 1,
                "P13 genuine OLE drop target did not accept one CF_HDROP file");
        const auto actual = folder/outputNames[i];
        require(std::filesystem::is_regular_file(actual) &&
                std::filesystem::file_size(actual)>128,
                "P13 OLE copy did not produce real exported file");
        require(std::filesystem::is_regular_file(drop.target().source()),
                "P13 source was removed before receiving DAW-style OLE drop");
        require(captureActualComponentState(processorComponent) == unchanged,
                "P13 drag unexpectedly mutated Drumator's project state");
        std::cout << "[PASS] P13 native GUI->COM OLE CF_HDROP "
                  << i << " accepted with retained source file\n";
    }
    require(drop.target().entered() >= 4,
            "P13 no four real OLE drag-enter events occurred");
    std::cout << "[PASS] P13 all 4 actual VSTGUI OLE CF_HDROP drops "
                 "accepted by independent native Windows target\n";
}


// P13: deterministic *source-side* test for an ephemeral non-interactive
// GitHub runner. Exercise real plugin GUI drag start / export / retained file,
// but DO NOT claim target OLE/DAW delivery. True OLE testing remains available
// separately in --drumator-ole-drag-drop on an interactive Windows desktop.
void runActualGuiDragSource(HWND child, IComponent* component,
                            ProductGuiClock& tempo, double logicalHeight,
                            const std::filesystem::path& folder) {
    std::filesystem::create_directories(folder);
    const auto baseline = captureActualComponentState(component);
    const std::array<const wchar_t*,4> names{
        L"125A Drumator Pattern.mid", L"125A Drumator Pattern.wav",
        L"125A Drumator Song.mid", L"125A Drumator Song.wav"
    };
    const std::array<const wchar_t*,4> out{
        L"pattern-midi.mid", L"pattern-wav.wav",
        L"song-midi.mid", L"song-wav.wav"
    };
    const auto root = std::filesystem::temp_directory_path();
    auto find = [&](std::wstring name) {
        std::vector<std::filesystem::path> paths;
        for(const auto& dir: std::filesystem::directory_iterator(root)) {
            if (!dir.is_directory()) continue;
            const auto folderName = dir.path().filename().wstring();
            if (folderName.find(L"125A-Drumator-Drag-") != 0) continue;
            const auto candidate = dir.path()/name;
            if (std::filesystem::is_regular_file(candidate))
                paths.push_back(candidate);
        }
        return paths;
    };
    RECT rect{};
    require(GetClientRect(child,&rect)!=0, "P13 source editor dimensions missing");
    const double scale = rect.right / 1280.0;
    for(size_t i=0;i<names.size();++i) {
        const auto existing = find(names[i]);
        tempo.publishTempo();
        pump(240);
        clickRealDrumatorGui(child,957.,logicalHeight-26.,
                             "P13 OPEN export popup for drag source");
        const int x = static_cast<int>(900.*scale);
        const int y = static_cast<int>((logicalHeight-149.+26.*i)*scale);
        const auto at = MAKELPARAM(x,y);
        const auto to = MAKELPARAM(x+static_cast<int>(42.*scale),
                                   y-static_cast<int>(14.*scale));
        (void)SendMessageW(child, WM_MOUSEMOVE, 0, at);
        injectButton(MOUSEEVENTF_LEFTDOWN);
        (void)SendMessageW(child, WM_LBUTTONDOWN, MK_LBUTTON, at);
        // The source VSTGUI state sees a real held logical left click.
        // Release the PHYSICAL state before entering blocking OLE on this
        // non-interactive service desktop. This leaves product onMouseMoved
        // with MK_LBUTTON but causes native OLE to abort immediately.
        injectButton(MOUSEEVENTF_LEFTUP);
        std::atomic<bool> completed{false};
        std::thread watchdog([&] {
            for(unsigned t=0;t<45;++t) {
                if(completed.load(std::memory_order_acquire)) return;
                Sleep(100);
            }
            std::cerr << "[FAIL] P13 drag source OLE did not return "
                         "after 4.5 seconds on headless Windows runner\n";
            TerminateProcess(GetCurrentProcess(), 15);
        });
        (void)SendMessageW(child, WM_MOUSEMOVE, MK_LBUTTON, to);
        completed.store(true,std::memory_order_release);
        watchdog.join();
        pump(180);
        auto candidates = find(names[i]);
        candidates.erase(
            std::remove_if(candidates.begin(),candidates.end(),
               [&](const auto& candidate) {
                   return std::find(existing.begin(),existing.end(),candidate)!=
                          existing.end();
               }),candidates.end());
        require(candidates.size()==1,
                "P13 GUI drag start did not produce exactly one new genuine export file");
        const auto target = folder/out[i];
        require(!std::filesystem::exists(target),
                "P13 test output collision before drag source copy");
        require(std::filesystem::file_size(candidates[0])>128,
                "P13 ephemeral drag source file was empty/truncated");
        std::filesystem::copy_file(candidates[0],target);
        require(std::filesystem::is_regular_file(candidates[0]),
                "P13 product deleted ephemeral drag source prematurely");
        require(captureActualComponentState(component)==baseline,
                "P13 GUI drag source unexpectedly changed project state");
        std::cout << "[PASS] P13 actual GUI drag source "<<i
                  << " exported "<<std::filesystem::file_size(target)
                  << " bytes, transient source retained\n";
    }
    std::cout << "[PASS] P13 source-side GUI drag exports 4 files;"
                 " external OLE DragEnter/Drop: INCONCLUSIVE on CI\n";
}

void runRealDrumatorGui(const std::string& path,
                        const std::filesystem::path& originalState,
                        const std::filesystem::path& canceledState,
                        const std::filesystem::path& appliedState,
                        bool exportDialogCancel = false,
                        const std::filesystem::path& exportSaveState = {},
                        bool checkOleDrag = false,
                        bool checkDragSourceOnly = false,
                        bool checkGuiLifecycle = false,
                        bool checkGuiControlStress = false) {
    std::cout << "[INFO] P09 load source-built packaged VST3 from " << path << "\n";
    std::string error;
    auto module = Module::create(path, error);
    require(static_cast<bool>(module), "P09 cannot load actual product VST3");
    std::cout << "[INFO] P09 module loaded successfully\n";
    HostApplication context;
    auto factory = module->getFactory();
    factory.setHostContext(&context);

    for (const auto& info : factory.classInfos()) {
        if (info.category() != kVstAudioEffectClass) continue;
        auto component = factory.createInstance<IComponent>(info.ID());
        require(static_cast<bool>(component), "P09 cannot create product component");
        require(component->initialize(&context) == kResultOk,
                "P09 cannot initialize Drumator component");
        std::cout << "[INFO] P09 product component initialized\n";

        Controller controller;
        acquireController(component.get(), factory, &context, controller);
        require(controller.connected,
                "P09 controller not connected to processor (fail closed)");
        std::cout << "[INFO] P09 controller connected to component\n";

        std::unique_ptr<ProductGuiClock> tempoClock;
        if (!exportSaveState.empty()) {
            tempoClock = std::make_unique<ProductGuiClock>(
                component.get(), controller.ptr, exportSaveState);
        }
        IPlugView* view = controller.ptr->createView(ViewType::kEditor);
        require(view != nullptr, "P09 no real product editor");
        std::cout << "[INFO] P09 product IPlugView created\n";
        ViewRect geometry{};
        require(view->getSize(&geometry) == kResultTrue &&
                view->isPlatformTypeSupported(kPlatformTypeHWND) == kResultTrue,
                "P09 product editor is not a Win32 view");
        std::cout << "[INFO] P09 pre-attach product IPlugView::getSize = "
                  << geometry.getWidth() << "x" << geometry.getHeight() << "\n";
        if (geometry.getWidth() < 100 || geometry.getHeight() < 60) {
            // Some VSTGUI editors report an uninitialized rect before the
            // host proposes an initial size. This is a TEST HOST negotiation,
            // not a change in product source or any production parameter.
            ViewRect proposed{0, 0, 1280, 700};
            require(view->onSize(&proposed) == kResultTrue,
                    "P09 product rejected host's initial editor size");
            require(view->getSize(&geometry) == kResultTrue,
                    "P09 product getSize failed after host onSize");
            std::cout << "[WARN] P09 product requires initial host size proposal; "
                      << "rect after negotiation=" << geometry.getWidth() << "x"
                      << geometry.getHeight() << "\n";
        }
        require(geometry.getWidth() >= 100 && geometry.getHeight() >= 60 &&
                geometry.getWidth() <= 8192 && geometry.getHeight() <= 8192,
                "P09 editor geometry invalid even after host negotiation");
        Window window(geometry);
        std::cout << "[INFO] P09 real native host HWND created\n";
        HostFrame* frame = new HostFrame(window.get());
        bool frameAssigned = false;
        bool attached = false;
        try {
            require(view->setFrame(frame) == kResultTrue,
                    "P09 product IPlugView::setFrame failed");
            frameAssigned = true;
            require(view->attached(window.get(), kPlatformTypeHWND) == kResultTrue,
                    "P09 product IPlugView::attached failed");
            attached = true;
            std::cout << "[INFO] P09 real product editor attached to HWND\n";
            ShowWindow(window.get(), SW_SHOWNA);
            UpdateWindow(window.get());
            pump(300);
            const HWND child = getRealVstGuiWindow(window.get());
            RECT client{};
            require(GetClientRect(child, &client) != 0,
                    "P09 cannot read native product editor size");
            const double logicalHeight =
                static_cast<double>(client.bottom) * 1280.0 /
                static_cast<double>(client.right);
            require(logicalHeight >= 254.0 && logicalHeight <= 1250.0,
                    "P09 unsupported product logical height; cannot locate modal");
            std::cout << "[INFO] P09 product editor 1280x" << logicalHeight
                      << " logical, native " << client.right << "x"
                      << client.bottom << " pixels\n";

            if (checkGuiControlStress) {
                // P19: exercise the real stateful limiter control repeatedly.
                // Every odd click must change the processor state; every
                // even click must restore it byte-for-byte.
                const auto original = captureActualComponentState(component.get());
                constexpr int kPairs = 48;
                for (int pair = 1; pair <= kPairs; ++pair) {
                    clickRealDrumatorGui(child, 1122.5, 29.0,
                                         "P19 toggle limiter ON");
                    require(captureActualComponentState(component.get()) != original,
                            "P19 real GUI limiter ON failed to change processor state");
                    clickRealDrumatorGui(child, 1122.5, 29.0,
                                         "P19 toggle limiter OFF");
                    require(captureActualComponentState(component.get()) == original,
                            "P19 real GUI limiter roundtrip corrupted component state");
                    if (pair % 12 == 0)
                        std::cout << "[INFO] P19 completed " << pair * 2
                                  << " actual GUI clicks with exact state recovery\n";
                }
                std::cout << "[PASS] P19 96 real GUI clicks and 48 state roundtrips\n";
            } else if (checkGuiLifecycle) {
                // P17: stress the actual production editor's VST3 lifecycle
                // without altering any musical settings. State is captured
                // from the processor, not inferred from editor appearance.
                const auto expected = captureActualComponentState(component.get());
                constexpr int kCycles = 16;
                for (int cycle = 1; cycle <= kCycles; ++cycle) {
                    require(view->removed() == kResultTrue,
                            "P17 view removal failed during repeated lifecycle");
                    attached = false;
                    require(view->attached(window.get(), kPlatformTypeHWND) == kResultTrue,
                            "P17 view re-attach failed during repeated lifecycle");
                    attached = true;
                    pump(35);
                    const HWND refreshed = getRealVstGuiWindow(window.get());
                    RECT current{};
                    require(GetClientRect(refreshed, &current) != 0 &&
                            current.right >= 700 && current.bottom >= 250,
                            "P17 reattached editor lost its native window");
                    require(captureActualComponentState(component.get()) == expected,
                            "P17 opening/closing GUI unexpectedly modified processor state");
                    std::cout << "[PASS] P17 genuine editor detach/reattach cycle "
                              << cycle << "/" << kCycles << " state unchanged\n";
                }
                std::cout << "[PASS] P17 all 16 editor lifecycle cycles stable\n";
            } else if (checkDragSourceOnly) {
                require(tempoClock != nullptr, "P13 source host tempo missing");
                runActualGuiDragSource(child, component.get(), *tempoClock,
                                       logicalHeight, originalState.parent_path());
            } else if (checkOleDrag) {
                require(tempoClock != nullptr, "P13 host tempo was not initialized");
                runActualOleDragDrop(child, window.get(), component.get(),
                                     *tempoClock, logicalHeight,
                                     originalState.parent_path());
            } else if (tempoClock) {
                runNativeGuiExportSave(child, component.get(), *tempoClock,
                                       logicalHeight, originalState.parent_path());
            } else if (exportDialogCancel) {
                runNativeExportDialogCancel(child, component.get(), logicalHeight,
                                            originalState.parent_path());
            } else {
            saveActualComponentState(component.get(), originalState);
            // A visible, stateful control independently proves that the
            // native pointer reaches the live controller AND the processor.
            // If it fails, don't interpret GENERATE/APPLY state as a plugin
            // defect: this host cannot yet reproduce real GUI input.
            const auto baseline = captureActualComponentState(component.get());
            clickRealDrumatorGui(child, 1122.5, 29.0,
                                 "CONTROL: toggle LIMIT OFF to ON");
            const auto afterLimiter = captureActualComponentState(component.get());
            require(afterLimiter != baseline,
                    "P09 GUI input bridge failed: LIMIT click produced no component change");
            std::cout << "[PASS] P09 positive control: actual GUI limiter click "
                         "changed processor state\n";
            clickRealDrumatorGui(child, 1122.5, 29.0,
                                 "CONTROL: restore limiter OFF");
            const auto restored = captureActualComponentState(component.get());
            require(restored == baseline,
                    "P09 limiter reversal failed to restore original project state");
            std::cout << "[PASS] P09 positive control: limiter toggled back to baseline\n";
            // Click real production Beat Creator button at its 1280px
            // logical header coordinates (center x=769,y=115).
            clickRealDrumatorGui(child, 769.0, 115.0, "OPEN Beat Creator");
            // Dialog is 820x252 centered, independent of editor height.
            const double footerY = (logicalHeight - 252.0) / 2.0 + 233.5;
            clickRealDrumatorGui(child, 522.5, footerY, "GENERATE A/B/C");
            clickRealDrumatorGui(child, 756.5, footerY, "CANCEL generator");
            saveActualComponentState(component.get(), canceledState);
            clickRealDrumatorGui(child, 769.0, 115.0, "REOPEN Beat Creator");
            clickRealDrumatorGui(child, 522.5, footerY, "GENERATE A/B/C again");
            // Factory pattern A already contains kick notes. Product UI
            // explicitly requires a second APPLY click to confirm overwriting
            // occupied A/B/C slots. One click only opens the confirmation.
            clickRealDrumatorGui(child, 639.5, footerY,
                                 "APPLY: request occupied-pattern confirmation");
            clickRealDrumatorGui(child, 639.5, footerY,
                                 "CONFIRM: overwrite occupied A/B/C");
            pump(250);
            saveActualComponentState(component.get(), appliedState);
            }
            require(view->removed() == kResultTrue,
                    "P09 product IPlugView::removed failed");
            attached = false;
            require(view->setFrame(nullptr) == kResultTrue,
                    "P09 product IPlugView::setFrame(nullptr) failed");
            frameAssigned = false;
            frame->release();
            frame = nullptr;
        } catch (...) {
            if (attached) (void)view->removed();
            if (frameAssigned) (void)view->setFrame(nullptr);
            if (frame) frame->release();
            view->release();
            throw;
        }
        view->release();
        // VST3 requires processing stop and deactivation BEFORE terminate.
        tempoClock.reset();
        controller.close();
        require(component->terminate() == kResultOk, "P09 component terminate failed");
        std::cout << "[PASS] P09 real Drumator GUI HWND opened, "
                     "CANCEL and APPLY action sequences dispatched\n";
        return;
    }
    throw std::runtime_error("P09 no audio plugin class found");
}

} // namespace

int main(int argc, char** argv) {
    std::cout << std::unitbuf;
    std::cerr << std::unitbuf;
    try {
        ComApartment guiCom;
        if (argc == 3 && std::string(argv[1]) == "--ole-receiver-contract") {
            runOleReceiverContract(argv[2]);
            return 0;
        }
        if (argc == 4 && std::string(argv[1]) == "--drumator-gui-control-stress") {
            const std::filesystem::path folder = argv[3];
            runRealDrumatorGui(argv[2], folder/"before.bin",
                              folder/"cancel.bin", folder/"after.bin",
                              false, {}, false, false, false, true);
            return 0;
        }
        if (argc == 4 && std::string(argv[1]) == "--drumator-gui-lifecycle") {
            const std::filesystem::path folder = argv[3];
            runRealDrumatorGui(argv[2], folder/"before.bin",
                              folder/"cancel.bin", folder/"after.bin",
                              false, {}, false, false, true);
            return 0;
        }
        if (argc == 5 && std::string(argv[1]) == "--drumator-drag-source") {
            const std::filesystem::path folder = argv[4];
            runRealDrumatorGui(argv[2], folder/"before.bin",
                              folder/"cancel.bin", folder/"after.bin",
                              false, argv[3], false, true);
            return 0;
        }
        if (argc == 5 && std::string(argv[1]) == "--drumator-ole-drag-drop") {
            const std::filesystem::path folder = argv[4];
            runRealDrumatorGui(argv[2], folder/"before.bin",
                              folder/"cancel.bin", folder/"after.bin",
                              false, argv[3], true);
            return 0;
        }
        if (argc == 5 && std::string(argv[1]) == "--drumator-export-dialog-save") {
            const std::filesystem::path folder = argv[4];
            runRealDrumatorGui(argv[2], folder / "before.bin",
                              folder / "cancel.bin", folder / "after.bin",
                              false, argv[3]);
            return 0;
        }
        if (argc == 4 && std::string(argv[1]) == "--drumator-export-dialog-cancel") {
            const std::filesystem::path folder = argv[3];
            runRealDrumatorGui(argv[2], folder / "before.bin",
                              folder / "cancel.bin", folder / "after.bin", true);
            return 0;
        }
        if (argc == 6 && std::string(argv[1]) == "--drumator-beat-creator") {
            runRealDrumatorGui(argv[2], argv[3], argv[4], argv[5]);
            return 0;
        }
        if (argc == 9 && (std::string(argv[1]) == "--explore-gui-click" ||
                          std::string(argv[1]) == "--explore-gui-sham")) {
            const int x = workflowInt(argv[3], 8191);
            const int y = workflowInt(argv[4], 8191);
            return exploreOneGuiClick(argv[2], x, y,
                                      std::string(argv[1]) == "--explore-gui-click",
                                      argv[5], argv[6], argv[7], argv[8]);
        }
        if (argc == 6 && std::string(argv[1]) == "--gui-workflow")
            return runGuiWorkflow(argv[2], argv[3], argv[4], argv[5]);
        if (argc == 8 && std::string(argv[1]) == "--prove-click-at-from") {
            const int x = std::stoi(argv[4]);
            const int y = std::stoi(argv[5]);
            const double initial = std::stod(argv[6]);
            const double expected = std::stod(argv[7]);
            require(x >= 0 && y >= 0 && std::isfinite(initial) &&
                    std::isfinite(expected) && initial >= 0.0 && initial <= 1.0 &&
                    expected >= 0.0 && expected <= 1.0 &&
                    std::abs(initial - expected) > 0.00001,
                    "invalid bidirectional GUI click oracle");
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])),
                       x, y, expected, {}, initial);
        }
        if (argc == 9 && std::string(argv[1]) == "--prove-click-and-snapshot-from") {
            const int x = std::stoi(argv[4]);
            const int y = std::stoi(argv[5]);
            const double initial = std::stod(argv[6]);
            const double expected = std::stod(argv[7]);
            require(x >= 0 && y >= 0 && std::isfinite(initial) &&
                    std::isfinite(expected) && initial >= 0.0 && initial <= 1.0 &&
                    expected >= 0.0 && expected <= 1.0 &&
                    std::abs(initial - expected) > 0.00001,
                    "invalid screenshot click initial/final values");
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])),
                       x, y, expected, std::filesystem::path(argv[8]), initial);
        }
        if (argc == 7 && std::string(argv[1]) == "--prove-click-at") {
            const int x = std::stoi(argv[4]);
            const int y = std::stoi(argv[5]);
            const double expected = std::stod(argv[6]);
            require(x >= 0 && y >= 0 && std::isfinite(expected) &&
                    expected > 0.0 && expected <= 1.0,
                    "invalid GUI control coordinates or expected normalized value");
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])),
                       x, y, expected);
        }
        if (argc == 8 && std::string(argv[1]) == "--prove-click-and-snapshot") {
            const int x = std::stoi(argv[4]);
            const int y = std::stoi(argv[5]);
            const double expected = std::stod(argv[6]);
            require(x >= 0 && y >= 0 && std::isfinite(expected) &&
                    expected > 0.0 && expected <= 1.0,
                    "invalid GUI interaction parameters");
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])),
                       x, y, expected, std::filesystem::path(argv[7]));
        }
        if (argc == 4 && std::string(argv[1]) == "--inventory-parameters")
            return inventoryParameters(argv[2],argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--sweep-parameters")
            return sweepParameters(argv[2], argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--verify-parameter-text")
            return verifyParameterText(argv[2], argv[3]);
        if (argc == 4 && std::string(argv[1]) == "--snapshot-editor")
            return run(argv[2], false, 0, -1, -1, 1.0,
                       std::filesystem::path(argv[3]));
        if (argc == 3 && std::string(argv[1]) == "--probe")
            return run(argv[2], false, 0);
        if (argc == 4 && std::string(argv[1]) == "--prove-click")
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])));
        std::cerr << "Usage: 125A_Test_Lab_GUI --inventory-parameters <plugin.vst3> <parameters.tsv>\n"                  << "       125A_Test_Lab_GUI --gui-workflow <plugin.vst3> <approved-actions.tsv> <report.tsv> <screenshots-dir>\n"
                  << "       125A_Test_Lab_GUI --explore-gui-click <plugin.vst3> <x> <y> <native.tsv> <baseline-a.bmp> <baseline-b.bmp> <after.bmp>\n"
                  << "       125A_Test_Lab_GUI --explore-gui-sham <plugin.vst3> <x> <y> <native.tsv> <baseline-a.bmp> <baseline-b.bmp> <after.bmp>\n"
                  << "       125A_Test_Lab_GUI --sweep-parameters <plugin.vst3> <sweep.tsv>\n"
                  << "       125A_Test_Lab_GUI --verify-parameter-text <plugin.vst3> <text.tsv>\n"

                  << "       125A_Test_Lab_GUI --prove-click-and-snapshot <plugin.vst3> <param-id> <x> <y> <expected> <output.bmp>\n"
                  << "       125A_Test_Lab_GUI --snapshot-editor <plugin.vst3> <output.bmp>\n"
                  << "       125A_Test_Lab_GUI --probe <plugin.vst3>\n"
                  << "       125A_Test_Lab_GUI --prove-click <plugin.vst3> <param-id>\n"
                  << "       125A_Test_Lab_GUI --prove-click-at <plugin.vst3> <param-id> <x> <y> <expected-normalized>\n"
                  << "       125A_Test_Lab_GUI --prove-click-at-from <plugin.vst3> <param-id> <x> <y> <initial> <expected>\n"
                  << "       125A_Test_Lab_GUI --prove-click-and-snapshot-from <plugin.vst3> <param-id> <x> <y> <initial> <expected> <output.bmp>\n"
                  << "       125A_Test_Lab_GUI --drumator-beat-creator <plugin.vst3> <before.bin> <cancel.bin> <after.bin>\n"
                  << "       125A_Test_Lab_GUI --drumator-export-dialog-cancel <plugin.vst3> <evidence-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-export-dialog-save <plugin.vst3> <state.bin> <output-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-ole-drag-drop <plugin.vst3> <state.bin> <output-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-drag-source <plugin.vst3> <state.bin> <output-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-gui-lifecycle <plugin.vst3> <output-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-gui-control-stress <plugin.vst3> <output-folder>\n";
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
