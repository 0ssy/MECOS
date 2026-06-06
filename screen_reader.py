from __future__ import annotations

from typing import Optional

from loguru import logger

try:
    import mss
except Exception:  # pragma: no cover - optional runtime dependency
    mss = None

try:
    import pytesseract
except Exception:  # pragma: no cover - optional runtime dependency
    pytesseract = None

from PIL import Image

try:
    from pywinauto import Desktop

    PYWINAUTO_AVAILABLE = True
except Exception:
    PYWINAUTO_AVAILABLE = False


class ScreenReader:
    """
    Captures screenshots and reads visible text with OCR.
    """

    def _check_available(self) -> bool:
        if mss is None:
            logger.warning("mss is not installed; screen capture disabled.")
            return False
        if pytesseract is None:
            logger.warning("pytesseract is not installed; OCR disabled.")
            return False
        return True

    def capture_screen(self, monitor: int = 1) -> Image.Image:
        if mss is None:
            raise RuntimeError("mss is required for screen capture.")
        with mss.mss() as sct:
            target_monitor = sct.monitors[max(1, int(monitor))]
            screenshot = sct.grab(target_monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def read_text_from_screen(self, region: Optional[dict] = None) -> str:
        if not self._check_available():
            return ""
        with mss.mss() as sct:
            area = region or sct.monitors[1]
            screenshot = sct.grab(area)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return str(pytesseract.image_to_string(img))

    def read_active_window(self) -> str:
        if not PYWINAUTO_AVAILABLE:
            return ""
        try:
            active = Desktop(backend="uia").active()
            rect = active.rectangle()
            region = {
                "top": rect.top,
                "left": rect.left,
                "width": rect.width(),
                "height": rect.height(),
            }
            return self.read_text_from_screen(region)
        except Exception as e:
            logger.warning("Active window read failed: {}", e)
            return ""

    def find_text_on_screen(self, target_text: str) -> bool:
        screen_text = self.read_text_from_screen()
        if not screen_text:
            return False
        return target_text.lower() in screen_text.lower()

