// P181: read-only bounded QPC trace of actual IASIO callbacks.
// Included only after Arguments/Engine declarations, before run().
// Recording uses preallocated memory, no file or heap I/O in ASIO callback.
#if !defined(QA_ASIO_VIRTUAL_LOOPBACK)
inline std::vector<size_t> chooseTraceWindow(const std::vector<AsioTraceSample>& trace,
                                               size_t count) {
    std::vector<uint8_t> selected(count,0);
    for(size_t i=0;i<count;++i)if(trace[i].gapViolation) {
        const size_t first=i>=4?i-4:0;
        const size_t last=std::min(count-1,i+4);
        for(size_t n=first;n<=last;++n)selected[n]=1;
    }
    std::vector<size_t> indices;
    for(size_t i=0;i<count;++i)if(selected[i])indices.push_back(i);
    return indices;
}
inline int asioTraceSelfTest() {
    std::vector<AsioTraceSample> sample(13);
    for(size_t i=0;i<sample.size();++i){
        sample[i].startQpc=1000+static_cast<int64_t>(i)*100;
        sample[i].endQpc=sample[i].startQpc+20;
        sample[i].recorded=true;
    }
    ensure(chooseTraceWindow(sample,sample.size()).empty(),
           "P181 baseline must not fabricate timing violations");
    sample[6].gapViolation=true;
    auto win=chooseTraceWindow(sample,sample.size());
    ensure(win.size()==9&&win.front()==2&&win.back()==10,
           "P181 must retain four preceding/following callbacks around gap");
    sample[7].gapViolation=true;
    win=chooseTraceWindow(sample,sample.size());
    ensure(win.size()==10&&win.front()==2&&win.back()==11,
           "P181 adjacent gaps must be deduplicated, not discarded");
    sample[6].gapViolation=false;
    sample[7].gapViolation=false;
    sample[0].gapViolation=true;
    win=chooseTraceWindow(sample,sample.size());
    ensure(win.size()==5&&win.front()==0&&win.back()==4,
           "P181 startup callback gap must be bounded");
    sample[0].gapViolation=false;
    sample.back().gapViolation=true;
    win=chooseTraceWindow(sample,sample.size());
    ensure(win.size()==5&&win.front()==8&&win.back()==12,
           "P181 final callback gap must be bounded");
    std::cout<<"[PASS] P181 trace selection: no fake gaps, adjacency,"
                " startup/end bounds; physical ASIO NOT RUN\n";
    return 0;
}
inline void writeAsioTimingTrace(const Arguments& a,const Engine& e,
                                 const std::string& productHash,
                                 const std::string& hostHash) {
    if(a.traceOut.empty())return;
    ensure(e.traceEnabled,"P181 trace option not prepared before ASIO callback");
    ensure(!std::filesystem::exists(a.traceOut),
           "P181 refuses to overwrite a preexisting callback timing trace");
    const auto actual=static_cast<size_t>(e.asioCallbacks.load(std::memory_order_relaxed));
    const auto count=std::min(actual,e.trace.size());
    const auto selected=chooseTraceWindow(e.trace,count);
    const auto qpc=e.qpcFrequency;
    ensure(qpc>0,"P181 QPC counter unavailable");
    size_t incomplete=0;
    size_t anomalyCount=0;
    for(size_t i=0;i<count;++i) {
        if(!e.trace[i].recorded)++incomplete;
        if(e.trace[i].gapViolation)++anomalyCount;
    }
    const bool complete=incomplete==0&&e.traceDropped.load()==0&&count==actual;
    std::ofstream out(a.traceOut,std::ios::binary|std::ios::trunc);
    ensure(out.good(),"P181 callback trace cannot be created");
    out<<"{\n"
       <<"  \"schema\": \"125a-real-asio-callback-window-trace-v1\",\n"
       <<"  \"status\": \"DIAGNOSTIC_ONLY_NOT_HARDWARE_PASS\",\n"
       <<"  \"nonce\": \""<<a.nonce<<"\",\n"
       <<"  \"asio_driver_name\": \""<<escapeJSON(a.name)<<"\",\n"
       <<"  \"asio_driver_clsid\": \""<<escapeJSON(a.clsid)<<"\",\n"
       <<"  \"product_sha256\": \""<<productHash<<"\",\n"
       <<"  \"executor_sha256\": \""<<hostHash<<"\",\n"
       <<"  \"sample_rate\": "<<a.rate<<",\n"
       <<"  \"buffer_frames\": "<<a.frames<<",\n"
       <<"  \"qpc_frequency_hz\": "<<qpc<<",\n"
       <<"  \"requested_callbacks\": "<<a.callbacks<<",\n"
       <<"  \"actual_callbacks\": "<<actual<<",\n"
       <<"  \"recorded_callbacks\": "<<count<<",\n"
       <<"  \"unrecorded_callback_slots\": "<<incomplete<<",\n"
       <<"  \"trace_overflow_callbacks\": "<<e.traceDropped.load()<<",\n"
       <<"  \"trace_complete\": "<<(complete?"true":"false")<<",\n"
       <<"  \"callback_start_spacing_violations\": "<<anomalyCount<<",\n"
       <<"  \"selected_window_callbacks\": "<<selected.size()<<",\n"
       <<"  \"events\": [\n";
    for(size_t p=0;p<selected.size();++p) {
        const auto i=selected[p];
        const auto& v=e.trace[i];
        const auto us=[&](int64_t ticks)->double {
            return ticks*1000000.0/static_cast<double>(qpc);
        };
        const int64_t ref=e.trace.front().startQpc;
        const auto currentNs=v.startQpc-ref;
        const auto prevEnd=i>0?e.trace[i-1].endQpc:0;
        const auto previousDuration=i>0?
            (prevEnd-e.trace[i-1].startQpc):0;
        out<<"    {\n"
           <<"      \"callback_index_zero_based\": "<<i<<",\n"
           <<"      \"driver_buffer_index\": "<<v.bufferIndex<<",\n"
           <<"      \"thread_id\": "<<v.threadId<<",\n"
           <<"      \"qpc_start_ticks\": "<<v.startQpc<<",\n"
           <<"      \"qpc_end_ticks\": "<<v.endQpc<<",\n"
           <<"      \"relative_start_us\": "<<std::fixed<<std::setprecision(3)<<us(currentNs)<<",\n"
           <<"      \"previous_start_to_start_us\": "<<us(v.startQpc-(i?e.trace[i-1].startQpc:v.startQpc))<<",\n"
           <<"      \"previous_callback_duration_us\": "<<us(previousDuration)<<",\n"
           <<"      \"this_callback_duration_us\": "<<us(v.endQpc-v.startQpc)<<",\n"
           <<"      \"gap_violation\": "<<(v.gapViolation?"true":"false")<<",\n"
           <<"      \"process_success\": "<<(v.processOk?"true":"false")<<",\n"
           <<"      \"driver_overload_or_resync_messages\": "<<v.xrunsAtStart<<",\n"
           <<"      \"sample_rate_change_messages\": "<<v.rateChangesAtStart<<",\n"
           <<"      \"midi_note_on_count_after\": "<<v.noteOnCount<<",\n"
           <<"      \"midi_note_off_count_after\": "<<v.noteOffCount<<"\n"
           <<"    }"<<(p+1==selected.size()?"":",")<<"\n";
    }
    out<<"  ],\n"
       <<"  \"captured_after_asio_driver_stop\": true,\n"
       <<"  \"physical_asio_verified\": false,\n"
       <<"  \"commercial_daw_verified\": false,\n"
       <<"  \"release_approved\": false\n"
       <<"}\n";
    out.flush();
    ensure(out.good(),"P181 complete native ASIO callback trace not written");
    std::cerr<<"[P181 DIAGNOSTIC ONLY] callback_gaps="<<anomalyCount
             <<" trace_complete="<<(complete?"YES":"NO")
             <<" captured="<<count<<" selected_windows="<<selected.size()
             <<" no_hardware_pass_claim\n";
}
#endif
