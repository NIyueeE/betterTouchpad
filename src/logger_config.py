import logging

def configure_logger():
    """
    配置日志记录器
    设置日志级别和格式，返回配置好的logger实例
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)