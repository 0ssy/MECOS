import subprocess
from loguru import logger

async def sync_server_knowledge():
    try:
        logger.info("Syncing knowledge from server (iggy)...")
        # Pulls the server's discoveries to your laptop
        subprocess.run([
            "scp", 
            "jose@iggy:~/MECOS/exploration/discoveries/knowledge.json", 
            "./exploration/discoveries/server_knowledge.json"
        ], check=True)
        logger.success("Server knowledge synced successfully.")
    except Exception as e:
        logger.error(f"Failed to sync server knowledge: {e}")
