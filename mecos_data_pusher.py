# mecos_data_pusher.py
"""
Pushes MECOS local data files to the laptop server.
Runs on a schedule alongside MECOS — keeps local storage clean.
"""

import asyncio
import io
import json
import logging
import shutil
import zipfile
from pathlib import Path

import aiohttp
import schedule
import time

logger = logging.getLogger("mecos.pusher")
logging.basicConfig(level=logging.INFO)

SERVER_URL = "http://192.168.1.88:8765"  # your laptop

LOCAL_FILES = {
    "knowledge_graph":  Path("mecos_brain.gml"),
    "domain_graph":     Path("mecos_domain_graph.json"),
    "perception_memory":Path("mecos_system_perception.json"),
}

CHROMA_DIR = Path("mecos_chroma")


async def push_file(session: aiohttp.ClientSession, endpoint: str, file_path: Path):
    """Push a single file to the server."""
    if not file_path.exists():
        logger.warning("File not found: %s", file_path)
        return False
    try:
        data = aiohttp.FormData()
        data.add_field(
            "file",
            file_path.read_bytes(),
            filename=file_path.name,
            content_type="application/octet-stream",
        )
        async with session.post(f"{SERVER_URL}/push/{endpoint}", data=data, timeout=30) as r:
            result = await r.json()
            logger.info("Pushed %s → %s", file_path.name, result)
            return True
    except Exception as e:
        logger.error("Push failed for %s: %s", file_path, e)
        return False


async def push_vector_store(session: aiohttp.ClientSession):
    """Zip and push the ChromaDB directory."""
    if not CHROMA_DIR.exists():
        return
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in CHROMA_DIR.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(CHROMA_DIR))
        buf.seek(0)
        data = aiohttp.FormData()
        data.add_field(
            "file",
            buf.read(),
            filename="mecos_chroma.zip",
            content_type="application/zip",
        )
        async with session.post(f"{SERVER_URL}/push/vector_store", data=data, timeout=60) as r:
            result = await r.json()
            logger.info("Pushed vector store → %s", result)
    except Exception as e:
        logger.error("Vector store push failed: %s", e)


async def push_trade_log(session: aiohttp.ClientSession, log_path: Path):
    """Push trade log entries."""
    if not log_path.exists():
        return
    try:
        entries = []
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass

        if entries:
            async with session.post(
                f"{SERVER_URL}/push/trade_logs",
                json={"entries": entries, "source": str(log_path)},
                timeout=15
            ) as r:
                result = await r.json()
                logger.info("Pushed %d trade log entries", len(entries))

            # Clear local log after successful push
            log_path.write_text("")
            logger.info("Local trade log cleared after push")
    except Exception as e:
        logger.error("Trade log push failed: %s", e)


async def check_server() -> bool:
    """Check if the server is reachable."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SERVER_URL}/health", timeout=5) as r:
                data = await r.json()
                logger.info(
                    "Server online | Disk free: %.1f GB",
                    data.get("disk_free_gb", 0)
                )
                return True
    except Exception:
        logger.warning("Server at %s is unreachable", SERVER_URL)
        return False


async def run_push_cycle():
    """Push all data to server and clean up local files."""
    logger.info("Starting push cycle...")

    if not await check_server():
        logger.warning("Skipping push — server offline")
        return

    async with aiohttp.ClientSession() as session:
        # Push all tracked files
        for endpoint, path in LOCAL_FILES.items():
            await push_file(session, endpoint, path)

        # Push vector store (larger — less frequent)
        await push_vector_store(session)

        # Push trade logs
        for log_file in Path(".").glob("*.log"):
            await push_trade_log(session, log_file)
        for log_file in Path(".").glob("*.jsonl"):
            await push_trade_log(session, log_file)

    # Clean up local cache files to free storage
    _cleanup_local()
    logger.info("Push cycle complete")


def _cleanup_local():
    """
    After successful push, remove local copies of large files
    to free storage on the main PC.
    """
    cleanup_targets = [
        Path("mecos_learn.log"),
        Path("mecos_expansion.log"),
    ]

    # Remove old cycle reports (keep latest only)
    cycle_reports = sorted(Path(".").glob("mecos_cycle_*_report.json"))
    if len(cycle_reports) > 2:
        for old in cycle_reports[:-2]:
            old.unlink()
            logger.info("Cleaned up old report: %s", old)

    # Truncate large logs
    for log in cleanup_targets:
        if log.exists() and log.stat().st_size > 10 * 1024 * 1024:  # 10MB
            log.write_text("")
            logger.info("Truncated large log: %s", log)


def start_pusher(interval_minutes: int = 30):
    """Run the pusher on a schedule."""
    logger.info("MECOS Data Pusher started. Server: %s", SERVER_URL)
    logger.info("Push interval: every %d minutes", interval_minutes)

    # Run immediately on start
    asyncio.run(run_push_cycle())

    schedule.every(interval_minutes).minutes.do(
        lambda: asyncio.run(run_push_cycle())
    )

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="Push once and exit")
    args = parser.parse_args()

    if args.once:
        asyncio.run(run_push_cycle())
    else:
        start_pusher(args.interval)