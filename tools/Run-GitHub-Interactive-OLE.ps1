# P16: native VSTGUI -> independent Win32 COM target on a real RDP desktop.
# This runs only inside the disposable GitHub Windows VM.
param([string]$Kit = "artifact/P14-Interactive-OLE")
$ErrorActionPreference = "Stop"
$kitPath = (Resolve-Path -LiteralPath $Kit).Path
$proof = Join-Path $kitPath "P16-RESULT.txt"
$diagnostics = Join-Path $kitPath "P16-DIAGNOSTICS.txt"
$account = "125a_oleqa"
$task = "125A-P16-Interactive-OLE"
$rdp = $null
$password = $null
$originalRdp = $null
$rule = $false
$taskCreated = $false
try {
  $originalRdp = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections).fDenyTSConnections
  $alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#%"
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $buffer = New-Object byte[] 32
  $rng.GetBytes($buffer)
  $password = -join ($buffer | ForEach-Object { $alphabet[([int]$_) % $alphabet.Length] })
  $rng.Dispose()
  Write-Host ("::add-mask::{0}" -f $password)
  New-LocalUser -Name $account -Password (ConvertTo-SecureString $password -AsPlainText -Force) -PasswordNeverExpires | Out-Null
  Add-LocalGroupMember -Group "Remote Desktop Users" -Member $account
  Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections -Value 0
  Start-Service TermService
  New-NetFirewallRule -DisplayName "125A-P16-RDP-localhost" -Direction Inbound -Protocol TCP -LocalPort 3389 -RemoteAddress 127.0.0.1 -Action Allow | Out-Null
  $rule = $true
  choco install freerdp.portable --version=3.28.0 --yes --no-progress --limit-output
  if ($LASTEXITCODE -ne 0) { throw "FreeRDP install failed" }
  $client = "C:\ProgramData\chocolatey\lib\freerdp.portable\tools\wfreerdp.exe"
  if (-not (Test-Path -LiteralPath $client)) { $client = (Get-Command wfreerdp.exe -ErrorAction Stop).Source }
  $rdp = Start-Process -FilePath $client -ArgumentList @("/v:127.0.0.1","/u:$account","/p:$password","/cert:ignore","/size:1600x1000","/sec:nla") -PassThru
  $connected = $false
  for ($i=0;$i -lt 45;$i++) {
    Start-Sleep -Seconds 2
    if ((quser 2>&1 | Out-String) -match [regex]::Escape($account)) { $connected=$true; break }
    if ($rdp.HasExited) { throw "FreeRDP exited without desktop login" }
  }
  if (-not $connected) { throw "No interactive RDP user session" }
  $runner = Join-Path $kitPath "P16-Run-In-Desktop.cmd"
  @(
    "@echo off",
    "set GITHUB_ACTIONS=",
    "set CI=",
    ('cd /d "{0}"' -f $kitPath),
    ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{0}" > "{1}" 2>&1' -f (Join-Path $kitPath "Run-Interactive-OLE.ps1"),(Join-Path $kitPath "P16-DESKTOP-LOG.txt"))
  ) | Set-Content -LiteralPath $runner -Encoding ASCII
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument ('/c "{0}"' -f $runner)
  $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
  Register-ScheduledTask -TaskName $task -Action $action -Settings $settings -User "$env:COMPUTERNAME\$account" -Password $password -Force | Out-Null
  $taskCreated = $true
  $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$account" -LogonType Interactive -RunLevel Limited
  Set-ScheduledTask -TaskName $task -Principal $principal | Out-Null
  Start-ScheduledTask -TaskName $task
  for ($i=0;$i -lt 100;$i++) {
    Start-Sleep -Seconds 2
    $matches = @(Get-ChildItem -LiteralPath (Join-Path $kitPath "results") -Recurse -File -Filter "RESULT.txt" -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) { continue }
    $latest = $matches | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    Copy-Item -LiteralPath $latest.FullName -Destination $proof -Force
    $status = Get-Content -LiteralPath $proof -Raw
    if ($status -match "Status: PASS") { Write-Host "[PASS] P16 all four real OLE drops received"; return }
    throw "Native drag result not PASS"
  }
  throw "P16 interactive drag timed out"
} catch {
  if (-not (Test-Path -LiteralPath $proof)) {
    @("Status: FAIL",("Reason: {0}" -f $_.Exception.Message)) | Set-Content -LiteralPath $proof
  }
  Write-Host ("::error::{0}" -f $_.Exception.Message)
  exit 1
} finally {
  @("P16 interactive native OLE integration",("Session: {0}" -f (quser 2>&1 | Out-String)),
    ("Proof: {0}" -f $proof)) | Set-Content -LiteralPath $diagnostics
  if ($taskCreated) { Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue }
  if ($rdp -and -not $rdp.HasExited) { Stop-Process -Id $rdp.Id -Force -ErrorAction SilentlyContinue }
  if ($rule) { Remove-NetFirewallRule -DisplayName "125A-P16-RDP-localhost" -ErrorAction SilentlyContinue }
  if ($null -ne $originalRdp) { Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" -Name fDenyTSConnections -Value $originalRdp -ErrorAction SilentlyContinue }
  Remove-LocalUser -Name $account -ErrorAction SilentlyContinue
}
