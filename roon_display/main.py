"""Main application entry point for Roon Album Art Display."""

import importlib
import logging
import sys
from pathlib import Path

from .anniversary import AnniversaryManager
from .config.config_manager import ConfigManager
from .roon_client.client import RoonClient
from .simulation import SimulationServer
from .utils import ensure_extra_images_dir_exists, ensure_image_dir_exists, set_performance_logging
from .viewers.eink_viewer import EinkViewer
from .viewers.tk_viewer import TkViewer

# Configure logging format (level will be set after config is loaded)
log_format = "%(asctime)s [%(levelname)-7s] %(name)-12s: %(message)s [[%(funcName)s]]"
logging.basicConfig(
    level=logging.DEBUG, format=log_format, handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RoonArtFrame")

# Configure API logger
api_logger = logging.getLogger("roonapi")
for handler in api_logger.handlers:
    handler.setFormatter(logging.Formatter(log_format))


def create_viewer(config_manager):
    """Create appropriate viewer based on configuration."""
    display_config = config_manager.get_display_config()
    display_type = display_config["type"]

    if display_type == "system_display":
        logger.info("Creating Tkinter system display viewer")
        import tkinter as tk

        from PIL import ImageTk

        root = tk.Tk()
        viewer = TkViewer(config_manager, root)
        return viewer, root

    elif display_type == "epd13in3E":
        partial_refresh = display_config["partial_refresh"]
        logger.info(
            f"Creating e-ink viewer for {display_type} (partial_refresh: {partial_refresh})"
        )

        # Add libs directory to path for e-ink modules
        libs_dir = Path(__file__).parent.parent / "libs"
        if libs_dir.exists():
            sys.path.insert(0, str(libs_dir))

        try:
            eink_module = importlib.import_module(f"libs.{display_type}")
            viewer = EinkViewer(
                config_manager, eink_module, partial_refresh=partial_refresh
            )
            return viewer, None
        except ImportError as e:
            logger.error(f"Could not import e-ink module {display_type}: {e}")
            raise
    else:
        raise ValueError(f"Unknown display type: {display_type}")


def main():
    """Main application entry point."""
    try:
        logger.info("Starting Roon Album Art Display")

        # Ensure required directories exist
        ensure_image_dir_exists()
        ensure_extra_images_dir_exists()

        # Load configuration
        config_manager = ConfigManager()

        # Set logging level from config
        log_level = config_manager.get_log_level()
        logging.getLogger().setLevel(log_level)
        logger.info(f"Log level set to: {logging.getLevelName(log_level)}")

        # Set performance logging from config
        performance_logging = config_manager.get_performance_logging()
        set_performance_logging(performance_logging)
        if performance_logging:
            logger.info(f"Performance logging enabled: {performance_logging}")

        # Create anniversary manager
        anniversary_config = config_manager.get_anniversaries_config()
        anniversary_manager = AnniversaryManager(anniversary_config)

        # Create viewer
        viewer, tk_root = create_viewer(config_manager)

        # Create Roon client with anniversary manager
        roon_client = RoonClient(
            config_manager, viewer, viewer.image_processor, anniversary_manager
        )

        # Start simulation server for testing
        simulation_server = SimulationServer(roon_client)
        simulation_server.start()

        if tk_root:
            # For Tkinter, we need to start connection in background thread
            # so the GUI can show authorization messages
            import threading
            
            def connect_and_run():
                """Connect to Roon and start event loop in background."""
                try:
                    roon_client.connect()
                    roon_client.run()
                except Exception as e:
                    logger.error(f"Error in Roon client: {e}")
            
            # Start Roon connection in background thread
            roon_thread = threading.Thread(target=connect_and_run, daemon=True)
            roon_thread.start()
            
            # Start Tkinter main loop immediately (blocks here)
            viewer.check_pending_updates()
            tk_root.mainloop()
            
        else:
            # For e-ink, connect synchronously (no GUI to show)
            roon_client.connect()
            event_thread = roon_client.run()
            try:
                event_thread.join()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        # Cleanup
        if "roon_client" in locals():
            roon_client.stop()
        if "simulation_server" in locals():
            simulation_server.stop()
        logger.info("Application stopped")


if __name__ == "__main__":
    main()
