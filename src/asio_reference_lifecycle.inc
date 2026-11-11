// P183: exercise a real source-built VST3 module's lifecycle before any
// physical ASIO access. Specifically catches inherited/non-OK setProcessing.
// This path creates NO IASIO device, NO audio evidence and NO release PASS.
int referenceInstrumentLifecycleSelfTest(int argc, char** argv) {
    const auto path=std::filesystem::u8path(requireArg(argc,argv,"--plugin"));
    ensure(std::filesystem::exists(path)&&path.extension()==".vst3",
           "P183 requires an actual x64 VST3 module");
    std::string error;
    auto module=Module::create(path.string(),error);
    ensure(bool(module),"P183 unable to load VST3 reference module");
    HostApplication host;
    auto factory=module->getFactory();
    factory.setHostContext(&host);
    int audioClasses=0;
    for(const auto& cls:factory.classInfos())
        if(cls.category()==kVstAudioEffectClass)++audioClasses;
    ensure(audioClasses==1,"P183 reference module must contain one audio class");
    for(const auto& cls:factory.classInfos()) {
        if(cls.category()!=kVstAudioEffectClass)continue;
        auto component=factory.createInstance<IComponent>(cls.ID());
        ensure(bool(component),"P183 IComponent instance missing");
        ensure(component->initialize(&host)==kResultOk,
               "P183 reference VST3 initialize failed");
        IAudioProcessor* processor{};
        bool active=false, processing=false;
        try {
            ensure(component->queryInterface(IAudioProcessor::iid,
                 reinterpret_cast<void**>(&processor))==kResultOk&&processor,
                   "P183 real module missing IAudioProcessor");
            ensure(processor->canProcessSampleSize(kSample32)==kResultTrue,
                   "P183 reference does not accept 32-bit float");
            Processing audio;
            audio.prepare(component.get(),512,44100.0);
            ProcessSetup setup{};
            setup.processMode=kRealtime;
            setup.symbolicSampleSize=kSample32;
            setup.maxSamplesPerBlock=512;
            setup.sampleRate=44100.0;
            ensure(processor->setupProcessing(setup)==kResultOk,
                   "P183 reference setupProcessing failed");
            ensure(component->setActive(true)==kResultOk,
                   "P183 reference setActive(true) failed");
            active=true;
            ensure(processor->setProcessing(true)==kResultOk,
                   "P183 reference setProcessing(true) failed");
            processing=true;

            auto render=[&](int midiEvent)->float {
                audio.midiEvents.clear();
                if(midiEvent!=0) {
                    Event event{};
                    event.sampleOffset=0;
                    if(midiEvent>0) {
                        event.type=Event::kNoteOnEvent;
                        event.noteOn.channel=0;event.noteOn.pitch=48;
                        event.noteOn.velocity=100.f/127.f;
                        event.noteOn.noteId=47;
                    }else{
                        event.type=Event::kNoteOffEvent;
                        event.noteOff.channel=0;event.noteOff.pitch=48;
                        event.noteOff.velocity=0.f;event.noteOff.noteId=47;
                    }
                    ensure(audio.midiEvents.addEvent(event)==kResultOk,
                           "P183 reference MIDI event insertion failed");
                }
                for(auto& bus:audio.outputs)for(auto& ch:bus.channels)
                    std::fill(ch.begin(),ch.end(),0.f);
                ensure(processor->process(audio.data)==kResultOk,
                       "P183 reference process with MIDI failed");
                float peak=0.f;
                for(int ch=0;ch<2;++ch)for(float v:audio.outputs[0].channels[ch]){
                    ensure(std::isfinite(v),"P183 reference emitted nonfinite PCM");
                    peak=std::max(peak,std::abs(v));
                }
                return peak;
            };
            const auto before=render(0);
            ensure(before==0.f,
                   "P183 reference generated audio without a MIDI NoteOn");
            const auto during=render(1);
            ensure(during>0.04f&&during<=0.051f,
                   "P183 reference NoteOn 48 produced no known audible PCM");
            const auto after=render(-1);
            ensure(after==0.f,
                   "P183 reference did not silence on NoteOff 48");
            ensure(processor->setProcessing(false)==kResultOk,
                   "P183 reference setProcessing(false) failed");
            processing=false;
            ensure(component->setActive(false)==kResultOk,
                   "P183 reference setActive(false) failed");
            active=false;
        }catch(...){
            if(processing)(void)processor->setProcessing(false);
            if(active)(void)component->setActive(false);
            if(processor)processor->release();
            (void)component->terminate();
            throw;
        }
        processor->release();
        ensure(component->terminate()==kResultOk,
               "P183 reference terminate failed");
    }
    std::cout<<"[PASS] P183 real VST3 lifecycle setProcessing + MIDI48"
                " silence->PCM->silence; NO physical ASIO driver was opened\n";
    return 0;
}
