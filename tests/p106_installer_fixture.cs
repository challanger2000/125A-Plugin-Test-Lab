using System;
using System.IO;
using System.Text;

internal static class P106InstallerFixture
{
    private static int Main(string[] args)
    {
        if (args.Length < 1 || args.Length > 2) return 64;
        if (args.Length == 2 && args[1] == "fail") return 42;
        if (args.Length == 2 && args[1] == "omit") return 0;
        var target = Path.GetFullPath(args[0]);
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        File.WriteAllBytes(target, new UTF8Encoding(false).GetBytes("125A-P106-INSTALLED\n"));
        return 0;
    }
}
