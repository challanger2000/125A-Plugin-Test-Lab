// P04 minimal Win32 editor host, with observable native mouse-to-VST3
// parameter assertion. No vendor DAW dependency or product source code.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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


std::vector<std::uint8_t> captureActualComponentState(IComponent* component) {
    ResizableMemoryIBStream stream;
    require(component->getState(&stream) == kResultOk,
            "P09 cannot read live VST3 component state");
    const auto bytes = stream.getCursor();
    require(bytes > 64 && bytes < 16 * 1024 * 1024,
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
    require(size >= 64 && size < 16 * 1024 * 1024,
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
        require(len > 0 && len < 16 * 1024 * 1024,
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

void runRealDrumatorGui(const std::string& path,
                        const std::filesystem::path& originalState,
                        const std::filesystem::path& canceledState,
                        const std::filesystem::path& appliedState,
                        bool exportDialogCancel = false,
                        const std::filesystem::path& exportSaveState = {}) {
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

            if (tempoClock) {
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
        if (argc == 3 && std::string(argv[1]) == "--probe")
            return run(argv[2], false, 0);
        if (argc == 4 && std::string(argv[1]) == "--prove-click")
            return run(argv[2], true, static_cast<ParamID>(std::stoul(argv[3])));
        std::cerr << "Usage: 125A_Test_Lab_GUI --probe <plugin.vst3>\n"
                  << "       125A_Test_Lab_GUI --prove-click <plugin.vst3> <param-id>\n"
                  << "       125A_Test_Lab_GUI --drumator-beat-creator <plugin.vst3> <before.bin> <cancel.bin> <after.bin>\n"
                  << "       125A_Test_Lab_GUI --drumator-export-dialog-cancel <plugin.vst3> <evidence-folder>\n"
                  << "       125A_Test_Lab_GUI --drumator-export-dialog-save <plugin.vst3> <state.bin> <output-folder>\n";
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
