// P102: STRICTLY DIAGNOSTIC evidence after real IASIO driver STOP.
// Never written on the real-time callback thread, never a PASS certificate.
// This file is #included from the anonymous namespace of physical_asio.cpp.
#if !defined(QA_ASIO_VIRTUAL_LOOPBACK)
inline void updateDiagnosticMax(std::atomic<uint64_t>& target,uint64_t sample) noexcept {
    uint64_t observed=target.load(std::memory_order_relaxed);
    while(observed<sample && !target.compare_exchange_weak(
        observed,sample,std::memory_order_relaxed,std::memory_order_relaxed)) {}
}
inline void writeAsioDiagnostics(const Arguments& a,const Engine& e,
                                 const std::string& productHash,
                                 const std::string& hostHash) {
    if(a.diagnosticOut.empty())return;
    ensure(a.diagnosticOut != a.output && a.diagnosticOut != a.midiOut,
           "P102 diagnostic output paths must be distinct");
    ensure(!std::filesystem::exists(a.diagnosticOut),
           "P102 refuses to overwrite an existing diagnostic report");
    std::ofstream out(a.diagnosticOut,std::ios::binary|std::ios::trunc);
    ensure(out.good(),"P102 could not create hardware diagnostic JSON");
    const auto callbacks=e.asioCallbacks.load(std::memory_order_relaxed);
    const auto completed=e.processedCallbacks.load(std::memory_order_relaxed);
    const auto deadline=e.deadlineMisses.load(std::memory_order_relaxed);
    const auto gap=e.callbackGapMisses.load(std::memory_order_relaxed);
    const auto duration=e.callbackDurationMisses.load(std::memory_order_relaxed);
    const auto xruns=e.xruns.load(std::memory_order_relaxed);
    const auto failures=e.processFailures.load(std::memory_order_relaxed);
    const auto changes=e.sampleRateChanges.load(std::memory_order_relaxed);
    const bool meetsThreshold=callbacks>=static_cast<uint64_t>(a.callbacks);
    const bool matches=completed==callbacks;
    const bool clean=deadline==0&&xruns==0&&failures==0&&changes==0;
    const bool hasPCM=e.audibleSamples>=100&&e.observedPeak>0.0001f;
    out<<"{\n"
       <<"  \"schema\": \"125a-asio-callback-diagnostic-v1\",\n"
       <<"  \"status\": \"DIAGNOSTIC_ONLY_NOT_HARDWARE_PASS\",\n"
       <<"  \"nonce\": \""<<a.nonce<<"\",\n"
       <<"  \"asio_driver_name\": \""<<escapeJSON(a.name)<<"\",\n"
       <<"  \"asio_driver_clsid\": \""<<escapeJSON(a.clsid)<<"\",\n"
       <<"  \"product_sha256\": \""<<productHash<<"\",\n"
       <<"  \"executor_sha256\": \""<<hostHash<<"\",\n"
       <<"  \"sample_rate\": "<<a.rate<<",\n"
       <<"  \"buffer_frames\": "<<a.frames<<",\n"
       <<"  \"requested_callbacks\": "<<a.callbacks<<",\n"
       <<"  \"asio_callbacks\": "<<callbacks<<",\n"
       <<"  \"successful_process_callbacks\": "<<completed<<",\n"
       <<"  \"failed_process_callbacks\": "<<failures<<",\n"
       <<"  \"deadline_misses_total\": "<<deadline<<",\n"
       <<"  \"callback_spacing_violations\": "<<gap<<",\n"
       <<"  \"callback_execution_over_budget\": "<<duration<<",\n"
       <<"  \"maximum_callback_duration_ns\": "<<e.maxCallbackDurationNs.load()<<",\n"
       <<"  \"maximum_callback_spacing_ns\": "<<e.maxCallbackSpacingNs.load()<<",\n"
       <<"  \"hardware_asio_overload_or_resync_messages\": "<<xruns<<",\n"
       <<"  \"sample_rate_change_notifications\": "<<changes<<",\n"
       <<"  \"midi_event_failures\": "<<e.midiEventFailures.load()<<",\n"
       <<"  \"vst_process_returned_error\": "<<e.vstProcessErrors.load()<<",\n"
       <<"  \"nonfinite_vst_pcm_samples\": "<<e.nonfinitePcmSamples.load()<<",\n"
       <<"  \"missing_asio_output_buffers\": "<<e.missingOutputBuffers.load()<<",\n"
       <<"  \"asio_sample_write_failures\": "<<e.asioWriteFailures.load()<<",\n"
       <<"  \"caught_callback_exceptions\": "<<e.callbackExceptions.load()<<",\n"
       <<"  \"note_on_events\": "<<e.emittedNoteOn<<",\n"
       <<"  \"note_off_events\": "<<e.emittedNoteOff<<",\n"
       <<"  \"nonzero_pcm_samples\": "<<e.audibleSamples<<",\n"
       <<"  \"observed_peak_before_safety_limit\": "<<e.observedPeak<<",\n"
       <<"  \"observed_after_actual_driver_stop\": true,\n"
       <<"  \"callback_threshold_met\": "<<(meetsThreshold?"true":"false")<<",\n"
       <<"  \"callback_process_counts_equal\": "<<(matches?"true":"false")<<",\n"
       <<"  \"timing_process_and_driver_metrics_clean\": "<<(clean?"true":"false")<<",\n"
       <<"  \"midi_audio_detected\": "<<(hasPCM?"true":"false")<<",\n"
       <<"  \"physical_asio_verified\": false,\n"
       <<"  \"commercial_daw_verified\": false,\n"
       <<"  \"release_approved\": false\n"
       <<"}\n";
    out.flush();
    ensure(out.good(),"P102 hardware diagnostics could not be completed");
    std::cerr<<"[P102 DIAGNOSTIC ONLY] callbacks="<<callbacks
             <<" processed="<<completed<<" failed="<<failures
             <<" deadline="<<deadline<<" gap="<<gap
             <<" execution="<<duration<<" xruns="<<xruns
             <<" sample_rate_changes="<<changes
             <<" midi_events="<<e.emittedNoteOn<<"/"<<e.emittedNoteOff
             <<" audible_samples="<<e.audibleSamples
             <<" peak="<<e.observedPeak<<"\n";
}
#endif
