import threading
import os
import pystray
import platform
import time
from PIL import Image, ImageDraw
from configure_logger import configure_logger
from path_resolver import get_resource_path, get_application_path

# Linux系统下设置pystray使用AppIndicator后端
if platform.system() == 'Linux':
    import gi
    gi.require_version('AppIndicator3', '0.1')
    os.environ['PYSTRAY_BACKEND'] = 'appindicator'
    
    # 修复DBus通知问题
    try:
        import pystray._util.notify_dbus
        
        # 创建一个空的通知处理类以替代默认的DBus通知功能
        class DummyNotifier:
            """空通知器类，用于替代Linux下默认的DBus通知器，解决通知相关问题"""
            def __init__(self):
                """初始化空通知器"""
                pass
                
            def notify(self, message, title):
                """空通知方法，忽略所有通知"""
                pass
                
            def hide(self):
                """隐藏通知方法"""
                pass

            def close(self):
                """关闭通知方法"""
                pass
                
        # 替换原有的通知器
        pystray._util.notify_dbus.Notifier = DummyNotifier
        
    except ImportError:
        pass

# 初始化日志记录器
logger = configure_logger()

class SystemTrayController:
    """
    系统托盘管理类
    
    负责创建和管理系统托盘图标和菜单，并与主程序通过命令队列进行通信。
    提供触控板状态反馈和用户交互功能。
    """
    def __init__(self, controller, command_queue):
        """
        初始化系统托盘管理器
        
        参数:
            controller: 触控板控制器对象
            command_queue: 用于跨线程通信的命令队列
        """
        self.controller = controller
        self.command_queue = command_queue
        self.tray_icon = None
        self.tray_thread = None
        self.touchpad_active = False
    
    def start(self):
        """启动系统托盘图标（在后台线程中）"""
        self.tray_thread = threading.Thread(target=self._start_tray_icon, daemon=True)
        self.tray_thread.start()
        logger.info("系统托盘图标线程已启动")
    
    def stop(self):
        """停止系统托盘图标"""
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as e:
                logger.error(f"停止系统托盘图标失败: {e}")
    
    def update_touchpad_status(self, is_active):
        """
        更新触控板状态并刷新图标显示
        
        参数:
            is_active (bool): 触控板是否激活
        """
        self.touchpad_active = is_active
        self._update_tray_icon()
    
    def _start_tray_icon(self):
        """在独立线程中创建并运行系统托盘图标"""
        self.tray_icon = self._create_tray_icon()
        self._update_tray_icon()  # 初始化图标状态
        self.tray_icon.run()

    def _create_tray_icon(self):
        """
        创建系统托盘图标及其菜单
        
        返回:
            pystray.Icon: 创建的系统托盘图标对象
        """
        # 使用path_resolver获取图标路径
        icon_path = get_resource_path('default.png')
        
        # 获取图标图像
        icon_image = None
        if icon_path and os.path.exists(icon_path):
            try:
                icon_image = Image.open(icon_path)
            except Exception as e:
                logger.error(f"加载图标失败: {e}")
                icon_image = None
        
        # 如果图标不存在或加载失败，创建默认图标
        if not icon_image:
            icon_image = self._create_default_icon()
            try:
                # 获取应用程序路径，用于保存默认图标
                app_path = get_application_path()
                resources_dir = os.path.join(app_path, 'resources')
                os.makedirs(resources_dir, exist_ok=True)
                save_path = os.path.join(resources_dir, 'default.png')
                icon_image.save(save_path)
                logger.info(f"创建默认图标: {save_path}")
            except Exception as e:
                logger.error(f"保存默认图标失败: {e}")
        
        # 创建图标菜单
        if platform.system() == 'Windows':
            menu = (
                pystray.MenuItem('切换模式', self._toggle_mode),
                pystray.MenuItem('设置', self._open_settings),
                pystray.MenuItem('刷新配置', self._reload_config),
                pystray.MenuItem('退出', self._exit_app),
            )
        elif platform.system() == 'Linux':
            menu = (
                pystray.MenuItem('切换模式', self._toggle_mode),
                pystray.MenuItem('刷新配置', self._reload_config),
                pystray.MenuItem('退出', self._exit_app),
            )
            
        # 创建系统托盘图标
        try:
            return pystray.Icon(
                'betterTouchpad',
                icon_image,
                'Better Touchpad',
                menu
            )
        except Exception as e:
            logger.error(f"创建系统托盘图标失败: {e}")
            # 创建一个备用图标（纯色图标）
            backup_image = Image.new('RGB', (64, 64), color=(0, 120, 212))
            return pystray.Icon(
                'betterTouchpad',
                backup_image,
                'Better Touchpad',
                menu
            )
    
    def _update_tray_icon(self):
        """根据触控板状态更新系统托盘图标"""
        if not self.tray_icon:
            return
            
        try:
            # 根据触控板状态选择图标
            icon_name = 'on.png' if self.touchpad_active else 'off.png'
            icon_path = get_resource_path(icon_name)
            
            # 检查图标是否存在
            if not icon_path or not os.path.exists(icon_path):
                logger.warning(f"状态图标文件不存在: {icon_name}")
                return
                
            # 加载图标并更新
            icon_image = Image.open(icon_path)
            self.tray_icon.icon = icon_image
            logger.info(f"已更新系统托盘图标为: {icon_name}")
            
        except Exception as e:
            logger.error(f"更新系统托盘图标失败: {e}")
    
    def _create_default_icon(self):
        """
        创建默认图标（蓝色圆形触控板图标）
        
        返回:
            Image: PIL图像对象
        """
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 主圆形（触控板）
        draw.ellipse([(4, 4), (60, 60)], fill=(0, 120, 212), outline=(255, 255, 255, 128), width=2)
        
        # 中心触控点
        draw.ellipse([(28, 28), (36, 36)], fill=(255, 255, 255))
        
        return image
    
    # ----------------------- 菜单事件处理 -----------------------
    
    def _toggle_mode(self, icon, item):
        """切换触控板操作模式"""
        self.command_queue.put(('toggle_mode', None))
    
    def _open_settings(self, icon, item):
        """打开设置窗口"""
        logger.info("打开设置窗口请求")
        self.command_queue.put(('open_settings', None))
    
    def _reload_config(self, icon, item):
        """重新加载配置"""
        self.command_queue.put(('reload_config', None))
    
    def _exit_app(self, icon, item):
        """退出应用程序"""
        logger.info("用户从系统托盘退出应用")
        try:
            icon.stop()
        except Exception as e:
            logger.error(f"停止系统托盘图标失败: {e}")
            
        self.command_queue.put(('exit', None)) 