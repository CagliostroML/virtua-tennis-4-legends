param([int]$Seconds = 10)
$game = 'c:\Users\acorr\Documents\tenis\game'
Remove-Item "$game\xlive_mod.log" -ErrorAction SilentlyContinue
$start = Get-Date
$p = Start-Process -FilePath "$game\VT4.exe" -WorkingDirectory $game -PassThru
Write-Host "VT4.exe PID: $($p.Id)"
Start-Sleep -Seconds $Seconds
$alive = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if ($alive) { Write-Host "ALIVE: title='$($alive.MainWindowTitle)' ws=$([int]($alive.WorkingSet64/1MB))MB" } else { Write-Host "EXITED (code $($p.ExitCode))" }
Write-Host "---- xlive_mod.log ----"
if (Test-Path "$game\xlive_mod.log") { Get-Content "$game\xlive_mod.log" }
Write-Host "---- crashes since start ----"
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=$start} -ErrorAction SilentlyContinue |
    ForEach-Object { ($_.Message -split "`n" | Select-String 'VT4|Desplazamiento|Offset|módulo|module|Código|code') -join ' | ' }
