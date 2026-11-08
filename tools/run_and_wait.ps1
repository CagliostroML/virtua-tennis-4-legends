$p = Start-Process 'c:\Users\acorr\Documents\tenis\game\VT4.exe' -WorkingDirectory 'c:\Users\acorr\Documents\tenis\game' -PassThru
Write-Host "Started PID $($p.Id)"
$p.WaitForExit()
Write-Host "Exited with code: $($p.ExitCode)"
