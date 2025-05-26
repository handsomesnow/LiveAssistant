# debug_all_windows.py
import win32gui

def list_all_windows():
    def callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            class_name = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            results.append(f"[句柄: {hwnd}] [类名: {class_name}] [标题: {title}]")
        return True

    results = []
    win32gui.EnumWindows(callback, results)
    return results

if __name__ == "__main__":
    windows = list_all_windows()
    print(f"共找到 {len(windows)} 个可见窗口：")
    for win in windows:
        print(win)