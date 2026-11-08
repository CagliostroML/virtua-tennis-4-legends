$p = Start-Process 'c:\Users\acorr\Documents\tenis\game\VT4.exe' -WorkingDirectory 'c:\Users\acorr\Documents\tenis\game' -PassThru
Write-Host "VT4 PID: $($p.Id)"
Start-Sleep -Seconds 3

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinInfo {
    [DllImport("user32.dll")] public static extern bool EnumThreadWindows(int dwThreadId, EnumThreadDelegate lpfn, IntPtr lParam);
    public delegate bool EnumThreadDelegate(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr hWnd, System.Text.StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr hWnd, int nIndex);
    public struct RECT { public int Left, Top, Right, Bottom; }

    public static void Inspect(int pid) {
        var proc = System.Diagnostics.Process.GetProcessById(pid);
        foreach (System.Diagnostics.ProcessThread t in proc.Threads) {
            EnumThreadWindows(t.Id, (hwnd, l) => {
                var title = new System.Text.StringBuilder(256);
                GetWindowText(hwnd, title, 256);
                var cls = new System.Text.StringBuilder(256);
                GetClassName(hwnd, cls, 256);
                RECT r, cr;
                GetWindowRect(hwnd, out r);
                GetClientRect(hwnd, out cr);
                int style = GetWindowLong(hwnd, -16);
                Console.WriteLine(string.Format("HWND: 0x{0:X} Title: '{1}' Class: '{2}' Visible: {3} Style: 0x{4:X8} Rect: ({5},{6})-({7},{8}) [{9}x{10}] Client: [{11}x{12}]",
                    hwnd.ToInt64(), title, cls, IsWindowVisible(hwnd), style, r.Left, r.Top, r.Right, r.Bottom, r.Right-r.Left, r.Bottom-r.Top, cr.Right-cr.Left, cr.Bottom-cr.Top));
                return true;
            }, IntPtr.Zero);
        }
    }
}
"@

[WinInfo]::Inspect($p.Id)
