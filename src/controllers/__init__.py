import platform

def create_controller():
    """
    创建触控板控制器
    根据当前操作系统创建并返回对应的控制器实例
    
    返回:
        TouchpadController: 适用于当前操作系统的触控板控制器实例
        
    异常:
        NotImplementedError: 如果当前平台不支持
    """
    system = platform.system()
    if system == "Windows":
        from controllers.windows import WindowsTouchpadController
        return WindowsTouchpadController()
    elif system == "Linux":
        from controllers.linux import LinuxTouchpadController
        return LinuxTouchpadController()
    else:
        raise NotImplementedError(f"不支持的平台: {system}")