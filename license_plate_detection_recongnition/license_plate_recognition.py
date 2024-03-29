import sys
sys.path.append('../')
from pathlib import Path
import gi
import configparser
import argparse
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
from ctypes import *
import time
import sys
import math
import platform
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.FPS import PERF_DATA
from time import time

import pyds
import time
import math

no_display = False
silent = False
file_loop = False
perf_data = None


PGIE_CONFIG_FILE = "pgie_config_yolov4_test.txt"
SGIE1_CONFIG_FILE = "lpd_yolov4-tiny_us.txt"
TRACKER_CONFIG_FILE = "dstest2_tracker_config.txt"
MAX_DISPLAY_LEN=64
PGIE_CLASS_ID_CAR = 0
PGIE_CLASS_ID_PERSON = 1
SGIE_CLASS_ID_LPR = 2
MUXER_OUTPUT_WIDTH=1920
MUXER_OUTPUT_HEIGHT=1080
MUXER_BATCH_TIMEOUT_USEC=4000000
TILED_OUTPUT_WIDTH=1920
TILED_OUTPUT_HEIGHT=1080
CH2_CENTER_LINE=[[1070,1066],[997,408]]
CH4_CENTER_LINE=[[877,1080],[965,200]]
GST_CAPS_FEATURES_NVMM="memory:NVMM"
OSD_PROCESS_MODE= 0
OSD_DISPLAY_TEXT= 1
TRACKING_PROCESS = 1
past_tracking_meta=[0]
pgie_classes_str= ["Car", "Person"]


# def pgie_src_pad_buffer_probe(pad,info,u_data):
def nvanalytics_src_pad_buffer_probe(pad,info,u_data):
    frame_number=0
    num_rects=0
    got_fps = False
    flag_for_check_abnormal = 0

    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list

    past_circle_params = u_data.previous_point_dict
    object_id_in_roi = u_data.object_in_roi
    current_object_id_in_roi = u_data.current_object_in_roi

    object_id_in_passage = u_data.object_in_passage
    dict_car_in_passage_time = u_data.dict_car_in_passage_time
    dict_bbox_x_in_passage = u_data.dict_bbox_x_in_passage
    dict_bbox_y_in_passage = u_data.dict_bbox_y_in_passage
    double_parking = u_data.double_parking
    stepping_line = u_data.stepping_line

    point_x = u_data.trajectory_x
    point_y = u_data.trajectory_y

    x0 = u_data.trajectory_x0
    y0 = u_data.trajectory_y0
    
    

    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        
        ### print all u_data
        # u_data.print_object_in_roi_info()
        # u_data.print_previous_point_dict_info()   
        u_data.clear_current_object_in_roi()
        u_data.clear_current_object_in_passage()
        

        frame_number=frame_meta.frame_num
        l_obj=frame_meta.obj_meta_list
        num_rects = frame_meta.num_obj_meta

        obj_counter = {
            PGIE_CLASS_ID_CAR:0,
            PGIE_CLASS_ID_PERSON:0,
            SGIE_CLASS_ID_LPR:0
        }
        
        #Display Text
        display_meta=pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        # py_nvosd_circle_params = display_meta.circle_params
        
        
        roi_obj_count = 0
        line_num = 0
        text_num = 0
        while l_obj :
            try: 
                # Casting l_obj.data to pyds.NvDsObjectMeta
                obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
            except StopIteration:
                break
            obj_counter[obj_meta.class_id] += 1

            if (obj_meta.class_id == 0 or obj_meta.class_id == 1):
                obj_meta.rect_params.border_width = 0
                obj_meta.text_params.text_bg_clr.alpha =0
                obj_meta.text_params.font_params.font_color.set(1.0, 1.0, 1.0, 0.0)
                obj_meta.text_params.font_params.font_size = 15
            
            #ROI 영역 내에 있는 obj_meta에 대해서만 처리함
            l_user_meta=obj_meta.obj_user_meta_list
            while l_user_meta:
                try:
                    user_meta = pyds.NvDsUserMeta.cast(l_user_meta.data)

                    if user_meta.base_meta.meta_type == pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META"):   
                        user_meta_data = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                        
                        #객체가 roi영역에 존재하고 클래스가 차량일때
                        if (user_meta_data.roiStatus) and obj_meta.class_id == 0   :
                            #객체가 통로 구간에 있을 경우
                            if str(user_meta_data.roiStatus).find("passage") > 0 :
                                #매 프레임 새로운 차량 나오면 리스트와 3개의 딕셔너리에 정보 추가
                                if not obj_meta.object_id in object_id_in_passage :
                                    object_id_in_passage.append(obj_meta.object_id)
                                    dict_car_in_passage_time[obj_meta.object_id] = time.time()
                                    dict_bbox_x_in_passage[obj_meta.object_id] =  int(obj_meta.rect_params.left + obj_meta.rect_params.width / 2)
                                    dict_bbox_y_in_passage[obj_meta.object_id] =  int(obj_meta.rect_params.top + obj_meta.rect_params.height) 
                                
                
                                for key in object_id_in_passage :
                                    if obj_meta.object_id == key :
                                        if (time.time() - dict_car_in_passage_time[key] > 5) and int(time.time() - dict_car_in_passage_time[key]) %  5 == 0 :
                                            # print("teime : ", time.time() - dict_car_in_passage_time[key])
                                            # bbox point info
                                            bbox_top = obj_meta.rect_params.top
                                            bbox_left = obj_meta.rect_params.left
                                            bbox_width = obj_meta.rect_params.width
                                            bbox_height = obj_meta.rect_params.height

                                            # bbox bottom center point location
                                            bbox_bottom_x = int(bbox_left + bbox_width / 2)
                                            bbox_bottom_y = int(bbox_top + bbox_height) 
                                            previous_x = dict_bbox_x_in_passage[key]
                                            previous_y = dict_bbox_y_in_passage[key]
                                            
                                            # print("ID : ", key, "dist : ", calc_distance_between_points(bbox_bottom_x, bbox_bottom_y, previous_x, previous_y))
                                            if calc_distance_between_points(bbox_bottom_x, bbox_bottom_y, previous_x, previous_y) < 30 :
                                                if int(time.time() - dict_car_in_passage_time[key]) % 10 == 0 :
                                                    if not key in double_parking :
                                                        double_parking.append(key)
                                            else :
                                                if key in double_parking :
                                                    double_parking.remove(key)
                                            
                                # print("@@@object_id_in_passage : ", object_id_in_passage) 
                                # print("###double_parking : ", double_parking)
                                obj_meta.rect_params.bg_color.set(0.0, 0.6, 0.6, 0.5)     
                                obj_meta.text_params.text_bg_clr.alpha =1
                                obj_meta.text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
                                obj_meta.rect_params.has_bg_color = 1         

                                if obj_meta.object_id in double_parking :
                                    obj_meta.rect_params.bg_color.set(1.0, 0.0, 0.0, 0.4)
                                    obj_meta.rect_params.border_color.set(1.0, 0.0, 0.0, 0.6)
                                    obj_meta.rect_params.border_width = 4    
                                
                                roi_obj_count += 1
                            
                            #객체가 차선을 밟고 주차하는 경우
                            elif str(user_meta_data.roiStatus).find("stepping") > 0 :
                                obj_meta.text_params.text_bg_clr.alpha =1
                                obj_meta.text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
                                obj_meta.rect_params.has_bg_color = 1 
                                obj_meta.rect_params.bg_color.set(1.0, 0.0, 1.0, 0.4)
                                obj_meta.rect_params.border_color.set(1.0, 0.0, 1.0, 0.6)
                                obj_meta.rect_params.border_width = 4

                                if not obj_meta.object_id in stepping_line :
                                    stepping_line.append(obj_meta.object_id)


                            #객체가 통로 구간에 있을 경우
                            elif str(user_meta_data.roiStatus).find("parking") > 0 :
                                obj_meta.text_params.text_bg_clr.alpha =0
                                obj_meta.text_params.font_params.font_color.set(1.0, 1.0, 1.0, 0.0)
                                obj_meta.rect_params.border_color.set(0.0, 0.0, 1.0, 0.6)
                                obj_meta.rect_params.border_width = 3
                                obj_meta.rect_params.has_bg_color = 0     

                                roi_obj_count += 1 
                        
                         
                        if "lpd" in obj_meta.obj_label :
                            print("## class_id : ", obj_meta.class_id , "object_parent : ", obj_meta.parent)  
                            obj_meta.rect_params.bg_color.set(1.0, 0.0, 0.0, 0.4)
                            obj_meta.rect_params.border_color.set(1.0, 0.0, 0.0, 0.6)
                            obj_meta.rect_params.border_width = 4
                       
                                

       
                except StopIteration:
                    break

                try:
                    l_user_meta = l_user_meta.next
                except StopIteration:
                    break
            try: 
                l_obj=l_obj.next
            except StopIteration:
                break
        
        if frame_meta.source_id == 0 :
            py_nvosd_text_params = display_meta.text_params[0]
            py_nvosd_text_params.display_text = "Double Parking Count : {} : {}\nStepping Line Count : {} : {}".format(len(double_parking), double_parking, len(stepping_line) ,stepping_line)
            py_nvosd_text_params.x_offset = 10
            py_nvosd_text_params.y_offset = 12
            py_nvosd_text_params.font_params.font_name = "Serif"
            py_nvosd_text_params.font_params.font_size = 25
            py_nvosd_text_params.font_params.font_color.set(0.0, 1.0, 0.0, 1.0)
            py_nvosd_text_params.set_bg_clr = 1
            py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 0.7)

        stream_index = "stream{0}".format(frame_meta.pad_index)
        global perf_data
        perf_data.update_fps(stream_index)

        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)

        try:
            l_frame=l_frame.next
        except StopIteration:
            break
    
        

    return Gst.PadProbeReturn.OK


def dot(vevtor1, vector2):
    return vevtor1[0]*vector2[0]+vevtor1[1]*vector2[1]

def calc_angle_between_2line(x1, y1, x2, y2, x3, y3, x4, y4):
    # Get nicer vector form
    vector1 = [(x1-x2), (y1-y2)]
    vector2 = [(x3-x4), (y3-y4)]
    
    dot_prod = dot(vector1, vector2)
    # Get magnitudes
    magA = dot(vector1, vector1)**0.5
    magB = dot(vector2, vector2)**0.5
    # Get cosine value
    cos_ = dot_prod/magA/magB
    # Get angle in radians and then convert to degrees
    angle = math.acos(dot_prod/magB/magA)
    # Basically doing angle <- angle mod 360
    ang_deg = math.degrees(angle)%360
    
    if ang_deg-180 >= 0 :
        result = 360 - ang_deg
        # As in if statement
    else: 
        result = ang_deg
    
    if result >= 90 :
        result = 180 - result

    return round(result,2)

def calc_distance_between_points(x, y, previous_x, previous_y) :
        len_x = (x - previous_x)**2
        len_y = (y - previous_y)**2
        dist = int(math.sqrt(len_x + len_y))

        return dist
class trajectory_point :

    object_in_roi = []
    current_object_in_roi = []

    # 이상 주차 검출용 
    object_in_passage = []
    dict_car_in_passage_time = {}
    dict_bbox_x_in_passage = {}
    dict_bbox_y_in_passage = {}

    double_parking = []
    stepping_line = []

    

    previous_point_dict = {}

    trajectory_x = {}
    trajectory_y = {}
    trajectory_x0 = {}
    trajectory_y0 = {}
    

    def print_trajectory_point_info(self):
        print("trajectory_x : ", self.trajectory_x)
        print("trajectory_y : ", self.trajectory_y)
        print("trajectory_x0 : ", self.trajectory_x0)
        print("trajectory_y0 : ", self.trajectory_y0)
        
    
    # def point_setting(self, obj_num, ) :

    def clear_previous_point(self):
        previous_point_dict = {}

    def print_object_in_roi_info(self):
        print("len(object_in_roi : ", len(self.object_in_roi))
        print("object_in_roi : ", self.object_in_roi)
    
    def print_current_object_in_roi(self):
        print("len(current_object_in_roi : ", len(trajectory_point.current_object_in_roi))
        print("current_object_in_roi : ", trajectory_point.current_object_in_roi)

    def print_previous_point_dict_info(self):
        print("len(previous_point_dict : ", len(self.previous_point_dict))
        print("previous_point_dict : ", self.previous_point_dict)

    def __init__(self):
        self.previous_point_dict = {}
    
    def clear_current_object_in_roi(self):
        trajectory_point.current_object_in_roi = []

    def clear_current_object_in_passage(self):
        trajectory_point.current_object_in_passage = []

    def clear_double_parking_id_list(self):
        double_parking_id_list = []

    def pop_double_parking_id_list(id, self):
        if int(id) in self.double_parking_id_list :
            del self.double_parking_id_list[id]
    

    





def cb_newpad(decodebin, decoder_src_pad,data):
    print("In cb_newpad\n")
    caps=decoder_src_pad.get_current_caps()
    if not caps:
        caps = decoder_src_pad.query_caps()
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

    if "source" in name:
        source_element = child_proxy.get_by_name("source")
        if source_element.find_property('drop-on-latency') != None:
            Object.set_property("drop-on-latency", True)



def create_source_bin(index,uri):
    print("Creating source bin")

    bin_name="source-bin-%02d" %index
    print(bin_name)
    nbin=Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    if file_loop:
        # use nvurisrcbin to enable file-loop
        uri_decode_bin=Gst.ElementFactory.make("nvurisrcbin", "uri-decode-bin")
        uri_decode_bin.set_property("file-loop", 1)
    else:
        uri_decode_bin=Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    uri_decode_bin.set_property("uri",uri)
    uri_decode_bin.connect("pad-added",cb_newpad,nbin)
    uri_decode_bin.connect("child-added",decodebin_child_added,nbin)

   
    Gst.Bin.add(nbin,uri_decode_bin)
    bin_pad=nbin.add_pad(Gst.GhostPad.new_no_target("src",Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin


def main(args, requested_pgie=None, request_tracker=None, config=None, disable_probe=False):
    global perf_data
    perf_data = PERF_DATA(len(args))

    number_sources=len(args)

    userdata = trajectory_point()

    # Standard GStreamer initialization
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
        uri_name=args[i]
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
    queue6=Gst.ElementFactory.make("queue","queue6")
    queue7=Gst.ElementFactory.make("queue","queue7")
    queue8=Gst.ElementFactory.make("queue","queue8")
    pipeline.add(queue1)
    pipeline.add(queue2)
    pipeline.add(queue3)
    pipeline.add(queue4)
    pipeline.add(queue5)
    pipeline.add(queue6)
    pipeline.add(queue7)
    pipeline.add(queue8)

    nvdslogger = None
    transform = None

    print("Creating Pgie \n ")
    if requested_pgie != None and (requested_pgie == 'nvinferserver' or requested_pgie == 'nvinferserver-grpc') :
        pgie = Gst.ElementFactory.make("nvinferserver", "primary-inference")
    elif requested_pgie != None and requested_pgie == 'nvinfer':
        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    else:
        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")

    if not pgie:
        sys.stderr.write(" Unable to create pgie :  %s\n" % requested_pgie)
    
    sgie1 = Gst.ElementFactory.make("nvinfer", "secondary1-nvinference-engine")
    if not sgie1:
        sys.stderr.write(" Unable to make sgie1 \n")

    print("Creating Tracker \n ")
    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not tracker:
        sys.stderr.write(" Unable to create tracker \n")

    print("Creating nvdsanalytics \n ")
    nvanalytics = Gst.ElementFactory.make("nvdsanalytics", "analytics")
    if not nvanalytics:
        sys.stderr.write(" Unable to create nvanalytics \n")
    nvanalytics.set_property("config-file", "config_nvdsanalytics_test.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_cctv01.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_cctv02.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_cctv03.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_cctv04.txt")
    # nvanalytics.set_property("config-file", "config_nvdsanalytics_stepping_line.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_for_stepping_line_cctv02.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_for_stepping_line_cctv03.txt")
    # nvanalytics.set_property("config-file", "nvdsanalytics_for_stepping_line_cctv04.txt")


    if disable_probe:
        # Use nvdslogger for perf measurement instead of probe function
        print ("Creating nvdslogger \n")
        nvdslogger = Gst.ElementFactory.make("nvdslogger", "nvdslogger")

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


    if no_display:
        print("Creating Fakesink \n")
        sink = Gst.ElementFactory.make("fakesink", "fakesink")
        sink.set_property('enable-last-sample', 0)
        sink.set_property('sync', 0)
    else:
        if(is_aarch64()):
            print("Creating transform \n ")
            transform=Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
            if not transform:
                sys.stderr.write(" Unable to create transform \n")
        print("Creating EGLSink \n")
        sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")

    if not sink:
        sys.stderr.write(" Unable to create sink element \n")

    if is_live:
        print("At least one of the sources is live")
        streammux.set_property('live-source', 1)

    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', number_sources)
    streammux.set_property('batched-push-timeout', 4000000)

    if requested_pgie == "nvinferserver" and config != None:
        pgie.set_property('config-file-path', config)
    elif requested_pgie == "nvinferserver-grpc" and config != None:
        pgie.set_property('config-file-path', config)
    elif requested_pgie == "nvinfer" and config != None:
        pgie.set_property('config-file-path', config)
    else:
        pgie.set_property('config-file-path', PGIE_CONFIG_FILE)
        # pgie.set_property('config-file-path', "dstest3_pgie_config.txt")
    pgie_batch_size=pgie.get_property("batch-size")

    sgie1.set_property('config-file-path', SGIE1_CONFIG_FILE)

    if(pgie_batch_size != number_sources):
        print("WARNING: Overriding infer-config batch-size",pgie_batch_size," with number of sources ", number_sources," \n")
        pgie.set_property("batch-size",number_sources)
    tiler_rows=int(math.sqrt(number_sources))
    tiler_columns=int(math.ceil((1.0*number_sources)/tiler_rows))
    tiler.set_property("rows",tiler_rows)
    tiler.set_property("columns",tiler_columns)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)
    sink.set_property("qos",0)

    #Set properties of tracker
    config = configparser.ConfigParser()
    config.read(TRACKER_CONFIG_FILE)
    config.sections()

    for key in config['tracker']:
        if key == 'tracker-width' :
            tracker_width = config.getint('tracker', key)
            tracker.set_property('tracker-width', tracker_width)
        if key == 'tracker-height' :
            tracker_height = config.getint('tracker', key)
            tracker.set_property('tracker-height', tracker_height)
        if key == 'gpu-id' :
            tracker_gpu_id = config.getint('tracker', key)
            tracker.set_property('gpu_id', tracker_gpu_id)
        if key == 'll-lib-file' :
            tracker_ll_lib_file = config.get('tracker', key)
            tracker.set_property('ll-lib-file', tracker_ll_lib_file)
        if key == 'll-config-file' :
            tracker_ll_config_file = config.get('tracker', key)
            tracker.set_property('ll-config-file', tracker_ll_config_file)
        if key == 'enable-batch-process' :
            tracker_enable_batch_process = config.getint('tracker', key)
            tracker.set_property('enable_batch_process', tracker_enable_batch_process)
        if key == 'enable-past-frame' :
            tracker_enable_past_frame = config.getint('tracker', key)
            tracker.set_property('enable_past_frame', tracker_enable_past_frame)


    print("Adding elements to Pipeline \n")
    pipeline.add(pgie)
    pipeline.add(tracker)
    pipeline.add(nvanalytics)
    pipeline.add(sgie1)
    if nvdslogger:
        pipeline.add(nvdslogger)
    pipeline.add(tiler)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    if transform:
        pipeline.add(transform)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    streammux.link(queue1)
    queue1.link(pgie)
    pgie.link(queue2)
    queue2.link(tracker)
    tracker.link(queue3)
    queue3.link(sgie1)
    sgie1.link(queue4)
    queue4.link(nvanalytics)
    nvanalytics.link(queue5)
    
    # queue3.link(nvanalytics)
    # nvanalytics.link(queue4)
    # queue4.link(sgie1)
    # sgie1.link(queue5)

    if nvdslogger:
        queue5.link(nvdslogger)
        nvdslogger.link(tiler)
    else:
        queue5.link(tiler)
    tiler.link(queue6)
    queue6.link(nvvidconv)
    nvvidconv.link(queue7)
    queue7.link(nvosd)
    if transform:
        nvosd.link(queue8)
        queue8.link(transform)
        transform.link(sink)
    else:
        nvosd.link(queue8)
        queue8.link(sink)   

    # create an event loop and feed gstreamer bus mesages to it
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)

    nvanalytics_src_pad=nvanalytics.get_static_pad("src")
    if not nvanalytics_src_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        # if not disable_probe:
        nvanalytics_src_pad.add_probe(Gst.PadProbeType.BUFFER, nvanalytics_src_pad_buffer_probe, userdata)
        # perf callback function to print fps every 5 sec
        GLib.timeout_add(5000, perf_data.perf_print_callback)


    # pgie_src_pad=pgie.get_static_pad("src")
    # if not pgie_src_pad:
    #     sys.stderr.write(" Unable to get src pad \n")
    # else:
    #     # if not disable_probe:
    #     pgie_src_pad.add_probe(Gst.PadProbeType.BUFFER, pgie_src_pad_buffer_probe, 0)
    #     # perf callback function to print fps every 5 sec
    #     GLib.timeout_add(5000, perf_data.perf_print_callback)

    # List the sources
    print("Now playing...")
    for i, source in enumerate(args):
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

def parse_args():

    parser = argparse.ArgumentParser(prog="deepstream_test_3",
                    description="deepstream-test3 multi stream, multi model inference reference app")
    parser.add_argument(
        "-i",
        "--input",
        help="Path to input streams",
        nargs="+",
        metavar="URIs",
        default=["a"],
        required=True,
    )
    parser.add_argument(
        "-c",
        "--configfile",
        metavar="config_location.txt",
        default=None,
        help="Choose the config-file to be used with specified pgie",
    )
    parser.add_argument(
        "-g",
        "--pgie",
        default=None,
        help="Choose Primary GPU Inference Engine",
        choices=["nvinfer", "nvinferserver", "nvinferserver-grpc"],
    )
### add here
    parser.add_argument(
        "-t",
        "--tracker",
        metavar="config_location.txt",
        default=None,
        help="Choose the config-file to be used with specified tracker",
    )
### add end
    parser.add_argument(
        "--no-display",
        action="store_true",
        default=False,
        dest='no_display',
        help="Disable display of video output",
    )
    parser.add_argument(
        "--file-loop",
        action="store_true",
        default=False,
        dest='file_loop',
        help="Loop the input file sources after EOS",
    )
    parser.add_argument(
        "--disable-probe",
        action="store_true",
        default=False,
        dest='disable_probe',
        help="Disable the probe function and use nvdslogger for FPS",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        default=False,
        dest='silent',
        help="Disable verbose output",
    )
    # Check input arguments
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    stream_paths = args.input
    pgie = args.pgie
    tracker = args.tracker
    config = args.configfile
    disable_probe = args.disable_probe
    global no_display
    global silent
    global file_loop
    no_display = args.no_display
    silent = args.silent
    file_loop = args.file_loop

    if config and not pgie or pgie and not config:
        sys.stderr.write ("\nEither pgie or configfile is missing. Please specify both! Exiting...\n\n\n\n")
        parser.print_help()
        sys.exit(1)
    if config:
        config_path = Path(config)
        if not config_path.is_file():
            sys.stderr.write ("Specified config-file: %s doesn't exist. Exiting...\n\n" % config)
            sys.exit(1)

    print(vars(args))
    return stream_paths, pgie, tracker, config, disable_probe

if __name__ == '__main__':
    stream_paths, pgie, tracker, config, disable_probe = parse_args()
    sys.exit(main(stream_paths, pgie, tracker, config, disable_probe))

