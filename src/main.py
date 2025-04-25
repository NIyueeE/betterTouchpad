from .touchpad_controller import TouchpadController

if __name__ == "__main__":
    """
    程序入口点
    创建并运行事件处理器
    """
    controller = TouchpadController()
    controller.run()