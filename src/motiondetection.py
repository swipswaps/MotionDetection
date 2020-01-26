#!/usr/bin/env python3

import re
import os
import cv2
import sys
import time
import glob
import email
import socket
import smtplib
import logging
import threading
import subprocess
import multiprocessing
import logging.handlers

import numpy as np

from PIL import Image
from io import StringIO
from pynetgear import Netgear
from optparse import OptionParser

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler,HTTPServer

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Logging(object):

    @staticmethod
    def log(level,message,verbose=True):
        comm = re.search("(WARN|INFO|ERROR)", str(level), re.M)
        try:
            handler = logging.handlers.WatchedFileHandler(
                os.environ.get("LOGFILE","/var/log/motiondetection.log")
            )
            formatter = logging.Formatter(logging.BASIC_FORMAT)
            handler.setFormatter(formatter)
            root = logging.getLogger()
            root.setLevel(os.environ.get("LOGLEVEL", str(level)))
            root.addHandler(handler)
            # Log all calls to this class in the logfile no matter what.
            if comm is None:
                print(str(level) + " is not a level. Use: WARN, ERROR, or INFO!")
                return
            elif comm.group() == 'ERROR':
                logging.error(str(time.asctime(time.localtime(time.time()))
                    + " - MotionDetection - "
                    + str(message)))
            elif comm.group() == 'INFO':
                logging.info(str(time.asctime(time.localtime(time.time()))
                    + " - MotionDetection - "
                    + str(message)))
            elif comm.group() == 'WARN':
                logging.warn(str(time.asctime(time.localtime(time.time()))
                    + " - MotionDetection - "
                    + str(message)))
            if verbose or str(level) == 'ERROR':
                print("(" + str(level) + ") "
                    + str(time.asctime(time.localtime(time.time()))
                    + " - ImageCapture - "
                    + str(message)))
        except IOError as eIOError:
            if re.search('\[Errno 13\] Permission denied:', str(eIOError), re.M | re.I):
                print("(ERROR) MotionDetection - Must be sudo to run MotionDetection!")
                sys.exit(0)
            print("(ERROR) MotionDetection - IOError in Logging class => "
                + str(eIOError))
            logging.error(str(time.asctime(time.localtime(time.time()))
                + " - MotionDetection - IOError => "
                + str(eIOError)))
        except Exception as eLogging:
            print("(ERROR) MotionDetection - Exception in Logging class => "
                + str(eLogging))
            logging.error(str(time.asctime(time.localtime(time.time()))
                + " - MotionDetection - Exception => " 
                + str(eLogging)))
            pass
        return

# The config filename is passed to this class in the ImageCapture classes __init__ method.
# The option is the default value set in optparser and is blank by default. See the 
# optparser declaration at the bottom in the if __name__ == '__main__' check.
class ConfigFile(object):

    def __init__(self, file_name):
        self.args_list = []
        self.file_name = file_name
        if file_name:
            try:
                self.config_file = open(file_name,'r').read().splitlines()
                self.config_file_syntax_sanity_check()
            except IOError:
                Logging.log("ERROR","Config file does not exist.")
                sys.exit(0)

    def __getattr__(self, key):
        pass

    def __setattr__(self, key, val):
        pass

    # If a config file is 'NOT' passed via command line then this method will set the global
    # base variables for the config_dict data structure using the optparsers default values.
    # ---
    # If a config file 'IS' passed via command line then this method will read in the options
    # values and set the base options for the global config_dict data structure. If the config
    # files options have empty values then those options are loaded into an array nested inside
    # of the config_dict data structure. Which will later be used as a reference against the 
    # config_data structure so it knows to use optparsers default values for these options.
    def config_options(self):
        # If config file is 'NOT' supplied use optparsers default values.
        if not self.file_name:
            for default_opt in config_dict[0].keys():
                config_dict[0][default_opt][0] = config_dict[0][default_opt][1]
                Logging.log("INFO", "Setting option("
                    + default_opt + "): "
                    + str(config_dict[0][default_opt][0]))
            return
        # If the config file exists and the syntax is correct we will have to convert the
        # 'bool' values in the file which are being loaded in as strings to actual bool values.
        # The same applies for integers otehrwise load the values in as is.
        for line in self.config_file:
            comm = re.search(r'(^.*)=(.*)', str(line), re.M | re.I)
            if comm is not None:
                if not comm.group(2):
                    config_dict[1].append(comm.group(1))
                elif re.search('true', comm.group(2), re.I) is not None:
                    config_dict[0][comm.group(1)][0] = True
                elif re.search('false', comm.group(2), re.I) is not None:
                    config_dict[0][comm.group(1)][0] = False
                elif re.search('([0-9]{1,6})', comm.group(2)) is not None:
                    config_dict[0][comm.group(1)][0] = int(comm.group(2))
                else:
                    config_dict[0][comm.group(1)][0] = comm.group(2)
        return config_dict

    # If command line options 'ARE' passed via optparser/command line then this method
    # will override the default values set with optparser as well as override the options
    # in the config file that was passed.
    def override_values(self):
        for default_opt in config_dict[0].keys():
            comm = re.search('-(\w{0,9}|)'
                + config_dict[0][default_opt][2], str(sys.argv[1:]), re.M)
            if comm is not None:
                Logging.log("INFO", "Overriding "
                    + str(default_opt)
                    + " default value with command line switch value("
                    + str(config_dict[0][default_opt][1]) + ")")
                config_dict[0][default_opt][0] = config_dict[0][default_opt][1]

    # If a config file is supplied then this method will use the default options
    # in optparser if the option in the config file has no value. So if the password 
    # option in the config file looks like this -> password= then it will be populated 
    # by this method.
    def populate_empty_options(self):
        if config_dict[1] and self.config_file_supplied():
            for opt in config_dict[1]:
                config_dict[0][opt][0] = config_dict[0][opt][1]

    def config_file_supplied(self):
        if re.search(r'(\-C|\-\-config\-file)',str(sys.argv[1:]), re.M) is None:
            return False
        return True

    def config_file_syntax_sanity_check(self):
        for line in self.config_file:
            comm = re.search(r'(^.*)=(.*)', str(line), re.M | re.I)
            if comm is not None:
                try:
                    config_dict[0][comm.group(1)]
                except KeyError:
                    Logging.log("ERROR", "Config file option("
                        + comm.group(1)
                        + ") is not a recognized option!")
                    sys.exit(0)

class User(object):
    @staticmethod
    def name():
        comm = subprocess.Popen(["users"], shell=True, stdout=subprocess.PIPE)
        return re.search("(\w+)", str(comm.stdout.read())).group()

class PS(object):
    @classmethod
    def aux(self,process,user=User.name()):
        _aux_ = os.system("/bin/ps aux | /usr/bin/awk '/^"
            +str(user)+".*"+str(process)
            +"/{if($11 !~ /awk|ps/) print}'")
        print(str(_aux_))
        return _aux_

class Time(object):
    @staticmethod
    def now():
        return time.asctime(time.localtime(time.time()))

class Mail(object):

    __disabled__ = False

    @staticmethod
    def send(sender,to,password,port,subject,body):
        try:
            if not Mail.__disabled__:
                message = MIMEMultipart()
                message['Body'] = body
                message['Subject'] = subject
                message.attach(MIMEImage(open("/home/pi/.motiondetection/capture"
                    + str(MotionDetection.img_num())
                    + ".png","rb").read()))
                mail = smtplib.SMTP('smtp.gmail.com',port)
                mail.starttls()
                mail.login(sender,password)
                mail.sendmail(sender, to, message.as_string())
                Logging.log("INFO", "(Mail.send) - Sent email successfully!")
            else:
                Logging.log("WARN", "(Mail.send) - Sending mail has been disabled!")
        except smtplib.SMTPAuthenticationError:
            Logging.log("WARN", "(Mail.send) - Could not athenticate with password and username!")
        except TypeError as eTypeError:
            Logging.log("INFO", "(Mail.send) - Picture("
                + str(MotionDetection.img_num())
                + ".png) "
                + "TypeError => "
                + str(eTypeError))
            pass
        except Exception as e:
            Logging.log("ERROR",
                "(Mail.send) - Unexpected error in Mail.send() error e => "
                + str(e))
            pass

# Metaclass for locking video camera
class VideoFeed(type):

    def __new__(meta,name,bases,dct):
        if not hasattr(meta,'lock'):
            meta.lock = multiprocessing.Lock()
        return super().__new__(meta, name, bases, dct)

    def __init__(cls,name,bases,dct):
        if not hasattr(cls,'lock'):
            Logging.log("INFO", '(VideoFeed.__init__) - Passing "Lock" object to class "'
            + cls.__name__
            + '"')
            cls.lock = multiprocessing.Lock()
        if not hasattr(cls,'pid'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "pid" attribute to class "'
            + cls.__name__
            + '"')
            cls.pid = os.getpid()
        if not hasattr(cls,'main_pid'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "main_pid" attribute to class "'
            + cls.__name__
            + '"')
            cls.main_pid = os.getpid()
        if not hasattr(cls,'parent_pid'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "parent_pid" attribute to class "'
            + cls.__name__
            + '"')
            cls.parent_pid = os.getppid()
        if not hasattr(cls,'mac_addr_listed'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "mac_addr_listed" attribute to class "'
            + cls.__name__
            + '"')
            cls.mac_addr_listed = False
        if not hasattr(cls,'thread_locked'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "thread_locked" attribute to class "'
            + cls.__name__
            + '"')
            cls.thread_locked = False
        if not hasattr(cls,'timeout'):
            Logging.log("INFO", '(VideoFeed.__init__) - Adding "timeout" attribute to class "'
            + cls.__name__
            + '"')
            cls.timeout = 0
        super(VideoFeed,cls).__init__(name,bases,dct)

class MotionDetection(metaclass=VideoFeed):

    verbose = False

    colored_frame  = None
    camera_object  = None
    current_frame  = None
    previous_frame = None

    delta_count = None

    def __init__(self,options_dict={}):
        super().__init__()

        self.tracker           = 0
        self.count             = 60

        self.ip                = options_dict['ip']
        self.fps               = options_dict['fps']
        self.email             = options_dict['email']
        self.netgear           = options_dict['netgear']
        self.verbose           = options_dict['verbose']  
        self.password          = options_dict['password']
        self.email_port        = options_dict['email_port']
        self.accesslist        = options_dict['accesslist']
        self.configfile        = options_dict['configfile']
        self.server_port       = options_dict['server_port']
        self.standby_mode      = options_dict['standby_mode']
        self.cam_location      = options_dict['cam_location']
        self.disable_email     = options_dict['disable_email']
        self.burst_mode_opts   = options_dict['burst_mode_opts']

        self.delta_thresh_min  = options_dict['delta_thresh_min']
        self.delta_thresh_max  = options_dict['delta_thresh_max']
        self.motion_thresh_min = options_dict['motion_thresh_min']

        configFile = ConfigFile(self.configfile)
        configFile.config_options()
        configFile.populate_empty_options()
        configFile.override_values()

        Mail.__disabled__ = self.disable_email
        MotionDetection.verbose = self.verbose
        self.accesslist_semaphore = threading.Semaphore(1)

        if not self.disable_email and (self.email is None or self.password is None):
            Logging.log("ERROR",
                "(MotionDetection.__init__) - Both E-mail and password are required!")
            parser.print_help()
            sys.exit(0)

    @staticmethod
    def img_num():
        img_list = []
        os.chdir("/home/pi/.motiondetection/")
        if not FileOpts.file_exists('/home/pi/.motiondetection/capture1.png'):
            Logging.log("INFO", "(MotionDetection.img_num) - Creating capture1.png.",MotionDetection.verbose)
            FileOpts.create_file('/home/pi/.motiondetection/capture1.png')
        for file_name in glob.glob("*.png"):
            num = re.search("(capture)(\d+)(\.png)", file_name, re.M | re.I)
            img_list.append(int(num.group(2)))
        return max(img_list)
    
    @staticmethod
    def take_picture(frame):
        picture_name = (
            '/home/pi/.motiondetection/capture'
            + str(MotionDetection.img_num() + 1)
            + '.png'
        )
        image = Image.fromarray(frame)
        image.save(picture_name)

    @staticmethod
    def start_thread(proc,*args):
        try:
            t = threading.Thread(target=proc,args=args)
            t.daemon = True
            t.start()
        except Exception as eStartThread:
            Logging.log("ERROR",
                "Threading exception eStartThread => "
                + str(eStartThread))

    @classmethod
    def calculate_delta(cls):
        frame_delta = cv2.absdiff(cls.previous_frame, cls.current_frame)
        (ret, frame_delta) = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)
        frame_delta = cv2.dilate(frame_delta,np.ones((5,5), np.uint8),iterations=1)
        frame_delta = cv2.normalize(frame_delta, None, 0, 255, cv2.NORM_MINMAX)
        cls.delta_count = cv2.countNonZero(frame_delta)

    @classmethod
    def update_current_frame(cls):
        cls.previous_frame = cls.current_frame
        (ret, cls.current_frame) = cls.camera_object.read()
        cls.colored_frame = cls.current_frame
        cls.current_frame = cv2.cvtColor(cls.current_frame, cv2.COLOR_RGB2GRAY)
        cls.current_frame = cv2.GaussianBlur(cls.current_frame, (21, 21), 0)

    def capture(self,queue=None):

        MotionDetection.lock.acquire()

        Logging.log("INFO", "(MotionDetection.capture) - Lock acquired!",self.verbose)
        Logging.log("INFO", "(MotionDetection.capture) - MotionDetection system initialized!", self.verbose)
    
        MotionDetection.camera_object = cv2.VideoCapture(self.cam_location)
        MotionDetection.camera_object.set(cv2.CAP_PROP_FPS, self.fps)

        MotionDetection.previous_frame = MotionDetection.camera_object.read()[1]
        MotionDetection.colored_frame  = MotionDetection.previous_frame 
        MotionDetection.previous_frame = cv2.cvtColor(MotionDetection.previous_frame, cv2.COLOR_RGB2GRAY)
        MotionDetection.previous_frame = cv2.GaussianBlur(MotionDetection.previous_frame, (21, 21), 0)

        MotionDetection.current_frame = MotionDetection.camera_object.read()[1]
        MotionDetection.current_frame = cv2.cvtColor(MotionDetection.current_frame, cv2.COLOR_RGB2GRAY)
        MotionDetection.current_frame = cv2.GaussianBlur(MotionDetection.current_frame, (21, 21), 0)

        while(True):

            if not queue.empty() and queue.get() == 'start_monitor':
                Logging.log("INFO",
                    "(MotionDetection.capture) - (Queue message) -> Killing camera.",self.verbose)
                del(MotionDetection.camera_object)
                queue.close()
                MotionDetection.lock.release()
                break

            if self.standby_mode:
                accesslist_thread = threading.Thread(
                    target=AccessList.mac_addr_presence,
                    args=(self.accesslist_semaphore,self.netgear,self.accesslist)
                )
                if not AccessList.thread_locked and AccessList.timedout(30):
                    AccessList.thread_locked = True
                    accesslist_thread.start()

            time.sleep(0.1)

            MotionDetection.calculate_delta()

            if MotionDetection.delta_count > self.delta_thresh_min and MotionDetection.delta_count < self.delta_thresh_max:
                self.tracker += 1
                if self.tracker >= 60 or self.count >= 60:
                    self.count   = 0
                    self.tracker = 0
                    Logging.log("INFO",
                        "(MotionDetection.capture) - Motion detected with threshold levels at "
                        + str(MotionDetection.delta_count)
                        + "!", self.verbose)
                    # Access list feature
                    if not AccessList.mac_addr_listed:
                        for placeholder in range(0,self.burst_mode_opts):
                            time.sleep(1)
                            MotionDetection.take_picture(MotionDetection.camera_object.read()[1])
                            MotionDetection.start_thread(Mail.send,self.email,self.email,self.password,self.email_port,
                                'Motion Detected','MotionDecetor.py detected movement!')
            elif MotionDetection.delta_count < self.motion_thresh_min:
                self.count  += 1
                self.tracker = 0

            MotionDetection.update_current_frame()

class CamHandler(BaseHTTPRequestHandler,metaclass=VideoFeed):

    __record__    = False

    def do_GET(self):
        try:
            CamHandler.lock.acquire()
            Logging.log("INFO", "(CamHandler.do_GET) - Lock acquired!")
            if self.path.endswith('.mjpg'):
                self.rfile._sock.settimeout(1)
                self.send_response(200)
                self.send_header('Content-type',
                    'multipart/x-mixed-replace; boundary=--jpgboundary')
                self.end_headers()
            while True:
                if not self.server.queue.empty():
                    if self.server.queue.get() == 'kill_monitor':
                        Logging.log("INFO",
                            '(CamHandler.do_GET) - (Queue message) -> Killing Live Feed!')
                        del(self.server.video_capture)
                        self.server.queue.put('close_camview')
                        break
                    elif self.server.queue.get() == 'start_recording':
                        CamHandler.__record__ = True
                        Logging.log("INFO",
                            "(CamHandler.do_GET) - queue.get() == 'start_recording'")
                    elif self.server.queue.get() == 'stop_recording':
                        CamHandler.__record__ = False
                        Logging.log("INFO",
                            "(CamHandler.do_GET) - queue.get() == 'stop_recording'")
                (read_cam, image) = self.server.video_capture.read()
                if not read_cam:
                    continue
                try:
                    self.server.video_output.write(image)
                    '''if CamHandler.__record__:
                        self.server.video_output.write(image)'''
                except Exception as eWrite:
                    print("Exception eWrite => "+str(eWrite))
                    pass
                rgb = cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
                jpg = Image.fromarray(rgb)
                jpg_file = StringIO.StringIO()
                jpg.save(jpg_file,'JPEG')
                self.wfile.write("--jpgboundary")
                self.send_header('Content-type','image/jpeg')
                self.send_header('Content-length',str(jpg_file.len))
                self.end_headers()
                jpg.save(self.wfile,'JPEG')
                time.sleep(0.05)
        except KeyboardInterrupt:
            del(self.server.video_capture)
            CamHandler.lock.release()
        except Exception as e:
            if re.search('[Errno 32] Broken pipe',str(e), re.M | re.I):
                Logging.log("WARN", "(CamHandler.do_GET) - [Errno 32] Broken pipe.")
            print("(CamHandler.do_GET) - Exception e => "+str(e))
        return CamHandler

class ThreadedHTTPServer(ThreadingMixIn,HTTPServer):
    def __init__(self, server_address,RequestHandlerClass,queue,verbose,video_capture,video_output,bind_and_activate=True):
        HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.queue   = queue
        self.verbose = verbose
        self.video_ouput = video_output
        self.video_capture = video_capture
        HTTPServer.allow_reuse_address = True

class Stream(MotionDetection,metaclass=VideoFeed):

    def __init__(self):
        super().__init__(options_dict)
        self.fps          = options_dict['fps']
        self.verbose      = options_dict['verbose']
        self.camview_port = options_dict['camview_port']
        self.cam_location = options_dict['cam_location']

    def stream_main(self,queue=None):
        Stream.lock.acquire()
        Logging.log("INFO", "(Stream.stream_main) - Lock acquired!")
        try:
            video_capture = cv2.VideoCapture(self.cam_location)
            video_capture.set(3,320)
            video_capture.set(4,320)
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            video_output = cv2.VideoWriter(
                '/home/pi/.motiondetection/stream.avi',
                fourcc, self.fps, (
                    int(video_capture.get(3)),
                    int(video_capture.get(4))
                )
            )
            Stream.lock.release()
            Logging.log("INFO", "(Stream.stream_main) - Streaming HTTPServer started")
            server = ThreadedHTTPServer(
                ('0.0.0.0', self.camview_port), CamHandler, queue, video_capture, video_output
            )
            server.timeout = 1
            server.queue   = queue
            server.verbose = self.verbose
            server.video_output  = video_output
            server.video_capture = video_capture
            del(video_capture)
            while(True):
                if not queue.empty() and queue.get() == 'close_camview':
                    CamHandler.lock.release()
                    queue.close()
                    break
                server.handle_request()
        except KeyboardInterrupt:
            CamHandler.lock.release()
            Stream.lock.release()
            queue.close()
        except Exception as eThreadedHTTPServer:
            Logging.log("ERROR",
                "(Stream.stream_main) - eThreadedHTTPServer => "
                + str(eThreadedHTTPServer))
            queue.close()

class FileOpts(object):

    def __init__(self,logfile):

        if not self.dir_exists(self.root_directory()):
            self.mkdir_p(self.root_directory())

        if not FileOpts.file_exists(logfile):
            FileOpts.create_file(logfile)

    def root_directory(self):
        return "/home/pi/.motiondetection"

    @staticmethod
    def file_exists(file_name):
        return os.path.isfile(file_name)

    @staticmethod
    def create_file(file_name):
        if FileOpts.file_exists(file_name):
            Logging.log("INFO", "(FileOpts.compress_file) - File "
                + str(file_name)
                + " exists.")
            return
        Logging.log("INFO", "(FileOpts.compress_file) - Creating file "
            + str(file_name)
            + ".")
        open(file_name, 'w')

    def dir_exists(self,dir_path):
        return os.path.isdir(dir_path)

    def mkdir_p(self,dir_path):
        try:
            Logging.log("INFO", "Creating directory " + str(dir_path))
            os.makedirs(dir_path)
        except OSError as e:
            if e.errno == errno.EEXIST and self.dir_exists(dir_path):
                pass
            else:
                Logging.log("ERROR", "mkdir error: " + str(e))
                raise
            
class AccessList(metaclass=VideoFeed):

    @staticmethod
    def set_default_values(semaphore,listed=False,locked=False):
        AccessList.mac_addr_listed = listed
        semaphore.release()
        AccessList.thread_locked = locked

    @classmethod
    def timedout(cls,seconds=60):
        if AccessList.timeout == 0:
            AccessList.timeout += 1
        elif AccessList.timeout >= 10 * seconds:
            AccessList.timeout = 0
            return True
        else:
            AccessList.timeout += 1

    @classmethod
    def mac_addr_presence(cls,semaphore,netgear,accesslist):
        semaphore.acquire(blocking=True)
        try:
            if isinstance(netgear, Netgear):
                for device in netgear.get_attached_devices():
                    if not device.mac in open(accesslist,'r').read():
                        AccessList.set_default_values(semaphore,False,False)
                    else:
                        Logging.log("INFO","(AccessList.mac_addr_presence) - Device name: "+str(device.name))
                        Logging.log("INFO","(AccessList.mac_addr_presence) - Device IP address: "+str(device.ip))
                        Logging.log("INFO","(AccessList.mac_addr_presence) - Device MAC address: "+str(device.mac))
                        AccessList.set_default_values(semaphore,True,False)
                        break
            else:
                AccessList.set_default_values(semaphore,False,False)
        except:
            AccessList.set_default_values(semaphore,False,False)
            pass

class Server(MotionDetection,metaclass=VideoFeed):

    def __init__(self,queue):
        super().__init__(options_dict)

        self.queue = queue
        self.camview_port = options_dict['camview_port']

        self.process = multiprocessing.Process(
            target=MotionDetection(options_dict).capture,name='capture',args=(queue,)
        )
        self.process.daemon = True
        self.process.start()

        Server.main_pid   = os.getpid()
        Server.parent_pid = os.getppid()
        Logging.log("INFO","(Server.__init__) - Server.main_pid: "+str(Server.main_pid))
        Logging.log("INFO","(Server.__init__) - Server.parent_pid: "+str(Server.parent_pid))

        MotionDetection.pid = self.process.pid
        Logging.log("INFO","(Server.__init__) - MotionDetection.pid: "+str(MotionDetection.pid))

        try:
            self.sock = socket.socket()
            self.sock.bind(('0.0.0.0', self.server_port))
        except Exception as eSock:
            #if 'Address already in use' in eSock and PS.aux('motiondetection') is not None:
            if 'Address already in use' in eSock:
                Logging.log("ERROR",
                    "(Server.__init__) - eSock error e => "+str(eSock))
                os.system('/usr/bin/sudo /sbin/reboot')

    def handle_incoming_message(self,*data):
        for(sock,queue) in data:
            message = sock.recv(1024)
            if(message == 'start_monitor'):
                Logging.log("INFO",
                    "(Server.handle_incoming_message) - Starting camera! -> (start_monitor)")
                queue.put('start_monitor')
                Server.lock.acquire()
                if self.process.name == 'capture':
                    Logging.log("INFO",
                        "(Server.handle_incoming_message) - Terminating "
                        + str(self.process.name)
                        + " process")
                    self.process.terminate()
                Server.lock.release()
                self.proc = multiprocessing.Process(
                    target=Stream().stream_main,name='stream_main',args=(queue,)
                )
                self.proc.daemon = True
                self.proc.start()
                MotionDetection.pid = self.proc.pid
                Logging.log("INFO","(Server.handle_incoming_message) - MotionDetection.pid: "+str(Stream.pid))
            elif(message == 'kill_monitor'):
                Logging.log("INFO",
                    "(Server.handle_incoming_message) - Killing camera! -> (kill_monitor)")
                queue.put('kill_monitor')
                Server.lock.acquire()
                if self.process.name == 'stream_main':
                    Logging.log("INFO",
                        "(Server.handle_incoming_message) - Terminating "
                        + str(self.process.name)
                        + " process")
                    self.process.terminate()
                Server.lock.release()
                self.process = multiprocessing.Process(
                    target=MotionDetection(options_dict).capture,name='capture',args=(queue,)
                )
                self.process.daemon = True
                self.process.start()
                MotionDetection.pid = self.process.pid
                Logging.log("INFO","(Server.handle_incoming_message) - MotionDetection.pid: "+str(MotionDetection.pid))
            elif(message == 'start_recording'):
                queue.put('start_recording')
            elif(message == 'stop_recording'):
                queue.put('stop_recording')
            elif(message == 'ping'):
                sock.send(str([Server.main_pid,MotionDetection.pid,Server.parent_pid]))
            else:
                pass
            sock.close()

    def server_main(self):

        Logging.log("INFO", "(Server.server_main) - Listening for connections.")

        while(True):
            time.sleep(0.05)
            try:
                self.sock.listen(10)
                (con, addr) = self.sock.accept()
                if not '127.0.0.1' in str(addr):
                    Logging.log("INFO",
                        "(Server.server_main) - Received connection from "
                        + str(addr))

                Server.handle_incoming_message(self,(con,self.queue))

            except KeyboardInterrupt:
                print('\n')
                Logging.log("INFO", "(Server.server_main) - Caught control + c, exiting now.\n")
                self.sock.close()
                sys.exit(0)
            except Exception as eAccept:
                Logging.log("ERROR", "(Server.server_main) - Socket accept error: "
                    + str(eAccept))

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option('-i', '--ip',
        dest='ip', default='0.0.0.0',
        help='This is the IP address of the server.')
    parser.add_option('-v', '--verbose',
        dest='verbose', action='store_true', default=False,
        help="Turns on verbose logging. This is turned off by default.")
    parser.add_option('-E', '--email-port',
        dest='email_port', type='int', default=587,
        help='E-mail port defaults to port 587')
    parser.add_option('-l', '--log-file',
        dest='logfile', default='/var/log/motiondetection.log',
        help='Log file defaults to /var/log/motiondetection.log.')
    parser.add_option('-D', '--disable-email',
        dest='disable_email', action='store_true', default=False,
        help='This option allows you to disable the sending of E-mails.')
    parser.add_option("-g", "--config-file",
        dest="configfile", default='',
        help="Configuration file path.")
    parser.add_option('-P', '--standby-mode',
        dest='standby_mode', action='store_true', default=False,
        help='This option allows you to disable the system if your phone '
            + 'is connected to Wi-Fi.')
    parser.add_option('-c', '--camera-location',
        dest='cam_location', type='int', default=0,
        help='Camera index number that defaults to 0. This is the '
            + 'location of the camera - Which is usually /dev/video0.')
    parser.add_option('-f', '--fps',
        dest='fps', type='int', default='30',
        help='This sets the frames per second for the motion '
            + 'capture system. It defaults to 30 frames p/s.')
    parser.add_option('-w', '--white-list',
        dest='accesslist', default='/home/pi/.motiondetection/accesslist',
        help='This ensures that the MotionDetection system does not run '
            + 'if the mac is in the accesslist. This defaults to '
            + '/home/pi/.motiondetection/accesslist.')
    parser.add_option('-e', '--email',
        dest='email',
        help='This argument is required unless you pass the '
            + 'pass the --disable-email flag on the command line. '
            + 'Your E-mail address is used to send the pictures taken as '
            + 'well as notify you of motion detected.')
    parser.add_option('-p', '--password',
        dest='password',
        help='This argument is required unless you pass the '
            + 'pass the --disable-email flag on the command line. '
            + 'Your E-mail password is used to send the pictures taken '
            + 'as well as notify you of motion detected.')
    parser.add_option('-r', '--router-password',
        dest='router_password', default='password',
        help='This option is your routers password. This is used to '
            + 'circumvent the motiondetection system. If your phone is '
            + 'connected to your router and in the access list. The '
            + 'MotionDetection system will not run.')
    parser.add_option('-C', '--camview-port',
        dest='camview_port', type='int', default=5000,
        help='CamView port defaults to port 5000'
            + 'This is the port the streaming feature runs on. '
            + 'The streaming feature is the ability to view the '
            + 'live feed from the camera via ANdroid app.')
    parser.add_option('-t', '--delta-threshold-min',
        dest='delta_thresh_min', type='int', default=1500,
        help='Sets the minimum movement threshold '
            + 'to trigger the programs image capturing/motion routines. If movement '
            + 'above this level is detected then this is when MotiondDetection '
            + 'goes to work. The default value is set at 1500.')
    parser.add_option('-T', '--delta-threshold-max',
        dest='delta_thresh_max', type='int', default=10000,
        help='Sets the maximum movement threshold when the '
            + 'programs image capturingi/motion routines stops working. '
            + 'If movement above this level is detected then this program '
            + ' will not perform any tasks and sit idle. The default value is set at 10000.')
    parser.add_option('-b', '--burst-mode',
        dest='burst_mode_opts', type='int', default='1',
        help='This allows the motiondetection framework to take '
            + 'multiple pictures instead of a single picture once it '
            + 'detects motion. Example usage for burst mode would look '
            + 'like: --burst-mode=10. 10 being the number of photos to take '
            + 'once motion has been detected.')
    parser.add_option('-m', '--motion-threshold-min',
        dest='motion_thresh_min', type='int', default=500,
        help='Sets the minimum movement threshold to start the framework '
            + 'and trigger the programs main motion detection routine. '
            + 'This is used because even if there is no movement as all '
            + 'the program still receives false hits and the values can '
            + 'range from 1 to around 500 and is what the default is set to - 500.')
    parser.add_option('-S', '--server-port',
        dest='server_port', type='int', default=50050,
        help='Server port defaults to port 50050.'
            + 'This is the port the command server runs on. '
            + 'This server listens for specific commands from '
            + 'the Android app and controls the handling of the '
            + 'camera lock thats passed abck and forth between the '
            + 'streaming server and the motion detection system.')
    (options, args) = parser.parse_args()

    Logging.log("INFO", "(MotionDetection.__main__) - Initializing netgear object.",options.verbose)
    if options.standby_mode:
        netgear = Netgear(password=options.router_password)
    else:
        netgear = None

    fileOpts = FileOpts(options.logfile)

    # These strings are used to compare against the command line args passed.
    # It could have been done with an action but default values were used instead.
    # These strings are coupled with their respective counterpart in the config_dist
    # data structure declared below.

    ip = '(i|--ip)'
    fps = '(f|--fps)'
    email = '(e|--email)'
    verbose = '(v|--verbose)'
    password = '(p|--password)'
    logfile = '(l|--log-file)'
    email_port = '(E|--email-port)'
    config_file = '(g|--config-file)'
    burst_mode_opts = '(b|--burst-mode)'
    accesslist = '(w|--white-list)'
    server_port = '(S|--server-port)'
    camview_port = '(C|--camview-port)'
    standby_mode = '(P|--standby-mode)'
    disable_email = '(D|--disable-email)'
    cam_location = '(c|--camera-location)'
    router_password = '(r|--router-password)'
    delta_thresh_max = '(T|--delta-threshold-max)'
    delta_thresh_min = '(t|--delta-threshold-min)'
    motion_thresh_min = '(m|--motion-threshold-min)'

    config_dict = [{
        'ip': ['', options.ip, ip],
        'fps': ['', options.fps, fps],
        'netgear': ['', netgear, netgear],
        'email': ['', options.email, email],
        'verbose': ['', options.verbose, verbose],
        'logfile': ['', options.logfile, logfile],
        'password': ['', options.password, password],
        'email_port': ['', options.email_port, email_port],
        'accesslist': ['', options.accesslist, accesslist],
        'configfile': ['', options.configfile, configfile],
        'server_port': ['', options.server_port, server_port],
        'standby_mode': ['', options.standby_mode, standby_mode],
        'cam_location': ['', options.cam_location, cam_location],
        'camview_port': ['', options.camview_port, camview_port],
        'disable_email': ['', options.disable_email, disable_email],
        'burst_mode_opts': ['', options.burst_mode_opts, burst_mode_opts],
        'router_password': ['', options.router_password, router_password],
        'delta_thresh_max': ['', options.delta_thresh_max, delta_thresh_max],
        'delta_thresh_min': ['', options.delta_thresh_min, delta_thresh_min],
        'motion_thresh_min': ['', options.motion_thresh_min, motion_thresh_min]
    }, []]

    options_dict = {
        'standby_mode': options.standby_mode,
        'logfile': options.logfile, 'fps': options.fps,
        'netgear': netgear, 'disable_email': options.disable_email,
        'server_port': options.server_port, 'email': options.email,
        'delta_thresh_max': options.delta_thresh_max, 'ip': options.ip, 
        'password': options.password, 'cam_location': options.cam_location,
        'email_port': options.email_port, 'camview_port': options.camview_port,
        'verbose': options.verbose, 'burst_mode_opts': options.burst_mode_opts,
        'accesslist': options.accesslist, 'delta_thresh_min': options.delta_thresh_min,
        'router_password': options.router_password, 'motion_thresh_min': options.motion_thresh_min,
    }

    motion_detection = MotionDetection(options_dict)
    Server(multiprocessing.Queue()).server_main()
