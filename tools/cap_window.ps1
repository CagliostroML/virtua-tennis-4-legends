Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Drawing;
using System.Drawing.Imaging;

public class WinCap {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static void CapturePid(uint targetPid, string file) {
        EnumWindows((hWnd, lParam) => {
            uint pid;
            GetWindowThreadProcessId(hWnd, out pid);
            if (pid == targetPid) {
                RECT r;
                GetWindowRect(hWnd, out r);
                int w = r.Right - r.Left;
                int h = r.Bottom - r.Top;
                Console.WriteLine("Found HWND: " + hWnd + " Size: " + w + "x" + h);
                if (w > 100 && h > 100) {
                    Bitmap bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
                    using (Graphics g = Graphics.FromImage(bmp)) {
                        IntPtr hdc = g.GetHdc();
                        try {
                            PrintWindow(hWnd, hdc, 2); // 2 = PW_RENDERFULLCONTENT
                        } finally {
                            g.ReleaseHdc(hdc);
                        }
                    }
                    bmp.Save(file, ImageFormat.Png);
                    Console.WriteLine("Saved screenshot to: " + file);
                    return false;
                }
            }
            return true;
        }, IntPtr.Zero);
    }
}
"@ -ReferencedAssemblies System.Drawing, System.Windows.Forms

[WinCap]::CapturePid(14052, "c:\Users\acorr\Documents\tenis\vt4_window.png")
