// Additive P185 observer. Reuses the existing P181 preallocated callback slots.
// All marker publication, JSON serialization and hashing run after/before ASIO.
#if !defined(QA_ASIO_VIRTUAL_LOOPBACK)
struct P185Lifecycle {
    int64_t createBefore{},createAfter{},active{},processing{},armed{},startBefore{},startAfter{},stopBefore{},stopAfter{};
};
void writeP185(const Arguments& a,const Engine& e,const P185Lifecycle& life,
               const p185::Clock& clock,const std::string& moduleHash,const std::string& executorHash) {
    if(a.p185Out.empty())return;
    ensure(!std::filesystem::exists(a.p185Out),"P185 refuses stale output");
    const size_t actual=static_cast<size_t>(e.asioCallbacks.load());
    const size_t count=std::min(actual,e.trace.size());
    size_t missing=0; for(size_t i=0;i<count;++i)if(!e.trace[i].recorded)++missing;
    std::ofstream o(a.p185Out,std::ios::binary);
    o<<"{\"schema\":\"125a-p185-asio-observation-v1\",\"nonce\":\""<<a.nonce
     <<"\",\"pid\":"<<GetCurrentProcessId()<<",\"qpc_frequency\":"<<e.qpcFrequency
     <<",\"product_sha256\":\""<<moduleHash<<"\",\"executor_sha256\":\""<<executorHash
     <<"\",\"driver_clsid\":\""<<escapeJSON(a.clsid)<<"\",\"sample_rate\":"<<a.rate
     <<",\"frames\":"<<a.frames<<",\"requested\":"<<a.callbacks<<",\"actual\":"<<actual
     <<",\"complete\":"<<((count==actual&&missing==0&&e.traceDropped.load()==0)?"true":"false")
     <<",\"binary_identity_after\":"<<((hashFile(a.plugin)==moduleHash&&hashFile(selfPath())==executorHash)?"true":"false")
     <<",\"gap_count\":"<<e.callbackGapMisses.load()<<",\"execution_overruns\":"<<e.callbackDurationMisses.load()
     <<",\"xrun_messages\":"<<e.xruns.load()<<",\"process_failures\":"<<e.processFailures.load()
     <<",\"rate_changes\":"<<e.sampleRateChanges.load()<<",\"markers\":[";
    for(size_t i=0;i<2;++i) { const auto& m=clock.markers[i];
        if(i)o<<','; o<<"{\"sequence\":"<<i+1<<",\"before\":"<<m.before<<",\"after\":"<<m.after
            <<",\"result\":"<<m.result<<",\"tid\":"<<m.tid<<'}'; }
    o<<"],\"lifecycle\":{\"create_before\":"<<life.createBefore<<",\"create_after\":"<<life.createAfter
     <<",\"active\":"<<life.active<<",\"processing\":"<<life.processing<<",\"armed\":"<<life.armed
     <<",\"start_before\":"<<life.startBefore<<",\"start_after\":"<<life.startAfter
     <<",\"stop_before\":"<<life.stopBefore<<",\"stop_after\":"<<life.stopAfter<<"},\"callbacks\":[";
    for(size_t i=0;i<count;++i) { const auto& v=e.trace[i]; if(i)o<<',';
        o<<"{\"index\":"<<i<<",\"tid\":"<<v.threadId<<",\"buffer\":"<<v.bufferIndex
         <<",\"start\":"<<v.startQpc<<",\"end\":"<<v.endQpc<<",\"gap\":"<<(v.gapViolation?"true":"false")<<",\"ok\":"<<(v.processOk?"true":"false")<<'}'; }
    o<<"],\"release_approved\":false}\n"; o.flush(); ensure(o.good(),"P185 observer output failed");
}
#endif
