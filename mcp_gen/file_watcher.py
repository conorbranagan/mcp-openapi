import logging
import time
import asyncio

from watchdog.events import FileSystemEventHandler

from mcp_gen.server_manager import ServerManager

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, server_manager: ServerManager, loop: asyncio.AbstractEventLoop):
        self.server_manager = server_manager
        self.last_modified = time.time()
        self.loop = loop  # Store the event loop

    def on_modified(self, event):
        # Ignore non-yaml files and directory events
        if event.is_directory or not event.src_path.endswith(".yaml"):
            return

        # Debounce multiple events
        current_time = time.time()
        if current_time - self.last_modified < 1:
            return
        self.last_modified = current_time

        logger.info(f"Config file changed: {event.src_path}")
        # Use the stored event loop to schedule the coroutines
        asyncio.run_coroutine_threadsafe(self._handle_config_change(), self.loop)

    async def _handle_config_change(self):
        """Handle configuration changes asynchronously"""
        await self.server_manager.stop_servers()
        self.server_manager.load_config()
        await self.server_manager.start_servers()
