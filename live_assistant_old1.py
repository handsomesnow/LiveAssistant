# live_assistant.py
import re
import win32gui
import tkinter as tk
from tkinter import font
from configparser import ConfigParser
from ctypes import windll
from PIL import Image, ImageDraw
import pystray

# --------------------------
# 配置加载模块
# --------------------------
config = ConfigParser()
config.read('config.ini', encoding='utf-8')

# --------------------------
# QQ音乐监控模块
# --------------------------
class QQMusicMonitor:
    @staticmethod
    def get_window_handle():
        """获取QQ音乐窗口句柄（修正类名）"""
        def callback(hwnd, handles):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                # 精确匹配最新版QQ音乐窗口特征
                if ("TXGuiFoundation" in class_name) :
                    handles.append(hwnd)
            return True

        handles = []
        win32gui.EnumWindows(callback, handles)
        return handles[0] if handles else None

    @classmethod
    def get_current_track(cls):
        """解析播放信息（增强容错）"""
        hwnd = cls.get_window_handle()
        if not hwnd:
            return None

        title = win32gui.GetWindowText(hwnd)
        # 支持中英文破折号/空格
        match = re.match(
            r"^\s*(.+?)\s*[—-]\s*(.+?)(\s*-\s*QQ音乐)?\s*$", 
            title
        )
        if match:
            return {
                "title": match.group(1).strip(),
                "artist": match.group(2).strip()
            }
        return None

# --------------------------
# GUI主程序
# --------------------------
class LiveAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.setup_tray()
        self.load_config()
        self.setup_drag()
        
        # 初始化后延迟启动检测
        self.after(100, self.update_display)

    def init_ui(self):
        """初始化界面"""
        self.title("直播助手 - QQ音乐")
        self.configure(bg='#1A1A1A')
        
        self.wm_attributes("-topmost", True)  # 新增此行
        # 自定义字体
        self.font_style = font.Font(
            family=config.get('UI', 'font', fallback='微软雅黑'),
            size=config.getint('UI', 'font_size', fallback=14)
        )
        
        # 显示标签
        self.label = tk.Label(
            self,
            text="初始化中...",
            fg=config.get('UI', 'color', fallback='#00FF00'),
            bg='#1A1A1A',
            font=self.font_style
        )
        self.label.pack(padx=20, pady=10)
        
        # 窗口属性
        self.overrideredirect(True)  # 隐藏标题栏
        self.wm_attributes("-alpha", config.getfloat('UI', 'opacity', fallback=0.9))
        self.geometry(f"+{config.getint('Position', 'x', fallback=100)}+"
                      f"{config.getint('Position', 'y', fallback=100)}")

    def setup_tray(self):
        """系统托盘图标"""
        image = Image.new('RGB', (64, 64), '#1A1A1A')
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill='#00FF00')
        
        menu = pystray.Menu(
            pystray.MenuItem('退出', self.destroy_app),
            pystray.MenuItem('显示窗口', self.deiconify)
        )
        self.tray_icon = pystray.Icon(
            "live_assistant", 
            image, 
            "直播助手", 
            menu
        )

    def setup_drag(self):
        """窗口拖动支持"""
        self.bind("<ButtonPress-1>", self.start_drag)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.save_position)

    def update_display(self):
        """更新显示内容"""
        try:
            track = QQMusicMonitor.get_current_track()
            if track:
                display_text = f"QQ音乐：{track['title']} - {track['artist']}"
                color = "#EBF3EB"
            else:
                display_text = "QQ音乐未播放"
                color = '#FF0000'
            
            self.label.config(text=display_text, fg=color)
        except Exception as e:
            print(f"[ERROR] 更新失败: {str(e)}")
        finally:
            self.after(1000, self.update_display)

    # --------------------------
    # 事件处理
    # --------------------------
    def start_drag(self, event):
        self._drag_data = {"x": event.x_root, "y": event.y_root}

    def on_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        self.geometry(f"+{self.winfo_x()+dx}+{self.winfo_y()+dy}")
        self._drag_data = {"x": event.x_root, "y": event.y_root}

    def save_position(self, _):
        """保存窗口位置"""
        config['Position'] = {
            'x': str(self.winfo_x()),
            'y': str(self.winfo_y())
        }
        with open('config.ini', 'w', encoding='utf-8') as f:
            config.write(f)

    def destroy_app(self):
        """安全退出"""
        self.tray_icon.stop()
        self.destroy()

    def load_config(self):
        """配置初始化"""
        if not config.has_section('UI'):
            config['UI'] = {
                'font': '微软雅黑',
                'font_size': '14',
                'color': '#00FF00',
                'opacity': '0.9'
            }
        if not config.has_section('Position'):
            config['Position'] = {'x': '100', 'y': '100'}

# --------------------------
# 启动程序
# --------------------------
if __name__ == "__main__":
    # 解决Windows高DPI缩放模糊问题
    windll.shcore.SetProcessDpiAwareness(1)
    
    app = LiveAssistant()
    app.mainloop()