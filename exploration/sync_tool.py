import subprocess
import asyncio
from loguru import logger

async def sync_server_knowledge():
    try:
        # Using the IP address 192.168.1.88 which we know works
        logger.info("Syncing knowledge from server (192.168.1.88)...")
        await asyncio.to_thread(
            subprocess.run,
            [
                "scp",
                "-o", "BatchMode=yes",  # Prevents hangs if password auth is required
                "jose@192.168.1.88:~/MECOS/exploration/discoveries/knowledge.json",
                "./exploration/discoveries/server_knowledge.json",
            ],
            check=True,
        )
        logger.success("Server knowledge synced successfully.")
    except Exception as e:
        logger.error(f"Failed to sync server knowledge: {e}. Ensure SSH keys are set up.")
