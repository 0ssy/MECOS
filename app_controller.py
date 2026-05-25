import os
import subprocess
import json
from loguru import logger
from pathlib import Path

class AppController:
    def __init__(self, knowledge_base_path=None):
        self.kb_path = knowledge_base_path or "exploration/discoveries/knowledge.json"
        logger.info(f"AppController initialized. Using KB: {self.kb_path}")

    def _get_app_path(self, app_name):
        """Look up the app path in the discovered knowledge."""
        try:
            if os.path.exists(self.kb_path):
                with open(self.kb_path, 'r') as f:
                    kb = json.load(f)
                    apps = kb.get("system_apps", {})
                    # Case-insensitive search
                    for name, path in apps.items():
                        if app_name.lower() in name.lower():
                            return path
        except Exception as e:
            logger.error(f"Error reading Knowledge Base: {e}")
        return None

    async def execute_command(self, command: str) -> str:
        # Check if the command is "open [app]"
        if command.lower().startswith("open "):
            app_name = command[5:].strip()
            app_path = self._get_app_path(app_name)
            
            if app_path:
                logger.info(f"Found app path for '{app_name}': {app_path}")
                try:
                    # Launch the app on Windows
                    subprocess.Popen([app_path], shell=True)
                    return f"Successfully opened {app_name}."
                except Exception as e:
                    return f"Error launching {app_name}: {e}"
            else:
                return f"I haven't discovered the app '{app_name}' yet. I'll keep exploring!"
        
        # Default to system execution for other commands
        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, text=True)
            return result
        except subprocess.CalledProcessError as e:
            return e.output

