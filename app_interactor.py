from __future__ import annotations

from typing import Any, Optional

from loguru import logger

try:
    from pywinauto import Desktop

    PYWINAUTO_AVAILABLE = True
except Exception:
    PYWINAUTO_AVAILABLE = False
    Desktop = None


class AppInteractor:
    """
    Interacts with desktop applications using pywinauto (UIA backend).
    """

    def _find_window(self, app_name: str):
        if not PYWINAUTO_AVAILABLE:
            return None
        app_name_lower = app_name.lower().strip()
        if not app_name_lower:
            return None
        desktop = Desktop(backend="uia")
        windows = [
            w for w in desktop.windows()
            if app_name_lower in (w.window_text() or "").lower()
        ]
        if not windows:
            return None
        return windows[0]

    def click_button(self, app_name: str, button_text: str) -> bool:
        try:
            window = self._find_window(app_name)
            if window is None:
                return False
            btn = window.child_window(title=button_text, control_type="Button")
            btn.click_input()
            return True
        except Exception as e:
            logger.warning("Click failed: %s", e)
            return False

    def type_in_app(self, app_name: str, text: str, field_name: Optional[str] = None) -> bool:
        try:
            window = self._find_window(app_name)
            if window is None:
                return False
            if field_name:
                field = window.child_window(title=field_name, control_type="Edit")
                field.type_keys(text, with_spaces=True, set_foreground=True)
            else:
                window.type_keys(text, with_spaces=True, set_foreground=True)
            return True
        except Exception as e:
            logger.warning("Type failed: %s", e)
            return False

    def click_menu(self, app_name: str, menu_path: list[str]) -> bool:
        try:
            window = self._find_window(app_name)
            if window is None:
                return False
            menu = window.menu()
            item = menu.item_by_path("->".join(menu_path))
            item.click_input()
            return True
        except Exception as e:
            logger.warning("Menu click failed: %s", e)
            return False

    def get_app_state(self, app_name: str) -> dict[str, Any]:
        try:
            window = self._find_window(app_name)
            if window is None:
                return {}

            state: dict[str, Any] = {"title": window.window_text(), "fields": {}}
            for ctrl in window.descendants(control_type="Edit"):
                try:
                    name = ctrl.window_text() or ctrl.automation_id() or "field"
                    value = ""
                    try:
                        value = ctrl.get_value()
                    except Exception:
                        try:
                            texts = ctrl.texts()
                            value = texts[0] if texts else ""
                        except Exception:
                            value = ""
                    state["fields"][name] = value
                except Exception:
                    continue
            return state
        except Exception as e:
            return {"error": str(e)}

