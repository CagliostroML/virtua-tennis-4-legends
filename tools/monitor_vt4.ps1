Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$game = 'c:\Users\acorr\Documents\tenis\game'
$p = Start-Process -FilePath "$game\VT4.exe" -WorkingDirectory $game -PassThru
Write-Host "VT4 started PID: $($p.Id)"

for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host "Process exited at second $i with code $($p.ExitCode)"
        break
    }
    Write-Host "Second ${i}: ALIVE ws=$([int]($proc.WorkingSet64/1MB))MB title='$($proc.MainWindowTitle)'"
    if ($i -eq 5 -or $i -eq 10) {
        # Take screenshot of screen
        $bmp = New-Object System.Drawing.Bitmap([System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width, [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen(0, 0, 0, 0, $bmp.Size)
        $out = "c:\Users\acorr\Documents\tenis\screenshot_${i}s.png"
        $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose()
        $bmp.Dispose()
        Write-Host "Saved screenshot to $out"
    }
}

$proc = Get-Process -Id $p.Id -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "VT4 IS RUNNING NORMALLY!"
    # Don't kill it yet, let it run or kill if needed
}
