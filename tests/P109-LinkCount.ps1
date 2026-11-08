#requires -Version 5.1
# P110: NTFS hard links are NOT reparse points. Detect multi-linked files
# with the Windows file handle's nNumberOfLinks (not name/attribute checks).
# This helper defines a function only; it does not inspect arbitrary paths.
if (-not ('P110LinkCount' -as [type])) {
  Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class P110LinkCount
{
    [StructLayout(LayoutKind.Sequential)]
    private struct WinTime { public uint Low; public uint High; }
    [StructLayout(LayoutKind.Sequential)]
    private struct NativeInfo
    {
        public uint FileAttributes;
        public WinTime CreationTime;
        public WinTime LastAccessTime;
        public WinTime LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetFileInformationByHandle(SafeFileHandle file, out NativeInfo info);

    public static uint Count(string path)
    {
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read,
                    FileShare.ReadWrite | FileShare.Delete))
        {
            NativeInfo info;
            if (!GetFileInformationByHandle(stream.SafeFileHandle, out info))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            if (info.NumberOfLinks == 0) throw new IOException("P110 invalid NTFS link count");
            return info.NumberOfLinks;
        }
    }
}
'@ -ErrorAction Stop
}
function Assert-P110SingleLink([string]$file) {
  if ([P110LinkCount]::Count($file) -ne 1) {
    throw 'P110 source or installed VST3 contains an NTFS hard-linked resource'
  }
}
