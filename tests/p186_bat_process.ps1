#requires -Version 5.1
# Test-only Windows process invocation. Pass cmd's raw command string through
# ProcessStartInfo so PowerShell's legacy native-argument quoting cannot alter it.
function Invoke-P186TestProcess([string]$Executable,[string]$Arguments) {
  $start=[Diagnostics.ProcessStartInfo]::new()
  $start.FileName=$Executable;$start.Arguments=$Arguments
  $start.UseShellExecute=$false;$start.CreateNoWindow=$true
  $start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
  $start.EnvironmentVariables['CI']='true'
  $process=[Diagnostics.Process]::Start($start)
  try {
    $stdout=$process.StandardOutput.ReadToEnd();$stderr=$process.StandardError.ReadToEnd()
    if(-not $process.WaitForExit(30000)){$process.Kill();throw 'P186 test process timeout'}
    if($stdout){Write-Host $stdout};if($stderr){Write-Host $stderr}
    return @{exit_code=[int]$process.ExitCode;output=($stdout+$stderr)}
  } finally {$process.Dispose()}
}
function Invoke-P186TestBat([string]$Bat,[string]$Arguments) {
  Invoke-P186TestProcess $env:ComSpec ('/d /s /c ""'+$Bat+'" '+$Arguments+'"')
}
