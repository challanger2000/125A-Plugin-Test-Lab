-- P91 REAPER ReaScript. Runs INSIDE actual REAPER, never a mocked DAW.
-- Python runner prepends local TEST_* config strings to this file.
local function check(ok, text)
  if not ok then error("P91: " .. text, 0) end
end
local function marker(path, data)
  local tmp = path .. ".writing"
  local f, err = io.open(tmp, "wb")
  check(f ~= nil, "status file open: " .. tostring(err))
  f:write(data)
  f:close()
  os.remove(path)
  check(os.rename(tmp, path) ~= nil, "cannot atomically publish status")
end
local function safe_line(s)
  return tostring(s):gsub("[\r\n]", " ")
end
local function setup()
  check(reaper.GetAppVersion ~= nil, "ReaScript API unavailable")
  check(reaper.CountTracks(0) == 0, "expected isolated new project")
  check(reaper.SetCurrentBPM ~= nil, "tempo API unavailable")
  reaper.SetCurrentBPM(0, TEST_BPM, true)
  reaper.GetSetProjectInfo(0, "PROJECT_SRATE", TEST_RATE, true)
  reaper.GetSetProjectInfo(0, "PROJECT_SRATE_USE", 1, true)
  reaper.InsertTrackAtIndex(0, false)
  local track = reaper.GetTrack(0, 0)
  check(track ~= nil, "cannot add MIDI track")
  reaper.GetSetMediaTrackInfo_String(track, "P_NAME", "125A REAPER QA", true)
  -- instantiate=1 inserts newly found effect. REAPER must already have
  -- scanned this installed VST3. No opaque RPP chunk injection.
  local fx = reaper.TrackFX_AddByName(track, TEST_FX, false, 1)
  check(fx >= 0, "REAPER cannot load named VST3 FX: " .. TEST_FX)
  local okname, actual_name = reaper.TrackFX_GetFXName(track, fx, "")
  check(okname and actual_name and actual_name ~= "", "FX identity not readable")
  check(reaper.TrackFX_GetCount(track) == 1, "unexpected FX chain")
  local item = reaper.CreateNewMIDIItemInProj(track, 0, TEST_DURATION, false)
  check(item ~= nil, "could not create MIDI media item")
  local take = reaper.GetActiveTake(item)
  check(take ~= nil and reaper.TakeIsMIDI(take), "MIDI take missing")
  local start_tick = reaper.MIDI_GetPPQPosFromProjTime(take, 0.1)
  local end_tick = reaper.MIDI_GetPPQPosFromProjTime(take, 0.75)
  check(reaper.MIDI_InsertNote(take, false, false, start_tick, end_tick,
                              0, TEST_NOTE, TEST_VELOCITY, false),
        "MIDI note insertion failed")
  reaper.MIDI_Sort(take)
  local _, note_count = reaper.MIDI_CountEvts(take)
  check(note_count == 1, "generated MIDI note not found")
  reaper.GetSetProjectInfo(0, "RENDER_SETTINGS", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_BOUNDSFLAG", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_STARTPOS", 0, true)
  reaper.GetSetProjectInfo(0, "RENDER_ENDPOS", TEST_DURATION, true)
  reaper.GetSetProjectInfo(0, "RENDER_SRATE", TEST_RATE, true)
  reaper.GetSetProjectInfo(0, "RENDER_CHANNELS", 2, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FILE", TEST_OUTPUT_DIR, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_PATTERN", TEST_RENDER_NAME, true)
  reaper.GetSetProjectInfo_String(0, "RENDER_FORMAT", "evaw", true)
  reaper.Main_SaveProjectEx(0, TEST_PROJECT, 8)
  local saved = io.open(TEST_PROJECT, "rb")
  check(saved ~= nil, "project file missing after REAPER SaveProjectEx")
  saved:close()
  local done = "phase=setup\nfx_name=" .. safe_line(actual_name)
    .. "\nnote_count=" .. tostring(note_count)
    .. "\nreaper_version=" .. safe_line(reaper.GetAppVersion())
    .. "\nproject=" .. safe_line(TEST_PROJECT) .. "\n"
  marker(TEST_STATUS, done)
end
local function verify()
  check(reaper.CountTracks(0) == 1, "saved project has wrong track count")
  local track = reaper.GetTrack(0, 0)
  check(reaper.TrackFX_GetCount(track) == 1, "saved FX chain missing")
  local valid, name = reaper.TrackFX_GetFXName(track, 0, "")
  check(valid and name and name ~= "", "saved VST3 not loaded")
  local item = reaper.GetTrackMediaItem(track, 0)
  check(item ~= nil, "saved MIDI item missing")
  local take = reaper.GetActiveTake(item)
  check(take ~= nil and reaper.TakeIsMIDI(take), "reloaded MIDI take missing")
  local _, notes = reaper.MIDI_CountEvts(take)
  check(notes == 1, "saved note count changed")
  local found, _, _, begin_tick, stop_tick, channel, pitch, velocity =
    reaper.MIDI_GetNote(take, 0)
  check(found and pitch == TEST_NOTE and velocity == TEST_VELOCITY
        and channel == 0 and stop_tick > begin_tick, "saved MIDI changed")
  marker(TEST_STATUS, "phase=reload\nfx_name=" .. safe_line(name)
    .. "\nnote_count=" .. tostring(notes)
    .. "\npitch=" .. tostring(pitch)
    .. "\nvelocity=" .. tostring(velocity)
    .. "\nreaper_version=" .. safe_line(reaper.GetAppVersion()) .. "\n")
end
local ok, err = xpcall(function()
  if TEST_PHASE == "setup" then setup()
  elseif TEST_PHASE == "reload" then verify()
  else error("unknown phase") end
end, debug.traceback)
if not ok then
  marker(TEST_STATUS, "phase=FAIL\nerror=" .. safe_line(err) .. "\n")
end
