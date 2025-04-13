from pynput import mouse
import logging

logger = logging.getLogger(__name__)

class TouchpadController:
    """
    触控板控制器基类
    定义所有触控板控制器必须实现的接口
    """
    def __init__(self):
        """初始化控制器并创建鼠标控制器实例"""
        self.mouse = mouse.Controller()
    
    def toggle(self, enable):
        """
        切换触控板状态
        子类必须实现此方法
        """
        raise NotImplementedError
    
    def cleanup(self):
        """
        清理资源
        在程序退出前调用
        """
        pass

    def create_dummy_window(self):
        """
        创建虚拟窗口
        部分平台需要实现此方法以支持全局事件捕获
        """
        raise NotImplementedError