// P101. Included only inside physical_asio.cpp's anonymous namespace.
// Real IASIO capability readback, never a synthetic hardware acceptance.
inline bool asioFramesAllowed(long frames,long min,long max,long pref,long gran) {
    if(min<1 || max<min || frames<min || frames>max)return false;
    if(gran==-1)return (frames&(frames-1))==0;
    if(gran==0)return frames==pref;
    return gran>0 && ((frames-min)%gran)==0;
}
inline long asioChooseFrames(long min,long max,long pref,long gran) {
    long best=0;
    int64_t distance=std::numeric_limits<int64_t>::max();
    for(long f=64;f<=4096;++f) {
        if(!asioFramesAllowed(f,min,max,pref,gran))continue;
        const int64_t delta=int64_t(f)-int64_t(pref);
        const int64_t d=delta<0?-delta:delta;
        if(d<distance||(d==distance&&f<best)) {
            best=f;
            distance=d;
        }
    }
    ensure(best!=0,"Driver has no supported ASIO buffer in safe 64..4096 frame range");
    return best;
}
inline int asioBufferSelfTest() {
    ensure(asioFramesAllowed(512,64,1024,512,0),
           "P101 preferred frames incorrectly rejected");
    ensure(!asioFramesAllowed(256,64,1024,512,0),
           "P101 unsupported 256 frames incorrectly accepted");
    ensure(asioChooseFrames(64,1024,512,0)==512,
           "P101 preferred-only buffer chooser");
    ensure(asioChooseFrames(64,2048,512,-1)==512,
           "P101 power-of-two chooser");
    ensure(!asioFramesAllowed(768,64,2048,512,-1),
           "P101 rejected power-of-two negative");
    ensure(asioChooseFrames(192,1024,500,64)==512,
           "P101 granular step chooser");
    ensure(asioChooseFrames(64,4096,2048,0)==2048,
           "P101 larger preferred size");
    bool rejected=false;
    try {(void)asioChooseFrames(8192,16384,8192,0);}
    catch(const std::exception&){rejected=true;}
    ensure(rejected,"P101 out-of-contract size must reject");
    std::cout<<"[PASS] P101 buffer policy selftests; hardware NOT RUN\n";
    return 0;
}
#if !defined(QA_ASIO_VIRTUAL_LOOPBACK)
inline int asioReadDriverCapabilities(int argc,char**argv) {
    const std::string name=requireArg(argc,argv,"--driver-name");
    const std::string clsid=requireArg(argc,argv,"--driver-clsid");
    const std::string nonce=requireArg(argc,argv,"--nonce");
    const auto output=std::filesystem::u8path(requireArg(argc,argv,"--out"));
    ensure(nonce.size()==48&&std::all_of(nonce.begin(),nonce.end(),[](char c) {
        return (c>='0'&&c<='9')||(c>='a'&&c<='f');
    }),"P101 capability nonce invalid");
    const auto wideClsid=widen(clsid);
    GUID classId{};
    ensure(SUCCEEDED(CLSIDFromString(wideClsid.c_str(),&classId)),
           "P101 ASIO driver CLSID invalid");
    verifyRegisteredDriver(name,wideClsid);
    const HRESULT co=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    ensure(SUCCEEDED(co),"P101 COM init failed");
    IASIO* driver=nullptr;
    try {
        ensure(SUCCEEDED(CoCreateInstance(classId,nullptr,CLSCTX_INPROC_SERVER,
            classId,reinterpret_cast<void**>(&driver)))&&driver,
            "P101 cannot instantiate the registered ASIO driver");
        ensure(driver->init(GetConsoleWindow())==ASIOTrue,
               "P101 ASIO driver did not initialize");
        long in{},outputs{},minimum{},maximum{},preferred{},granularity{};
        checkASIO(driver->getChannels(&in,&outputs),
                  "P101 getChannels failed");
        ensure(outputs>=2,"P101 physical ASIO output channels <2");
        checkASIO(driver->getBufferSize(&minimum,&maximum,&preferred,&granularity),
                  "P101 getBufferSize failed");
        const long selected=asioChooseFrames(minimum,maximum,preferred,granularity);
        const auto supports=[&](double hz) {
            const auto result=driver->canSampleRate(hz);
            return result==ASE_OK||result==ASE_SUCCESS;
        };
        const bool r44100=supports(44100.);
        const bool r48000=supports(48000.);
        const bool r96000=supports(96000.);
        const int selectedRate=r44100?44100:r48000?48000:r96000?96000:0;
        ensure(selectedRate!=0,"P101 driver supports no 44.1/48/96k sample rate");
        std::ofstream out(output,std::ios::binary|std::ios::trunc);
        ensure(out.good(),"P101 capability JSON cannot be created");
        out<<"{\n"
           <<"  \"schema\": \"125a-asio-driver-capability-v1\",\n"
           <<"  \"nonce\": \""<<nonce<<"\",\n"
           <<"  \"driver_name\": \""<<escapeJSON(name)<<"\",\n"
           <<"  \"driver_clsid\": \""<<escapeJSON(clsid)<<"\",\n"
           <<"  \"executor_sha256\": \""<<hashFile(selfPath())<<"\",\n"
           <<"  \"minimum_frames\": "<<minimum<<",\n"
           <<"  \"maximum_frames\": "<<maximum<<",\n"
           <<"  \"preferred_frames\": "<<preferred<<",\n"
           <<"  \"granularity\": "<<granularity<<",\n"
           <<"  \"selected_frames\": "<<selected<<",\n"
           <<"  \"selected_rate\": "<<selectedRate<<",\n"
           <<"  \"rate_44100\": "<<(r44100?"true":"false")<<",\n"
           <<"  \"rate_48000\": "<<(r48000?"true":"false")<<",\n"
           <<"  \"rate_96000\": "<<(r96000?"true":"false")<<",\n"
           <<"  \"physical_audio_callbacks\": false,\n"
           <<"  \"release_approved\": false\n"
           <<"}\n";
        out.flush();
        ensure(out.good(),"P101 ASIO capability proof incomplete");
        driver->Release();driver=nullptr;
        CoUninitialize();
        std::cout<<"P101 REAL DRIVER preferred="<<preferred
                 <<" chosen_frames="<<selected<<" chosen_rate="<<selectedRate
                 <<" (capability only, no ASIO callbacks)\n";
        return 0;
    } catch(...) {
        if(driver)driver->Release();
        CoUninitialize();
        throw;
    }
}
#endif
