import sys
import threading
sys.path.append('../')
import gi
import configparser
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from gi.repository import GLib
from ctypes import *
import time
import sys
import math
import platform
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.FPS import GETFPS
import datetime

import cv2
import numpy as np
import pyds

from ch_settings import *
import json
from kafka import KafkaProducer 
from json import dumps 
import time 

fps_streams={}

MAX_DISPLAY_LEN=64
PGIE_CLASS_ID_EMPTY = 0
PGIE_CLASS_ID_OCCUPIED = 1
PGIE_CLASS_ID_CAR = 2
PGIE_CLASS_ID_PERSON = 3
PGIE_CLASS_ID_TRUCK = 4
PGIE_CLASS_ID_BUS = 5

MUXER_OUTPUT_WIDTH=1920
MUXER_OUTPUT_HEIGHT=1080
MUXER_BATCH_TIMEOUT_USEC=4000000

TILED_OUTPUT_WIDTH=1920
TILED_OUTPUT_HEIGHT=1080
GST_CAPS_FEATURES_NVMM="memory:NVMM"
OSD_PROCESS_MODE= 1
OSD_DISPLAY_TEXT= 1
pgie_classes_str= ["empty", "occupied", "car","person","truck","bus"]

# IP = "localhost"
IP = "172.18.200.81"
PORT = "9092"
topic = ["cctv-rest-parkinglot", "cctv-rest-congest", "cctv-rest-event"]


def InitalizeKafka():
    ip = IP
    port = PORT

    producer = KafkaProducer(bootstrap_servers=[ip + ':' + port], value_serializer=lambda v: json.dumps(v, separators=(',', ':')).encode("utf-8"),api_version=(2,0,2))
    return producer

def SendJSON(producer, topic, json_data):
    # producer.send(topic, json_data).add_callback(on_send_success).add_errback(on_send_error)  
    producer.send(topic, json_data).add_callback(on_send_success).add_errback(on_send_error)

def on_send_success(record_metadata):
    # print(record_metadata.topic)
    # print(record_metadata.partition)
    # print(record_metadata.offset)
    return

def on_send_error(excp):
    log.error('I am an errback', exc_info=excp)
    # handle exception  

def SendParkinglot(interval, channel, u_data,tick) :
    if  u_data.send_parking_timer[channel-1]  >= interval  :
        u_data.clear_json_parkinglot()
        u_data.cctv_rest_parkinglot['cctv'] = channel
        u_data.cctv_rest_parkinglot['cctvState'] = u_data.cctvState
        if u_data.cctvState == 'valid':
            u_data.cctv_rest_parkinglot['availableParking'] = int(u_data.availableParking)
        else:
            pass
        u_data.cctv_rest_parkinglot['timestamp'] = int(time.time())
        
        SendJSON(u_data.producer,topic[0],u_data.cctv_rest_parkinglot)

        u_data.clear_send_parking_timer(channel)

    else :
        u_data.set_send_parking_timer(channel,tick)
        

def SendCongest(interval, channel, u_data,tick) :
    if  tick - u_data.past_send_congest_timer[channel-1] == interval  or  tick - u_data.past_send_congest_timer[channel-1] == interval - 10 :
        u_data.clear_json_congest()
        u_data.cctv_rest_congest['cctv'] = channel
        u_data.cctv_rest_congest['object'] = u_data.object_list
        u_data.cctv_rest_congest['timestamp'] = int(time.time())

        SendJSON(u_data.producer, topic[1], u_data.cctv_rest_congest)
        u_data.clear_send_congest_timer(channel)
        u_data.set_past_send_congest_timer(channel,tick)
    
    else :
        u_data.set_past_send_congest_timer(channel,tick)

def SendEvent(interval, channel, u_data,tick) : 
    if u_data.send_event_timer[channel-1]  >= interval:
        # u_data.clear_json_event()
        if u_data.sendPedestrian[channel-1] == "": # send first time
            u_data.sendPedestrian[channel-1] = u_data.personEvent_list['eventStatus']
            u_data.event_list.append(u_data.personEvent_list)
        elif u_data.sendPedestrian[channel-1] != "": 
            if u_data.sendPedestrian[channel-1] == u_data.personEvent_list['eventStatus']: # same state is ignored
                pass
            else:
                u_data.sendPedestrian[channel-1] = u_data.personEvent_list['eventStatus'] # different state is accepted and updated
                u_data.event_list.append(u_data.personEvent_list)
        if u_data.sendParkingOutside[channel-1] == "": # send first time
            u_data.sendParkingOutside[channel-1] = u_data.carEvent_list['eventStatus']
            u_data.event_list.append(u_data.carEvent_list)
        elif u_data.sendParkingOutside[channel-1] != "": 
            if u_data.sendParkingOutside[channel-1] == u_data.carEvent_list['eventStatus']: # same state is ignored
                pass
            else:
                u_data.sendParkingOutside[channel-1] = u_data.carEvent_list['eventStatus'] # different state is accepted and updated
                u_data.event_list.append(u_data.carEvent_list)
        if len(u_data.event_list) != 0:
            u_data.cctv_rest_event['cctv'] = channel
            u_data.cctv_rest_event['event'] = u_data.event_list
            u_data.cctv_rest_event['timestamp'] = int(time.time())
    
            SendJSON(u_data.producer, topic[2], u_data.cctv_rest_event)
        
        u_data.clear_send_timer(channel)
    
    else :
        u_data.set_send_timer(channel,tick)


def tiler_src_pad_buffer_probe(pad,info,u_data):

    frame_number=0
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    u_data.clear_part1()
    
    # sendParkingOutside = u_data.sendParkingOutside 
    # sendPedestrian = u_data.sendPedestrian
    
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list

    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        
        u_data.clear_part2()
        
        event_list = u_data.event_list
        
        # json
        cctv_rest_parkinglot = u_data.cctv_rest_parkinglot
        cctv_rest_congest = u_data.cctv_rest_congest
        cctv_rest_event = u_data.cctv_rest_event

        frame_number=frame_meta.frame_num
        l_obj=frame_meta.obj_meta_list
        source_index = frame_meta.source_id
        ch = int(u_data.channel[source_index])
        

        obj_counter = {
        PGIE_CLASS_ID_EMPTY : 0,
        PGIE_CLASS_ID_OCCUPIED : 0,
        PGIE_CLASS_ID_CAR : 0,
        PGIE_CLASS_ID_PERSON : 0,
        PGIE_CLASS_ID_TRUCK : 0,
        PGIE_CLASS_ID_BUS : 0
        }

        #Display Text
        display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_circle_params = display_meta.circle_params
        # Define Area
        u_data.danger_area, u_data.parking_area, u_data.not_parking_area, u_data.parking_space = ch_area(ch)
        
        while l_obj is not None:
            try: 
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break

            # Define
            area = ""
            obj_score = obj_meta.confidence
            obj_meta.rect_params.border_width = 1

            # bbox_color
            if obj_meta.class_id == 0 :
                obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.0)
                predicted_class = "empty"
            elif obj_meta.class_id == 1 :
                obj_meta.rect_params.border_color.set(0.0, 1.0, 0.0, 0.0)
                predicted_class = "occupied"
            elif obj_meta.class_id == 2 :
                obj_meta.rect_params.border_color.set(1.0, 1.0, 0.0, 0.0)
                predicted_class = "car"
            elif obj_meta.class_id == 3 :
                obj_meta.rect_params.border_color.set(1.0, 1.0, 1.0, 0.0)
                predicted_class = "person"
            elif obj_meta.class_id == 4 :
                obj_meta.rect_params.border_color.set(1.0, 0.0, 1.0, 0.0)
                predicted_class = "truck"
            elif obj_meta.class_id == 5 :
                obj_meta.rect_params.border_color.set(0.0, 0.0, 0.0, 0.0)
                predicted_class = "bus"
            
            score = str(predicted_class) + " " + str(round(obj_score,3))
            obj_meta.text_params.font_params.font_size = 8
            obj_meta.text_params.display_text = score

            # bbox point info
            bbox_top = obj_meta.rect_params.top
            bbox_left = obj_meta.rect_params.left
            bbox_width = obj_meta.rect_params.width
            bbox_height = obj_meta.rect_params.height

            # bbox bottom center point location
            bbox_bottom_x = int(bbox_left + bbox_width / 2)
            bbox_bottom_y = int(bbox_top + bbox_height) 
            if predicted_class == "empty" or predicted_class == "occupied":
                bbox_bottom_x = int(bbox_left + bbox_width / 2)
            bbox_center = (bbox_bottom_x , bbox_bottom_y)

            # Drw circle of bbox_center
            if ch == 1 :
                display_bbox_bottom_x = int(bbox_left + bbox_width / 2)
                display_bbox_bottom_y = int(bbox_top + bbox_height)
            elif ch == 2 : 
                display_bbox_bottom_x = int(bbox_left + bbox_width / 2) + 1920
                display_bbox_bottom_y = int(bbox_top + bbox_height)
            else :
                display_bbox_bottom_x = int(bbox_left + bbox_width / 2)
                display_bbox_bottom_y = int(bbox_top + bbox_height) + 1080
            
            # draw circle for person
            if obj_meta.class_id == 3 :
                py_nvosd_circle_params[obj_counter[3]].xc = int (display_bbox_bottom_x / 2)
                py_nvosd_circle_params[obj_counter[3]].yc = int (display_bbox_bottom_y / 2)
                py_nvosd_circle_params[obj_counter[3]].radius = 2
                py_nvosd_circle_params[obj_counter[3]].circle_color.set(1.0, 0.0, 1.0, 1.0)
                py_nvosd_circle_params[obj_counter[3]].has_bg_color = True
                py_nvosd_circle_params[obj_counter[3]].bg_color.set(1.0, 1.0, 1.0, 1.0)
            
            obj_counter[obj_meta.class_id] += 1

            # Polygon test
            if cv2.pointPolygonTest(u_data.danger_area, bbox_center, False) >= 0:
                area = "driving" 
                if predicted_class == "person" :
                    u_data.eventPedestrian = True
                    u_data.dangerPerson.append([bbox_bottom_x, bbox_bottom_y])
                    obj_meta.rect_params.border_color.set(1.0, 0.0, 0.0, 0.0)
            elif cv2.pointPolygonTest(u_data.not_parking_area, bbox_center, False) >= 0:
                area = "nonparking"
                if predicted_class == "car"  or predicted_class == "truck"    or predicted_class == "bus" :
                    u_data.eventParkingOutside = True
                    u_data.outsideCar.append([bbox_bottom_x, bbox_bottom_y])
            elif cv2.pointPolygonTest(u_data.parking_area, bbox_center, False) >= 0:
                area = "parking"
                if predicted_class == "empty" or predicted_class == "occupied" :
                    u_data.numOfSpaces +=1
            else:
                area = "other"
            u_data.availableParking = u_data.parking_space - obj_counter[1]
            if u_data.availableParking < 0:
                u_data.availableParking = 0
        
            # cctv_rest_congest topic
            if predicted_class == "empty" or predicted_class == "occupied" :
                pass
            else:
                u_data.object_list.append({"label": predicted_class,"position":[bbox_bottom_x, bbox_bottom_y],"area":area})
        
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break
        
        if ch == 1 or ch == 3:
            py_nvosd_text_params = display_meta.text_params[0]
            py_nvosd_text_params.display_text = "cctvState: {}\nTotal lots: {}\nAvailable lots: {}\n================\nEVENT CASE\n1.Parking outside: {}({})\n2.Danger area: {}({})".format(u_data.cctvState,u_data.parking_space,u_data.availableParking,u_data.eventParkingOutside,len(u_data.outsideCar),u_data.eventPedestrian,len(u_data.dangerPerson))
            py_nvosd_text_params.x_offset = 10
            py_nvosd_text_params.y_offset = 12
            py_nvosd_text_params.font_params.font_name = "Serif"
            py_nvosd_text_params.font_params.font_size = 10
            py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            py_nvosd_text_params.set_bg_clr = 1
            py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.7)
        else:
            py_nvosd_text_params = display_meta.text_params[0]
            py_nvosd_text_params.display_text = "cctvState: {}\nTotal lots: {}\nAvailable lots: {}\n================\nEVENT CASE\n1.Danger area: {}({})".format(u_data.cctvState,u_data.parking_space,u_data.availableParking,u_data.eventPedestrian,len(u_data.dangerPerson))
            py_nvosd_text_params.x_offset = 10
            py_nvosd_text_params.y_offset = 12
            py_nvosd_text_params.font_params.font_name = "Serif"
            py_nvosd_text_params.font_params.font_size = 10
            py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
            py_nvosd_text_params.set_bg_clr = 1
            py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.7)
        
        #Draw circle
        display_meta.num_circles = obj_counter[3]+1
        for i in range(0,display_meta.num_circles) :
            py_nvosd_circle_params = display_meta.circle_params[i]

        if frame_number % 10 == 0:
            # print("ch",ch,"space",u_data.parking_space,"detection:", obj_counter[0]+obj_counter[1])
            if u_data.parking_space > obj_counter[0]+obj_counter[1]:
                u_data.cctvState = "invalid"
                # print("change ch",ch, u_data.cctvState)
            else:
                u_data.cctvState = "valid"

        if u_data.cctvState == "invalid":
            u_data.availableParking = u_data.previousAvailableParking
        else:
            u_data.availableParking = u_data.parking_space - obj_counter[1] #parking_space-numOfOccupied
            if u_data.availableParking < 0:
                u_data.availableParking = 0
            u_data.previousAvailableParking = u_data.availableParking
        
        # cctv_rest_event topic
        if u_data.eventParkingOutside:
            u_data.carEvent_list = {"eventType":"parking_outside","eventStatus":"start","position":u_data.outsideCar}
        else:
            u_data.carEvent_list = {"eventType":"parking_outside","eventStatus":"end","position":[]}
        if u_data.eventPedestrian:
            u_data.personEvent_list = {"eventType":"pedestrain","eventStatus":"start","position":u_data.dangerPerson}
        else:
            u_data.personEvent_list = {"eventType":"pedestrain","eventStatus":"end","position":[]}
        
        interval = 0
        tick = cv2.getTickCount()/cv2.getTickFrequency()
        if u_data.past_send_timer[ch-1] !=0 :
            interval = tick - u_data.past_send_timer[ch-1]
        
        # cctv_rest_parkinglot topic
        SendParkinglot(5, ch, u_data,interval)
        # cctv_rest_congest topic
        test_tick = int(cv2.getTickCount()/cv2.getTickFrequency()) % 10
        SendCongest(1, ch, u_data,test_tick)

        # cctv_rest_event topic
        SendEvent(1, ch, u_data,interval)
        
        u_data.set_past_send_timer(ch,tick)

        # producer.flush()
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        # Get frame rate through this probe
        # fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps()
        try:
            l_frame=l_frame.next    
        except StopIteration:
            break

    return Gst.PadProbeReturn.OK



def cb_newpad(decodebin, decoder_src_pad,data):
    print("In cb_newpad\n")
    caps=decoder_src_pad.get_current_caps()
    gststruct=caps.get_structure(0)
    gstname=gststruct.get_name()
    source_bin=data
    features=caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=",gstname)
    if(gstname.find("video")!=-1):
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=",features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad=source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write("Failed to link decoder src pad to source bin ghost pad\n")
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")

def decodebin_child_added(child_proxy,Object,name,user_data):
    print("Decodebin child added:", name, "\n")
    if(name.find("decodebin") != -1):
        Object.connect("child-added",decodebin_child_added,user_data)

def create_source_bin(index,uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name="source-bin-%02d" %index
    print(bin_name)
    nbin=Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin=Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri",uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added",cb_newpad,nbin)
    uri_decode_bin.connect("child-added",decodebin_child_added,nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin,uri_decode_bin)
    bin_pad=nbin.add_pad(Gst.GhostPad.new_no_target("src",Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin

class databank :
    # kafka producer for send json
    producer = InitalizeKafka()
    channel = []
    send_timer = [0,0,0]
    send_parking_timer = [0,0,0]
    send_congest_timer = [0,0,0]
    past_send_congest_timer = [0,0,0]
    send_event_timer = [0,0,0]
    past_send_timer = [0,0,0]
    tick = 0

    danger_area = []
    parking_area = []
    not_parking_area = []
    parking_space = []
    availableParking = 0
    previousAvailableParking = 0
    cctvState = "valid"
    sendParkingOutside = ["","",""]
    sendPedestrian = ["","",""]
    
    # Define parameters
    object_list = []
    carEvent_list = {}
    personEvent_list = {}
    event_list = []
    numOfSpaces= 0
    eventPedestrian, eventParkingOutside = False,False
    dangerPerson = []
    outsideCar = []

    # json
    cctv_rest_parkinglot = {}
    cctv_rest_congest = {}
    cctv_rest_event = {}

    def clear_part1(self):
        databank.danger_area = []
        databank.parking_area = []
        databank.not_parking_area = []
        databank.parking_space = []
        databank.availableParking = 0
        # databank.previousAvailableParking = 0
        # databank.cctvState = "valid"
        self.cctvState = "valid"
    
    def clear_part2(self):
        databank.object_list = []
        databank.carEvent_list = {}
        databank.personEvent_list = {}
        databank.event_list = []
        self.numOfSpaces= 0
        self.eventPedestrian = False
        self.eventParkingOutside = False
        databank.dangerPerson = []
        databank.outsideCar = []


    def clear_json_parkinglot(self) :
        databank.cctv_rest_parkinglot = {}

    def clear_json_congest(self) :
        databank.cctv_rest_congest = {}

    def clear_json_event(self) :
        databank.cctv_test_congest = {}

    def set_send_parking_timer(self,channel,time) :
        self.send_parking_timer[channel-1] += time
    def set_send_timer(self,channel,time) :
        self.send_timer[channel-1] += time
    def set_past_send_timer(self,channel,time) :
        self.past_send_timer[channel-1] = time
    

    def clear_send_parking_timer(self,channel) :
        self.send_parking_timer[channel-1] = 0        
    def clear_send_timer(self,channel) :
        self.send_timer[channel-1] = 0        

    def set_send_congest_timer(self,channel,time) :
        self.send_congest_timer[channel-1] = time
    def set_past_send_congest_timer(self,channel,time) :
        self.past_send_congest_timer[channel-1] = time
    def clear_send_congest_timer(self,channel) :
        self.send_congest_timer[channel-1] = 0

def main(args):
    # Check input arguments
    if len(args) < 2:
        sys.stderr.write("usage: %s <uri1> [uri2] ... [uriN]\n" % args[0])
        sys.exit(1)

    for i in range(0,len(args)-1):
        fps_streams["stream{0}".format(i)]=GETFPS(i)
    number_sources=int((len(args)-1) / 2) 
    # number_sources = args[1]
    userdata = databank()
    
    
    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    is_live = False

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    print("Creating streamux \n ")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    pipeline.add(streammux)
    for i in range(number_sources):
        print("Creating source_bin ",i," \n ")
        userdata.channel.append(args[2*i+2])
        uri_name=args[2*i+1]
        if uri_name.find("rtsp://") == 0 :
            is_live = True
        source_bin=create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")
        pipeline.add(source_bin)
        padname="sink_%u" %i
        sinkpad= streammux.get_request_pad(padname) 
        if not sinkpad:
            sys.stderr.write("Unable to create sink pad bin \n")
        srcpad=source_bin.get_static_pad("src")
        if not srcpad:
            sys.stderr.write("Unable to create src pad bin \n")
        srcpad.link(sinkpad)

    queue1=Gst.ElementFactory.make("queue","queue1")
    queue2=Gst.ElementFactory.make("queue","queue2")
    queue3=Gst.ElementFactory.make("queue","queue3")
    queue4=Gst.ElementFactory.make("queue","queue4")
    queue5=Gst.ElementFactory.make("queue","queue5")

    pipeline.add(queue1)
    pipeline.add(queue2)
    pipeline.add(queue3)
    pipeline.add(queue4)
    pipeline.add(queue5)

    print("Creating Pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")
    print("Creating tiler \n ")
    tiler=Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")
    print("Creating nvvidconv \n ")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")
    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")
    nvosd.set_property('process-mode',OSD_PROCESS_MODE)
    nvosd.set_property('display-text',OSD_DISPLAY_TEXT)
    if(is_aarch64()):
        print("Creating transform \n ")
        transform=Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
        # transform=Gst.ElementFactory.make("queue", "queue")
        if not transform:
            sys.stderr.write(" Unable to create transform \n")

    print("Creating EGLSink \n")
    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    # sink = Gst.ElementFactory.make("nvoverlaysink", "nvvideo-renderer")
    # sink.set_property('sync',0)
    if not sink:
        sys.stderr.write(" Unable to create egl sink \n")

    if is_live:
        print("Atleast one of the sources is live")
        streammux.set_property('live-source', 1)

    streammux.set_property('live-source', 1)
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', number_sources)
    streammux.set_property('batched-push-timeout', 4000000)
    pgie.set_property('config-file-path', "dstest_pgie_config.txt")
    pgie_batch_size=pgie.get_property("batch-size")
    if(pgie_batch_size != number_sources):
        print("WARNING: Overriding infer-config batch-size",pgie_batch_size," with number of sources ", number_sources," \n")
        pgie.set_property("batch-size",number_sources)
        
    if number_sources == 3 :
        tiler_rows = 2
        tiler_columns = 2
    else :
        tiler_rows=int(math.sqrt(number_sources))
        tiler_columns=int(math.ceil((1.0*number_sources)/tiler_rows))
    tiler.set_property("rows",tiler_rows)
    tiler.set_property("columns",tiler_columns)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)
    sink.set_property("qos",0)

    print("Adding elements to Pipeline \n")
    pipeline.add(pgie)
    pipeline.add(tiler)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    if is_aarch64():
        pipeline.add(transform)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    streammux.link(queue1)
    queue1.link(pgie)
    pgie.link(queue2)
    queue2.link(tiler)
    tiler.link(queue3)
    queue3.link(nvvidconv)
    nvvidconv.link(queue4)
    queue4.link(nvosd)
    if is_aarch64():
        nvosd.link(queue5)
        queue5.link(transform)
        transform.link(sink)
    else:
        nvosd.link(queue5)
        queue5.link(sink)   

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)
    tiler_src_pad=pgie.get_static_pad("src")
    if not tiler_src_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        # tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)
        tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, userdata)

    # List the sources
    print("Now playing...")
    for i, source in enumerate(args):
        if (i != 0 and i%2 != 0):
            print(i, ": ", source)

    print("Starting pipeline \n")
    # start play back and listed to events		
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))