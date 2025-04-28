import os
import sys
import logging

logger = logging.getLogger(__name__)

def get_application_path():
    """
    获取应用程序根目录路径
    
    如果是PyInstaller打包的应用，返回exe所在目录
    如果是开发环境，返回源代码目录
    
    返回:
        str: 应用程序根目录路径
    """
    if getattr(sys, 'frozen', False):
        # 当前是PyInstaller打包的应用
        return os.path.dirname(sys.executable)
    else:
        # 当前是开发环境
        return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    """
    获取资源文件的完整路径
    
    Args:
        relative_path (str): 相对于resources目录的文件路径
    
    Returns:
        str: 资源文件的完整路径
    """
    app_path = get_application_path()
    
    # 首先检查外部resources目录
    external_resource_path = os.path.join(app_path, 'resources', relative_path)
    if os.path.exists(external_resource_path):
        return external_resource_path
    
    # 如果外部不存在，则检查源代码目录
    src_resource_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', relative_path)
    if os.path.exists(src_resource_path):
        return src_resource_path
    
    logger.warning(f"资源文件未找到: {relative_path}")
    return None

def get_config_path():
    """
    获取配置文件的完整路径
    
    Returns:
        str: 配置文件的完整路径
    """
    app_path = get_application_path()
    
    # 首先检查外部配置文件
    external_config_path = os.path.join(app_path, 'configure.json')
    if os.path.exists(external_config_path):
        return external_config_path
    
    # 如果外部不存在，则使用源代码目录中的配置文件
    src_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configure.json')
    if os.path.exists(src_config_path):
        return src_config_path
    
    logger.warning("配置文件未找到，将使用默认配置")
    return None 