import threading
import tkinter as tk
from PIL import Image, ImageTk
import pyautogui
import platform
import os
from .configure_logger import configure_logger

# 初始化日志记录器
logger = configure_logger()

class CursorIndicator:
    """
    鼠标指示器类，用于显示触控板状态的可视化反馈图标。
    支持Windows和Linux平台。
    """
    def __init__(self, command_queue=None):
        self.command_queue = command_queue
        self.root = None
        self.is_running = False
        self.window_created = False
        self.indicator_thread = None
        self.tk_img = None
        self.hide_timer = None
        self.is_showing = False
        
    def start(self, icon_type="default", auto_hide_duration=None):
        """
        启动指示器，指定图标类型和可选的自动隐藏功能
        
        参数:
            icon_type: 图标类型 ("default", "on", 或 "off")
            auto_hide_duration: 自动隐藏前的显示时间（秒），None表示不自动隐藏
        """
        # 取消任何已存在的隐藏计时器
        if self.hide_timer:
            self.hide_timer.cancel()
            self.hide_timer = None
            
        # 如果窗口已存在但被隐藏，则显示并更新图标
        if self.window_created and self.root and self.root.winfo_exists():
            if not self.is_showing:
                self.root.deiconify()
                self.is_showing = True
                
            self._update_icon(icon_type)
            self.is_running = True
        else:
            # 首次创建窗口
            self.is_running = True
            self.is_showing = True
            
            self.indicator_thread = threading.Thread(
                target=self._create_window, 
                args=(icon_type,), 
                daemon=True
            )
            self.indicator_thread.start()
            logger.info(f"鼠标指示器线程已启动，图标类型: {icon_type}")
        
        # 如果提供了持续时间，设置自动隐藏
        if auto_hide_duration is not None:
            self.hide_timer = threading.Timer(auto_hide_duration, self.hide)
            self.hide_timer.daemon = True
            self.hide_timer.start()
            logger.info(f"指示器将在 {auto_hide_duration} 秒后自动隐藏")
    
    def hide(self):
        """隐藏指示器但不销毁窗口"""
        if self.window_created and self.root and self.root.winfo_exists() and self.is_showing:
            self.root.withdraw()
            self.is_showing = False
            logger.info("鼠标指示器已隐藏")
    
    def destroy(self):
        """完全销毁指示器窗口和资源"""
        self.is_running = False
        self.is_showing = False
        
        if self.hide_timer:
            self.hide_timer.cancel()
            self.hide_timer = None
            
        if self.window_created and self.root and self.root.winfo_exists():
            try:
                self.root.destroy()
                self.window_created = False
                logger.info("鼠标指示器窗口已销毁")
            except Exception as e:
                logger.error(f"销毁指示器窗口失败: {e}")
    
    def _create_window(self, icon_type):
        """创建指示器窗口和UI组件"""
        try:
            self.root = tk.Tk()
            self.window_created = True
            self.root.config(bg='#00ff00')  # 透明色
            
            # 窗口属性
            self.root.overrideredirect(True)
            self.root.attributes('-topmost', True)
            
            # 跨平台透明处理
            if platform.system() == 'Windows':
                self.root.wm_attributes('-transparentcolor', '#00ff00')
            elif platform.system() == 'Linux':
                self.root.attributes('-alpha', 0.9)
            
            # 加载图标
            self._load_icon(icon_type)
            
            # 创建标签显示图标
            self.label = tk.Label(self.root, image=self.tk_img, bg='#00ff00')
            self.label.pack()
            
            # 设置关闭行为
            self.root.protocol("WM_DELETE_WINDOW", self.hide)
            
            # 开始位置更新
            self._update_position()
            
            # 进入主循环
            self.root.mainloop()
            
        except Exception as e:
            logger.error(f"创建指示器窗口失败: {e}")
            self.is_running = False
            self.window_created = False
            if self.command_queue:
                self.command_queue.put(('cursor_indicator_failed', None))
    
    def _update_position(self):
        """更新窗口位置以跟随鼠标光标"""
        if not self.is_running or not self.window_created:
            return
            
        try:
            # 获取鼠标坐标
            x, y = pyautogui.position()
            
            # 计算窗口位置（右下角偏移）
            offset = 20
            win_x = x + offset
            win_y = y + offset
            
            # 防止窗口超出屏幕范围
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            icon_width = self.tk_img.width() if self.tk_img else 32
            icon_height = self.tk_img.height() if self.tk_img else 32
            
            if win_x + icon_width > screen_width:
                win_x = screen_width - icon_width
            if win_y + icon_height > screen_height:
                win_y = screen_height - icon_height
            
            # 更新窗口位置
            self.root.geometry(f"+{win_x}+{win_y}")
            
            # 安排下一次更新
            self.root.after(30, self._update_position)
            
        except Exception as e:
            logger.error(f"更新指示器位置失败: {e}")
    
    def _update_icon(self, icon_type):
        """更新当前显示的图标"""
        if not self.window_created or not self.root:
            return
            
        try:
            self._load_icon(icon_type)
            
            # 更新标签
            if hasattr(self, 'label') and self.label.winfo_exists():
                self.label.config(image=self.tk_img)
                logger.info(f"已更新指示器图标为: {icon_type}")
        except Exception as e:
            logger.error(f"更新指示器图标失败: {e}")
    
    def _load_icon(self, icon_type):
        """加载指定类型的图标"""
        try:
            # 获取图标目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_dir = os.path.join(current_dir, 'source')
            
            # 根据类型选择图标文件
            icon_files = {
                "default": "cursor_default.png",
                "on": "cursor_on.png",
                "off": "cursor_off.png",
            }
            
            icon_file = icon_files.get(icon_type, "cursor_default.png")
            icon_path = os.path.join(icon_dir, icon_file)
            
            # 检查图标是否存在，如不存在则创建默认图标
            if not os.path.exists(icon_path):
                logger.warning(f"未找到图标文件: {icon_path}，创建默认图标")
                self._create_default_icon(icon_path, icon_type)
            
            # 加载图标
            img = Image.open(icon_path)
            self.tk_img = ImageTk.PhotoImage(img)
            
        except Exception as e:
            logger.error(f"加载指示器图标失败: {e}")
            self._create_default_icon_memory(icon_type)
    
    def _create_default_icon_memory(self, icon_type):
        """在内存中创建默认图标"""
        size = 24
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # 根据类型设置颜色
        colors = {
            "default": (0, 120, 215),  # 蓝色
            "on": (0, 180, 0),         # 绿色
            "off": (220, 0, 0)         # 红色
        }
        color = colors.get(icon_type, (0, 120, 215))
        
        # 创建简单图标
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.ellipse([(2, 2), (size-2, size-2)], fill=color)
        
        self.tk_img = ImageTk.PhotoImage(img)
    
    def _create_default_icon(self, save_path, icon_type):
        """创建并保存默认图标"""
        size = 24
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        # 根据类型设置颜色
        colors = {
            "default": (0, 120, 215),  # 蓝色
            "on": (0, 180, 0),         # 绿色
            "off": (220, 0, 0)         # 红色
        }
        color = colors.get(icon_type, (0, 120, 215))
        
        # 创建简单图标
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.ellipse([(2, 2), (size-2, size-2)], fill=color)
        
        # 保存图标
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img.save(save_path)
            logger.info(f"已创建并保存默认图标: {save_path}")
        except Exception as e:
            logger.error(f"保存默认图标失败: {e}")
            
