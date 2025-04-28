from src.touchpad_controller import TouchpadController

if __name__ == "__main__":
    """
    程序入口点
    用于pyinstaller打包
    """
    controller = TouchpadController()
    controller.run()