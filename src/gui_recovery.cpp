#define WIN32_LEAN_AND_MEAN
#include <windows.h>
// P30 generic native VST3 IComponent/IEditController connection recovery probe.
// Domain expectations are supplied ONLY by the independent Python oracle.
// Real GUI pixel/display verification is deliberately NOT COVERED.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/utility/memoryibstream.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivstmessage.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/vst/vsttypes.h"
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace Steinberg;
using namespace Steinberg::Vst;
using namespace VST3::Hosting;
namespace {
void need(bool cond,const char* why){if(!cond)throw std::runtime_error(why);}
struct State {uint32 magic;int32 bank;int32 program;uint32 checksum;};
constexpr uint32 kMagic=0x125A2526;
State stateFor(int32 b,int32 p) {
  return {kMagic,b,p,kMagic^uint32(b)^(uint32(p)<<8)};
}
bool setState(IComponent* component,IEditController* controller,const State& s) {
  ResizableMemoryIBStream processorState;
  int32 wrote=0;
  need(processorState.write(const_cast<State*>(&s),sizeof(s),&wrote)==kResultOk&&
       wrote==sizeof(s),"cannot stage processor state");
  processorState.rewind();
  if(component->setState(&processorState)!=kResultOk)return false;
  ResizableMemoryIBStream controllerState;
  wrote=0;
  need(controllerState.write(const_cast<State*>(&s),sizeof(s),&wrote)==kResultOk&&
       wrote==sizeof(s),"cannot stage controller state");
  controllerState.rewind();
  need(controller->setComponentState(&controllerState)==kResultOk,"controller denied valid synchronized state");
  return true;
}
State readState(IComponent* component) {
  ResizableMemoryIBStream state;
  need(component->getState(&state)==kResultOk&&state.getCursor()==sizeof(State),
       "processor getState returned invalid size/status");
  State s{};
  std::memcpy(&s,state.getData(),sizeof(s));
  return s;
}
float render(IAudioProcessor* processor){
  std::array<Sample32,64> left{},right{};
  Sample32* channel[]{left.data(),right.data()};
  AudioBusBuffers bus{};bus.numChannels=2;bus.channelBuffers32=channel;
  ProcessData data{};data.processMode=kRealtime;data.symbolicSampleSize=kSample32;
  data.numSamples=64;data.numOutputs=1;data.outputs=&bus;
  need(processor->process(data)==kResultOk,"process after connection state change failed");
  for(int i=0;i<64;++i)
    need(std::isfinite(left[size_t(i)])&&std::isfinite(right[size_t(i)]),
         "nonfinite PCM after controller sync");
  return left[0];
}
void snapshot(std::ostream& out,const char* label,IComponent* component,
              IEditController* controller,IAudioProcessor* processor,HWND parent){
  HWND child=GetWindow(parent,GW_CHILD);
  need(child&&IsWindow(child),"IPlugView has no Win32 child HWND");
  InvalidateRect(child,nullptr,TRUE);
  need(UpdateWindow(child)!=FALSE,"editor did not repaint successfully");
  HDC dc=GetDC(child);
  need(dc!=nullptr,"GUI device context unavailable");
  const COLORREF pixel=GetPixel(dc,160,90);
  ReleaseDC(child,dc);
  need(pixel!=CLR_INVALID,"GUI pixel read invalid");
  const auto s=readState(component);
  out<<label<<"\t"<<s.bank<<"\t"<<s.program<<"\t"
     <<controller->getParamNormalized(1001)<<"\t"
     <<controller->getParamNormalized(1002)<<"\t"
     <<render(processor)<<"\t"
     <<int(GetRValue(pixel))<<"\t"<<int(GetGValue(pixel))<<"\t"
     <<int(GetBValue(pixel))<<"\n";
}
int run(const std::string& path,const std::filesystem::path& output){
  std::string error;auto module=Module::create(path,error);
  need(bool(module),"cannot load VST3 production API module");
  HostApplication host;auto factory=module->getFactory();
  factory.setHostContext(&host);
  int classes=0;
  for(const auto& info:factory.classInfos()){
    if(info.category()!=kVstAudioEffectClass)continue;
    ++classes;if(classes>1)continue;
    auto component=factory.createInstance<IComponent>(info.ID());
    need(bool(component),"cannot instantiate IComponent");
    need(component->initialize(&host)==kResultOk,"component initialization failed");
    TUID controllerId{};
    need(component->getControllerClassId(controllerId)==kResultOk,
         "no separate controller class");
    auto controller=factory.createInstance<IEditController>(VST3::UID(controllerId));
    need(bool(controller),"IEditController cannot be constructed");
    need(controller->initialize(&host)==kResultOk,"controller initialize failed");
    IAudioProcessor* processor=nullptr;
    need(component->queryInterface(IAudioProcessor::iid,
       reinterpret_cast<void**>(&processor))==kResultOk&&processor,
       "processor unavailable");
    IConnectionPoint* componentPoint=nullptr;
    IConnectionPoint* controllerPoint=nullptr;
    need(component->queryInterface(IConnectionPoint::iid,
       reinterpret_cast<void**>(&componentPoint))==kResultOk&&componentPoint,
       "component IConnectionPoint unavailable");
    need(controller->queryInterface(IConnectionPoint::iid,
       reinterpret_cast<void**>(&controllerPoint))==kResultOk&&controllerPoint,
       "controller IConnectionPoint unavailable");
    // Real Win32 plugin editor: use actual VST3 IPlugView::attached(HWND).
    IPlugView* view=controller->createView(ViewType::kEditor);
    need(view!=nullptr,"VST3 controller does not provide native editor view");
    HWND visualParent=nullptr;
    bool viewAttached=false;
    auto closeView=[&]() {
      if(viewAttached) {(void)view->removed();viewAttached=false;}
      if(visualParent) {DestroyWindow(visualParent);visualParent=nullptr;}
      if(view){view->release();view=nullptr;}
    };
    bool connected=false,active=false,processing=false;
    try{
      need(component->getBusCount(kAudio,kOutput)==1,"one stereo output required by adapter");
      BusInfo bus{};
      need(component->getBusInfo(kAudio,kOutput,0,bus)==kResultOk&&bus.channelCount==2,
           "stereo output required by adapter");
      (void)component->activateBus(kAudio,kOutput,0,true);
      ProcessSetup setup{};setup.sampleRate=48000.;setup.maxSamplesPerBlock=64;
      setup.processMode=kRealtime;setup.symbolicSampleSize=kSample32;
      need(processor->setupProcessing(setup)==kResultOk,"setupProcessing failed");
      need(component->setActive(true)==kResultOk,"setActive failed");active=true;
      need(processor->setProcessing(true)==kResultOk,"setProcessing failed");processing=true;
      need(componentPoint->connect(controllerPoint)==kResultOk &&
           controllerPoint->connect(componentPoint)==kResultOk,"initial connect rejected");
      connected=true;
      ViewRect geometry{};
      need(view->getSize(&geometry)==kResultOk &&
           geometry.getWidth()>=200 && geometry.getHeight()>=100,
           "native editor geometry invalid");
      visualParent=CreateWindowExW(WS_EX_TOOLWINDOW,L"STATIC",L"P31 Native GUI",
          WS_OVERLAPPEDWINDOW|WS_VISIBLE,100,100,
          geometry.getWidth()+32,geometry.getHeight()+64,
          nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
      need(visualParent!=nullptr,"cannot create real Win32 GUI parent");
      need(view->isPlatformTypeSupported(kPlatformTypeHWND)==kResultTrue,
           "VST3 editor lacks HWND support");
      need(view->attached(visualParent,kPlatformTypeHWND)==kResultTrue,
           "VST3 editor refused actual HWND attachment");
      viewAttached=true;
      ShowWindow(visualParent,SW_SHOWNA);
      UpdateWindow(visualParent);
      if(!output.parent_path().empty())std::filesystem::create_directories(output.parent_path());
      std::ofstream file(output,std::ios::trunc);
      need(bool(file),"evidence file unavailable");
      file<<"schema\t125A-P31-v1\n";
      need(setState(component.get(),controller.get(),stateFor(11,22)),
           "initial state A rejected");
      snapshot(file,"initial",component.get(),controller.get(),processor,visualParent);
      need(componentPoint->disconnect(controllerPoint)==kResultOk &&
           controllerPoint->disconnect(componentPoint)==kResultOk,"disconnect rejected");
      connected=false;
      // Failure injection: invalid state after disconnect must not corrupt
      // the actual component. An explicitly separate oracle checks that.
      const State invalid=stateFor(99,99);
      ResizableMemoryIBStream failed;int32 wrote=0;
      need(failed.write(const_cast<State*>(&invalid),sizeof(invalid),&wrote)==kResultOk,
           "cannot stage invalid state");failed.rewind();
      need(component->setState(&failed)!=kResultOk,"invalid disconnected state accepted");
      snapshot(file,"after_reject",component.get(),controller.get(),processor,visualParent);
      // The processor is updated while connection is down. Reconnecting
      // alone is not a semantic sync: explicitly send component state.
      ResizableMemoryIBStream newProcessor;const State next=stateFor(33,44);
      wrote=0;
      need(newProcessor.write(const_cast<State*>(&next),sizeof(next),&wrote)==kResultOk,
           "cannot stage valid recovery");newProcessor.rewind();
      need(component->setState(&newProcessor)==kResultOk,"recovery state rejected");
      need(componentPoint->connect(controllerPoint)==kResultOk &&
           controllerPoint->connect(componentPoint)==kResultOk,
           "reconnect rejected");
      connected=true;
      ResizableMemoryIBStream sync;
      wrote=0;need(sync.write(const_cast<State*>(&next),sizeof(next),&wrote)==kResultOk,
                   "cannot stage controller sync");sync.rewind();
      need(controller->setComponentState(&sync)==kResultOk,
           "controller refused recovery component state");
      snapshot(file,"after_reconnect",component.get(),controller.get(),processor,visualParent);
      need(setState(component.get(),controller.get(),stateFor(11,22)),
           "final restore to A rejected");
      snapshot(file,"after_restore",component.get(),controller.get(),processor,visualParent);
      file.flush();need(file.good(),"evidence flush failed");
      closeView();
      if(connected){
        (void)componentPoint->disconnect(controllerPoint);
        (void)controllerPoint->disconnect(componentPoint);connected=false;
      }
      need(processor->setProcessing(false)==kResultOk,"setProcessing(false) failed");
      processing=false;
      need(component->setActive(false)==kResultOk,"setActive(false) failed");
      active=false;
    }catch(...){
      closeView();
      if(connected){
        (void)componentPoint->disconnect(controllerPoint);
        (void)controllerPoint->disconnect(componentPoint);
      }
      if(processing)(void)processor->setProcessing(false);
      if(active)(void)component->setActive(false);
      componentPoint->release();controllerPoint->release();processor->release();
      (void)controller->terminate();(void)component->terminate();
      throw;
    }
    componentPoint->release();controllerPoint->release();processor->release();
    need(controller->terminate()==kResultOk,"controller termination failed");
    need(component->terminate()==kResultOk,"component termination failed");
    std::cout<<"[PASS] P31 native VST3 connect/disconnect/reconnect API sequence; independent state oracle required\n";
  }
  need(classes>0,"no VST3 processor class");
  return 0;
}
}
int main(int argc,char** argv){
  try{
    if(argc!=4||std::string(argv[1])!="--connection"){
      std::cerr<<"Usage: --connection <plugin.vst3> <evidence.tsv>\n";return 2;
    }
    return run(argv[2],argv[3]);
  }catch(const std::exception& e){
    std::cerr<<"[FAIL] P31 native controller host: "<<e.what()<<"\n";return 1;
  }
}
