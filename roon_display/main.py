"""Main application entry point for Roon Album Art Display."""

import argparse
import logging
import sys
from pathlib import Path

from .anniversary import AnniversaryManager
from .config.config_manager import ConfigManager
from .roon_client.client import RoonClient
from .simulation import SimulationServer
from .utils import (
    ensure_extra_images_dir_exists,
    ensure_image_dir_exists,
    set_performance_logging,
)
from .viewers import create_viewer

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

# Suppress verbose PIL debug logs
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.WARNING)

# Suppress verbose websocket debug logs
websocket_logger = logging.getLogger("websocket")
websocket_logger.setLevel(logging.WARNING)


def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="Roon Album Art Display")
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        metavar="PATH",
        help="Image file or directory to display without Roon (exits after display)",
    )
    args = parser.parse_args()

    if args.image is not None:
        from .standalone import run as run_standalone

        run_standalone(args.image)
        return  # run_standalone calls sys.exit(), but be explicit

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
        logger.info(f"Global log level set to: {logging.getLevelName(log_level)}")

        # Configure component-specific log levels
        config_manager.configure_component_log_levels()
        logger.info("Component-specific log levels configured")

        # Set performance logging from config
        performance_logging = config_manager.get_performance_logging()
        set_performance_logging(performance_logging)
        if performance_logging:
            logger.info(f"Performance logging enabled: {performance_logging}")

        # Create anniversary manager
        anniversary_manager = AnniversaryManager(config_manager)

        # Create viewer
        viewer, tk_root = create_viewer(config_manager)

        # Create message renderer for coordinator
        from .message_renderer import MessageRenderer

        message_renderer = MessageRenderer(config_manager)

        # Create render coordinator
        from .render_coordinator import RenderCoordinator

        render_coordinator = RenderCoordinator(
            viewer,
            viewer.image_processor,
            message_renderer,
            config_manager,
            anniversary_manager,
        )

        # Set coordinator in viewer for state tracking
        viewer.set_render_coordinator(render_coordinator)

        # Create internal server for web communication
        from .internal_server import InternalServer

        internal_server = InternalServer(render_coordinator, config_manager)
        internal_server.start()

        # Create Roon client with coordinator
        roon_client = RoonClient(
            config_manager,
            viewer,
            viewer.image_processor,
            render_coordinator,
        )

        # Load any existing image on startup through coordinator
        from .utils import get_current_image_key, get_saved_image_dir

        current_key = get_current_image_key()
        if current_key:
            image_path = get_saved_image_dir() / f"album_art_{current_key}.jpg"
            if image_path.exists():
                logger.info(f"Loading last displayed image on startup: {current_key}")
                render_coordinator.set_main_content(
                    content_type="last_art",
                    image_key=current_key,
                    image_path=image_path,
                    track_info="Last displayed artwork",
                )

        # Start simulation server for testing
        simulation_server = SimulationServer(roon_client, config_manager)
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
