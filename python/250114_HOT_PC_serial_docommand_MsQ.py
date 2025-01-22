# -*- coding: utf-8 -*-
"""
Created on Fri Nov 15 15:31:48 2024

@author: carac001
"""

import numpy as np
import json
from glob import glob
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.stats import ttest_ind, ttest_ind_from_stats

from datetime import datetime
import re
import pandas as pd 
import seaborn as sns
from scipy.ndimage import median_filter
from time import localtime, strftime
import matplotlib.pylab as pl
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import os, webbrowser, glob
import serial
import sys
import time
import itertools

today = datetime.today().strftime('%Y%m%d')[2:]


def serial_ports():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def findMsQ():
    for port in serial_ports():
        with serial.Serial(port, baudrate=115200, timeout = 1) as ser:
            ser.write("hello".encode())
            answer = ser.readline().decode()
            # print(port, answer)
            if answer == "MultispeQ Ready\n":
                return port
            else:
                pass 
            
def findPID():
    TRIALS = 10 # number of read trials, other 
    for port in serial_ports():
        with serial.Serial(port, baudrate=115200, timeout = 1) as ser:
           ser.write("\"hello\n\n\"".encode())
           answer = ser.readline()
           for i in range(TRIALS):
               if b"" != answer:
                   # print(port, answer)
                   if b'PID ready\r\n' == answer:
                       return port
                   else:
                       answer = ser.readline()

def do_MsQcommand(PORT,string):
    with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
        ser.setRTS(False)
        ser.write(f"{string}".encode())
        response = ser.readline().decode()
        return response

def do_PIDcommand(PORT,string):
    with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
        ser.setRTS(False)
        ser.write(f"\"{string}\"\n\n".encode())
        response = ser.readline().decode()
        return response
    
def do_MsQprotocol(PORT,string):
    with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
        ser.setRTS(False)
        ser.write(f"{string}".encode())
        
        response = []
        while True:
            bt = ser.readline().decode()
            response += bt
            # print(bt)
            if re.match(".*}[A-Z,0-9]{8}",bt):
                break
        return response
    
def parse_response(response):
    a = ''.join(map(str, response)).replace("\n","")
    a = re.search(r"data:\[(.*)\]",a).group(1)
    a = a.split(",")
    a = [float(x) for x in a]
    a = [int(x) for x in a]
    return a

def response_json(response):
    import json
    s = ''.join(map(str, response)).replace("\n","")[:-8]
    j = json.loads(s)
    return j

###############################################################################

import matplotlib as mpl
import matplotlib.cm as cm
   
norm = mpl.colors.Normalize(vmin=20, vmax=30)
cmap = cm.viridis
m = cm.ScalarMappable(norm=norm, cmap=cmap)



OUTDIR = f"../../../Data/multispeq/{today}/" # output directory

result = []
for filename in os.listdir(OUTDIR)[-8:]:
    with open(os.path.join(OUTDIR,filename)) as f:
        data = json.load(f)
        
    y = np.array(data["sample"][0]["set"][0]["data_raw"])
    x = np.arange(len(y))
    fo = np.round(np.mean(y[:20]),3)
    fm = np.round(np.mean(y[1500:1520]),3)
    fv = fm-fo
    fvfm = np.round(fv/fm,3)
    temp = float(re.search(".*_setpoint([0-9]{2})_.*",filename).group(1))
    result.append([filename,temp,fo,fm,fvfm])
    plt.plot(x,y,c=m.to_rgba(temp),label=f"{temp}°C")
    plt.ylim([0,100])
    
    # plt.title(f"{filename}")

plt.xlim([0,300])
handles, labels = plt.gca().get_legend_handles_labels()
by_label = dict(zip(labels, handles))
plt.legend(by_label.values(), by_label.keys())
plt.ylabel("Rel. Fluo. Yield")
plt.xlabel("Pulse number")
plt.show()

df = pd.DataFrame(result,columns=["filename","temp","fo","fm","fvfm"])

###############################################################################


# STRING_MsQprotocol = "[{\"v_arrays\":[[100,1000,10000],[100,100,100],[0,0,0]],\"share\":1,\"set_repeats\":1,\"_protocol_set_\":[{\"label\":\"phi2\",\"nonpulsed_lights\":[[2],[2],[2]],\"nonpulsed_lights_brightness\":[[0],[-2000],[0]],\"pulsed_lights\":[[1],[1],[1]],\"detectors\":[[1],[1],[1]],\"pulses\":[60,2000,60],\"pulse_distance\":[250000,750,250000],\"pulsed_lights_brightness\":[[-200],[-200],[-200]],\"pulse_length\":[[10],[10],[10]],\"protocol_averages\":1,\"protocol_repeats\":1,\"environmental\":[[\"light_intensity\"],[\"contactless_temp\"],[\"thp\"],[\"thp2\"]]}]}]"

# RANGE_TEMP = [22]   # range of temperature 
# REP = 2
# STABILIZE =  60*10         # seconds 
# OUTDIR = f"../../../Data/multispeq/{today}/" # output directory
# SAVE = True


# PORT_MS = findMsQ()
# PORT_PID = findPID()
# assert PORT_MS != None
# assert PORT_PID != None

# for RANGE_TEMP_VALUE in RANGE_TEMP:
#     for _idx in range(REP):
#         STRING_PIDsetpoint = f"setpoint_{RANGE_TEMP_VALUE}"
#         print("SETING SETPOINT TO: ", STRING_PIDsetpoint)
#         with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#             ser.setRTS(False)
#             ser.write(f"\"{STRING_PIDsetpoint}\n\n\"".encode())
            
#             while True:
#                 TRIALS = 10
#                 for i in range(TRIALS):
#                     msg = ser.readline()
#                     if msg:
#                         try:
#                             setpoint = int(re.search("setpoint: ([0-9]*),",msg.decode()).group(1))
#                             measured = float(re.search(".*measured: ([0-9]*\.[0-9]*).*",msg.decode()).group(1))
#                             pwm = float(re.search(".*PWM: ([0-9]*\.[0-9]*)\r\n",msg.decode()).group(1))
#                             print("READING: ",setpoint,measured,pwm)
#                             break
#                         except:
#                             print(f"FAILED to read, value message: {msg}")
#                             msg = ser.readline()
#                             time.sleep(0.5)
#                     else:
#                         print("NO messages")
#                         msg = ser.readline()
    
#                         time.sleep(0.5)
                
#                 if abs(measured - setpoint) < 0.5:
#                     print("READY to protocol")
#                     break
            
#             print("STABILIZING")
#             time.sleep(STABILIZE) # delay to stabilize
#             print("PROTOCOLLING")
#             ser.write("\"stop\n\n\"".encode())
#             data = do_MsQprotocol(PORT_MS, STRING_MsQprotocol)
            
#             myjson = response_json(data)
#             y = np.array(myjson["sample"][0]["set"][0]["data_raw"])
#             x = np.arange(len(y))
#             # Plot
#             plt.plot(x,y)
#             plt.title(f"{today}\nsetpoint: {setpoint}, measured: {measured}, stabilize: {STABILIZE}s")
#             plt.show()
#             if SAVE:
#                 if not os.path.exists(OUTDIR):
#                     os.mkdir(OUTDIR)
#                 FIDX = "{:03d}".format(len(os.listdir(OUTDIR)))
#                 filename = f"{today}_{FIDX}_HOT_setpoint{setpoint}_stabilize{STABILIZE}.json"
#                 with open(OUTDIR+filename, 'w', encoding='utf-8') as f:
#                     json.dump(myjson, f, ensure_ascii=False, indent=4)
    











#############################################################



# STRING_MsQprotocol = "[{\"v_arrays\":[[100,1000,10000],[100,100,100],[0,0,0]],\"share\":1,\"set_repeats\":1,\"_protocol_set_\":[{\"autogain\":[[1,1,1,10,500]],\"do_once\":1},{\"label\":\"phi2\",\"nonpulsed_lights\":[[2],[2],[2]],\"nonpulsed_lights_brightness\":[[0],[-2000],[0]],\"pulsed_lights\":[[1],[1],[1]],\"detectors\":[[1],[1],[1]],\"pulses\":[60,2000,60],\"pulse_distance\":[250000,750,250000],\"pulsed_lights_brightness\":[[-200],[-200],[-200]],\"pulse_length\":[[10],[10],[10]],\"protocol_averages\":1,\"protocol_repeats\":1,\"environmental\":[[\"light_intensity\"],[\"contactless_temp\"],[\"thp\"],[\"thp2\"]]}]}]"

# STABILIZE =  0                      # seconds 
# OUTDIR = f"../../../Data/multispeq/{today}/" # output directory
# SAVE = True
# REP = 2


# PORT_MS = findMsQ()
# PORT_PID = findPID()
# assert PORT_MS != None
# assert PORT_PID != None

# for _idx in range(REP):
#     with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#         ser.setRTS(False)
#         ser.write("\"setpoint_NA\n\n\"".encode())
#         TRIALS = 10
#         for i in range(TRIALS):
#             msg = ser.readline()
#             if msg:
#                 try:
#                     setpoint = int(re.search("setpoint: ([0-9]*),",msg.decode()).group(1))
#                     measured = float(re.search(".*measured: ([0-9]*\.[0-9]*).*",msg.decode()).group(1))
#                     pwm = float(re.search(".*PWM: ([0-9]*\.[0-9]*)\r\n",msg.decode()).group(1))
#                     print("READING: ",setpoint,measured,pwm)
#                     break     
#                 except:
#                     print(f"FAILED to read, value message: {msg}")
#                     msg = ser.readline()
#                     time.sleep(0.5) 
#             else:
#                 print("NO messages")
#                 msg = ser.readline()
#                 time.sleep(0.5)
        
#         setpoint = "CONTROL"
#         time.sleep(STABILIZE) # delay to stabilize
#         print("PROTOCOLLING")
#         ser.write("\"stop\n\n\"".encode())
#         data = do_MsQprotocol(PORT_MS, STRING_MsQprotocol)
        
#         myjson = response_json(data)
#         autogain_index, autogain_pulsed_LED, autogain_detector, autogain_pulse_duration, autogain_pulse_intensity, target_value= myjson["sample"][0]["set"][0]["autogain"][0]
#         assert autogain_pulse_intensity < 0
#         y = np.array(myjson["sample"][0]["set"][1]["data_raw"])
#         fluo = y / (-1*autogain_pulse_duration*autogain_pulse_intensity)
#         x = np.arange(len(y))
#         # Plot
#         plt.plot(x,fluo)
#         # plt.title(f"{today}\nsetpoint: {setpoint}, measured: {measured}, stabilize: {STABILIZE}s")
#         # plt.show()
#         # Save
#         if SAVE:
#             if not os.path.exists(OUTDIR):
#                 os.mkdir(OUTDIR)
#             FIDX = "{:03d}".format(len(os.listdir(OUTDIR)))
#             filename = f"{today}_{FIDX}_HOT_setpoint{setpoint}_stabilize{STABILIZE}.json"
#             with open(OUTDIR+filename, 'w', encoding='utf-8') as f:
#                 json.dump(myjson, f, ensure_ascii=False, indent=4)

#     if _idx <REP-1:
#         time.sleep(60*10)
#     else:
#         pass




# for filename in os.listdir(OUTDIR)[-3:]:
    
#     with open(os.path.join(OUTDIR,filename)) as f:
#         data = json.load(f)
        
#     autogain_index, autogain_pulsed_LED, autogain_detector, autogain_pulse_duration, autogain_pulse_intensity, target_value= data["sample"][0]["set"][0]["autogain"][0]
#     y = np.array(data["sample"][0]["set"][1]["data_raw"])
#     fluo = y / (-1*autogain_pulse_duration*autogain_pulse_intensity)
#     x = np.arange(len(fluo))
#     plt.plot(x,fluo)
#     plt.title(f"{filename}")
#     plt.show()


#############################################################
    




"""
Range temperature
"""
# for RANGE_TEMP_VALUE in RANGE_TEMP:
#     STRING_PIDsetpoint = f"setpoint_{RANGE_TEMP_VALUE}"
#     print("SETING SETPOINT TO: ", STRING_PIDsetpoint)
#     with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#         ser.setRTS(False)
#         ser.write(f"\"{STRING_PIDsetpoint}\n\n\"".encode())
        
#         while True:
#             TRIALS = 10
#             for i in range(TRIALS):
#                 msg = ser.readline()
#                 if msg:
#                     try:
#                         setpoint = int(re.search("setpoint: ([0-9]*),",msg.decode()).group(1))
#                         measured = float(re.search(".*measured: ([0-9]*\.[0-9]*).*",msg.decode()).group(1))
#                         pwm = float(re.search(".*PWM: ([0-9]*\.[0-9]*)\r\n",msg.decode()).group(1))
#                         print("READING: ",setpoint,measured,pwm)
#                         break
#                     except:
#                         print(f"FAILED to read, value message: {msg}")
#                         msg = ser.readline()
#                         time.sleep(0.5)
#                 else:
#                     print("NO messages")
#                     msg = ser.readline()

#                     time.sleep(0.5)
            
#             if abs(measured - setpoint) < 0.5:
#                 print("READY to protocol")
#                 break
            
#         time.sleep(STABILIZE) # delay to stabilize
#         print("PROTOCOLLING")
#         ser.write("\"stop\n\n\"".encode())
#         data = do_MsQprotocol(PORT_MS, STRING_MsQprotocol)
        
#         myjson = response_json(data)
#         y = np.array(myjson["sample"][0]["set"][1]["data_raw"])
#         x = np.arange(len(y))
#         df = pd.DataFrame(np.array([x,y]).T,columns=["pulse_count", "fluo"])
#         # Plot
#         plt.plot(x,y)
#         plt.title(f"{today}\nsetpoint: {setpoint}, measured: {measured}, stabilize: {STABILIZE}s")
#         plt.show()
#         # Save
#         if SAVE:
#             if not os.path.exists(OUTDIR):
#                 os.mkdir(OUTDIR)
#             FIDX = len(os.listdir(OUTDIR))
#             filename = f"{today}_{FIDX}_HOT_setpoint{setpoint}_stabilize{STABILIZE}.csv"
#             df.to_csv(OUTDIR+filename)
    
    
    
    
    
    
    
    
    
"""
###############################################################################
##############################     BACKUP      ################################
###############################################################################
"""
####################  15 - 01 - 2025 ########################################


# def serial_ports():
#     """ Lists serial port names

#         :raises EnvironmentError:
#             On unsupported or unknown platforms
#         :returns:
#             A list of the serial ports available on the system
#     """
#     if sys.platform.startswith('win'):
#         ports = ['COM%s' % (i + 1) for i in range(256)]
#     elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
#         # this excludes your current terminal "/dev/tty"
#         ports = glob.glob('/dev/tty[A-Za-z]*')
#     elif sys.platform.startswith('darwin'):
#         ports = glob.glob('/dev/tty.*')
#     else:
#         raise EnvironmentError('Unsupported platform')

#     result = []
#     for port in ports:
#         try:
#             s = serial.Serial(port)
#             s.close()
#             result.append(port)
#         except (OSError, serial.SerialException):
#             pass
#     return result

# def findMsQ():
#     for port in serial_ports():
#         with serial.Serial(port, baudrate=115200, timeout = 1) as ser:
#             ser.write("hello".encode())
#             answer = ser.readline().decode()
#             # print(port, answer)
#             if answer == "MultispeQ Ready\n":
#                 return port
#             else:
#                 pass 
            
# def findPID():
#     TRIALS = 10 # number of read trials, other 
#     for port in serial_ports():
#         with serial.Serial(port, baudrate=115200, timeout = 1) as ser:
#            ser.write(f"\"hello\n\n\"".encode())
#            answer = ser.readline()
#            for i in range(TRIALS):
#                if b"" != answer:
#                    print(port, answer)
#                    if b'PID ready\r\n' == answer:
#                        return port
#                    else:
#                        answer = ser.readline()

# def do_MsQcommand(PORT,string):
#     with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
#         ser.setRTS(False)
#         ser.write(f"{string}".encode())
#         response = ser.readline().decode()
#         return response

# def do_PIDcommand(PORT,string):
#     with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
#         ser.setRTS(False)
#         ser.write(f"\"{string}\"\n\n".encode())
#         response = ser.readline().decode()
#         return response
    
# def do_MsQprotocol(PORT,string):
#     with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
#         ser.setRTS(False)
#         ser.write(f"{string}".encode())
        
#         response = []
#         while True:
#             bt = ser.readline().decode()
#             response += bt
#             # print(bt)
#             if re.match(".*}[A-Z,0-9]{8}",bt):
#                 break
#         return response
    
# def parse_response(response):
#     a = ''.join(map(str, response)).replace("\n","")
#     a = re.search(r"data:\[(.*)\]",a).group(1)
#     a = a.split(",")
#     a = [float(x) for x in a]
#     a = [int(x) for x in a]
#     return a

# def response_json(response):
#     import json
#     s = ''.join(map(str, response)).replace("\n","")[:-8]
#     j = json.loads(s)
#     return j

# STRING_MsQprotocol = "[{\"v_arrays\":[[100,1000,10000],[100,100,100],[0,0,0]],\"share\":1,\"set_repeats\":1,\"_protocol_set_\":[{\"autogain\":[[1,1,1,10,500]],\"do_once\":1},{\"label\":\"phi2\",\"nonpulsed_lights\":[[2],[2],[2]],\"nonpulsed_lights_brightness\":[[0],[-500],[0]],\"pulsed_lights\":[[1],[1],[1]],\"detectors\":[[1],[1],[1]],\"pulses\":[20,2000,20],\"pulse_distance\":[250000,750,250000],\"pulsed_lights_brightness\":[[\"a_b1\"],[\"a_b1\"],[\"a_b1\"]],\"pulse_length\":[[\"a_d1\"],[\"a_d1\"],[\"a_d1\"]],\"protocol_averages\":1,\"protocol_repeats\":1,\"environmental\":[[\"temperature_humidity_pressure\"],[\"light_intensity\"]]}]}]"
# # string2 = b"[{\"v_arrays\":[[100,1000,10000],[100,100,100],[0,0,0]],\"share\":1,\"set_repeats\":1,\"_protocol_set_\":[{\"autogain\":[[1,1,1,10,500]],\"do_once\":1},{\"label\":\"phi2\",\"nonpulsed_lights\":[[2],[2],[2]],\"nonpulsed_lights_brightness\":[[0],[-2000],[0]],\"pulsed_lights\":[[1],[1],[1]],\"detectors\":[[1],[1],[1]],\"pulses\":[20,2000,20],\"pulse_distance\":[250000,750,250000],\"pulsed_lights_brightness\":[[\"a_b1\"],[\"a_b1\"],[\"a_b1\"]],\"pulse_length\":[[\"a_d1\"],[\"a_d1\"],[\"a_d1\"]],\"protocol_averages\":1,\"protocol_repeats\":1,\"environmental\":[[\"temperature_humidity_pressure\"],[\"light_intensity\"]]}]}]"
    
# PORT_MS = findMsQ()
# PORT_PID = findPID()

# RANGE_TEMP = [25, 22, 30]
# STABILIZE = 5               # second to stabilize at a certain temperature



# assert PORT_MS != None
# assert PORT_PID != None

# for RANGE_TEMP_VALUE in RANGE_TEMP:
#     STRING_PIDsetpoint = f"setpoint_{RANGE_TEMP_VALUE}"
#     print("SETING SETPOINT TO: ", STRING_PIDsetpoint)
#     with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#         ser.setRTS(False)
#         ser.write(f"\"{STRING_PIDsetpoint}\n\n\"".encode())
        
#         while True:
#             TRIALS = 10
#             for i in range(TRIALS):
#                 msg = ser.readline()
#                 if msg:
#                     try:
#                         setpoint = int(re.search("setpoint: ([0-9]*),",msg.decode()).group(1))
#                         measured = float(re.search(".*measured: ([0-9]*\.[0-9]*).*",msg.decode()).group(1))
#                         pwm = float(re.search(".*PWM: ([0-9]*\.[0-9]*)\r\n",msg.decode()).group(1))
#                         print("READING: ",setpoint,measured,pwm)
#                         break
#                     except:
#                         print(f"FAILED to read, value message: {msg}")
#                         msg = ser.readline()
#                         time.sleep(0.5)
#                 else:
#                     print("NO messages")
#                     msg = ser.readline()

#                     time.sleep(0.5)
            
#             if abs(measured - setpoint) < 0.5:
#                 print("READY to protocol")
#                 break     
#         time.sleep(STABILIZE) # delay to stabilize
#         print("PROTOCOLLING")
#         ser.write("\"stop\n\n\"".encode())
#         data = do_MsQprotocol(PORT_MS, STRING_MsQprotocol)
#         myjson = response_json(data)
#         y = np.array(myjson["sample"][0]["set"][1]["data_raw"])
#         x = np.arange(len(y))
#         plt.plot(x,y)
#         plt.title(f"{today}\nsetpoint: {setpoint}, measured: {measured}")
#         plt.show()
#         # ser.close




##############################################################################


# string = f"setpoint_{RANGE_TEMP[0]}"
# with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#     ser.setRTS(False)
#     ser.write(f"\"setpoint_20\"\n\n".encode())
#     msg = ser.readline()
#     TRIALS = 10
#     for i in range(TRIALS):
#         if msg:
#             try:
#                 setpoint = int(re.search("setpoint: ([0-9]*),",msg.decode()).group(1))
#                 measured = float(re.search(".*measured: ([0-9]*\.[0-9]*).*",msg.decode()).group(1))
#                 pwm = float(re.search(".*PWM: ([0-9]*\.[0-9]*)\r\n",msg.decode()).group(1))
#                 break
#             except:
#                 print(f"FAILED to read, value message: {msg}")
#                 msg = ser.readline()
#                 time.sleep(0.5)
#         else:
#             print("No messages")
#             time.sleep(0.5)
#     print(setpoint,measured,pwm)
            
            
# data = do_protocol(PORT_MS, string)
# myjson = response_json(data)
# y = np.array(myjson["sample"][0]["set"][1]["data_raw"])
# x = np.arange(len(y))
# plt.plot(x,y)





