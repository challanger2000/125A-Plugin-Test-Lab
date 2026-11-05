#pragma once
#include <windows.h>
// This is the Windows DROPFILES clipboard header layout used by CF_HDROP.
// Do not include shlobj.h globally: its COM IConnectionPoint conflicts with VST3.
struct DROPFILES {
    DWORD pFiles;
    POINT pt;
    BOOL fNC;
    BOOL fWide;
};
