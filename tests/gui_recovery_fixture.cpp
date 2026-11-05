#define WIN32_LEAN_AND_MEAN
#include <windows.h>
// P30 real VST3 component/controller recovery fixtures
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "public.sdk/source/common/pluginview.h"
#include <cstring>
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include <atomic>
using namespace Steinberg;
using namespace Steinberg::Vst;
#ifndef P30_MODE
#define P30_MODE 0
#endif
namespace {
const FUID componentId(0x125A3130,0x20261105,0x31000000+P30_MODE,0x12340000+P30_MODE);
const FUID controllerId(0x125A3131,0x20261105,0x31000000+P30_MODE,0x12340000+P30_MODE);
constexpr uint32 kMagic=0x125A2526;
struct State {uint32 magic;int32 bank;int32 program;uint32 check;};
bool valid(const State& s) {
  return s.magic==kMagic&&s.check==(kMagic^uint32(s.bank)^(uint32(s.program)<<8))&&
      ((s.bank==11&&s.program==22)||(s.bank==33&&s.program==44));
}
class Processor final:public AudioEffect {
public:
  static FUnknown* createInstance(void*){return static_cast<IAudioProcessor*>(new Processor);}
  tresult PLUGIN_API initialize(FUnknown* context) override {
    if(AudioEffect::initialize(context)!=kResultOk)return kResultFalse;
    addAudioOutput(STR16("Stereo"),SpeakerArr::kStereo);
    return kResultOk;
  }
  tresult PLUGIN_API getControllerClassId(TUID id) override {
    controllerId.toTUID(id);return kResultOk;
  }
  tresult PLUGIN_API setProcessing(TBool) override{return kResultOk;}
  tresult PLUGIN_API setState(IBStream* stream) override {
    if(!stream)return kInvalidArgument;
    State state{};int32 count=0;
    if(stream->read(&state,sizeof(state),&count)!=kResultOk||count!=sizeof(state)||!valid(state))
      return kResultFalse;
    bank_.store(state.bank,std::memory_order_release);
    program_.store(state.program,std::memory_order_release);
    return kResultOk;
  }
  tresult PLUGIN_API getState(IBStream* stream) override {
    if(!stream)return kInvalidArgument;
    const int32 bank=bank_.load(std::memory_order_acquire);
    const int32 program=program_.load(std::memory_order_acquire);
    State state{kMagic,bank,program,kMagic^uint32(bank)^(uint32(program)<<8)};
    int32 written=0;
    return stream->write(&state,sizeof(state),&written)==kResultOk&&
        written==sizeof(state)?kResultOk:kResultFalse;
  }
  tresult PLUGIN_API process(ProcessData& data) override {
    if(data.symbolicSampleSize!=kSample32||data.numSamples<0||data.numOutputs!=1||
       !data.outputs||data.outputs[0].numChannels!=2||
       !data.outputs[0].channelBuffers32)return kResultFalse;
    const auto gain=Sample32(bank_.load(std::memory_order_acquire)==11?0.25f:0.125f);
    for(int c=0;c<2;++c) {
      auto* samples=data.outputs[0].channelBuffers32[c];if(!samples)return kResultFalse;
      for(int i=0;i<data.numSamples;++i)samples[i]=gain;
    }
    data.outputs[0].silenceFlags=0;
    return kResultOk;
  }
private:
  std::atomic<int32> bank_{11},program_{22};
};
class Controller;
class StatusView final:public CPluginView {
public:
  explicit StatusView(Controller* owner):CPluginView(nullptr),owner_(owner) {
    setRect(ViewRect(0,0,320,180));
  }
  tresult PLUGIN_API isPlatformTypeSupported(FIDString type) override {
    return type&&std::strcmp(type,kPlatformTypeHWND)==0?kResultTrue:kResultFalse;
  }
  tresult PLUGIN_API attached(void* parent,FIDString type) override;
  tresult PLUGIN_API removed() override;
private:
  static LRESULT CALLBACK windowProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp);
  Controller* owner_{};
  HWND child_{};
};
class Controller final:public EditController {
public:
  static FUnknown* createInstance(void*){return static_cast<IEditController*>(new Controller);}
  tresult PLUGIN_API initialize(FUnknown* context) override {
    if(EditController::initialize(context)!=kResultOk)return kResultFalse;
    parameters.addParameter(STR16("Bank"),nullptr,0,11.0/100.0,
                            ParameterInfo::kCanAutomate,1001);
    parameters.addParameter(STR16("Program"),nullptr,0,22.0/100.0,
                            ParameterInfo::kCanAutomate,1002);
    return kResultOk;
  }
  IPlugView* PLUGIN_API createView(FIDString type) override {
    if(!type||std::strcmp(type,ViewType::kEditor)!=0)return nullptr;
    return new StatusView(this);
  }
  COLORREF visibleColor() {
    const auto v=getParamNormalized(1001);
    return v>0.2?RGB(220,110,40):RGB(40,140,220);
  }
  tresult PLUGIN_API setComponentState(IBStream* stream) override {
    if(!stream)return kInvalidArgument;
    State state{};int32 count=0;
    if(stream->read(&state,sizeof(state),&count)!=kResultOk||count!=sizeof(state)||!valid(state))
      return kResultFalse;
#if P30_MODE==1
    if(hasSeen_.exchange(true,std::memory_order_acq_rel))return kResultOk;
#endif
    (void)setParamNormalized(1001,double(state.bank)/100.);
    (void)setParamNormalized(1002,double(state.program)/100.);
    return kResultOk;
  }
private:
  std::atomic<bool> hasSeen_{false};
};
LRESULT CALLBACK StatusView::windowProc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp) {
  if(msg==WM_NCCREATE) {
    const auto* cs=reinterpret_cast<CREATESTRUCTW*>(lp);
    SetWindowLongPtrW(hwnd,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(cs->lpCreateParams));
    return TRUE;
  }
  if(msg==WM_PAINT) {
    auto* self=reinterpret_cast<StatusView*>(GetWindowLongPtrW(hwnd,GWLP_USERDATA));
    PAINTSTRUCT ps{};
    const HDC dc=BeginPaint(hwnd,&ps);
    RECT rect{};GetClientRect(hwnd,&rect);
    const HBRUSH brush=CreateSolidBrush(
       self&&self->owner_?self->owner_->visibleColor():RGB(0,0,0));
    FillRect(dc,&rect,brush);DeleteObject(brush);
    EndPaint(hwnd,&ps);return 0;
  }
  return DefWindowProcW(hwnd,msg,wp,lp);
}
tresult PLUGIN_API StatusView::attached(void* parent,FIDString type) {
  if(!parent||isPlatformTypeSupported(type)!=kResultTrue)return kResultFalse;
  if(CPluginView::attached(parent,type)!=kResultTrue)return kResultFalse;
  static const wchar_t className[]=L"125A_P31_RecoveryVisualFixture";
  WNDCLASSW wc{};wc.hInstance=GetModuleHandleW(nullptr);
  wc.lpfnWndProc=&StatusView::windowProc;wc.lpszClassName=className;
  if(!RegisterClassW(&wc)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)
    return kResultFalse;
  child_=CreateWindowExW(0,className,L"P31",WS_CHILD|WS_VISIBLE,
      0,0,320,180,static_cast<HWND>(parent),nullptr,
      GetModuleHandleW(nullptr),this);
  return child_?kResultTrue:kResultFalse;
}
tresult PLUGIN_API StatusView::removed(){
  if(child_) {DestroyWindow(child_);child_=nullptr;}
  return CPluginView::removed();
}
#if P30_MODE==0
constexpr const char* processorName="125A QA Visual Recovery Good";
constexpr const char* controllerName="125A QA Recovery Controller";
#else
constexpr const char* processorName="125A QA Visual Recovery Stale";
constexpr const char* controllerName="125A QA Recovery Stale Controller";
#endif
}
BEGIN_FACTORY_DEF("125A Universal QA","https://github.com/challanger2000","qa@125a.invalid")
DEF_CLASS2(INLINE_UID_FROM_FUID(componentId),PClassInfo::kManyInstances,
  kVstAudioEffectClass,processorName,Vst::kDistributable,"Fx","0.1",
  kVstVersionString,Processor::createInstance)
DEF_CLASS2(INLINE_UID_FROM_FUID(controllerId),PClassInfo::kManyInstances,
  kVstComponentControllerClass,controllerName,0,"","0.1",
  kVstVersionString,Controller::createInstance)
END_FACTORY
