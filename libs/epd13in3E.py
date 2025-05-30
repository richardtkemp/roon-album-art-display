# /*****************************************************************************
# * | File        :	  epd12in48.py
# * | Author      :   Waveshare electrices
# * | Function    :   Hardware underlying interface
# * | Info        :
# *----------------
# * |	This version:   V1.0
# * | Date        :   2019-11-01
# * | Info        :   
# ******************************************************************************/
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
import time
import sys
import logging
import epdconfig

import PIL
from PIL import Image
import io
import inspect


EPD_WIDTH       = 1200
EPD_HEIGHT      = 1600

log_format = '%(asctime)s [%(levelname)-7s] %(name)-12s: %(message)s [[%(funcName)s]]'
# Configure logging
logging.basicConfig(
    level = logging.DEBUG,
    format = log_format,
    handlers = [logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("epd13in3E")

def getParent():
    frame = inspect.currentframe().f_back.f_back
    return frame.f_code.co_name

class EarlyExit(Exception):
    logger.debug("Exiting early")
    pass

class EPD():
    def __init__(self):
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        self.BLACK  = 0x000000   #   0000  BGR
        self.WHITE  = 0xffffff   #   0001
        self.YELLOW = 0x00ffff   #   0010
        self.RED    = 0x0000ff   #   0011
        self.BLUE   = 0xff0000   #   0101
        self.GREEN  = 0x00ff00   #   0110
        
        self.EPD_CS_M_PIN  = epdconfig.EPD_CS_M_PIN
        self.EPD_CS_S_PIN  = epdconfig.EPD_CS_S_PIN

        self.EPD_DC_PIN  = epdconfig.EPD_DC_PIN
        self.EPD_RST_PIN  = epdconfig.EPD_RST_PIN
        self.EPD_BUSY_PIN  = epdconfig.EPD_BUSY_PIN
        self.EPD_PWR_PIN  = epdconfig.EPD_PWR_PIN

        self.should_stop = False
        # In case the script somehow restarts while the display is powered on,
        # shut it down here
        # segfaults: self.writePower(False, "Startup")
        # Dangerous? TODO
        self.powered_on = False

    
    def Reset(self):
        epdconfig.digital_write(self.EPD_RST_PIN, 1) 
        time.sleep(0.03) 
        epdconfig.digital_write(self.EPD_RST_PIN, 0) 
        time.sleep(0.03) 
        epdconfig.digital_write(self.EPD_RST_PIN, 1) 
        time.sleep(0.03) 
        epdconfig.digital_write(self.EPD_RST_PIN, 0) 
        time.sleep(0.03) 
        epdconfig.digital_write(self.EPD_RST_PIN, 1) 
        time.sleep(0.03) 

    # CS = chip select
    def CS_ALL(self, Value):
        epdconfig.digital_write(self.EPD_CS_M_PIN, Value)
        epdconfig.digital_write(self.EPD_CS_S_PIN, Value)

    def SendCommand(self, Command):
        epdconfig.spi_writebyte(Command)

    def SendData(self, Data):
        epdconfig.spi_writebyte(Data)
    
    def SendData2(self, buf, Len):
        epdconfig.spi_writebyte2(buf, Len)

    def ReadBusyH(self, where, observe_stop_flag=True):
        logger.debug(f"e-Paper busy H checking at {where}")
        while(epdconfig.digital_read(self.EPD_BUSY_PIN) == 0):      # 0: busy, 1: idle
            if observe_stop_flag and self.should_stop:
                return
            epdconfig.delay_ms(100)
        logger.debug(f"e-Paper busy H released at {where}")

    def writePower(self, state, title, stop=True):
        if state == True:
            name = "on"
            cmd  = 0x04
        elif state == False:
            name = "off"
            cmd  = 0x02
        else:
            logger.error(f"Invalid input: {state} for {title}")
            return

        logger.debug(f"Write power {name} starting for {title}") # Power on
        self.CS_ALL(0)
#        self.returnFunc(title)
        self.SendCommand(cmd)
#        self.returnFunc(title)
        if state == False:
            self.SendData(0x00)
#            self.returnFunc(title)
        self.CS_ALL(1)
#        self.returnFunc(title)
        self.ReadBusyH(f"[[{getParent()}]] for {title}", stop)
        self.powered_on = state

    def writeDRF(self, title):
        logger.debug(f"Write DRF for {title}") # Display refresh
        self.CS_ALL(0)
        self.returnFunc("1 "+title)
        self.SendCommand(0x12)
        self.returnFunc("2 "+title)
        self.SendData(0x00)
        self.returnFunc("3 "+title)
        self.CS_ALL(1)
        self.returnFunc("4 "+title)
        self.ReadBusyH(f"Write DRF {title}", True)
        self.returnFunc("5 "+title)

    def updateDisplay(self, title):
        try:
            if self.powered_on == False:
                logger.debug(f"POWER ON = {self.powered_on}")
                self.writePower(True, title, not self.powered_on)

            epdconfig.delay_ms(50)

            self.writeDRF(title)

            self.writePower(False, title)
            logger.debug(f"Write to display complete for {title}")

        except EarlyExit:
            return

    def Init(self):
        logger.debug("EPD init...")
        epdconfig.module_init()
        
        self.Reset() 
        self.ReadBusyH("EPD init")

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x74)
        self.SendData(0xC0)
        self.SendData(0x1C)
        self.SendData(0x1C)
        self.SendData(0xCC)
        self.SendData(0xCC)
        self.SendData(0xCC)
        self.SendData(0x15)
        self.SendData(0x15)
        self.SendData(0x55)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0xF0)
        self.SendData(0x49)
        self.SendData(0x55)
        self.SendData(0x13)
        self.SendData(0x5D)
        self.SendData(0x05)
        self.SendData(0x10)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0x00)
        self.SendData(0xDF)
        self.SendData(0x69)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0x50)
        self.SendData(0xF7)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0x60)
        self.SendData(0x03)
        self.SendData(0x03)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0x86)
        self.SendData(0x10)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0xE3)
        self.SendData(0x22)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0xE0)
        self.SendData(0x01)
        self.CS_ALL(1)

        self.CS_ALL(0)
        self.SendCommand(0x61)
        self.SendData(0x04)
        self.SendData(0xB0)
        self.SendData(0x03)
        self.SendData(0x20)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x01)
        self.SendData(0x0F)
        self.SendData(0x00)
        self.SendData(0x28)
        self.SendData(0x2C)
        self.SendData(0x28)
        self.SendData(0x38)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0xB6)
        self.SendData(0x07)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x06)
        self.SendData(0xE8)
        self.SendData(0x28)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0xB7)
        self.SendData(0x01)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x05)
        self.SendData(0xE8)
        self.SendData(0x28)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0xB0)
        self.SendData(0x01)
        self.CS_ALL(1)

        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0xB1)
        self.SendData(0x02)
        self.CS_ALL(1)
    
    def getbuffer(self, image):
        # Create a pallette with the 7 colors supported by the panel
        pal_image = Image.new("P", (1,1))
        # original
        pal_image.putpalette( (0,0,0,  255,255,255,  255,255,0,  255,0,0,  0,0,0,  0,0,255,  0,255,0) + (0,0,0)*249)
        # claude suggests
        #pal_image.putpalette((25,30,33, 241,241,241, 49,49,143, 83,164,40, 210,14,19, 184,94,28, 243,207,17) + (0,0,0)*249)
        pal_image.putpalette((0,0,0, 255,255,255, 255,236,35, 209,0,0, 0,0,0, 35,35,255, 0,208,65) + (0,0,0)*249)
        # not sure?
        #pal_image.putpalette((0,0,0,  255,255,255,  0,255,0,   0,0,255,  255,0,0,  255,255,0, 255,128,0) + (0,0,0)*249)

        # Check if we need to rotate the image
        imwidth, imheight = image.size
        if(imwidth == self.width and imheight == self.height):
            image_temp = image
        elif(imwidth == self.height and imheight == self.width):
            image_temp = image.rotate(90, expand=True)
        else:
            logger.error("Invalid image dimensions: %d x %d, expected %d x %d" % (imwidth, imheight, self.width, self.height))

        # Convert the soruce image to the 7 colors, dithering if needed
        image_7color = image_temp.convert("RGB").quantize(palette=pal_image)
        buf_7color = bytearray(image_7color.tobytes('raw'))

        # PIL does not support 4 bit color, so pack the 4 bits of color
        # into a single byte to transfer to the panel
        buf = [0x00] * int(self.width * self.height / 2)
        idx = 0
        for i in range(0, len(buf_7color), 2):
            buf[idx] = (buf_7color[i] << 4) + buf_7color[i+1]
            idx += 1
            
        return buf
    
    def Clear(self, color=0x11):
        epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
        self.SendCommand(0x10)
        for i in range(self.height):
            self.SendData2([color]* int(self.width/2), int(self.width/2))
        self.CS_ALL(1)
        epdconfig.digital_write(self.EPD_CS_S_PIN, 0)
        self.SendCommand(0x10)
        for i in range(self.height):
            self.SendData2([color]* int(self.width/2), int(self.width/2))
        self.CS_ALL(1)

        self.writePower(True, "Clear")

    def returnFunc(self, title):
        if self.should_stop:
            logger.info(f"Returning early from [[{getParent()}]] due to should_stop for {title}")
            epdconfig.digital_write(self.EPD_BUSY_PIN, 1) 
            self.should_stop = False
            raise EarlyExit()

    def display(self, image, title):
        try:
            Width  = int(self.width / 4)
            Width1 = int(self.width / 2)

            self.ReadBusyH(f"Starting [[{getParent()}]] {title}")
            logger.debug(f"Sending data 1 for {title}")
            self.CS_ALL(1)
            self.returnFunc("1 "+title)
            epdconfig.digital_write(self.EPD_CS_M_PIN, 0)
            self.returnFunc("2 "+title)
            self.SendCommand(0x10)
            self.returnFunc("3 "+title)
            for i in range(self.height):
                self.SendData2(image[i * Width1 : i * Width1+Width], Width)
                self.returnFunc("4 "+title)
            self.CS_ALL(1)
            self.returnFunc("5 "+title)

            logger.debug(f"Sending data 2 for {title}")
            epdconfig.digital_write(self.EPD_CS_S_PIN, 0)
            self.returnFunc("6 "+title)
            self.SendCommand(0x10)
            self.returnFunc("7 "+title)
            for i in range(self.height):
                self.SendData2(image[i * Width1+Width : i * Width1+Width1], Width)
                self.returnFunc("8 "+title)
            self.CS_ALL(1)
            self.returnFunc("9 "+title)

            self.updateDisplay(title)

        except EarlyExit:
            return

    def sleep(self):
        self.CS_ALL(0)
        self.SendCommand(0x07)
        self.SendData(0XA5)
        self.CS_ALL(1)

        epdconfig.delay_ms(2000)
        epdconfig.module_exit()
### END OF FILE ###


