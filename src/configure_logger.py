import logging

def configure_logger():
    """
    配置日志记录器
    设置日志级别和格式，返回配置好的logger实例
    
    返回:
        logging.Logger: 配置好的日志记录器
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)