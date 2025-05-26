# live_assistant_final.py
import re
import time
import win32gui
import tkinter as tk
from tkinter import font, ttk  # 修改此行
from configparser import ConfigParser
from ctypes import windll
from PIL import Image, ImageDraw
import pystray
import threading
# --------------------------
# 配置加载模块
# --------------------------
config = ConfigParser()
config.read('config.ini', encoding='utf-8')

# --------------------------
# 番茄钟模块
# --------------------------
class PomodoroTimer:
    def __init__(self, app):
        self.app = app
        self.is_running = False
        self.start_time = 0
        self.total_seconds = 0
        self.paused_time = 0
        self.paused_by_external = False  # 新增：标记是否因外部原因（如B站）暂停
        self._update_loop = None  # 用于存储定时器ID

    def start(self):
        """启动番茄钟"""
        if not self.is_running:
            self.is_running = True
            self.start_time = time.time() - self.paused_time
            self._schedule_update()

    def _schedule_update(self):
        """使用after调度计时更新"""
        if self.is_running:
            elapsed = int(time.time() - self.start_time)
            self.total_seconds = elapsed
            self.app.update_pomodoro_display(elapsed)
            self._update_loop = self.app.after(1000, self._schedule_update)

    def pause_or_resume(self, is_external=False):
            if self.is_running:
                # 暂停逻辑
                self.is_running = False
                self.paused_time = time.time() - self.start_time
                self.paused_by_external = is_external
                if self._update_loop:
                    self.app.after_cancel(self._update_loop)
            else:
                # 恢复逻辑
                self.is_running = True
                self.start_time = time.time() - self.paused_time
                self.paused_by_external = False
                self._schedule_update()

   

    def get_elapsed_time(self):
        if self.is_running:
            return time.time() - self.start_time
        return self.paused_time

    def update_timer(self):
         while self.is_running:
            elapsed = int(time.time() - self.start_time)
            self.total_seconds = elapsed
            self.app.update_pomodoro_display(elapsed)
            time.sleep(1)

# --------------------------
# 哔哩哔哩监控模块
# --------------------------
class BilibiliMonitor:
    @staticmethod
    def is_playing():
        def callback(hwnd, handles):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                if "哔哩哔哩 (゜-゜)つロ 干杯~-bilibili" in title and "Chrome_WidgetWin_1" in class_name:
                    handles.append(hwnd)
            return True

        handles = []
        win32gui.EnumWindows(callback, handles)
        return len(handles) > 0
    
# --------------------------
# QQ音乐监控模块
# --------------------------
class QQMusicMonitor:
    @staticmethod
    def get_window_handle():
        """获取QQ音乐窗口句柄"""
        def callback(hwnd, handles):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                if "TXGuiFoundation" in class_name:
                    handles.append(hwnd)
            return True

        handles = []
        win32gui.EnumWindows(callback, handles)
        return handles[0] if handles else None

    @classmethod
    def get_current_track(cls):
        """解析播放信息"""
        hwnd = cls.get_window_handle()
        if not hwnd:
            return None

        title = win32gui.GetWindowText(hwnd)
        match = re.match(
            r"^\s*(.+?)\s*[—-]\s*(.+?)(\s*-\s*QQ音乐)?\s*$", 
            title
        )
        return {
            "title": match.group(1).strip(),
            "artist": match.group(2).strip()
        } if match else None

# --------------------------
# GUI主程序
# --------------------------
class LiveAssistant(tk.Tk):
    def __init__(self):
        super().__init__()
        self.entries = []  # 输入框列表
        self.init_ui()
        self.setup_tray()
        self.load_config()
        self.setup_drag()
        self.setup_key_bindings()  # 新增此行
        self.after(100, self.update_display)
        self.pomodoro = PomodoroTimer(self)
        self.init_pomodoro_ui()  # 新增初始化番茄钟UI
        self.after(1000, self.check_bilibili_loop)

        self.pomodoro.start()
    
    def init_ui(self):
        """初始化界面"""
        self.title("直播助手 - QQ音乐")
        self.configure(bg='#1A1A1A')
        self.wm_attributes("-topmost", True)
          # 在原有输入框容器后添加番茄钟容器
        self.pomodoro_frame = tk.Frame(self, bg='#1A1A1A')
        self.pomodoro_frame.pack(pady=(2, 3), padx=20, fill='x')
        
        # 字体设置
        self.font_style = font.Font(
            family=config.get('UI', 'font', fallback='微软雅黑'),
            size=config.getint('UI', 'font_size', fallback=14)
        )

        # 播放信息标签
        self.label = tk.Label(
            self,
            text="初始化中...",
            fg=config.get('UI', 'color', fallback='#00FF00'),
            bg='#1A1A1A',
            font=self.font_style
        )
        self.label.pack(padx=20, pady=2)

        # 窗口属性
        self.overrideredirect(True)
        self.wm_attributes("-alpha", config.getfloat('UI', 'opacity', fallback=0.9))
        self.geometry(f"+{config.getint('Position', 'x', fallback=100)}+"
                      f"{config.getint('Position', 'y', fallback=100)}")

        # 输入框容器（必须先创建）
        self.entry_frame = tk.Frame(self, bg='#1A1A1A')
        self.entry_frame.pack(pady=(0, 10), padx=20, fill='x')

        # 加载已有输入框
        self.load_custom_text()

        # 初始空输入框
        if not self.entries:
            self.create_new_entry(config.get('CustomText', 'content0', fallback='欢迎~~'))

    def setup_tray(self):
        """系统托盘"""
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
        """窗口拖动"""
        self.bind("<ButtonPress-1>", self.start_drag)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.save_position)

    def init_pomodoro_ui(self):
        """初始化番茄钟界面"""
        style = ttk.Style()
        style.configure('Round.TButton', 
                      font=self.font_style,
                      relief='flat',
                      background="#EBEBEB",
                      borderwidth=0)

        # 主容器（水平排列）
        timer_frame = tk.Frame(self.pomodoro_frame, bg='#1A1A1A')
        timer_frame.pack(side='top', pady=5, fill='x')

        
  # 时间标签
        self.time_label = tk.Label(
            timer_frame,
            text="00:00:00",
            fg="#B4B4B4",
            bg='#1A1A1A',
            font=self.font_style,
            width=10
        )
        self.time_label.pack(side='left', padx=(0, 0))

        # 圆形按钮容器
        btn_canvas = tk.Canvas(
            timer_frame,
            bg='#1A1A1A',
            width=40,
            height=40,
            highlightthickness=0
        )
        btn_canvas.pack(side='right')

        # 绘制圆形按钮
        self.btn_circle = btn_canvas.create_oval(
            5, 5, 32, 32,
            fill="#4D524D",
            outline="#1A1A1A",
            tags=("pause_btn",)
        )
        
        # 添加文字
        self.btn_text = btn_canvas.create_text(
            18, 18,
            text="❌",  # 初始状态为暂停（显示播放符号）
            fill="#1A1A1A",
            font=self.font_style,

            tags=("pause_btn",),
            activefill="#7A7676",  # 新增：悬停状态颜色
            disabledfill="#F3ECEC",  # 新增：禁用状态颜色
      
        )

        # 绑定点击事件
        btn_canvas.tag_bind("pause_btn", "<Button-1>", lambda e: self.pause_or_resume_pomodoro())

        # 定时检测哔哩哔哩
        self.after(1000, self.check_bilibili)

    def pause_or_resume_pomodoro(self):
        """更新按钮状态"""
        self.pomodoro.pause_or_resume()
        btn_canvas = self.time_label.master.winfo_children()[1]
        if self.pomodoro.is_running:
            btn_canvas.itemconfig(self.btn_text, text="❌")
          
        else:
            btn_canvas.itemconfig(self.btn_text, text="➕")
    
            
    def update_pomodoro_display(self, seconds):
        """更新时间显示"""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        self.time_label.config(text=f"{h:02}:{m:02}:{s:02}")

    def start_pomodoro(self):
        self.pomodoro.start()
        self.start_btn.config(state='disabled')
        self.pause_resume_btn.config(state='normal', text="暂停")


    def check_bilibili_loop(self):
        """替代线程的定时检测方法"""
        self.check_bilibili()
        self.after(1000, self.check_bilibili_loop)  # 每秒调度一次

    def check_bilibili(self):
        """检测哔哩哔哩播放状态"""
        is_playing = BilibiliMonitor.is_playing()
        
        # 情况1：检测到播放且计时正在运行 → 暂停计时
        if is_playing and self.pomodoro.is_running:
            self.pomodoro.pause_or_resume(is_external=True)   # 暂停计时
            # self.label.config(text="检测到视频播放，计时已暂停", fg='#FF0000')
        
        # 情况2：未检测到播放且是被外部暂停 → 自动恢复
        elif not is_playing and self.pomodoro.paused_by_external:
            self.pomodoro.pause_or_resume()  # 恢复计时
            # self.update_music_display()  # 恢复音乐显示


        
    def update_display(self):
        """更新音乐信息"""
        try:
            track = QQMusicMonitor.get_current_track()
            display_text = f"QQ音乐：{track['title']} - {track['artist']}" if track else "QQ音乐未播放"
            color = "#EBF3EB" if track else '#FF0000'
            self.label.config(text=display_text, fg=color)
        except Exception as e:
            print(f"[ERROR] 更新失败: {str(e)}")
        finally:
            self.after(1000, self.update_display)

    def create_new_entry(self, content=""):
        """创建新输入框"""
        entry = tk.Entry(
            self.entry_frame,
            bg='#1A1A1A',
            fg=config.get('UI', 'color', fallback="#FCFFFC"),
            insertbackground="#B7B9B7",
            font=self.font_style,
            width=25,
            highlightthickness=0,
            relief='flat'
        )
        entry.insert(0, content)
        entry.pack(fill='x', pady=2)
        entry.bind('<Return>', lambda e: self.add_new_entry())
        self.entries.append(entry)
        entry.focus_set()  # 新增焦点设置
        
    def add_new_entry(self):
        """新增输入框"""
        self.create_new_entry()
        self.save_custom_text()

    def load_custom_text(self):
        """加载配置"""
        # 清空现有输入框
        for entry in self.entries:
            entry.destroy()
        self.entries.clear()
        
        if config.has_section('CustomText'):
            # 按数字排序 content0, content1...
            contents = [
                config.get('CustomText', key)
                for key in sorted(config.options('CustomText'), 
                               key=lambda x: int(x[7:]))
                if key.startswith('content')
            ]
            for content in contents:
                self.create_new_entry(content)
    def setup_key_bindings(self):
        """绑定键盘事件"""
        self.bind_all('<Delete>', self.delete_last_entry)

    def delete_last_entry(self, event):
        """删除最后一个输入框"""
        if len(self.entries) > 1:  # 至少保留一个输入框
            last_entry = self.entries.pop()
            last_entry.destroy()
            self.save_custom_text()
            
    def save_custom_text(self, *args):
        """保存配置"""
        config.remove_section('CustomText')
        config.add_section('CustomText')
        for idx, entry in enumerate(self.entries):
            config.set('CustomText', f'content{idx}', entry.get())
        with open('config.ini', 'w', encoding='utf-8') as f:
            config.write(f)

    def load_config(self):
        """初始化配置"""
        if not config.has_section('UI'):
            config['UI'] = {
                'font': '微软雅黑',
                'font_size': '14',
                'color': '#00FF00',
                'opacity': '0.9'
            }
        if not config.has_section('Position'):
            config['Position'] = {'x': '100', 'y': '100'}
        if not config.has_section('CustomText'):
            config['CustomText'] = {'content0': '欢迎~~'}
        # 立即保存初始配置
        with open('config.ini', 'w', encoding='utf-8') as f:
            config.write(f)

    # 事件处理
    def start_drag(self, event):
        self._drag_data = {"x": event.x_root, "y": event.y_root}

    def on_drag(self, event):
        dx = event.x_root - self._drag_data["x"]
        dy = event.y_root - self._drag_data["y"]
        self.geometry(f"+{self.winfo_x()+dx}+{self.winfo_y()+dy}")
        self._drag_data = {"x": event.x_root, "y": event.y_root}

    def save_position(self, _):
        config['Position'] = {'x': self.winfo_x(), 'y': self.winfo_y()}
        with open('config.ini', 'w', encoding='utf-8') as f:
            config.write(f)

    def destroy_app(self):
        self.tray_icon.stop()
        self.destroy()

# --------------------------
# 启动程序
# --------------------------
if __name__ == "__main__":
    windll.shcore.SetProcessDpiAwareness(1)
    app = LiveAssistant()
    app.mainloop()