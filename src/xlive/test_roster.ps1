param([int]$WaitSec = 16)

Add-Type -AssemblyName System.Windows.Forms
$game = 'c:\Users\acorr\Documents\tenis\game'
Remove-Item "$game\xlive_mod.log" -ErrorAction SilentlyContinue

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

function Send-Key($hWnd, $vk) {
    [WinUtil]::PostMessage($hWnd, 0x0100, [IntPtr]$vk, [IntPtr]0) # WM_KEYDOWN
    Start-Sleep -Milliseconds 60
    [WinUtil]::PostMessage($hWnd, 0x0101, [IntPtr]$vk, [IntPtr]0) # WM_KEYUP
    Start-Sleep -Milliseconds 250
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

if ($hWnd -ne [IntPtr]::Zero) {
    [WinUtil]::SetForegroundWindow($hWnd)
    Start-Sleep -Milliseconds 500

    # Wait for MainMenu (around frame 120 / ~2.5s)
    Start-Sleep -Seconds 4

    # In MainMenu: Press DOWN to reach Exhibition
    Write-Host "1. Selecting Exhibition..."
    Send-Key $hWnd 0x28 # DOWN
    Start-Sleep -Milliseconds 600
    Send-Key $hWnd 0x0D # ENTER (Select Exhibition)
    Start-Sleep -Seconds 3

    # In Exhibition settings: Press UP to PREPARADO
    Write-Host "2. Navigating to PREPARADO..."
    Send-Key $hWnd 0x26 # UP
    Start-Sleep -Milliseconds 600
    Send-Key $hWnd 0x0D # ENTER (Confirm PREPARADO)
    Start-Sleep -Seconds 3

    # The auto-advance patch seamlessly transitions through Position Select to Character Select!
    Write-Host "3. Smoothly transitioning to Character Select Screen..."
    Start-Sleep -Seconds 4

    # NOW WE ARE IN CHARACTER SELECT!
    Write-Host "4. Taking screenshot of Character Select Screen (Slot 0 - Federer)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Navigate grid to Row 2, Slot 21 (Boris Becker)
    # The grid has 3 rows:
    # Row 0 (0..7): Federer, Nadal, Djokovic, Murray, Del Potro, Roddick, Monfils, Gonzalez
    # Row 1 (8..15): Kohlschreiber, Seppi, Haas, King, Duke, Sharapova, Venus, Kuznetsova
    # Row 2 (16..23): Ivanovic, Chakvetadze, Wozniacki, Laura Robson, Tenniel, Becker(21), Rafter(22), Edberg(23)
    # Move DOWN twice
    Write-Host "5. Moving DOWN twice to Row 2..."
    Send-Key $hWnd 0x28 # DOWN
    Start-Sleep -Milliseconds 500
    Send-Key $hWnd 0x28 # DOWN
    Start-Sleep -Milliseconds 500

    # Move RIGHT 5 times to Slot 21 (Boris Becker)
    Write-Host "6. Moving RIGHT to Slot 21 (Boris Becker)..."
    for ($i = 0; $i -lt 5; $i++) {
        Send-Key $hWnd 0x27 # RIGHT
        Start-Sleep -Milliseconds 400
    }
    Start-Sleep -Seconds 2
    Write-Host "7. Taking screenshot of Boris Becker (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Move RIGHT to Slot 22 (Patrick Rafter)
    Write-Host "8. Moving RIGHT to Slot 22 (Patrick Rafter)..."
    Send-Key $hWnd 0x27 # RIGHT
    Start-Sleep -Seconds 2
    Write-Host "9. Taking screenshot of Patrick Rafter (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Move RIGHT to Slot 23 (Stefan Edberg)
    Write-Host "10. Moving RIGHT to Slot 23 (Stefan Edberg)..."
    Send-Key $hWnd 0x27 # RIGHT
    Start-Sleep -Seconds 2
    Write-Host "11. Taking screenshot of Stefan Edberg (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2
}

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue

Write-Host "---- Done ----"
