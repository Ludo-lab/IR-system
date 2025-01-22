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
from tqdm import tqdm



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

def ensure_path_exists(path: str) -> None:
    """
    Ensures that the given directory path exists.
    If it does not exist, this function will create it (including any intermediate directories).

    :param path: The directory path to check (and potentially create).
    """
    if not os.path.exists(path):
        print(f"Creating path: {path}")
        os.makedirs(path)
    else:
        print(f"{path} exist")


def findDevice(question="hello", answer="", flush=True, timeout=1):
    """
    Attempts to find a device on any available serial port by sending 
    a 'question' string and looking for an 'answer' substring in the response.
    If no matching device is found on any port, implicitly return None

    :param question: The message to send to the device (default: "hello").
    :param answer: The substring we expect in the device's response (default: "").
    :param flush: Whether to flush the serial buffer before sending the question (default: True).
    :param timeout: The read timeout for the serial port in seconds (default: 1).
    :return: The port where the expected 'answer' is found, or None if not found.
    """
    for port in serial_ports():     # Iterate through each potential serial port returned by 'serial_ports()'
        with serial.Serial(port, baudrate=115200, timeout=timeout) as ser:         # Open the serial port using a context manager to ensure it closes automatically

            # If flush is True, clear any existing data in the buffer 
            # and give a short delay to stabilize
            if flush:
                ser.flush()
                time.sleep(0.5)
        
            ser.write(question.encode()) # Encode and write the 'question' to the serial port
            time.sleep(0.5) # Allow some time for the device to respond
            
            msg = ser.readline().decode() # Read one line of response from the serial port, then decode it
            
            # If the expected 'answer' substring is in the device response, 
            # print and return the port
            print(msg)
            if answer in msg:
                print(f"Found device at: {port}, answer: {msg}")
                return port
       

def gen_cmd_arr_line(num: int, freq: int, actinic: int) -> list:
    """
    Generate a single command-array entry of 8 parameters.
        
    :param num: Total number of measurement points (10-2_000).
    :param freq: Frequency measurement points (1-200).
    :param actinic: Actinic light setting (0-255).
    :return: List of 8 integer values representing the command.
    """
    return [
        2,              # Fixed flag or identifier
        0,              # Another fixed flag or placeholder
        num // 256,     # High byte of 'num'
        num % 256,      # Low byte of 'num'
        freq // 256,    # High byte of 'freq'
        freq % 256,     # Low byte of 'freq'
        actinic,        # Actinic light parameter
        1               # Fixed flag or terminator
    ]

def calc_arr_param(cmd: list, persist: bool = False):
    """
    Reshape a flat command list into a 2D array, construct a command string,
    and calculate measurement timelines and actinic-array values.

    :param cmd: A 1D list of length 8*N (multiple commands concatenated).
    :param persist: A flag indicating whether the command persists after completion.
    :return: Tuple (cmd_str, mea_tml, mea_act)
        - cmd_str: Formatted command string (e.g., for sending over serial).
        - mea_tml: NumPy array of timestamps (scaled by 0.854).
        - mea_act: List of actinic values (one per timestamp).
    """
    # Reshape 'cmd' into an N x 8 array
    cmd_arr = np.reshape(cmd, (-1, 8))
    arr_length = cmd_arr.shape[0]

    # Create a comma-separated command string:
    # e.g., "arrun1,N,persist,<entire cmd list>,\n"
    cmd_str = f"arrun1,{arr_length},{persist},{str(cmd)[1:-1]},\n"
    cmd_str = cmd_str.replace(" ", "")  # Remove spaces for a cleaner command

    # Parse the reshaped array into usable parameters
    num_pts = cmd_arr[:, 2] * 256 + cmd_arr[:, 3]  # Number of points (high/low bytes)
    act_arr = cmd_arr[:, 6]                       # Actinic setting
    mea_feq = 1 / (cmd_arr[:, 4] * 256 + cmd_arr[:, 5])  # Measurement frequency (1 / freq)

    # Build up the measurement timeline and actinic values
    _t = 0
    mea_tml = []
    mea_act = []

    # For each command segment, create a timeline and corresponding actinic values
    for _n, _f, _a in zip(num_pts, mea_feq, act_arr):
        segment_times = (np.arange(_n) * _f) + _t
        mea_tml.extend(segment_times)       # Accumulate times
        mea_act.extend([_a] * _n)           # Repeat actinic value _n times
        _t = segment_times[-1]              # Update the offset for the next segment

    # Scale the entire timeline by 0.854
    mea_tml = np.array(mea_tml) * 0.854

    return cmd_str, mea_tml, mea_act

def send_read_comand(PORT,string,baudrate=115200, timeout=10):
    """
    Function to open serial, get in master mode with "hello" comand and send comand.
    Read will stop when no more line to be read.
    Args:
        port: str, port name
        baudrate: int, baudrate
        timeout: int, timeout in seconds
    Returns:
        list, received data
    """

    with serial.Serial(PORT, baudrate = baudrate, timeout = timeout) as ser:
        ser.setRTS(False)
        ser.flush() # Flush 
        time.sleep(0.7)
        ser.write("hello\n".encode())
        time.sleep(0.5)
        ser.write(f"{string}\n".encode())
        lines = []
        try:
            while True:
                line = ser.readline() # Attempt to read one line
                if not line:    # If nothing was read (empty line), we assume there's no more data for now
                    break
                lines.append(line.decode('utf-8', errors='replace').rstrip()) # Convert bytes to string and strip trailing whitespace
        except:
            pass
    return lines



def parse_command_blocks(lines, cmd_prefix="cmd:"):
    """
    Parse a list of lines and group them by commands that match `cmd_prefix`.

    The function identifies lines containing commands (e.g., 'cmd: something')
    and collects all subsequent lines into that command's "block" until the
    next command (or end of list).

    :param lines: List of strings to parse.
    :param cmd_prefix: The prefix that indicates a new command. Defaults to 'cmd:'.
    :return: A dictionary mapping { command_name: [list_of_lines_until_next_command] }
             If the same command appears multiple times, each occurrence will
             overwrite previous data unless modified to handle duplicates.
    """
    command_dict = {}
    current_cmd = None
    current_data = []

    for line in lines:
        # Try to find a line that includes 'cmd:' (possibly with extra characters).
        # The regex captures whatever follows 'cmd:' up to the first whitespace 
        # or end of string. E.g., 'cmd: hello' => group(1) = 'hello'.
        match = re.search(r'cmd:\s*([^\s]+)', line)

        if match:
            # If we have a "current_cmd", store its accumulated data first
            if current_cmd is not None:
                command_dict[current_cmd] = current_data

            # Extract the new command from the current line
            current_cmd = match.group(1)
            current_data = []  # Start a fresh list for data following this command
        else:
            # If this line does not declare a new command, and we've already seen a command,
            # then add the line to the current command's block
            if current_cmd is not None:
                current_data.append(line)

    # At the end, if there is a command in progress, save its data
    if current_cmd is not None:
        command_dict[current_cmd] = current_data

    return command_dict


def parse_arrun1(command_dict):
    """
    From a parsed dictionary (use parse_command_block() ), locate the block after 'cmd: arrun1'
    and extract numeric values of T, F, S, R, Sun, and L for each
    matching line, returning them in a dictionary of lists.

    Example return structure:
    {
      'T':   [31.0, 31.0, 31.0],
      'F':   [0.0759, 0.0748, 0.0762],
      'S':   [506, 499, 509],
      'R':   [6667, 6669, 6678],
      'Sun': [380, 382, 380],
      'L':   [484, 486, 487]
    }

    :param lines: A list of text lines (e.g., from a serial device).
    :return: A dict of lists, one list per key: 'T', 'F', 'S', 'R', 'Sun', 'L'.
             If 'cmd: arrun1' or matching lines are not found, returns
             empty lists for each key.
    """
    # 1) Extract lines that belong to "arrun1"
    arrun1_lines = command_dict.get("arrun1", [])

    # 2) Prepare a regex to capture the six fields of interest
    pattern = re.compile(
        r"T:([^,]+),F:([^,]+),S:([^,]+),R:([^,]+),Sun:([^,]+),L:([^,]+)"
    )

    # 4) Initialize an output dict with empty lists for each key
    result = {"T": [],"F": [],"S": [],"R": [],"Sun": [],"L": [] }

    for line in arrun1_lines:
        match = pattern.search(line)
        if match:
            # Convert T, F to float and S, R, Sun, L to int
            try:
                t_val = float(match.group(1))
                f_val = float(match.group(2))
                s_val = int(match.group(3))
                r_val = int(match.group(4))
                sun_val = int(match.group(5))
                l_val = int(match.group(6))

                # Append to the lists
                result["T"].append(t_val)
                result["F"].append(f_val)
                result["S"].append(s_val)
                result["R"].append(r_val)
                result["Sun"].append(sun_val)
                result["L"].append(l_val)
            except ValueError:
                # If conversion fails (malformed line), ignore or handle it
                print(f"PARSING ERROR parse_arrun1_dict, {match}")
                pass

    return result


def plot_two_values(r_data,title=""):
    
    fig, ax1 = plt.subplots()
    
    color_f = 'tab:blue'
    ax1.set_xlabel('Measurement Index')
    ax1.set_ylabel('Fluo', color=color_f)
    line1 = ax1.plot(
        np.arange(len(r_data["F"])), 
        r_data["F"], 
        color=color_f, 
        label="Fluo"
    )
    # Match y-axis tick label color to the line color
    ax1.tick_params(axis='y', labelcolor=color_f)
    ax1.set_ylim([0.1,0.15])
    
    # 3) Create a secondary y-axis sharing the same x-axis
    ax2 = ax1.twinx()
    
    # 4) Plot the second data series on the secondary y-axis
    color_r = 'tab:red'
    ax2.set_ylabel('Reflectance', color=color_r)
    line2 = ax2.plot(
        np.arange(len(r_data["R"])), 
        r_data["R"], 
        color=color_r, 
        label="Reflectance"
    )
    ax2.tick_params(axis='y', labelcolor=color_r)
    ax2.set_ylim([6300,6900])
    
    # (Optional) Combine legends from both axes
    # Matplotlib won't automatically merge them if you use separate axes, so do this:
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc="best")
    
    
    plt.title(title)
    fig.tight_layout()  # Helps prevent overlapping labels on most backends
    plt.show() 









PORT_PID = findDevice(question="hello\n",answer="Hello PID here",flush=False,timeout=2)
PORT_AMB = findDevice(question="hello",answer="ESP-ROM:esp",flush=True,timeout=2)

assert PORT_AMB != None
assert PORT_PID != None



RANGE_TEMP = [20,25,30,35,30,25,20,35,20]   # range of temperature 
STABILIZE =  60                 # wait time after reaching setpoint, seconds 
OUTDIR = f"../../../Data/ambit/{today}/" # output directory
SAVE = True # True for saving json with data
INPUT = True # True for adding sample
myinput = "" # create string for sample

cmd = []
cmd += gen_cmd_arr_line(num = 20, freq = 10, actinic = 0)
cmd += gen_cmd_arr_line(num = 20, freq = 10, actinic = 200)
cmd += gen_cmd_arr_line(num = 20, freq = 10, actinic = 0)
cmd_str, timeline, act_arr = calc_arr_param(cmd, 0)




if SAVE:
    ensure_path_exists(OUTDIR)
if INPUT:
    myinput = input("\nInsert type of sample (eg. unicode, blank...)\n")
    
   
for TEMP_VALUE in RANGE_TEMP:  
    setpoint_command = f"setpoint_{TEMP_VALUE}" # Construct the command to set the device's temperature setpoint
    with serial.Serial(PORT_PID, baudrate=115200, timeout=1) as ser: # Open a serial connection to the PID controller
        print(f"Setting setpoint to {TEMP_VALUE}")  # Let the user know we are changing the setpoint
        ser.write(f"{setpoint_command}\n".encode()) # Send the setpoint command, followed by a newline to conform to typical serial protocols
        time.sleep(1) # Wait briefly to allow the device time to process the command
        msg = ser.readline().decode().strip()       # (Optional) Read and print the immediate response after setting the setpoint
        print(f"Initial response: {msg}")
        
        while True:   # Continuously poll the device to see if the measured temperature has reached our setpoint
            ser.write("query\n".encode())          # Send a "query" command to the device to get the current status
            msg = ser.readline().decode().strip()  # Read the response line, decode it to string, and strip whitespace
            print(f"Query response: {msg}")
            if msg:
                try:
                    # Parse the setpoint, measured temperature, and PID feedback using regular expressions
                    setpoint_match = re.search(r"Setpoint:\s*([0-9]*\.[0-9]*),", msg)
                    measured_match = re.search(r"Measured temp:\s*([0-9]*\.[0-9]*)", msg)
                    pwm_match = re.search(r"PID feedback:\s*([0-9]*)", msg)
                    # Extract each value if the above searches are successful, store as float and int
                    setpoint = float(setpoint_match.group(1))
                    measured = float(measured_match.group(1))
                    pwm = int(pwm_match.group(1))  
                    print(f"READING => Setpoint: {setpoint}, Measured: {measured}, PWM: {pwm}")
                    # If the measured temperature is close enough to the setpoint, break out of the loop
                    if abs(measured - setpoint) < 0.5:
                        print("Setpoint reached, stabilizing.")
                        for _ in tqdm(range(STABILIZE), desc="Loading"):
                            time.sleep(1)
                        print("Temperature is stable. READY to proceed.")
                        
                        break
                except (AttributeError, ValueError):
                    print(f"FAILED to parse the response: {msg}") # If the regex did not match or casting failed, print an error message
                    # # Short delay before trying again
                    time.sleep(0.5)
            else:
                # If no meaningful response is received, just log it and continue looping
                print(f"UNPARSABLE or empty message: {msg}")
            
            # Small delay to avoid spamming the device with too many queries
            time.sleep(0.5)   
            
        
        print("\n\nMeasuring temperature")
        t_serial = send_read_comand(PORT_AMB,"temp",timeout=1)
        t_parsed = parse_command_blocks(t_serial) 
        t_obj, t_board, _ = t_parsed["temp"][0].split("\t") # extract t object, t board
        print("Running protocol")
        r_serial = send_read_comand(PORT_AMB,cmd_str,timeout=1)
        r_parsed = parse_command_blocks(r_serial)
        r_data = parse_arrun1(r_parsed)
        
        # setup results dictionary
        metadata = {} # setup results dictionary
        metadata["datetime"] = today
        metadata["time"] = datetime.now().strftime("%H:%M:%S")
        metadata["sample"] = myinput
        metadata["t_setpoint"] = setpoint
        metadata["t_stabilization"] = STABILIZE
        metadata["t_obj"] = t_obj
        metadata["t_board"] = t_board
        metadata["cmd_str"] = cmd_str
        results = metadata | r_data
        
        if SAVE:
            FIDX = "{:04d}".format(len(os.listdir(OUTDIR)))
            filename = f"{today}_{FIDX}_Ambit.json"
            print(f"Saving as {OUTDIR+filename}")
            with open(OUTDIR+filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            
        
        plot_two_values(r_data,title=TEMP_VALUE)
        # print(data)
    
   
    
   
    

    
   
    
   
    
   
    
   
    
# =============================================================================
#                   Notes     
# =============================================================================
    

# def findAmbit():
#     """
#     Find the PORT of Ambit.
#     Iterates through serial ports, ask Hello and expect "ESP-ROM:esp" in answer.
#     Flush before asking
#     Return PORT.
#     """
#     for port in serial_ports():
#         with serial.Serial(port, baudrate=115200, timeout = 1) as ser:
#             ser.flush()
#             time.sleep(0.5)
#             ser.write("hello".encode())
#             time.sleep(0.5)
#             answer = ser.readline().decode()
#             # print(port, answer)
#             if "ESP-ROM:esp" in answer :
#                 print(f"Found Ambit at: {port}")
#                 return port
#             else:
#                 pass 
            
# def findPID():
#     """
#     Find the PORT of Ambit.
#     Iterates through serial ports, ask Hello and expect "Hello PID here" in answer.
#     Return PORT.
#     """
#     for port in serial_ports():
#         with serial.Serial(port, baudrate=115200, timeout = 2) as ser:
#             ser.write("hello\n".encode())
#             time.sleep(0.5)
#             answer = ser.readline().decode()
#             if "Hello PID here" in answer:
#                 print(f"Found PID at: {port}")
#                 return port
#             else:
#                 pass





# def do_PIDcommand(PORT,string):
#     with serial.Serial(PORT, baudrate=115200, timeout = 1) as ser:
#         # ser.setRTS(False)
#         ser.write(f"{string}\n".encode())
#         time.sleep(0.5)
#         msg = ser.readline().decode()
#         response = []
#         while msg:
#             response.append(msg)
#             msg = ser.readline().decode()
            
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


# for port in serial_ports():
#     with serial.Serial(port, baudrate=115200, timeout = 2) as ser:
#         ser.write("hello\n".encode())
#         answer = ser.readline().decode()
#         while answer:
#             print(answer)
#             answer = ser.readline().decode()
            


   
# for TEMP_VALUE in RANGE_TEMP:
#     STRING_PIDsetpoint = f"setpoint_{TEMP_VALUE}"
#     with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#         print(f"Setting setpoint to {TEMP_VALUE}")
#         ser.write(f"{STRING_PIDsetpoint}\n".encode())
#         time.sleep(1)
#         msg = ser.readline().decode()
#         print(msg)
#         while True:
#             ser.write("query\n".encode())
#             msg = ser.readline().decode()
#             print(msg)
#             if msg:
#                 try:
#                     setpoint = float(re.search("Setpoint: ([0-9]*.[0-9]*),",msg).group(1))
#                     measured = float(re.search(".*Measured temp: ([0-9]*.[0-9]*).*",msg).group(1))
#                     pwm = int(re.search(".*PID feedback: ([0-9]*.[0-9]*)",msg).group(1))
#                     print("READING: ",setpoint,measured,pwm)
#                     if abs(measured - setpoint) < 0.5:
#                         print("READY to protocol")
#                         break
#                 except:
#                     print(f"FAILED to read, value message: {msg}")
#                     msg = ser.readline()
#                     time.sleep(0.5)
#             else:
#                 print(f"UNPARSABLE messages: {msg}")
#             time.sleep(0.5)









##############################################################################   


# for RANGE_TEMP_VALUE in RANGE_TEMP:
#     STRING_PIDsetpoint = f"setpoint_{RANGE_TEMP_VALUE}"
#     with serial.Serial(PORT_PID,baudrate=115200, timeout=1) as ser:
#         ser.write(f"\"{STRING_PIDsetpoint}\n\n\"".encode())
#         time.sleep(1)
#         msg = ser.readline()
#         print(msg)
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
#                     print(f"UNPARSABLE messages: {msg}")
                    
#                     msg = ser.readline()
#                     time.sleep(0.5)
            
#             if abs(measured - setpoint) < 0.5:
#                 print("READY to protocol")
#                 break




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
#                         print(f"UNPARSABLE messages: {msg}")
                        
#                         msg = ser.readline()
#                         time.sleep(0.5)
                
#                 if abs(measured - setpoint) < 0.5:
#                     print("READY to protocol")
#                     break
            
            # print("STABILIZING")
            # time.sleep(STABILIZE) # delay to stabilize
            # print("PROTOCOLLING")
            # ser.write("\"stop\n\n\"".encode())
            # data = do_MsQprotocol(PORT_MS, STRING_MsQprotocol)
            
            # myjson = response_json(data)
            # y = np.array(myjson["sample"][0]["set"][0]["data_raw"])
            # x = np.arange(len(y))
            # # Plot
            # plt.plot(x,y)
            # plt.title(f"{today}\nsetpoint: {setpoint}, measured: {measured}, stabilize: {STABILIZE}s")
            # plt.show()
            # if SAVE:
            #     if not os.path.exists(OUTDIR):
            #         os.mkdir(OUTDIR)
            #     FIDX = "{:03d}".format(len(os.listdir(OUTDIR)))
            #     filename = f"{today}_{FIDX}_HOT_setpoint{setpoint}_stabilize{STABILIZE}.json"
            #     with open(OUTDIR+filename, 'w', encoding='utf-8') as f:
            #         json.dump(myjson, f, ensure_ascii=False, indent=4)
    
























###############################################################################

# import matplotlib as mpl
# import matplotlib.cm as cm
   
# norm = mpl.colors.Normalize(vmin=20, vmax=30)
# cmap = cm.viridis
# m = cm.ScalarMappable(norm=norm, cmap=cmap)



# OUTDIR = f"../../../Data/multispeq/{today}/" # output directory

# result = []
# for filename in os.listdir(OUTDIR)[-8:]:
#     with open(os.path.join(OUTDIR,filename)) as f:
#         data = json.load(f)
        
#     y = np.array(data["sample"][0]["set"][0]["data_raw"])
#     x = np.arange(len(y))
#     fo = np.round(np.mean(y[:20]),3)
#     fm = np.round(np.mean(y[1500:1520]),3)
#     fv = fm-fo
#     fvfm = np.round(fv/fm,3)
#     temp = float(re.search(".*_setpoint([0-9]{2})_.*",filename).group(1))
#     result.append([filename,temp,fo,fm,fvfm])
#     plt.plot(x,y,c=m.to_rgba(temp),label=f"{temp}°C")
#     plt.ylim([0,100])
    
#     # plt.title(f"{filename}")

# plt.xlim([0,300])
# handles, labels = plt.gca().get_legend_handles_labels()
# by_label = dict(zip(labels, handles))
# plt.legend(by_label.values(), by_label.keys())
# plt.ylabel("Rel. Fluo. Yield")
# plt.xlabel("Pulse number")
# plt.show()

# df = pd.DataFrame(result,columns=["filename","temp","fo","fm","fvfm"])

###############################################################################



# STRING_MsQprotocol = "[{\"v_arrays\":[[100,1000,10000],[100,100,100],[0,0,0]],\"share\":1,\"set_repeats\":1,\"_protocol_set_\":[{\"label\":\"phi2\",\"nonpulsed_lights\":[[2],[2],[2]],\"nonpulsed_lights_brightness\":[[0],[-2000],[0]],\"pulsed_lights\":[[1],[1],[1]],\"detectors\":[[1],[1],[1]],\"pulses\":[60,2000,60],\"pulse_distance\":[250000,750,250000],\"pulsed_lights_brightness\":[[-200],[-200],[-200]],\"pulse_length\":[[10],[10],[10]],\"protocol_averages\":1,\"protocol_repeats\":1,\"environmental\":[[\"light_intensity\"],[\"contactless_temp\"],[\"thp\"],[\"thp2\"]]}]}]"

# RANGE_TEMP = [22]   # range of temperature 
# REP = 2
# STABILIZE =  60*10         # seconds 
# OUTDIR = f"../../../Data/multispeq/{today}/" # output directory
# SAVE = True




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






