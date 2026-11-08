// P185 native ETW controller/consumer. Windows APIs only; no ADK dependency.
// Kernel + manifest-provider sessions stay separate. RAW_TIMESTAMP is mandatory.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <evntrace.h>
#include <evntcons.h>
#include <tdh.h>
#include <objbase.h>
#include "p185_clock.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace fs=std::filesystem;
namespace {
void check(bool b,const char* m){if(!b)throw std::runtime_error(m);}
std::string ascii(const wchar_t* p) { std::string s; if(p)while(*p){s+=*p<128?char(*p):'?';++p;}return s; }
std::string guidText(const GUID& g){wchar_t w[40]{};StringFromGUID2(g,w,40);return ascii(w);}
std::string safe(std::string s){for(auto& c:s)if(c=='"'||c=='\\'||c<32)c='_';return s;}
std::wstring quote(const std::wstring& s){ // CommandLineToArgvW inverse, including trailing slashes.
    std::wstring r=L"\"";size_t n=0;
    for(wchar_t c:s){if(c==L'\\'){++n;continue;}if(c==L'"')r.append(2*n+1,L'\\');else r.append(n,L'\\');r+=c;n=0;}
    r.append(2*n,L'\\');return r+L'"';
}
struct Provider {GUID id{};std::wstring name;ULONG enable=ERROR_NOT_SUPPORTED;};
std::vector<Provider> providers(){
    ULONG n=0;const auto first=TdhEnumerateProviders(nullptr,&n);
    if(first!=ERROR_INSUFFICIENT_BUFFER||n>16*1024*1024)return {};
    std::vector<BYTE> data(n);auto* list=reinterpret_cast<PROVIDER_ENUMERATION_INFO*>(data.data());
    if(TdhEnumerateProviders(list,&n)!=ERROR_SUCCESS)return {};
    std::vector<Provider> result;
    for(ULONG i=0;i<list->NumberOfProviders;++i){const auto& p=list->TraceProviderInfoArray[i];
        if(p.ProviderNameOffset>=n)continue;
        std::wstring name(reinterpret_cast<wchar_t*>(data.data()+p.ProviderNameOffset));
        // Enumerated manifest providers only, bounded allowlist. No invented GUIDs.
        if(name.rfind(L"Microsoft-Windows-USB-",0)==0||name.rfind(L"Microsoft-Windows-Audio",0)==0)
            if(result.size()<32)result.push_back({p.ProviderGuid,name,ERROR_NOT_SUPPORTED});
    }return result;
}
struct Session {
    std::vector<BYTE> bytes;TRACEHANDLE handle{};std::wstring name;ULONG start=ERROR_NOT_READY,stop=ERROR_NOT_READY;
    EVENT_TRACE_PROPERTIES* p(){return reinterpret_cast<EVENT_TRACE_PROPERTIES*>(bytes.data());}
    Session(const fs::path& path,const std::wstring& sessionName,bool kernel):name(sessionName){
        const auto file=path.wstring();bytes.resize(sizeof(EVENT_TRACE_PROPERTIES)+(name.size()+file.size()+2)*sizeof(wchar_t));
        auto* v=p();v->Wnode.BufferSize=static_cast<ULONG>(bytes.size());v->Wnode.Flags=WNODE_FLAG_TRACED_GUID;
        CoCreateGuid(&v->Wnode.Guid);v->Wnode.ClientContext=1; // QPC, never FILETIME/cycle clocks.
        v->BufferSize=256;v->MinimumBuffers=64;v->MaximumBuffers=128;v->FlushTimer=1;v->MaximumFileSize=256;
        v->LogFileMode=EVENT_TRACE_FILE_MODE_SEQUENTIAL|(kernel?EVENT_TRACE_SYSTEM_LOGGER_MODE:0);
        if(kernel)v->EnableFlags=EVENT_TRACE_FLAG_PROCESS|EVENT_TRACE_FLAG_THREAD|EVENT_TRACE_FLAG_CSWITCH|
            EVENT_TRACE_FLAG_DPC|EVENT_TRACE_FLAG_INTERRUPT|EVENT_TRACE_FLAG_DISPATCHER|EVENT_TRACE_FLAG_IMAGE_LOAD;
        v->LoggerNameOffset=sizeof(EVENT_TRACE_PROPERTIES);
        v->LogFileNameOffset=v->LoggerNameOffset+static_cast<ULONG>((name.size()+1)*sizeof(wchar_t));
        std::memcpy(bytes.data()+v->LoggerNameOffset,name.c_str(),(name.size()+1)*sizeof(wchar_t));
        std::memcpy(bytes.data()+v->LogFileNameOffset,file.c_str(),(file.size()+1)*sizeof(wchar_t));
        start=StartTraceW(&handle,name.c_str(),v);
    }
    void close(){if(start==ERROR_SUCCESS&&handle){stop=ControlTraceW(handle,nullptr,p(),EVENT_TRACE_CONTROL_STOP);handle=0;}}
    ~Session(){close();} // Never stops/replaces a session owned by somebody else.
    Session(const Session&)=delete;
    Session& operator=(const Session&)=delete;
};
struct Decode {
    std::ofstream switches,threads,ready,activity,markers;
    uint64_t events{},cswitches{},decodeErrors{};std::set<std::string> observed;DWORD targetPid{};std::set<uint64_t> targetThreads;
    explicit Decode(const fs::path& out,DWORD pid):switches(out/"cswitch.csv"),threads(out/"threads.csv"),ready(out/"ready.csv"),
        activity(out/"activity.csv"),markers(out/"markers.csv"),targetPid(pid){
        switches<<"qpc,cpu,old_tid,new_tid,old_state,wait_reason\n";
        threads<<"qpc,opcode,pid,tid\n";ready<<"qpc,tid,cpu\n";
        activity<<"qpc,cpu,provider,event_id,opcode,initial_time_valid,initial_time\n";
        markers<<"qpc,pid,tid,nonce,sequence\n";
    }
};
bool number(EVENT_RECORD* r,const wchar_t* key,uint64_t& value){
    PROPERTY_DATA_DESCRIPTOR d{};d.PropertyName=reinterpret_cast<ULONGLONG>(key);d.ArrayIndex=ULONG_MAX;ULONG n=0;
    if(TdhGetPropertySize(r,0,nullptr,1,&d,&n)!=ERROR_SUCCESS||n==0||n>8)return false;
    value=0;return TdhGetProperty(r,0,nullptr,1,&d,n,reinterpret_cast<PBYTE>(&value))==ERROR_SUCCESS;
}
static constexpr GUID threadGuid{0x3d6fa8d1,0xfe05,0x11d0,{0x9d,0xda,0,0xc0,0x4f,0xd7,0xba,0x7c}};
static constexpr GUID perfGuid{0xce1dbfb4,0x137e,0x4da6,{0x87,0xb0,0x3f,0x59,0xaa,0x10,0x2c,0xbc}};
void WINAPI event(EVENT_RECORD* r){
    auto& d=*static_cast<Decode*>(r->UserContext);++d.events;
    const auto t=r->EventHeader.TimeStamp.QuadPart;const auto cpu=r->BufferContext.ProcessorIndex;
    const auto op=r->EventHeader.EventDescriptor.Opcode;const auto& id=r->EventHeader.ProviderId;
    if(IsEqualGUID(id,p185::provider)){
        if(r->EventHeader.EventDescriptor.Id!=185||r->EventHeader.EventDescriptor.Version!=1||r->UserDataLength!=52){++d.decodeErrors;return;}
        std::string nonce(static_cast<const char*>(r->UserData),48);uint32_t seq{};
        std::memcpy(&seq,static_cast<const BYTE*>(r->UserData)+48,4);
        if(!std::all_of(nonce.begin(),nonce.end(),[](char c){return(c>='a'&&c<='f')||(c>='0'&&c<='9');})){++d.decodeErrors;return;}
        d.markers<<t<<','<<r->EventHeader.ProcessId<<','<<r->EventHeader.ThreadId<<','<<nonce<<','<<seq<<'\n';return;
    }
    if(IsEqualGUID(id,threadGuid)){
        uint64_t a=0,b=0,c=0,e=0;
        if(op==36){
            if(!number(r,L"NewThreadId",a)||!number(r,L"OldThreadId",b)||!number(r,L"OldThreadState",c)||!number(r,L"OldThreadWaitReason",e)){++d.decodeErrors;return;}
            if(!d.targetThreads.count(a)&&!d.targetThreads.count(b))return;
            d.switches<<t<<','<<cpu<<','<<b<<','<<a<<','<<c<<','<<e<<'\n';++d.cswitches;
        }else if(op>=1&&op<=4){
            if(!number(r,L"ProcessId",a)||!number(r,L"TThreadId",b)){++d.decodeErrors;return;}
            if(a==d.targetPid)d.targetThreads.insert(b);
            if(!d.targetThreads.count(b))return;
            d.threads<<t<<','<<unsigned(op)<<','<<a<<','<<b<<'\n';
        }else if(op==50){
            if(number(r,L"TThreadId",a)||number(r,L"ThreadId",a)){if(d.targetThreads.count(a))d.ready<<t<<','<<a<<','<<cpu<<'\n';}
            else ++d.decodeErrors;
        }return;
    }
    if(IsEqualGUID(id,perfGuid)&&(op==51||op==66||op==67||op==68||op==69)){
        uint64_t begin=0;const auto valid=number(r,L"InitialTime",begin);
        d.activity<<t<<','<<cpu<<",KERNEL_DPC_ISR,0,"<<unsigned(op)<<','<<valid<<','<<begin<<'\n';return;
    }
    // Keep only provider GUID/event metadata here. Personal payloads remain local in ETL.
    // Reject all unrequested providers; no name-based causal attribution.
    const auto key=guidText(id);
    if(d.observed.count(key))d.activity<<t<<','<<cpu<<','<<key<<','<<r->EventHeader.EventDescriptor.Id<<','<<unsigned(op)<<",0,0\n";
}
struct TraceResult {ULONG open{},process{},lost{},buffers{};int64_t frequency{};ULONG clock{};};
TraceResult decode(const fs::path& file,Decode& d){
    EVENT_TRACE_LOGFILEW log{};auto path=file.wstring();log.LogFileName=path.data();log.Context=&d;
    log.ProcessTraceMode=PROCESS_TRACE_MODE_EVENT_RECORD|PROCESS_TRACE_MODE_RAW_TIMESTAMP;log.EventRecordCallback=event;
    auto h=OpenTraceW(&log);TraceResult result{};
    if(h==INVALID_PROCESSTRACE_HANDLE){result.open=GetLastError();result.process=ERROR_INVALID_HANDLE;return result;}
    result.process=ProcessTrace(&h,1,nullptr,nullptr);CloseTrace(h);
    result.lost=log.LogfileHeader.EventsLost;result.buffers=log.LogfileHeader.BuffersLost;
    result.frequency=log.LogfileHeader.PerfFreq.QuadPart;result.clock=log.LogfileHeader.ReservedFlags;
    return result;
}
void traceJson(std::ostream& o,const TraceResult& r,Session& s){
    o<<"{\"start\":"<<s.start<<",\"stop\":"<<s.stop<<",\"open\":"<<r.open<<",\"process\":"<<r.process
     <<",\"events_lost\":"<<r.lost<<",\"buffers_lost\":"<<r.buffers<<",\"session_events_lost\":"<<s.p()->EventsLost
     <<",\"session_buffers_lost\":"<<s.p()->LogBuffersLost+s.p()->RealTimeBuffersLost
     <<",\"frequency\":"<<r.frequency<<",\"clock\":"<<r.clock<<'}';
}
int workload(const fs::path& file,const std::string& nonce){
    p185::Clock clock(true);clock.mark(0,nonce);
    const auto tid=GetCurrentThreadId();const auto before=p185::qpc();Sleep(80);
    LARGE_INTEGER f{};QueryPerformanceFrequency(&f);
    const auto busy=p185::qpc();while(p185::qpc()-busy<f.QuadPart/50)YieldProcessor();
    clock.mark(1,nonce);std::ofstream o(file);
    o<<"{\"pid\":"<<GetCurrentProcessId()<<",\"tid\":"<<tid<<",\"before_sleep\":"<<before<<",\"frequency\":"<<f.QuadPart<<",\"markers\":[";
    for(size_t i=0;i<2;++i){if(i)o<<',';const auto& m=clock.markers[i];o<<"{\"before\":"<<m.before<<",\"after\":"<<m.after<<",\"tid\":"<<m.tid<<",\"result\":"<<m.result<<'}';}o<<"]}";
    return o.good()?0:1;
}
int capture(const fs::path& out,const std::wstring& nonce,const std::vector<std::wstring>& args){
    check(!fs::exists(out),"Output directory exists (stale evidence refused)");fs::create_directories(out);
    const auto prefix=L"125A-P185-"+nonce;
    Session kernel(out/"kernel.etl",prefix+L"-K",true);
    Session user(out/"providers.etl",prefix+L"-U",false);
    auto ps=providers();ULONG markerEnable=ERROR_NOT_READY;DWORD childPid=0,childExit=DWORD(-1);bool timeout=false;
    if(kernel.start==ERROR_SUCCESS&&user.start==ERROR_SUCCESS){
        markerEnable=EnableTraceEx2(user.handle,&p185::provider,EVENT_CONTROL_CODE_ENABLE_PROVIDER,5,0,0,0,nullptr);
        for(auto& p:ps)p.enable=EnableTraceEx2(user.handle,&p.id,EVENT_CONTROL_CODE_ENABLE_PROVIDER,5,~0ULL,0,0,nullptr);
        if(markerEnable==ERROR_SUCCESS){
            std::wstring cmd;for(const auto& s:args){if(!cmd.empty())cmd+=L' ';cmd+=quote(s);}
            STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
            if(CreateProcessW(args.front().c_str(),cmd.data(),nullptr,nullptr,FALSE,CREATE_SUSPENDED,nullptr,nullptr,&si,&pi)){
                childPid=pi.dwProcessId;ResumeThread(pi.hThread);CloseHandle(pi.hThread);
                if(WaitForSingleObject(pi.hProcess,60000)!=WAIT_OBJECT_0){timeout=true;TerminateProcess(pi.hProcess,124);WaitForSingleObject(pi.hProcess,5000);}
                GetExitCodeProcess(pi.hProcess,&childExit);CloseHandle(pi.hProcess);
            }
        }
    }
    for(const auto& p:ps)if(p.enable==ERROR_SUCCESS)EnableTraceEx2(user.handle,&p.id,EVENT_CONTROL_CODE_DISABLE_PROVIDER,0,0,0,0,nullptr);
    if(markerEnable==ERROR_SUCCESS)EnableTraceEx2(user.handle,&p185::provider,EVENT_CONTROL_CODE_DISABLE_PROVIDER,0,0,0,0,nullptr);
    kernel.close();user.close();Decode d(out,childPid);for(const auto& p:ps)if(p.enable==0)d.observed.insert(guidText(p.id));
    TraceResult kr{},ur{};if(kernel.start==0)kr=decode(out/"kernel.etl",d);if(user.start==0)ur=decode(out/"providers.etl",d);
    std::ofstream o(out/"capture.json");
    o<<"{\"schema\":\"125a-p185-native-etw-v1\",\"nonce\":\""<<ascii(nonce.c_str())<<"\",\"child_pid\":"<<childPid
     <<",\"child_exit\":"<<childExit<<",\"timeout\":"<<(timeout?"true":"false")<<",\"marker_enable\":"<<markerEnable
     <<",\"events\":"<<d.events<<",\"cswitches\":"<<d.cswitches<<",\"decode_errors\":"<<d.decodeErrors<<",\"kernel\":";
    traceJson(o,kr,kernel);o<<",\"user\":";traceJson(o,ur,user);o<<",\"providers\":[";
    for(size_t i=0;i<ps.size();++i){if(i)o<<',';o<<"{\"name\":\""<<safe(ascii(ps[i].name.c_str()))<<"\",\"guid\":\""<<guidText(ps[i].id)<<"\",\"enable\":"<<ps[i].enable<<'}';}
    o<<"],\"physical_asio_verified\":false,\"release_approved\":false}\n";o.flush();check(o.good(),"ETW result write failed");
    if(kernel.start||user.start||markerEnable){std::cerr<<"ETW_NOT_AVAILABLE kernel="<<kernel.start<<" user="<<user.start<<" markers="<<markerEnable<<'\n';return 3;}
    if(!childPid||timeout||kr.process||ur.process)return 4;
    return childExit==0?0:1; // Strict ASIO failure remains failure; ETW files still available.
}
}
int wmain(int argc,wchar_t** argv){try{
    if(argc==4&&std::wstring(argv[1])==L"--workload")return workload(argv[2],ascii(argv[3]));
    if(argc==4&&std::wstring(argv[1])==L"--denied-selftest"){
        HANDLE token{},restricted{};check(OpenProcessToken(GetCurrentProcess(),TOKEN_DUPLICATE|TOKEN_QUERY,&token)!=0,"Open restricted-token source failed");
        BYTE sid[SECURITY_MAX_SID_SIZE]{};DWORD n=sizeof(sid);CreateWellKnownSid(WinBuiltinAdministratorsSid,nullptr,sid,&n);
        SID_AND_ATTRIBUTES deny{sid,0};const auto made=CreateRestrictedToken(token,DISABLE_MAX_PRIVILEGE,1,&deny,0,nullptr,0,nullptr,&restricted);CloseHandle(token);
        check(made&&ImpersonateLoggedOnUser(restricted),"Restricted impersonation failed");
        ULONG rc=0;{
          Session session(fs::absolute(argv[2]),L"125A-P185-DENIED-"+std::wstring(argv[3]),true);rc=session.start;
        }
        RevertToSelf();CloseHandle(restricted);
        std::ofstream o(fs::path(argv[2]).wstring()+L".json");o<<"{\"start_result\":"<<rc<<",\"physical_asio\":\"NOT_RUN\"}";
        check(rc==ERROR_ACCESS_DENIED||rc==ERROR_PRIVILEGE_NOT_HELD,"Restricted kernel trace unexpectedly allowed");return 0;
    }
    if(argc==3&&std::wstring(argv[1])==L"--capabilities"){
        std::ofstream o(argv[2]);auto ps=providers();o<<"{\"native_etw_api\":true,\"provider_count\":"<<ps.size()<<",\"physical_asio\":\"NOT_RUN\",\"capture_privilege\":\"NOT_PROBED\"}";return o.good()?0:1;
    }
    check(argc>=4,"Usage: --capture NEW-DIRECTORY NONCE -- EXE ARGS | --selftest NEW-DIRECTORY NONCE");
    std::wstring nonce=argv[3];check(nonce.size()==48&&std::all_of(nonce.begin(),nonce.end(),[](wchar_t c){return(c>=L'a'&&c<=L'f')||(c>=L'0'&&c<=L'9');}),"Invalid nonce");
    std::vector<std::wstring> child;
    if(std::wstring(argv[1])==L"--selftest"){
        wchar_t path[32768]{};check(GetModuleFileNameW(nullptr,path,32768)>0,"Self path unavailable");
        child={path,L"--workload",(fs::path(argv[2])/"control.json").wstring(),nonce};
    }else{check(std::wstring(argv[1])==L"--capture"&&std::wstring(argv[4])==L"--"&&argc>5,"Invalid capture command");
        for(int i=5;i<argc;++i)child.emplace_back(argv[i]);}
    return capture(fs::absolute(argv[2]),nonce,child);
}catch(const std::exception& e){std::cerr<<"P185: "<<e.what()<<'\n';return 2;}}
