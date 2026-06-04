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


def main() -> None:
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="Roon Album Art Display")
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        metavar="PATH",
        help="Image file or directory to display without Roon (exits after display)",
    )
    parser.add_argument(
        "--time",
        action="store_true",
        help="Render the current date/time without Roon, then exit (display test)",
    )
    args = parser.parse_args()

    if args.image is not None:
        from .standalone import run as run_standalone

        run_standalone(args.image)
        return  # run_standalone calls sys.exit(), but be explicit

    if args.time:
        from .standalone import run_time

        run_time()
        return  # run_time calls sys.exit(), but be explicit

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
        internal_server.set_roon_client(roon_client)

        # Start simulation server for testing
        simulation_server = SimulationServer(roon_client, config_manager)
        simulation_server.start()

        # Connection runs in a background thread for both display types.
        # connect_loop handles retries with overlay feedback so the user
        # always sees connection status on both e-ink and web UI.
        import threading

        def connect_and_run() -> None:
            """Connect to Roon and start event loop in background."""
            try:
                roon_client.connect_loop()
                event_thread = roon_client.run()
                event_thread.join()
            except Exception as e:
                logger.error(f"Error in Roon client: {e}")

        roon_client.running = True
        roon_thread = threading.Thread(
            target=connect_and_run, daemon=True, name="roon-client"
        )
        roon_thread.start()

        # Show a clock on the display whenever Roon is not connected (e.g. while
        # the server is unreachable or the extension awaits approval in Roon).
        from .connection_clock import ConnectionClock

        connection_clock = ConnectionClock(
            roon_client, render_coordinator, message_renderer
        )
        connection_clock.start()

        if tk_root:
            tk_root.mainloop()
        else:
            try:
                roon_thread.join()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        # Cleanup
        if "connection_clock" in locals():
            connection_clock.stop()
        if "roon_client" in locals():
            roon_client.stop()
        if "simulation_server" in locals():
            simulation_server.stop()
        if "viewer" in locals() and hasattr(viewer, "cleanup"):
            viewer.cleanup()
        logger.info("Application stopped")


if __name__ == "__main__":
    main()
