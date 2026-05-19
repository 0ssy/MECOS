import json
from pathlib import Path
from datetime import datetime
from exploration.config import config

class KnowledgeBase:
    def __init__(self):
        self.knowledge_file = config.DISCOVERIES_DIR / "knowledge.json"
        self._load_knowledge()

    def _load_knowledge(self):
        if self.knowledge_file.exists():
            with open(self.knowledge_file, 'r') as f:
                self.knowledge = json.load(f)
        else:
            self.knowledge = {}

    def add_log(self, target_name, log):
        if target_name not in self.knowledge:
            self.knowledge[target_name] = {"history": []}
        log["timestamp"] = datetime.now().isoformat()
        self.knowledge[target_name]["history"].append(log)
        with open(self.knowledge_file, 'w') as f:
            json.dump(self.knowledge, f, indent=2)
