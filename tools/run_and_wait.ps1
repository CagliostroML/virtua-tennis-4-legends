$p = Start-Process (Join-Path (Split-Path -Parent $PSScriptRoot) "game\VT4.exe") -WorkingDirectory (Join-Path (Split-Path -Parent $PSScriptRoot) "game") -PassThru
Write-Host "Started PID $($p.Id)"
$p.WaitForExit()
Write-Host "Exited with code: $($p.ExitCode)"
