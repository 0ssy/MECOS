"""
MECOS App Perception
=====================
Dynamically learns every application and file type on the system.
Nothing is hardcoded. MECOS discovers, observes, and builds schemas
for every app it finds — using accessibility APIs, process inspection,
file association registries, and web perception.

No app is pre-defined. MECOS learns each one from scratch.
"""

import asyncio
import json
import os
import re
import struct
import winreg
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil
from loguru import logger

# ------------------------------------------------------------------ #
#  Optional imports — graceful degradation if not installed           #
# ------------------------------------------------------------------ #
try:
    import pywinauto
    from pywinauto import Desktop
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False
    logger.warning("pywinauto not installed — UI observation disabled. Run: pip install pywinauto")

try:
    import comtypes.client
    COMTYPES_AVAILABLE = True
except ImportError:
    COMTYPES_AVAILABLE = False


class AppSchema:
    """
    Everything MECOS knows about a single application.
    Built up over time through observation — not hardcoded.
    """

    def __init__(self, name: str, exe_path: str):
        self.name          = name
        self.exe_path      = exe_path
        self.display_name  = ""
        self.description   = ""
        self.version       = ""
        self.publisher     = ""
        self.file_types    = []       # extensions this app handles
        self.ui_elements   = []       # observed UI controls
        self.menu_items    = []       # discovered menu structure
        self.capabilities  = []       # what MECOS thinks this app can do
        self.web_knowledge = ""       # from web perception
        self.icon_path     = ""
        self.install_dir   = ""
        self.last_observed = ""
        self.observation_count = 0

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> "AppSchema":
        schema = cls(data.get("name", ""), data.get("exe_path", ""))
        for k, v in data.items():
            setattr(schema, k, v)
        return schema


class FileTypeSchema:
    """Everything MECOS knows about a file type."""

    def __init__(self, extension: str):
        self.extension    = extension
        self.mime_type    = ""
        self.description  = ""
        self.default_app  = ""
        self.all_apps     = []        # all apps that can open this type
        self.category     = ""        # document, image, audio, code, data, etc.
        self.can_read     = False
        self.can_write    = False
        self.web_knowledge = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class SystemPerceptionMemory:
    """
    Persists everything MECOS learns about apps and file types.
    Stored as JSON — grows over time as MECOS observes more.
    """

    SCHEMA_FILE = Path("mecos_system_perception.json")

    def __init__(self):
        self.apps: dict[str, AppSchema]       = {}
        self.file_types: dict[str, FileTypeSchema] = {}
        self._load()

    def _load(self):
        if self.SCHEMA_FILE.exists():
            try:
                data = json.loads(self.SCHEMA_FILE.read_text(encoding="utf-8"))
                for name, app_data in data.get("apps", {}).items():
                    self.apps[name] = AppSchema.from_dict(app_data)
                for ext, ft_data in data.get("file_types", {}).items():
                    ft = FileTypeSchema(ext)
                    for k, v in ft_data.items():
                        setattr(ft, k, v)
                    self.file_types[ext] = ft
                logger.info(
                    "Loaded perception memory: {} apps, {} file types",
                    len(self.apps), len(self.file_types)
                )
            except Exception as e:
                logger.warning("Could not load perception memory: {}", e)

    def save(self):
        data = {
            "apps":       {name: schema.to_dict() for name, schema in self.apps.items()},
            "file_types": {ext: ft.to_dict() for ext, ft in self.file_types.items()},
            "last_saved": datetime.utcnow().isoformat(),
        }
        self.SCHEMA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_app(self, name: str) -> Optional[AppSchema]:
        return self.apps.get(name.lower())

    def set_app(self, schema: AppSchema):
        self.apps[schema.name.lower()] = schema

    def get_file_type(self, ext: str) -> Optional[FileTypeSchema]:
        return self.file_types.get(ext.lower().lstrip("."))

    def set_file_type(self, ft: FileTypeSchema):
        self.file_types[ft.extension.lower().lstrip(".")] = ft


class SystemScanner:
    """
    Scans the system to discover all installed applications
    and file type associations — no hardcoding.
    """

    def scan_installed_apps(self) -> list[dict]:
        """
        Discover all installed applications on Windows.
        Uses multiple sources: registry, Program Files, Start Menu.
        """
        apps = {}

        # Source 1: Windows registry (most complete)
        if os.name == "nt":
            apps.update(self._scan_registry())

        # Source 2: Program Files directories
        apps.update(self._scan_program_files())

        # Source 3: Running processes (currently active apps)
        apps.update(self._scan_running_processes())

        # Source 4: Start Menu shortcuts
        if os.name == "nt":
            apps.update(self._scan_start_menu())

        logger.info("System scan found {} unique applications", len(apps))
        return list(apps.values())

    def _scan_registry(self) -> dict:
        """Read Windows registry for installed software."""
        apps = {}
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, path in registry_paths:
            try:
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey      = winreg.OpenKey(key, subkey_name)
                        info        = {}
                        for field in ["DisplayName", "DisplayIcon", "InstallLocation",
                                      "Publisher", "DisplayVersion", "UninstallString"]:
                            try:
                                info[field] = winreg.QueryValueEx(subkey, field)[0]
                            except Exception:
                                pass
                        if info.get("DisplayName"):
                            name = info["DisplayName"].strip()
                            exe  = self._find_exe_from_registry_info(info)
                            apps[name.lower()] = {
                                "name":        name,
                                "exe_path":    exe,
                                "publisher":   info.get("Publisher", ""),
                                "version":     info.get("DisplayVersion", ""),
                                "install_dir": info.get("InstallLocation", ""),
                                "source":      "registry",
                            }
                    except Exception:
                        continue
            except Exception:
                continue

        return apps

    def _find_exe_from_registry_info(self, info: dict) -> str:
        """Extract the main executable path from registry info."""
        # Try DisplayIcon first (often points to the main exe)
        icon = info.get("DisplayIcon", "")
        if icon:
            # Strip icon index (e.g. "C:\path\app.exe,0" -> "C:\path\app.exe")
            exe_path = icon.split(",")[0].strip().strip('"')
            if exe_path.lower().endswith(".exe") and Path(exe_path).exists():
                return exe_path

        # Try InstallLocation
        install_dir = info.get("InstallLocation", "").strip().strip('"')
        if install_dir and Path(install_dir).exists():
            # Find exe files in install directory
            try:
                exes = list(Path(install_dir).glob("*.exe"))
                if exes:
                    return str(exes[0])
            except Exception:
                pass

        return ""

    def _scan_program_files(self) -> dict:
        """Scan Program Files directories for executables."""
        apps = {}
        dirs = []

        if os.name == "nt":
            for env_var in ["ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"]:
                d = os.environ.get(env_var, "")
                if d:
                    dirs.append(Path(d))
        else:
            dirs = [Path("/usr/bin"), Path("/usr/local/bin"), Path("/opt")]

        for base in dirs:
            if not base.exists():
                continue
            try:
                # Look one level deep — each subdirectory is likely one app
                for app_dir in base.iterdir():
                    if not app_dir.is_dir():
                        continue
                    exes = list(app_dir.glob("*.exe")) if os.name == "nt" else []
                    if not exes:
                        continue
                    # Pick the exe that matches the directory name most closely
                    best_exe = self._best_exe(app_dir.name, exes)
                    if best_exe:
                        name = app_dir.name
                        apps[name.lower()] = {
                            "name":        name,
                            "exe_path":    str(best_exe),
                            "install_dir": str(app_dir),
                            "source":      "program_files",
                        }
            except Exception:
                continue

        return apps

    def _best_exe(self, app_name: str, exes: list) -> Optional[Path]:
        """Pick the most likely main executable from a list."""
        name_lower = app_name.lower()
        # Prefer an exe whose name closely matches the directory
        for exe in exes:
            if name_lower in exe.stem.lower() or exe.stem.lower() in name_lower:
                return exe
        # Fall back to largest exe (usually the main one)
        return max(exes, key=lambda e: e.stat().st_size, default=None)

    def _scan_running_processes(self) -> dict:
        """Get currently running applications."""
        apps = {}
        for proc in psutil.process_iter(["name", "exe", "pid"]):
            try:
                exe = proc.info.get("exe") or ""
                name = proc.info.get("name") or ""
                if exe and name and not name.lower().startswith("svchost"):
                    apps[name.lower()] = {
                        "name":     name,
                        "exe_path": exe,
                        "pid":      proc.info.get("pid"),
                        "source":   "running_process",
                    }
            except Exception:
                continue
        return apps

    def _scan_start_menu(self) -> dict:
        """Scan Start Menu for application shortcuts."""
        apps = {}
        start_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]

        for start_dir in start_dirs:
            if not start_dir.exists():
                continue
            try:
                for lnk in start_dir.rglob("*.lnk"):
                    try:
                        target = self._resolve_lnk(lnk)
                        if target and target.lower().endswith(".exe"):
                            name = lnk.stem
                            apps[name.lower()] = {
                                "name":     name,
                                "exe_path": target,
                                "source":   "start_menu",
                            }
                    except Exception:
                        continue
            except Exception:
                continue

        return apps

    def _resolve_lnk(self, lnk_path: Path) -> str:
        """Resolve a Windows .lnk shortcut to its target path."""
        try:
            # Read .lnk file header to extract target path
            data = lnk_path.read_bytes()
            # Target path starts at offset 0x4C if it's a local file link
            if len(data) > 0x4C and data[:4] == b'L\x00\x00\x00':
                # Simple extraction — look for .exe path in binary
                text = data.decode("utf-16-le", errors="ignore")
                for match in re.finditer(r'[A-Za-z]:\\[^\x00]+\.exe', text):
                    path = match.group(0).rstrip('\x00')
                    if Path(path).exists():
                        return path
        except Exception:
            pass
        return ""

    def scan_file_associations(self) -> dict[str, dict]:
        """
        Discover file type associations from the Windows registry.
        Returns {extension: {description, default_app, mime_type, ...}}
        """
        associations = {}

        if os.name != "nt":
            return associations

        try:
            # HKEY_CLASSES_ROOT contains all file associations
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
            for i in range(min(winreg.QueryInfoKey(key)[0], 5000)):
                try:
                    ext = winreg.EnumKey(key, i)
                    if not ext.startswith("."):
                        continue

                    ext_key  = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext)
                    try:
                        prog_id = winreg.QueryValue(ext_key, "")
                    except Exception:
                        prog_id = ""

                    # Get MIME type
                    mime = ""
                    try:
                        mime = winreg.QueryValueEx(ext_key, "Content Type")[0]
                    except Exception:
                        pass

                    # Get description and default app from ProgID
                    description = ""
                    default_app = ""
                    if prog_id:
                        try:
                            prog_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id)
                            description = winreg.QueryValue(prog_key, "") or ""
                            # Find open command
                            cmd_key = winreg.OpenKey(
                                winreg.HKEY_CLASSES_ROOT,
                                f"{prog_id}\\shell\\open\\command"
                            )
                            cmd = winreg.QueryValue(cmd_key, "") or ""
                            # Extract exe path from command
                            match = re.search(r'"?([A-Za-z]:\\[^"]+\.exe)"?', cmd)
                            if match:
                                default_app = match.group(1)
                        except Exception:
                            pass

                    associations[ext.lower()] = {
                        "extension":   ext.lower(),
                        "prog_id":     prog_id,
                        "mime_type":   mime,
                        "description": description,
                        "default_app": default_app,
                    }
                except Exception:
                    continue
        except Exception as e:
            logger.warning("File association scan failed: {}", e)

        logger.info("Scanned {} file type associations", len(associations))
        return associations


class UIObserver:
    """
    Observes running application UIs using the Windows
    Accessibility API (UIA) via pywinauto.

    Learns UI structure — menus, buttons, panels, controls —
    without any hardcoding.
    """

    def observe_window(self, app_name: str) -> dict:
        """
        Observe the UI of a currently running application.
        Returns a schema of all discovered UI elements.
        """
        if not PYWINAUTO_AVAILABLE:
            return {"error": "pywinauto not available"}

        try:
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            # Find windows matching this app
            target_windows = [
                w for w in windows
                if app_name.lower() in (w.window_text() or "").lower()
                or app_name.lower() in (w.class_name() or "").lower()
            ]

            if not target_windows:
                return {"error": f"No window found for {app_name}"}

            window = target_windows[0]
            schema = {
                "title":       window.window_text(),
                "class_name":  window.class_name(),
                "controls":    [],
                "menus":       [],
                "observed_at": datetime.utcnow().isoformat(),
            }

            # Walk the control tree
            schema["controls"] = self._walk_controls(window, depth=0, max_depth=4)

            # Try to read menu structure
            schema["menus"] = self._read_menus(window)

            return schema

        except Exception as e:
            logger.warning("UI observation failed for {}: {}", app_name, e)
            return {"error": str(e)}

    def _walk_controls(self, parent, depth: int, max_depth: int) -> list:
        """Recursively walk UI control tree."""
        if depth >= max_depth:
            return []

        controls = []
        try:
            for child in parent.children():
                try:
                    control = {
                        "type":       child.friendly_class_name(),
                        "text":       (child.window_text() or "")[:100],
                        "enabled":    child.is_enabled(),
                        "visible":    child.is_visible(),
                        "children":   self._walk_controls(child, depth + 1, max_depth),
                    }
                    # Only include meaningful controls
                    if control["text"] or control["type"] not in ("Static", ""):
                        controls.append(control)
                except Exception:
                    continue
        except Exception:
            pass

        return controls[:50]  # cap at 50 per level

    def _read_menus(self, window) -> list:
        """Try to read the menu bar structure."""
        menus = []
        try:
            menu = window.menu()
            if menu:
                for item in menu.items():
                    try:
                        menu_entry = {
                            "text":     item.text(),
                            "enabled":  item.is_enabled(),
                            "children": [],
                        }
                        # Try to read submenu
                        try:
                            sub = item.sub_menu()
                            if sub:
                                for sub_item in sub.items():
                                    menu_entry["children"].append({
                                        "text":    sub_item.text(),
                                        "enabled": sub_item.is_enabled(),
                                    })
                        except Exception:
                            pass
                        menus.append(menu_entry)
                    except Exception:
                        continue
        except Exception:
            pass
        return menus

    def get_open_windows(self) -> list[dict]:
        """Get all currently open application windows."""
        if not PYWINAUTO_AVAILABLE:
            return []

        windows = []
        try:
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    title = w.window_text() or ""
                    if title and title not in ("", "Default IME", "MSCTFIME UI"):
                        windows.append({
                            "title":      title,
                            "class_name": w.class_name() or "",
                            "pid":        w.process_id(),
                            "visible":    w.is_visible(),
                        })
                except Exception:
                    continue
        except Exception as e:
            logger.warning("Could not enumerate windows: {}", e)

        return windows


class AppKnowledgeBuilder:
    """
    Builds deep knowledge about each discovered application
    by combining system data + UI observation + web perception.
    """

    # Categories for capability inference
    CAPABILITY_KEYWORDS = {
        "code_editor":    ["code", "editor", "ide", "develop", "debug", "syntax"],
        "browser":        ["browser", "chrome", "firefox", "edge", "web", "http"],
        "media_player":   ["player", "video", "audio", "music", "media", "vlc"],
        "office":         ["word", "excel", "powerpoint", "office", "document", "spreadsheet"],
        "terminal":       ["terminal", "cmd", "powershell", "console", "shell", "bash"],
        "file_manager":   ["explorer", "finder", "files", "folder", "manager"],
        "communication":  ["slack", "teams", "discord", "zoom", "mail", "chat", "skype"],
        "design":         ["photoshop", "illustrator", "figma", "design", "image", "draw"],
        "database":       ["sql", "database", "mysql", "postgres", "mongodb", "db"],
        "security":       ["antivirus", "firewall", "vpn", "security", "protect"],
        "finance":        ["trading", "broker", "finance", "market", "stock", "crypto"],
        "productivity":   ["todo", "notes", "calendar", "task", "notion", "obsidian"],
    }

    FILE_CATEGORIES = {
        "code":       [".py", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".go", ".rs",
                       ".php", ".rb", ".swift", ".kt", ".html", ".css", ".sql"],
        "document":   [".pdf", ".doc", ".docx", ".txt", ".md", ".odt", ".rtf", ".tex"],
        "spreadsheet":[".xlsx", ".xls", ".csv", ".ods"],
        "image":      [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico"],
        "audio":      [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
        "video":      [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
        "archive":    [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
        "data":       [".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"],
        "executable": [".exe", ".msi", ".bat", ".sh", ".cmd", ".ps1"],
        "font":       [".ttf", ".otf", ".woff", ".woff2"],
        "3d":         [".obj", ".fbx", ".stl", ".blend", ".3ds"],
        "database":   [".db", ".sqlite", ".mdb", ".accdb"],
    }

    def infer_capabilities(self, app: AppSchema) -> list[str]:
        """Infer what an app can do from its name, path, and UI."""
        caps = []
        search_text = (
            f"{app.name} {app.exe_path} {app.description} "
            f"{' '.join(app.menu_items)} {' '.join(str(e) for e in app.ui_elements)}"
        ).lower()

        for capability, keywords in self.CAPABILITY_KEYWORDS.items():
            if any(kw in search_text for kw in keywords):
                caps.append(capability)

        return caps

    def categorise_file_type(self, extension: str) -> str:
        """Determine the category of a file type."""
        ext = extension.lower().lstrip(".")
        for category, extensions in self.FILE_CATEGORIES.items():
            if f".{ext}" in extensions or ext in [e.lstrip(".") for e in extensions]:
                return category
        return "unknown"

    async def build_web_knowledge(self, app_name: str) -> str:
        """
        Search the web for information about this application.
        Uses free search — no API key.
        """
        try:
            from free_search import free_search
            results = free_search(f"{app_name} application features how to use", max_total=3)
            if results:
                snippets = [f"{r.title}: {r.snippet[:200]}" for r in results[:3]]
                return " | ".join(snippets)
        except ImportError:
            pass
        except Exception as e:
            logger.warning("Web knowledge build failed for {}: {}", app_name, e)
        return ""


class AppPerception:
    """
    Main perception class — learns every app and file type
    on the system dynamically.

    Usage:
        perception = AppPerception(memory_system, app_controller)
        await perception.scan_and_learn_system()     # full scan
        await perception.observe_app("chrome")       # observe specific app
        schema = perception.get_app_schema("chrome") # retrieve what we know
    """

    def __init__(self, memory_system=None, controller=None):
        self.memory     = memory_system
        self.controller = controller
        self.store      = SystemPerceptionMemory()
        self.scanner    = SystemScanner()
        self.ui_obs     = UIObserver()
        self.builder    = AppKnowledgeBuilder()

    # ------------------------------------------------------------------ #
    #  Main learning cycle                                                 #
    # ------------------------------------------------------------------ #

    async def scan_and_learn_system(self, learn_web: bool = False):
        """
        Full system scan. Discovers all apps and file types,
        builds initial schemas, optionally enriches with web knowledge.
        """
        logger.info("Starting full system perception scan...")

        # Step 1: Discover all apps
        raw_apps = self.scanner.scan_installed_apps()
        logger.info("Discovered {} applications", len(raw_apps))

        # Step 2: Build schemas for each app
        new_count = 0
        for app_data in raw_apps:
            name = app_data.get("name", "").strip()
            if not name:
                continue

            # Don't overwrite existing rich schemas
            existing = self.store.get_app(name)
            if existing and existing.observation_count > 2:
                continue

            schema = AppSchema(name=name, exe_path=app_data.get("exe_path", ""))
            schema.publisher   = app_data.get("publisher", "")
            schema.version     = app_data.get("version", "")
            schema.install_dir = app_data.get("install_dir", "")

            # Infer capabilities from name and path
            schema.capabilities = self.builder.infer_capabilities(schema)
            schema.last_observed = datetime.utcnow().isoformat()
            schema.observation_count = 1

            # Optionally enrich with web knowledge (slower)
            if learn_web:
                schema.web_knowledge = await self.builder.build_web_knowledge(name)
                await asyncio.sleep(1)  # polite delay

            self.store.set_app(schema)
            new_count += 1

        # Step 3: Scan file associations
        await self._scan_file_types()

        # Step 4: Save everything
        self.store.save()

        logger.info(
            "System scan complete: {} apps learned ({} new), {} file types",
            len(self.store.apps), new_count, len(self.store.file_types)
        )

        # Step 5: Store in MECOS memory if available
        if self.memory:
            await self.memory.add_experience(
                content=f"SYSTEM SCAN [{datetime.now().isoformat()}]: "
                        f"Learned {len(self.store.apps)} apps, "
                        f"{len(self.store.file_types)} file types.",
                source="app_perception",
            )

        return {
            "apps_total":    len(self.store.apps),
            "apps_new":      new_count,
            "file_types":    len(self.store.file_types),
        }

    async def observe_app(self, app_name: str, use_web: bool = True) -> AppSchema:
        """
        Deep observation of a specific app — UI structure,
        menu items, capabilities, web knowledge.
        Called when MECOS needs to interact with an app.
        """
        logger.info("Observing app: {}", app_name)

        # Get or create schema
        schema = self.store.get_app(app_name) or AppSchema(name=app_name, exe_path="")

        # Observe UI if app is running
        open_windows = self.ui_obs.get_open_windows()
        matching = [w for w in open_windows if app_name.lower() in w["title"].lower()]

        if matching:
            ui_schema = self.ui_obs.observe_window(app_name)
            if "error" not in ui_schema:
                schema.ui_elements = ui_schema.get("controls", [])
                schema.menu_items  = [
                    m["text"] for m in ui_schema.get("menus", []) if m.get("text")
                ]
                schema.capabilities = self.builder.infer_capabilities(schema)
                logger.info(
                    "UI observed for %s: %d controls, %d menus",
                    app_name, len(schema.ui_elements), len(schema.menu_items)
                )

        # Web knowledge
        if use_web and not schema.web_knowledge:
            schema.web_knowledge = await self.builder.build_web_knowledge(app_name)

        schema.last_observed = datetime.utcnow().isoformat()
        schema.observation_count += 1

        self.store.set_app(schema)
        self.store.save()

        # Store in MECOS memory
        if self.memory:
            await self.memory.add_experience(
                content=f"APP OBSERVED: {app_name} | "
                        f"Capabilities: {schema.capabilities} | "
                        f"Menus: {schema.menu_items[:5]} | "
                        f"Web: {schema.web_knowledge[:200]}",
                source="app_perception",
            )

        return schema

    async def learn_file_type(self, extension: str, use_web: bool = True) -> FileTypeSchema:
        """
        Learn everything about a specific file type.
        Called when MECOS encounters a file it hasn't seen before.
        """
        ext = extension.lower().lstrip(".")
        ft = self.store.get_file_type(ext) or FileTypeSchema(ext)

        ft.category = self.builder.categorise_file_type(ext)

        # Find which apps handle this type
        ft.all_apps = self._find_apps_for_extension(f".{ext}")

        if ft.all_apps:
            ft.default_app = ft.all_apps[0]

        # Web knowledge about this file type
        if use_web and not ft.web_knowledge:
            try:
                from free_search import free_search
                results = free_search(f".{ext} file format what is it used for", max_total=2)
                if results:
                    ft.web_knowledge = results[0].snippet[:300]
            except Exception:
                pass

        self.store.set_file_type(ft)
        self.store.save()

        logger.info(
            "File type learned: .%s | Category: %s | Apps: %s",
            ext, ft.category, ft.all_apps[:3]
        )
        return ft

    # ------------------------------------------------------------------ #
    #  Observation during MECOS operation                                 #
    # ------------------------------------------------------------------ #

    async def observe_current_desktop(self) -> dict:
        """
        Snapshot of what's currently on screen / running.
        Called regularly so MECOS knows what the user is doing.
        """
        open_windows = self.ui_obs.get_open_windows()

        # For each open window, check if we have a schema
        window_knowledge = []
        for window in open_windows:
            title  = window["title"]
            schema = self._match_window_to_schema(title)
            self._update_usage_stats(title)
            window_knowledge.append({
                "window":       title,
                "app_schema":   schema.name if schema else "unknown",
                "capabilities": schema.capabilities if schema else [],
                "known":        schema is not None,
            })

        # Observe unknown apps
        for wk in window_knowledge:
            if not wk["known"]:
                # Learn this app we haven't seen before
                asyncio.create_task(self.observe_app(wk["window"]))

        if open_windows:
            self.store.save()

        return {
            "timestamp":       datetime.utcnow().isoformat(),
            "open_windows":    len(open_windows),
            "known_apps":      sum(1 for wk in window_knowledge if wk["known"]),
            "unknown_apps":    sum(1 for wk in window_knowledge if not wk["known"]),
            "window_details":  window_knowledge,
        }

    async def start_continuous_observation(self, interval_seconds: int = 30):
        """
        Runs continuously and learns newly observed desktop apps automatically.
        """
        interval = max(5, int(interval_seconds))
        while True:
            try:
                snapshot = await self.observe_current_desktop()
                for wk in snapshot.get("window_details", []):
                    if not wk.get("known"):
                        await self.observe_app(str(wk.get("window", "")))
            except Exception as e:
                logger.warning("Observation loop error: {}", e)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------ #
    #  Query interface                                                     #
    # ------------------------------------------------------------------ #

    def get_app_schema(self, app_name: str) -> Optional[AppSchema]:
        """Get everything MECOS knows about an app."""
        return self.store.get_app(app_name)

    def get_file_type_schema(self, extension: str) -> Optional[FileTypeSchema]:
        """Get everything MECOS knows about a file type."""
        return self.store.get_file_type(extension)

    def find_app_by_capability(self, capability: str) -> list[AppSchema]:
        """Find apps that can do something specific."""
        return [
            schema for schema in self.store.apps.values()
            if capability.lower() in [c.lower() for c in schema.capabilities]
        ]

    def get_app_for_file(self, extension: str) -> Optional[AppSchema]:
        """Which app should MECOS use to open a file of this type?"""
        ft = self.store.get_file_type(extension)
        if ft and ft.default_app:
            # Find app schema by exe path
            for schema in self.store.apps.values():
                if ft.default_app.lower() in schema.exe_path.lower():
                    return schema
        return None

    def most_used_apps(self, top_n: int = 10) -> list[AppSchema]:
        return sorted(
            self.store.apps.values(),
            key=lambda s: int(getattr(s, "usage_count", 0)),
            reverse=True,
        )[:max(1, int(top_n))]

    def stats(self) -> dict:
        caps = {}
        for schema in self.store.apps.values():
            for cap in schema.capabilities:
                caps[cap] = caps.get(cap, 0) + 1
        return {
            "total_apps":         len(self.store.apps),
            "total_file_types":   len(self.store.file_types),
            "apps_with_ui_data":  sum(1 for s in self.store.apps.values() if s.ui_elements),
            "apps_with_web_data": sum(1 for s in self.store.apps.values() if s.web_knowledge),
            "capabilities_found": caps,
        }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _scan_file_types(self):
        """Scan all file associations and build FileTypeSchema objects."""
        associations = self.scanner.scan_file_associations()
        for ext, data in associations.items():
            ft = self.store.get_file_type(ext) or FileTypeSchema(ext)
            ft.mime_type    = data.get("mime_type", "")
            ft.description  = data.get("description", "")
            ft.default_app  = data.get("default_app", "")
            ft.category     = self.builder.categorise_file_type(ext)
            self.store.set_file_type(ft)

    def _find_apps_for_extension(self, ext: str) -> list[str]:
        """Find all apps that can open a specific extension."""
        apps = []
        if os.name != "nt":
            return apps
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                f"{ext}\\OpenWithList"
            )
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    apps.append(winreg.EnumKey(key, i))
                except Exception:
                    break
        except Exception:
            pass
        return apps

    def _match_window_to_schema(self, window_title: str) -> Optional[AppSchema]:
        """Match a window title to a known app schema."""
        title_lower = window_title.lower()
        # Exact match first
        schema = self.store.get_app(window_title)
        if schema:
            return schema
        # Partial match
        for name, schema in self.store.apps.items():
            if name in title_lower or title_lower in name:
                return schema
        return None

    def _update_usage_stats(self, window_title: str):
        schema = self._match_window_to_schema(window_title)
        if not schema:
            return
        usage_count = int(getattr(schema, "usage_count", 0))
        setattr(schema, "usage_count", usage_count + 1)
        setattr(schema, "last_used", datetime.utcnow().isoformat())
        self.store.set_app(schema)

    # ------------------------------------------------------------------ #
    #  Backward compatibility with original interface                     #
    # ------------------------------------------------------------------ #

    async def map_computer(self):
        """Original interface — now triggers full system scan."""
        return await self.scan_and_learn_system()

    async def learn_workflow(self, workflow_name: str, commands: list, timeout: int = 30):
        """Original workflow learning — preserved from original."""
        if not self.controller:
            return {"error": "No controller available"}

        traces = []
        for index, command in enumerate(commands, start=1):
            result = await self.controller.run_command(command, timeout=timeout)
            traces.append({
                "step":      index,
                "command":   command,
                "exit_code": result.get("exit_code", "-1"),
                "stdout":    (result.get("stdout", "") or "")[:1500],
                "stderr":    (result.get("stderr", "") or "")[:500],
            })
            await asyncio.sleep(0)

        payload = {
            "workflow":  workflow_name,
            "timestamp": datetime.now().isoformat(),
            "steps":     traces,
        }

        if self.memory:
            await self.memory.add_experience(
                content=f"APP WORKFLOW TRACE: {payload}",
                source="app_workflow_learning",
            )

        logger.info("Captured workflow '{}' with {} steps.", workflow_name, len(traces))
        return payload
