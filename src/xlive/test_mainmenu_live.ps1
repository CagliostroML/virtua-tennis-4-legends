param([int]$WaitSec = 15)

$game = 'c:\Users\acorr\Documents\tenis\game'
Remove-Item "$game\xlive_mod.log" -ErrorAction SilentlyContinue

$p = Start-Process -FilePath "$game\VT4.exe" -WorkingDirectory $game -PassThru
Write-Host "Started VT4.exe PID: $($p.Id)"

Start-Sleep -Seconds 8

# Check log
$log = Get-Content "$game\xlive_mod.log" -ErrorAction SilentlyContinue
$liveRemoved = $log | Select-String -Pattern "LIVE Mode cleanly eliminated"
Write-Host "LIVE mode eliminated check: $liveRemoved"

$mainMenu = $log | Select-String -Pattern "MainMenu"
Write-Host "MainMenu logs count: $($mainMenu.Count)"

Stop-Process -Id $p.Id -Force
Write-Host "Test finished and process killed."
