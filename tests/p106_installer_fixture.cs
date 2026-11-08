using System;
using System.IO;
using System.Text;

internal static class P106InstallerFixture
{
    private static int Main(string[] args)
    {
        if (args.Length >= 1 && args[0] == "copydir")
        {
            if (args.Length != 3 || !Directory.Exists(args[1]) || Directory.Exists(args[2])) return 65;
            var source = Path.GetFullPath(args[1]);
            var dest = Path.GetFullPath(args[2]);
            Directory.CreateDirectory(dest);
            foreach (var file in Directory.GetFiles(source, "*", SearchOption.AllDirectories))
            {
                var relative = file.Substring(source.Length).TrimStart(Path.DirectorySeparatorChar);
                var output = Path.Combine(dest, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(output));
                File.Copy(file, output);
            }
            return 0;
        }
        if (args.Length < 1 || args.Length > 2) return 64;
        if (args.Length == 2 && args[1] == "fail") return 42;
        if (args.Length == 2 && args[1] == "omit") return 0;
        if (args.Length == 2 && args[1] == "sleep") System.Threading.Thread.Sleep(8000);
        var target = Path.GetFullPath(args[0]);
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        File.WriteAllBytes(target, new UTF8Encoding(false).GetBytes("125A-P106-INSTALLED\n"));
        return 0;
    }
}
