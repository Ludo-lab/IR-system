import sys
from machine import Pin, PWM
import time
from time import sleep_ms, sleep
from zacwire_TSic716 import ZACwire
from PID import PID
import re


# Set DAC for LDR
pin15 = Pin(15,Pin.OUT)
pwm15 = PWM(pin15)
pwm15.freq(10_000)
pwm15.duty_u16(35_000) # 2600 max, 30_000 min, resistor 300 ohm R2
# Set PWM for Til111
pin14 = Pin(14,Pin.OUT)
pwm14 = PWM(pin14)
pwm14.freq(1_000)
pwm14.duty_u16(35_000)
# Set comm for TSic716
zw = ZACwire(pin = 2, start = True,timeout=6)

# Set PID PWM

pwmPIN = pwm15
pwmPIN.duty_u16(64_000)



import sys,uselect
spoll=uselect.poll()
spoll.register(sys.stdin,uselect.POLLIN)

def myread():
    return(sys.stdin.read(1) if spoll.poll(0) else None)

def myreadline():
    bit = myread()
    if bit:
        msg = []
        while True:
            msg += bit
            bit = myread()
            if ['\n', '\n'] == msg[-2:]:
                parsed = "".join([x for x in msg if "\"" not in x if "\n" not in x])
                #print(msg)
                msg = []
                return parsed
                break
            else:
                pass
    else:
        return None

sys.stdout.write(f"PID ready\n")
while True:
    msg = myreadline()
    if msg:
        if "hello" in msg:
            sys.stdout.write(f"PID ready\n")

        elif "setpoint_" in msg:
            sys.stdout.write("RECEIVED Setpoint\n")
            sys.stdout.write(f"Message received: {msg}\n")
            try:
                setpoint = int(re.search("setpoint_([0-9]*)",msg).group(1))
                sys.stdout.write("PARSED Setpoint\n")
            except:
                setpoint = 15
                sys.stdout.write("/!\ UNPARSED Setpoint\n")

            pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')
            while True:
                T = zw.T() 						# Get temperature
                control = pid(T) 				# Input temperature in PID
                pwmPIN.duty_u16(int(control)) 	# Get PID control
                string = f"setpoint: {setpoint}, measured: {float(T)}, PWM: {float(control)}\n"
                sys.stdout.write(string)
                msg = myreadline()
                if msg:
                    if "setpoint_" in msg:
                        sys.stdout.write("RECEIVED Setpoint\n")
                        sys.stdout.write(f"Message received: {msg}\n")
                        try:
                            setpoint = int(re.search("setpoint_([0-9]*)",msg).group(1))
                            sys.stdout.write("PARSED Setpoint\n")
                        except:
                            setpoint = 15
                            sys.stdout.write("/!\ UNPARSED Setpoint\n")
                        
                        pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')
                        sys.stdout.write("UPDATED Setpoint\n")
                    elif "hello" in msg:
                        sys.stdout.write(f"PID ready\n")
                        break
                        
                    elif "stop" in msg:
                        VALUE = 64_000
                        pwmPIN.duty_u16(VALUE)
                        sys.stdout.write(f"STOPING\n PWM set to: {VALUE}\n")
                        break
                
                else:
                    sleep_ms(500)     
    else:
        time.sleep(1)






















"""
## Working while true polling, non blocking
import sys,uselect
spoll=uselect.poll()
spoll.register(sys.stdin,uselect.POLLIN)

def myread():
    return(sys.stdin.read(1) if spoll.poll(0) else None)

def myreadline():
    bit = myread()
    if bit:
        msg = []
        while True:
            msg += bit
            bit = myread()
            if ['\n', '\n'] == msg[-2:]:
                parsed = "".join([x for x in msg if "\"" not in x if "\n" not in x])
                #print(msg)
                msg = []
                return parsed
                break
            else:
                pass
    else:
        return None

while True:
    msg = myreadline()
    if msg:
        print(msg)
    else:
        time.sleep(0.1)

###################################################
#### working read non blocking
import sys,uselect
spoll=uselect.poll()
spoll.register(sys.stdin,uselect.POLLIN)
def read1():
    return(sys.stdin.read(1) if spoll.poll(0) else None)

   
sys.stdout.write("PID ready\n")   
msg = []
while True:
    bit = read1()
    if bit:    
        msg +=bit
        if ['\n', '\n'] == msg[-2:]:
            parsed = "".join([x for x in msg if "\"" not in x if "\n" not in x])
            #print(msg)
            print(parsed)
            msg = []
#        except:
#            pass
    else:
        time.sleep(0.1)

####################################################

# 
while True:
    sys.stdout.write("PID ready\n")
    
    try:
        msg = sys.stdin.readline()
    if "setpoint_" in msg:
        sys.stdout.write("RECEIVED Setpoint\n")
        sys.stdout.write(f"Message received: {msg}")
        try:
            setpoint = int(re.search("setpoint_([0-9]*)\n",msg).group(1))
            sys.stdout.write("PARSED Setpoint\n")
        except:
            setpoint = 15
            sys.stdout.write("/!\ UNPARSED Setpoint\n")

        pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')
        while True:
            T = zw.T() 						# Get temperature
            control = pid(T) 				# Input temperature in PID
            pwmPIN.duty_u16(int(control)) 	# Get PID control
            string = f"setpoint: {setpoint}, measured: {T}, PWM: {control}\n"
            sys.stdout.write(string)
            msg = sys.stdin.readline()
            if "setpoint_" in msg:
                sys.stdout.write("UPDATING Setpoint\n")
                try:
                    setpoint = int(re.search("setpoint_([0-9]*)\n",msg).group(1))
                    sys.stdout.write("PARSED Setpoint\n")
                except:
                    setpoint = 15
                    sys.stdout.write("/!\ UNPARSED Setpoint\n")
                
                pid = PID(Kp=-5000, Ki=-4000, Kd=-4000, setpoint=setpoint, sample_time=500,output_limits=[4000, 64_000] , scale='ms')
                sys.stdout.write("UPDATED Setpoint\n")
            elif "stop" in msg:
                pwmPIN.duty_u16(64_000)
                sys.stdout.write("STOPING\n")
                continue
            
            else:
                sleep_ms(500)     
    else:
        time.sleep(1)
        pass
"""


        







