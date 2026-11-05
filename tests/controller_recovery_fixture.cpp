// P30 real VST3 component/controller recovery fixtures
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstaudioeffect.h"
#include "public.sdk/source/vst/vsteditcontroller.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/vstspeaker.h"
#include <atomic>
using namespace Steinberg;
using namespace Steinberg::Vst;
#ifndef P30_MODE
#define P30_MODE 0
#endif
namespace {
const FUID componentId(0x125A3030,0x20261105,0x30000000+P30_MODE,0x12340000+P30_MODE);
const FUID controllerId(0x125A3031,0x20261105,0x30000000+P30_MODE,0x12340000+P30_MODE);
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
#if P30_MODE==0
constexpr const char* processorName="125A QA Controller Recovery Good";
constexpr const char* controllerName="125A QA Recovery Controller";
#else
constexpr const char* processorName="125A QA Controller Recovery Stale";
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
