// P185 control-thread markers only. Never called from the audio callback.
#pragma once
#include <windows.h>
#include <evntprov.h>
#include <array>
#include <cstdint>
#include <string>
namespace p185 {
inline constexpr GUID provider{0x7a51f185,0x4130,0x4990,{0x91,0x85,0x12,0x5a,0x00,0x00,0x01,0x85}};
inline int64_t qpc() { LARGE_INTEGER v{}; QueryPerformanceCounter(&v); return v.QuadPart; }
struct Marker { int64_t before{},after{}; ULONG result=ERROR_INVALID_HANDLE; DWORD tid{}; };
class Clock {
    REGHANDLE handle{};
public:
    std::array<Marker,2> markers{};
    explicit Clock(bool enabled) { if(enabled) EventRegister(&provider,nullptr,nullptr,&handle); }
    ~Clock() { if(handle) EventUnregister(handle); }
    Clock(const Clock&)=delete;
    Clock& operator=(const Clock&)=delete;
    void mark(unsigned index,const std::string& nonce) {
        auto& m=markers.at(index); m.tid=GetCurrentThreadId();
        EVENT_DESCRIPTOR desc{}; desc.Id=185; desc.Version=1;
        EVENT_DATA_DESCRIPTOR data[2]{};
        const uint32_t seq=index+1;
        EventDataDescCreate(&data[0],nonce.data(),static_cast<ULONG>(nonce.size()));
        EventDataDescCreate(&data[1],&seq,sizeof(seq));
        m.before=qpc(); m.result=handle?EventWrite(handle,&desc,2,data):ERROR_INVALID_HANDLE; m.after=qpc();
    }
};
}
