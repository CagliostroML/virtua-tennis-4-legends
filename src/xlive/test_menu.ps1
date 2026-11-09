param([int]$WaitSec = 4)

Add-Type -AssemblyName System.Windows.Forms
$game = 'c:\Users\acorr\Documents\tenis\game'
Remove-Item "$game\xlive_mod.log" -ErrorAction SilentlyContinue

$p = Start-Process -FilePath "$game\VT4.exe" -WorkingDirectory $game -PassThru
Write-Host "Started VT4.exe PID: $($p.Id)"
Start-Sleep -Seconds $WaitSec

# Send F2 directly to game window via PostMessage or SendKeys
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinUtil {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);
}
"@

$hWnd = $p.MainWindowHandle
if ($hWnd -eq [IntPtr]::Zero) {
    Start-Sleep -Seconds 1
    $p.Refresh()
    $hWnd = $p.MainWindowHandle
}
Write-Host "Game HWND: $hWnd"

if ($hWnd -ne [IntPtr]::Zero) {
    [WinUtil]::SetForegroundWindow($hWnd)
    Start-Sleep -Milliseconds 300

    # WM_KEYDOWN = 0x0100, VK_F2 = 0x71
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]0x71, [IntPtr]0) # F2
    Start-Sleep -Milliseconds 400
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]0x28, [IntPtr]0) # DOWN
    Start-Sleep -Milliseconds 400
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]0x27, [IntPtr]0) # RIGHT
    Start-Sleep -Milliseconds 400
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]0x0D, [IntPtr]0) # ENTER
    Start-Sleep -Seconds 2
}

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue

Write-Host "---- Menu & Settings Log Entries ----"
if (Test-Path "$game\xlive_mod.log") {
    Get-Content "$game\xlive_mod.log" | Select-String "Menu|Settings|F2|saved|updated"
}
