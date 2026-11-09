Add-Type -AssemblyName System.Windows.Forms
$game = 'c:\Users\acorr\Documents\tenis\game'
Remove-Item "$game\xlive_mod.log" -ErrorAction SilentlyContinue
Remove-Item "$game\vt4_present_*.png" -ErrorAction SilentlyContinue

$p = Start-Process -FilePath "$game\VT4.exe" -WorkingDirectory $game -PassThru
Write-Host "Started VT4.exe PID: $($p.Id)"

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

function Send-Key($hWnd, $vk, $holdMs = 150) {
    [WinUtil]::SetForegroundWindow($hWnd)
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]$vk, [IntPtr]0) # WM_KEYDOWN
    Start-Sleep -Milliseconds $holdMs
    [WinUtil]::PostMessage($hWnd, 0x0101, [IntPtr]$vk, [IntPtr]0) # WM_KEYUP
    Start-Sleep -Milliseconds 400
}

# Wait until game window exists
$hWnd = [IntPtr]::Zero
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 250
    $p.Refresh()
    if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
        $hWnd = $p.MainWindowHandle
        break
    }
}
Write-Host "Game HWND: $hWnd"
if ($hWnd -eq [IntPtr]::Zero) {
    Write-Host "Failed to find window handle!"
    Stop-Process -Id $p.Id -Force
    exit 1
}

[WinUtil]::SetForegroundWindow($hWnd)
Start-Sleep -Seconds 4

# On Title Screen: Press Enter
Write-Host "1. On Title Screen: Pressing ENTER..."
Send-Key $hWnd 0x0D # ENTER
Start-Sleep -Seconds 4

# Screenshot 1: Main Menu
Write-Host "2. Capturing Main Menu screenshot (F10)..."
Send-Key $hWnd 0x79 # F10
Start-Sleep -Seconds 2

# Rotate Carousel DOWN once
Write-Host "3. Rotating Carousel DOWN (DOWN arrow)..."
Send-Key $hWnd 0x28 # DOWN
Start-Sleep -Seconds 2

# Screenshot 2: Main Menu after rotation
Write-Host "4. Capturing Main Menu after DOWN (F10)..."
Send-Key $hWnd 0x79 # F10
Start-Sleep -Seconds 2

# Select Arcade or Exhibition with ENTER
Write-Host "5. Pressing ENTER on selected menu item..."
Send-Key $hWnd 0x0D # ENTER
Start-Sleep -Seconds 4

# Screenshot 3: Settings or Court Position
Write-Host "6. Capturing next screen (F10)..."
Send-Key $hWnd 0x79 # F10
Start-Sleep -Seconds 2

# Navigate down if on settings, or press Enter
Write-Host "7. Pressing ENTER..."
Send-Key $hWnd 0x0D # ENTER
Start-Sleep -Seconds 5

# Screenshot 4: Character select or court
Write-Host "8. Capturing Character Select screen (F10)..."
Send-Key $hWnd 0x79 # F10
Start-Sleep -Seconds 2

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Write-Host "---- Test Completed ----"
