# all these imports come from MicroPython. https://docs.micropython.org/en/latest/index.html
from urandom import randint
import uselect
from machine import Pin, SPI, PWM, RTC
import framebuf
import time
import random
import gc
import math
from sys import stdin, exit
import micropython
import sys
from zacwire_TSic716 import ZACwire
from PID import PID
import re


# size of each letter in pixels
CHARACTER_SIZE = 8

# how serial lines are ended
TERMINATOR = "\n"


class Pico:
    """
    Global singleton, so we can use `self`. instead of global.
    Not sure if this will increase ram usage.
    """
    def __init__(self):
        """
        Run any once-off startup tasks.
        Set up the global PID object.
        Set up input.
        """
        # give a chance to break the boot to fix serial/code issues. Put any riskier startup code after this
        self.run_loop = True
        # store incomplete lines from serial here. list of strings (no typing module in micropython)
        self.buffered_input = []
        # when we get a full line store it here, without the terminator.
        # gets overwritten if a new line is read (as early as next tick).
        # blanked each tick.
        self.input_line_this_tick = ""
        
        self.pinPWM = PWM(Pin(15,Pin.OUT)) # enable PWM on control pin
        self.pinPWM.freq(10_000) # set PWM frequency
        self.pinPWM.duty_u16(64_000) # set duty cycle (higher fully dimmed)
        
        self.setpoint = 20 # set initial setpoint for PID, degrees
        self.pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=self.setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')

        
        self.zw = ZACwire(pin = 2, start = True,timeout=6) # initialize TSic16 on pin
        

        
        
    def main(self):
        """
        Code entrypoint.
        The function that gets called to start.
        All non-setup code here or in functions under it.
        """
        
        latest_input_line = ""
        # main loop
        while self.run_loop:
            # buffer from the USB to serial port
            self.read_serial_input()

            # show serial input on the screen.
            # only update if we have a new line
            if self.input_line_this_tick:
                latest_input_line = self.input_line_this_tick
                if "hello" == latest_input_line:
                    print("Hello PID here")
                elif "setpoint_" in latest_input_line:
                    print("Received setpoint")
                    try:
                        value = re.search("setpoint_([0-9]*.[0-9]*)",latest_input_line).group(1)
                        self.setpoint = float(value)
                        self.pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=self.setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')
                        print(f"Setpoint updated to: {value}")
                    except:
                        print(f"Can not parse setpoint, message was: {latest_input_line}")
                elif "query" == latest_input_line:
                     print(f"Setpoint: {self.setpoint}, Measured temp: {T}, PID feedback: {control}")

            # quit program to avoid locking serial up if specified
            if "stop" in latest_input_line:
                print("Stoping loop, fully dimming")
                self.pinPWM.duty_u16(64_000)
                self.exit()

            # simple loop speed control
            T = self.zw.T() # read temperature
            control = int(self.pid(T)) # get PID feedback control
            self.pinPWM.duty_u16(control) # update PWM pin
            
            time.sleep_ms(100)


    def read_serial_input(self):
        """
        Buffers serial input.
        Writes it to input_line_this_tick when we have a full line.
        Clears input_line_this_tick otherwise.
        """
        # stdin.read() is blocking which means we hang here if we use it. Instead use select to tell us if there's anything available
        # note: select() is deprecated. Replace with Poll() to follow best practises
        select_result = uselect.select([stdin], [], [], 0)
        while select_result[0]:
            # there's no easy micropython way to get all the bytes.
            # instead get the minimum there could be and keep checking with select and a while loop
            input_character = stdin.read(1)
            # add to the buffer
            self.buffered_input.append(input_character)
            # check if there's any input remaining to buffer
            select_result = uselect.select([stdin], [], [], 0)
        # if a full line has been submitted
        if TERMINATOR in self.buffered_input:
            line_ending_index = self.buffered_input.index(TERMINATOR)
            # make it available
            self.input_line_this_tick = "".join(self.buffered_input[:line_ending_index])
            # remove it from the buffer.
            # If there's remaining data, leave that part. This removes the earliest line so should allow multiple lines buffered in a tick to work.
            # however if there are multiple lines each tick, the buffer will continue to grow.
            if line_ending_index < len(self.buffered_input):
                self.buffered_input = self.buffered_input[line_ending_index + 1 :]
            else:
                self.buffered_input = []
        # otherwise clear the last full line so subsequent ticks can infer the same input is new input (not cached)
        else:
            self.input_line_this_tick = ""


    def exit(self):
        self.run_loop = False

    def on_key_a_pressed(self, p):
        print("key a pressed: ", p)


# start the code

pico = Pico()
pico.main()
# when the above exits, clean up
gc.collect()
