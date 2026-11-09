param([int]$WaitSec = 25)

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

if ($hWnd -ne [IntPtr]::Zero) {
    [WinUtil]::SetForegroundWindow($hWnd)
    Start-Sleep -Milliseconds 500

    # Wait for Title Screen (around 3.5s)
    Start-Sleep -Seconds 4

    # On Title Screen ("Empezar partida" is default selected), press ENTER to advance to Main Menu
    Write-Host "0. Pressing ENTER on Title Screen ('Empezar partida')..."
    Send-Key $hWnd 0x0D # ENTER
    # Wait for MainMenu carousel entrance animation to complete
    Start-Sleep -Milliseconds 4500

    # Now on Main Menu (purple carousel ring)
    # Screenshot of MainMenu: Verify "ENTRENAMIENTO" (NO "PS3") and NO "Live"
    Write-Host "1. Capturing MainMenu screenshot (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # In MainMenu: Press DOWN once to reach Arcade Mode (Item 1)
    Write-Host "2. Navigating to Arcade Mode (DOWN x1)..."
    Send-Key $hWnd 0x28 # DOWN to Arcade
    # Wait for carousel rotation animation to settle on Arcade
    Start-Sleep -Seconds 3

    # Screenshot of carousel centered on Arcade
    Write-Host "2b. Capturing Arcade selected on carousel (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Select Arcade with ENTER
    Write-Host "2c. Selecting Arcade (ENTER)..."
    Send-Key $hWnd 0x0D # ENTER
    Start-Sleep -Seconds 4

    # On Arcade Settings screen:
    # Row 0 ("TIPO DE PARTIDO") is highlighted.
    # Navigate DOWN x3 to reach "PREPARADO"
    Write-Host "3. On Arcade Settings screen: Navigating DOWN x3 to PREPARADO..."
    Send-Key $hWnd 0x28 # DOWN to Número de Jugadores
    Start-Sleep -Milliseconds 700
    Send-Key $hWnd 0x28 # DOWN to Nivel de Juego
    Start-Sleep -Milliseconds 700
    Send-Key $hWnd 0x28 # DOWN to PREPARADO
    Start-Sleep -Milliseconds 800

    # Capture screenshot on PREPARADO
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 1

    # Confirm PREPARADO with ENTER -> Transitions directly to Character Select
    Write-Host "3b. Confirming PREPARADO (ENTER)..."
    Send-Key $hWnd 0x0D # ENTER on PREPARADO
    # Wait for transition into Character Select (fade-in)
    Start-Sleep -Seconds 6

    # Now in Character Select (Page 1: ATP/WTA - Federer at Slot 0)
    Write-Host "4. Now in Character Select: Page 1 (Federer at Slot 0)..."
    Send-Key $hWnd 0x79 # F10 (Screenshot of Character Select Page 1)
    Start-Sleep -Seconds 3

    # Switch to Page 2 (Legends) using 'E' key
    Write-Host "5. Switching to Page 2 (Legends) with [E]..."
    Send-Key $hWnd 0x45 # 'E'
    Start-Sleep -Seconds 2

    # Screenshot of Page 2 (Slot 0 is now Boris Becker!)
    Write-Host "6. Capturing Page 2 (Boris Becker at Slot 0) (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Move RIGHT to Slot 1 (Stefan Edberg)
    Write-Host "7. Moving RIGHT to Slot 1 (Stefan Edberg)..."
    Send-Key $hWnd 0x27 # RIGHT
    Start-Sleep -Seconds 2
    Write-Host "8. Capturing Stefan Edberg (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Move RIGHT to Slot 2 (Patrick Rafter)
    Write-Host "9. Moving RIGHT to Slot 2 (Patrick Rafter)..."
    Send-Key $hWnd 0x27 # RIGHT
    Start-Sleep -Seconds 2
    Write-Host "10. Capturing Patrick Rafter (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2

    # Switch back to Page 1 with 'Q'
    Write-Host "11. Switching back to Page 1 with [Q]..."
    Send-Key $hWnd 0x51 # 'Q'
    Start-Sleep -Seconds 2
    Write-Host "12. Capturing back on Page 1 (F10)..."
    Send-Key $hWnd 0x79 # F10
    Start-Sleep -Seconds 2
}

Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
Write-Host "---- Test Completed ----"
