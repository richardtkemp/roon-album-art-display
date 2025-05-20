# vim: set tabstop=4 shiftwidth=4 expandtab softtabstop=4:
import sys
import os
import time
import importlib
import logging
from abc import ABC, abstractmethod
import threading
import shutil
import json
import requests
import configparser
from io import BytesIO
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageColor # aka pillow
from pathlib import Path
from roonapi import RoonApi, RoonDiscovery #, RoonApiWebSocket


this_script = __file__
log_format = '%(asctime)s [%(levelname)-7s] %(name)-12s: %(message)s [[%(funcName)s]]'
# Configure logging
logging.basicConfig(
    level = logging.DEBUG,
    format = log_format,
    handlers = [logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("RoonArtFrame")

# Get the API's logger - replace 'roonapisocket' with the actual logger name used by the API
api_logger = logging.getLogger('roonapi')

# Apply your formatter to all existing handlers in both loggers
for handler in api_logger.handlers:
    handler.setFormatter(logging.Formatter(log_format))

libdir = os.path.join(os.path.dirname(os.path.realpath(this_script)), 'libs')
if os.path.exists(libdir):
    sys.path.append(libdir)
    logger.debug(f"Adding libdir to path: {libdir}")
else:
    raise FileNotFoundError

cfgpath = os.path.join(os.path.dirname(os.path.realpath(this_script)), 'roon.cfg')

def setCurrentImageKey(key):
    path = getSavedImageDir() / "current_key"
    path.write_text(key)
    return None

def getCurrentImageKey():
    path = getSavedImageDir() / "current_key"
    if path.exists():
        return path.read_text().strip()
    return None

def getSavedImageDir():
    return getRootDir() / "album_art"

def getRootDir():
    return Path(os.path.dirname(os.path.dirname(os.path.realpath(this_script))))



###########################################################################
###########################################################################
########   Abstract class for Viewers. Defines common functions.   ########
###########################################################################
###########################################################################
class Viewer(ABC):
    def set_screen_size(self, w, h):
        self.scale_x = float(self.config.get('IMAGE_POSITION', 'scale_x'))
        self.scale_y = float(self.config.get('IMAGE_POSITION', 'scale_y'))
        self.rotation = float(self.config.get('IMAGE_POSITION', 'rotation'))
        if self.scale_x == 0 or self.scale_y == 0:
            logger.error('Scale must not be set to zero! Check config file')
            raise ValueError
        self.screen_width  = int(w)
        self.screen_height = int(h)
        self.image_width   = int(w * float(self.scale_x))
        self.image_height  = int(h * float(self.scale_y))
        self.image_size = min(self.image_width, self.image_height)
        
    def startup(self):
        self.load_config()
        # Load initial image
        image_key = getCurrentImageKey()
        image_path = getSavedImageDir / "album_art_" + image_key + ".jpg"
        if Path(image_path).exists():
            self.update(image_path, None)
    
    def check_pending_updates(self):
        pass
    
    @abstractmethod
    def update(self, image_path, img, title):
        pass

    @abstractmethod
    def display_image(self, image_path):
        pass

    def fetch_image(self, image_path):
        if Path(image_path).exists():
            # Open the image
            try:
                img = Image.open(image_path)
                return img
            except Exception as e:
                # Bad file?
                logger.error(f"Couldn't read image file {image_path}, error: {e}")
                os.remove(image_path)
                raise FileNotFoundError
        else:
            logger.error(f"Couldn't find image file {image_path}")
            return None

    def load_config(self):
        # Get image rendering controls from config
        for name in ['colour_balance', 'contrast', 'sharpness', 'brightness']:
            attr_name = f"{name}_adjustment"
            setattr(self, attr_name, float(self.config.get('IMAGE_RENDER', f'{name}_adjustment')))

        # Get image size and position controls from config
        self.position_offset_x = int(self.config.get('IMAGE_POSITION', 'position_offset_x'))
        self.position_offset_y = int(self.config.get('IMAGE_POSITION', 'position_offset_y'))


    def process_image_position(self, img):
        logger.debug("Starting to process image position")

        if self.rotation == 90:
            img = img.transpose(Image.ROTATE_90)
        elif self.rotation == 180:
            img = img.transpose(Image.ROTATE_180)
        elif self.rotation == 270:
            img = img.transpose(Image.ROTATE_270)

        # Calculate scaling to fit the screen while maintaining aspect ratio
        img_width, img_height = img.size

        # If we somehow downloaded an image of the wrong size, e.g. if screen size or scaling has changed
        if (not img_width == self.image_width) or (not img_height == self.screen_height) or not self.scale_x == self.scale_y:
            logger.debug("Resizing")
            scale_ratio = max(self.scale_x,self.scale_y)
            new_width   = int(img_width  * self.scale_x * scale_ratio)
            new_height  = int(img_height * self.scale_y * scale_ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        if not (self.screen_width, self.screen_height) == img.size:
            img = self.pad_image_to_size(img)

        return img

    def pad_image_to_size(self, img):
        logger.debug("Padding")

        # Get the original dimensions
        original_width, original_height = img.size
        
        # Create a new white image with the target dimensions
        logger.debug("Starting creating new image")
        new_image = Image.new('RGB', (self.screen_width, self.screen_height), color='white')
        logger.debug("Finished creating new image")
        
        # Calculate position to paste the original image
        paste_x = self.position_offset_x + (self.screen_width  - original_width ) // 2
        paste_y = self.position_offset_y + (self.screen_height - original_height) // 2
        
        # Paste the original image onto the new white canvas
        logger.debug("Starting pasting images together")
        new_image.paste(img, (paste_x, paste_y))
        logger.debug("Finished pasting images together")
        
        return new_image


###########################################################################
###########################################################################
########   Viewer for Eink devices, currently support Waveshare    ########
###########################################################################
###########################################################################
class EinkViewer(Viewer):
    def __init__(self, config, eink):
        self.config = config
        self.eink = eink
        self.set_screen_size(self.eink.EPD_WIDTH, self.eink.EPD_HEIGHT)
        self.update_thread = None

        self.epd = eink.EPD()
        self.epd.Init()
        self.startup()
    
    def startup(self):
        self.load_config()
        # No need to reload an image, it's still there

    def display_image(self, img, title):
        """Display an image"""

        # Render on the eink display
        logger.debug(f"Starting sending image to display for {title}")
        # TODO this break stuff, but seems like it should be needed?
        self.epd.should_stop = False
        self.epd.display(self.epd.getbuffer(img), title)
        self.epd.should_stop = False
        logger.info(f"Finished sending image to display for {title}")

    def update(self, image_path, img, title):
        if img is None:
            img = self.fetch_image(image_path)
        if img is None:
            return

        logger.info(f"Setting should_stop triggered by {title}") # TODO
        self.epd.should_stop = True

        # Process the image position, including scale and offset while we wait for the thread to stop
        img = self.process_image_position(img)

        logger.debug(f"Checking previous update thread for {title}")
        if self.update_thread is not None:
            while self.update_thread.is_alive():
                logger.debug(f"Waiting for previous thread to finish for {title}")
                time.sleep(0.1)
        logger.debug(f"Creating new update thread for {title}")

        self.update_thread = threading.Thread(
            target=self.display_image,
            args  =(img,title)
        )
        self.update_thread.start()


###########################################################################
###########################################################################
##########     Used to display images in system_display mode      ########a
###########################################################################
###########################################################################
class TkViewer(Viewer):
    def __init__(self, config, root):
        self.config = config
        self.set_screen_size(root.winfo_screenwidth(), root.winfo_screenheight())

        self.root = root
        self.root.title("Image Viewer")
        
        # Force light theme
        self.root.tk_setPalette(
            background='#f0f0f0',  # Light gray background
            foreground='black',    # Black text
            activeBackground='#e0e0e0',  # Slightly darker gray for active elements
            activeForeground='black'     # Black text for active elements
        )
        
        # For windowed mode
        #self.root.geometry("800x600")
        # For fullscreen
        self.root.attributes('-fullscreen', True)
        
        # Create label to display the image
        self.label = tk.Label(root)
        self.label.pack(fill=tk.BOTH, expand=True)
        
        # Bind Escape key to close the window
        self.root.bind('<Escape>', lambda e: self.root.destroy())
        
        # Handle window close button (X)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        
        # Variable to store the latest requested image path
        self.pending_image_path = None
        
        # Fetch, process, display the image
        self.startup()

    def check_pending_updates(self):
        # Schedule next check (every 100ms)
        self.root.after(100, self.check_pending_updates)

        """Check if there's a pending image update"""
        if self.pending_image_path is not None:
            self.display_image(self.pending_image_path)
            logger.info("Updated displayed image")
            self.pending_image_path = None
#        else:
#            logger.debug("No new image found")
    
    def display_image(self, image_path):
        """Display an image (should only be called from the main thread)"""
        img = self.fetch_image(image_path)
        if img is None:
            return

        # Process the image position, including scale and offset
        img = self.process_image_position(img)

        # Convert to PhotoImage
        self.photo = ImageTk.PhotoImage(img)
        
        # Update the label
        self.label.configure(image=self.photo)
        
        # Keep a reference to prevent garbage collection
        self.label.image = self.photo
        
    def update(self, image_path, img):
        """Thread-safe method to request an image update from anywhere"""
        # Store the latest image path instead of directly updating
        self.pending_image_path = image_path


###########################################################################
###########################################################################
###   Handles communication with Roon, calls viewer for image updates   ###
###########################################################################
###########################################################################
class RoonAlbumArt:
    def __init__(self, config, viewer):
        # Set up logging first
        logger.info("Starting Roon Album Art Display")
        
        # Save params
        self.viewer = viewer;
        self.config = config
        
        # Get zone info from config
        self.allowed_zone_names   = [zone for zone in self.config.get('ZONES', 'allowed_zone_names').split(',') if zone]
        self.forbidden_zone_names = [zone for zone in self.config.get('ZONES', 'forbidden_zone_names').split(',') if zone]
        logger.info(f"Allowed zone names: {json.dumps(self.allowed_zone_names)}")
        logger.info(f"Forbidden zone names: {json.dumps(self.forbidden_zone_names)}")
        
        # Get app info from config
        self.app_info = {
            "extension_id":    self.config.get('APP', 'extension_id'),
            "display_name":    self.config.get('APP', 'display_name'),
            "display_version": self.config.get('APP', 'display_version'),
            "publisher":       self.config.get('APP', 'publisher'),
            "email":           self.config.get('APP', 'email'),
        }
        
        # Path for token storage
        self.token_file = Path.home() / ".roon_album_display_token.txt"
        logger.info(f"Token file path: {self.token_file}")
        
        # Initiate some variables
        self.current_image_path = None
        self.last_event = None
        display_type = self.config.get('DISPLAY', 'type')
        if display_type == 'system_display':
            self.last_image_key = None
        else:
            self.last_image_key = getCurrentImageKey()
        
        # Connect to Roon - do this BEFORE starting to display an image
        logger.info("Connecting to Roon before starting display...")
        self.roon = self.connect_to_roon()
        
        # Get current album
        for key, dictionary in self.roon.zones.items():
            result = self.process_zone_data(key, dictionary)
            if result is not False:  # This checks for exactly False, not falsy values
                break

        # Event handling
        self.running = True
    
    def save_server_to_config(self, server_ip, server_port):
        """Save the server IP and port to config file for future use"""
        try:
            # Make sure SERVER section exists
            if 'SERVER' not in self.config:
                self.config['SERVER'] = {}
            
            # Update config
            self.config['SERVER']['ip'] = server_ip
            self.config['SERVER']['port'] = str(server_port)
            
            # Write to file
            with open(cfgpath, 'w') as configfile:
                self.config.write(configfile)
                
            logger.info(f"Saved server details ({server_ip}:{server_port}) to config for future use")
        except Exception as e:
            logger.error(f"Error saving server details to config: {e}")
            
    def connect_to_roon(self):
        """Connect to Roon server using saved details or discovery"""
        # Get token from file if it exists
        token = None
        if self.token_file.exists():
            token = self.token_file.read_text().strip()
            logger.info("Found existing auth token")
        else:
            logger.info("No existing auth token found, will need to authorize in Roon")
        
        # First try direct connection with saved settings
        try:
            if 'SERVER' in self.config and self.config.get('SERVER', 'ip') and self.config.get('SERVER', 'port'):
                server_ip = self.config.get('SERVER', 'ip')
                server_port = self.config.getint('SERVER', 'port')
                
                if server_ip and server_port:
                    logger.info(f"Trying direct connection to saved server at {server_ip}:{server_port}")
                    try:
                        api = RoonApi(self.app_info, token, server_ip, server_port)
                        # Add validation to confirm the connection is actually working
                        if api and api.host:
                            # Test the connection by trying to fetch zones
                            try:
                                zones = api.zones
                                if zones is not None and zones:
                                    logger.info("Successfully connected to saved server!")
                                    logger.debug(f"Zones data: {zones}")
                                    return api
                                else:
                                    api.stop()
                                    raise Exception("couldn't fetch zones")
                            except Exception as e:
                                raise e
                        else:
                            logger.warning("API instance created but appears to be invalid")
                            raise Exception("Invalid API instance")
                    except Exception as e:
                        logger.warning(f"Failed to connect to saved server: {e}")
                        logger.info("Falling back to discovery...")
                else:
                    logger.info("Saved server details incomplete, using discovery")
        except Exception as e:
            logger.warning(f"Error reading saved server details: {e}")
            logger.info("Falling back to discovery...")
        
        # If direct connection failed or no saved details, use discovery
        return self.discover_and_connect()

    def discover_and_connect(self):
        """Discover Roon servers on the network and connect to the first one found"""
        # Get token from file if it exists
        token = None
        if self.token_file.exists():
            token = self.token_file.read_text().strip()
            logger.info("Found existing auth token")
        else:
            logger.info("No existing auth token found, will need to authorize in Roon")
        
        # Start discovery process
        logger.info("Starting Roon server discovery...")
        discover = RoonDiscovery(None)
        
        while True:
            servers = discover.all()
            if servers:
                logger.info(f"Found {len(servers)} Roon server(s)")
                break
            
            logger.info("Waiting for Roon servers to be discovered...")
            time.sleep(1)
        
        # Stop discovery
        logger.debug("Shutting down discovery")
        discover.stop()
        
        # Only connect to the first server found
        server = servers[0]
        server_ip, server_port = server
        logger.info(f"Connecting to first Roon server found at {server_ip}:{server_port}")
        
        # Try to connect to the server
        try:
            api = RoonApi(self.app_info, token, server_ip, server_port, False)
            
            # Wait for authorization if needed
            if token is None and api is not None:
                logger.info("Waiting for authorization in Roon...")
                
                while api.token is None:
                    logger.info("Please approve this extension in the Roon app...")
                    time.sleep(2)

                # Save the token for future use
                self.token_file.write_text(api.token)
                logger.info("Authorization successful, token saved for future connections")
                
            elif api is not None:
                logger.info(f"Successfully connected using existing token")

            # Save server details for future connections
            self.save_server_to_config(server_ip, server_port)
            
            logger.info("Connected to Roon server!")
            return api
            
        except Exception as e:
            logger.exception(f"Error connecting to Roon server at {server_ip}:{server_port}: {e}")
            return None
    
    
    def subscribe_to_events(self):
        """Subscribe to zone and queue updates"""
        logger.info("Registering for state callbacks...")
        try:
            # Register for state callbacks with verbose logging
            logger.info("Registering state callback...")
            self.roon.register_state_callback(self.zone_event_callback, 'zones_changed')
            logger.info("Successfully registered for state callbacks")
            
        except Exception as e:
            logger.error(f"Error subscribing to Roon events: {e}")
            logger.exception("Detailed traceback:")
    
    def zone_event_callback(self, event_type, data):
        """Handle state update events from Roon"""
        try:
            logger.debug(f"Processing {event_type} event")
            
            # Handle list data structure
            if isinstance(data, list):
                for i, zone_item in enumerate(data):
                    # Fetch the complete zone data (including now playing) using the ID
                    if isinstance(zone_item, str):
                        zone_data = self.roon.zones.get(zone_item)
                        if zone_data:
                            self.process_zone_data(zone_item, zone_data)
                        else:
                            logger.warning(f"No zone data found for zone ID: {zone_item}")
            
            else:
                logger.warning(f"Unexpected data format in {event_type} event: {type(data)}")
            
        except Exception as e:
            logger.error(f"Error in zone event callback: {e}")
            logger.exception("Detailed traceback:")
    
    def process_zone_data(self, zone_id, zone_data):
        """Process zone data and update display if needed"""
        try:
            # Log zone data structure for debugging
            logger.debug(f"Processing zone {zone_id}, data keys: {zone_data.keys() if isinstance(zone_data, dict) else 'not a dict'}")
            
            name = zone_data['display_name']
            if self.forbidden_zone_names and name in self.forbidden_zone_names:
                logger.debug(f"Received event from zone {name} but it is in the forbidden list")
                return False
            if self.allowed_zone_names and not name in self.allowed_zone_names:
                logger.debug(f"Received event from zone {name} but it is not in the allowed list")
                return False

            # Check if the zone has now_playing information
            if isinstance(zone_data, dict):
                # Direct now_playing object
                if "now_playing" in zone_data and zone_data["now_playing"]:
                    now_playing = zone_data["now_playing"]
                    self.process_now_playing(now_playing)
                
                # Check if it might be in a nested structure
                elif "state" in zone_data and isinstance(zone_data["state"], dict):
                    if "now_playing" in zone_data["state"] and zone_data["state"]["now_playing"]:
                        now_playing = zone_data["state"]["now_playing"]
                        self.process_now_playing(now_playing)
                
                # Check if this is a different API structure
                elif "display_name" in zone_data and "queue" in zone_data and "now_playing" in zone_data.get("queue", {}):
                    now_playing = zone_data["queue"]["now_playing"]
                    self.process_now_playing(now_playing)
            
        except Exception as e:
            logger.error(f"Error processing zone data: {e}")
            logger.debug(f"Zone data that caused error: {str(zone_data)[:200]}...")
            
    def process_now_playing(self, now_playing):
        """Process the now_playing object to extract image and track info"""
        try:
            logger.debug(f"Now playing keys: {now_playing.keys() if isinstance(now_playing, dict) else 'not a dict'}")

            # Don't process duplicate events
            if now_playing == self.last_event:
                # Always log the event type for debugging
                logger.debug(f"Ignoring duplicate event {str(now_playing)}")
                return
            self.last_event = now_playing
            
            # First, try to get the image_key
            image_key = None
            
            if isinstance(now_playing, dict):
                if "image_key" in now_playing and now_playing["image_key"]:
                    image_key = now_playing["image_key"]
            
            if not image_key:
                logger.warning(f"No image key found in now_playing data {now_playing}")
                return
                
            # Only update if the image has changed
            if image_key != self.last_image_key:
                logger.info(f"New track detected with image key: {image_key}")
                self.last_image_key = image_key
                
                # Now try to get track information
                track_info  = "Unknown Track"
                artist_info = "Unknown Artist"
                album_info  = "Unknown Album"
                
                # Try to extract track info from different possible structures
                if isinstance(now_playing, dict):
                    # Try one_line/two_line/three_line structure
                    if "three_line" in now_playing and isinstance(now_playing["three_line"], dict):
                        track_info  = now_playing["three_line"].get("line1", track_info)
                        artist_info = now_playing["three_line"].get("line2", artist_info)
                        album_info  = now_playing["three_line"].get("line3", album_info)
                    elif "two_line" in now_playing and isinstance(now_playing["two_line"], dict):
                        track_info  = now_playing["two_line"].get("line1", track_info)
                        artist_info = now_playing["two_line"].get("line2", artist_info)
                    elif "one_line" in now_playing and isinstance(now_playing["one_line"], dict):
                        track_info = now_playing["one_line"].get("line1", track_info)
                    
                # Log track information
                logger.info(f"Now Playing: {track_info} - {artist_info} - {album_info}")
                
                # Fetch and display the album art
                self.fetch_and_display_album_art(image_key, track_info)
            else:
                logger.debug(f"Update contains the same image as is currently displayed")

        except Exception as e:
            logger.error(f"Error processing now_playing data: {e}")
            logger.debug(f"Now playing data that caused error: {str(now_playing)[:200]}...")
    
    def fetch_and_display_album_art(self, image_key, track_info):
        """Fetch album art from Roon and save it"""
        try:
            # Create a file path for the image
            image_path = getSavedImageDir() / f"album_art_{image_key}.jpg"
            
            if os.path.exists(image_path):
                logger.debug(f"File already exists at {image_path}")
                img = None
            else:
                # Fetch the image from Roon
                image_url = self.roon.get_image(image_key, "fit", self.viewer.image_size, self.viewer.image_size)
                logger.info(f"Fetching album art from: {image_url}")
                response = self.download_image(image_url)

                # Write the image first so we can load it properly
                # Converting bytes directly to an image doesn't seem to work well
                with open(image_path, 'wb') as file:
                    file.write(response)

                img = Image.open(image_path)

                # Apply image rendering effects
                if not (self.viewer.contrast_adjustment       == 1 and
                        self.viewer.colour_balance_adjustment == 1 and
                        self.viewer.brightness_adjustment     == 1 and
                        self.viewer.sharpness_adjustment     == 1):
                    img = self.tweak_image(img)

                # Cache image for later
                img.save(image_path)
                logger.info(f"Successfully saved album art to {image_path}")

            # Update the current image id 
            setCurrentImageKey(image_key)
            
            logger.debug("Updating viewer")
            # Update image display
            self.viewer.update(image_path, img, track_info)
                
        except Exception as e:
            logger.error(f"Error fetching album art: {e}")


    def download_image(self, image_url):
        try:
            # Send GET request to the image URL
            response = requests.get(image_url, stream=True)
            
            # Check if the request was successful
            response.raise_for_status()
                    
            logger.debug(f"Image successfully downloaded")
            return response.content
            
        except requests.exceptions.RequestException as e:
            logger.exception(f"Error downloading image: {e}")
            return False

    def tweak_image(self, img):
        logger.debug('Starting image tweaking')
        
        # Check if img is actually a PIL Image object
        try:
            if not hasattr(img, 'mode') or not callable(getattr(img, 'convert', None)):
                logger.error(f'Input is not a valid PIL Image: {type(img)}')
                return img
                
            logger.debug(f'Image type: {type(img)}, mode: {img.mode}, size: {img.size}')
            
            # Make a copy of the image to avoid modifying the original
            img = img.copy()
            
            # Apply enhancements with additional error checking
            if self.viewer.colour_balance_adjustment != 1:
                logger.debug('Creating color enhancer...')
                enhancer = ImageEnhance.Color(img)
                logger.debug('Applying color enhancement...')
                img = enhancer.enhance(self.viewer.colour_balance_adjustment)
                logger.debug('Color enhancement complete')
            
            if self.viewer.contrast_adjustment != 1:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(self.viewer.contrast_adjustment)
            
            if self.viewer.brightness_adjustment != 1:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(self.viewer.brightness_adjustment)
            
            if self.viewer.sharpness_adjustment != 1:
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(self.viewer.sharpness_adjustment)
            
            logger.debug('Image tweaking completed successfully')
            return img
        
        except Exception as e:
            import traceback
            logger.error(f'Error during image enhancement: {str(e)}')
            logger.error(traceback.format_exc())
            # Return the original image if enhancement fails
            return img
    
    
    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")
        if self.current_image_path and self.current_image_path.exists():
            try:
                os.remove(self.current_image_path)
            except:
                pass
        
        # Unsubscribe from notifications
        if self.roon:
            print("Disconnecting from Roon...")
            self.roon.stop()
    
    def run(self):
        """Run the application"""
        # Subscribe to events first
        self.subscribe_to_events()
        
        # Start API listener in a separate thread
        api_thread = threading.Thread(
            target=self.event_loop  # Call the event_loop method directly
        )
        api_thread.start()

    def event_loop(self):
        try:
            logger.info("Event loop started")
            while self.running:
                # Don't use 100% CPU
                time.sleep(0.1)
        except Exception as e:
            logger.exception(f"Error in event loop: {e}")
        finally:
            # Clean up
            self.cleanup()




###########################################################################
###########################################################################
###   Handles communication with Roon, calls viewer for image updates   ###
###########################################################################
###########################################################################
class RoonFrameConfig:
    def __init__(self):
        self.config =  self.load_config()

    def load_config(self):
        """Load configuration from roon.cfg file"""
        if not Path(cfgpath).exists():
            logger.info(f"Configuration file {cfgpath} not found. Creating default config.")
            self.create_default_config(cfgpath)
        
        config = configparser.ConfigParser()
        config.read(cfgpath)
        
        logger.info("Configuration loaded")
        
        return config
    
    def create_default_config(self, config_path):
        """Create a default configuration file"""
        config = configparser.ConfigParser()
        
        config['APP'] = {
            'extension_id'   : 'python_roon_album_display',
            'display_name'   : 'Album Art Display',
            'display_version': '1.0.0',
            'publisher'      : 'Richard Kemp',
            'email'          : 'richardtkemp@gmail.com'
        }
        
        config['DISPLAY'] = {
            'type' : 'epd13in3E'
            ## TODO config not reading properly?
            #  - 'system_display': Standard display connected to your computer (monitor, laptop screen, TV, etc.)
            #  - 'epd13in3E'     : Waveshare Spectra 6 13.3 inch
        }

        config['IMAGE_RENDER'] = {
            'colour_balance_adjustment': '1',
            'contrast_adjustment'      : '1',
            'sharpness_adjustment'     : '1',
            'brightness_adjustment'    : '1'
        }

        config['IMAGE_POSITION'] = {
            'position_offset_x': '0',
            'position_offset_y': '0',
            'scale_x'          : '1',
            'scale_y'          : '1',
            'rotation'         : '270'
        }
        
        config['ZONES'] = {
            'allowed_zone_names': 'comma,separated,list of zone names',
            'forbidden_zone_names': 'comma,separated,list of zone names'
        }
        
        with open(config_path, 'w') as f:
            config.write(f)
        
        logger.info(f"Default configuration created at {config_path}")
        logger.info(f"Please check it and re-run")
        sys.exit(0)



## Change log level on RoonApiWebSocket.send_request
# Store the original method
#original_send_request = RoonApiWebSocket.send_request
## Adapted from https://github.com/pavoni/pyroon/blob/master/roonapi/roonapisocket.py
#def custom_send_request(self, command, body=None, content_type="application/json", header_type="REQUEST"):
#    """Send request to the roon sever."""
#    if not self.connected:
#        LOGGER.warning("Connection is not (yet) ready!") # This is the only change, I want this to be warn not err
#        return False
#    request_id = self._requestid
#    self._requestid += 1
#    self._results[request_id] = None
#    if body is None:
#        msg = "MOO/1 REQUEST %s\nRequest-Id: %s\n\n" % (command, request_id)
#    else:
#        body = json.dumps(body)
#        msg = (
#            "MOO/1 REQUEST %s\nRequest-Id: %s\nContent-Length: %s\nContent-Type: %s\n\n%s"
#            % (command, request_id, len(body), content_type, body)
#        )
#    msg = bytes(msg, "utf-8")
#    self._socket.send(msg, 0x2)
#    return request_id
## Replace the original method with the custom one
#RoonApiWebSocket.send_request = custom_send_request





if __name__ == "__main__":
    dir = getSavedImageDir()
    if not os.path.exists(dir):
       os.mkdir(dir)

    # Load config
    config = RoonFrameConfig().config

    display_type = config.get('DISPLAY', 'type')
    if display_type == 'system_display':
        logger.info(f"Importing tkinter")
        import tkinter as tk           # aka tk
        from PIL import ImageTk
        # Set up the Tkinter display
        root = tk.Tk()
        viewer = TkViewer(config, root)
    elif display_type == 'epd13in3E':
        # Import the appropriate module
        logger.debug(f"Importing {display_type}")
        eink = importlib.import_module('libs.' + display_type)
        logger.debug(f"Finished importing {display_type}")
        viewer = EinkViewer(config, eink)
        logger.debug('Created viewer')
        
    
    # Create and start API connection on separate thread
    # Tkinter has to run it's loop on the main thread!
    display = RoonAlbumArt(config, viewer)
    display.run()
    
    # Now start the UI loop on the main thread
    try:
        if display_type == 'system_display':
            # Start periodic check for image updates for Tkinter
            viewer.check_pending_updates()
            viewer.root.mainloop()
    except KeyboardInterrupt:
        print("Shutting down...")
        ui.running = False
        api.stop()

