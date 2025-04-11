# touchpad-control/main.py
import platform
import logging
from config.logging import configure_logging
from core.factory import create_controller
from core.event_handler import EventHandler

def main():
    configure_logging()
    controller = create_controller()
    handler = EventHandler(controller)
    handler.run()

if __name__ == "__main__":
    main()