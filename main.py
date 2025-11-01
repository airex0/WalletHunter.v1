# main.py (v9.0 - Final)

import flet as ft
from ui.views import MainView, SettingsView
from core.state import AppState
from database import initialize_database
from loguru import logger
from config.app_config import LOG_FILE_PATH

def setup_logging():
    logger.add(
        LOG_FILE_PATH, level="INFO", rotation="10 MB", retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
    )

def main(page: ft.Page):
    page.title = "WalletHunter Elite"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1200
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 700

    app_state = AppState(page)

    def on_window_event(e):
        if e.data == "close":
            logger.info("Window close event received. Shutting down...")
            app_state.is_running_app = False
            if app_state.engine and app_state.is_running:
                app_state.engine.stop_scan()
            if app_state.sys_monitor:
                app_state.sys_monitor.stop()
            app_state.db_queue.put((None, None))
            page.window_destroy()

    page.on_window_event = on_window_event

    def route_change(route):
        page.views.clear()
        if page.route == "/settings":
            page.views.append(SettingsView(app_state, page.go))
        else:
            page.views.append(MainView(app_state, page.go))
        page.update()

    page.on_route_change = route_change
    page.go("/")

if __name__ == "__main__":
    setup_logging()
    logger.info("Starting WalletHunter Elite application...")

    try:
        initialize_database()
    except Exception as e:
        logger.critical(f"Database initialization failed. Cannot start: {e}")
        exit(1)

    ft.app(target=main)