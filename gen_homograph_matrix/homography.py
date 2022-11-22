####################################################################################
# 
#
#	find T for estimate real location using pixel location
#
#	Pixel location (in screen) : (Px,Py)
#	Real location (in real world) : (Rx,Ry) 
#	we assume camera's location as (0.0) in real world
# 
#	|a,b,c|     |Px|     |Rx|
#	|d,e,f|  X  |py|  => |Ry|
#	|0,0,1|     |1 |     |1 |
#
#	here is the code to find matrix T ( T = [[a,b,c],[d,e,f],[0,0,1]] )
#	
#   code by Baek Janghyun
####################################################################################

from __future__ import print_function
from ctypes import *
import math
import numpy as np


def input_dataset(location):
    file = open(location, "r")

    pixel = file.readline()
    p1x,p1y,p2x,p2y,p3x,p3y,p4x,p4y = pixel.split(sep=' ')
    # print(pixel)

    real_distance = file.readline()
    r1x,r1y,r2x,r2y,r3x,r3y,r4x,r4y = real_distance.split(sep=' ')
    # print(real_distance)

    file.close()

    result = np.array([[float(p1x),float(p2x),float(p3x),float(p4x)],[float(p1y),float(p2y),float(p3y),float(p4y)],[float(r1x),float(r2x),float(r3x),float(r4x)],[float(r1y),float(r2y),float(r3y),float(r4y)]])
    return result



    
def make_T(arr):
    # Point1,2,3 pixel map
    p_1 = np.array([ [arr[0][0],arr[0][1],arr[0][2]]
                    ,[arr[1][0],arr[1][1],arr[1][2]] 
                    ,[1,1,1]])
    # Point1,2,4 pixel map                
    p_2 = np.array([ [arr[0][0],arr[0][1],arr[0][3]]
                    ,[arr[1][0],arr[1][1],arr[1][3]] 
                    ,[1,1,1]])
    # Point1,3,4 pixel map
    p_3 = np.array([ [arr[0][0],arr[0][2],arr[0][3]]
                    ,[arr[1][0],arr[1][2],arr[1][3]] 
                    ,[1,1,1]])
    # Point2,3,4 pixel map                   
    p_4 = np.array([ [arr[0][1],arr[0][2],arr[0][3]]
                    ,[arr[1][1],arr[1][2],arr[1][3]] 
                    ,[1,1,1]])

    # Point1,2,3 Real map _x
    rx_1 = np.array([arr[2][0],arr[2][1],arr[2][2]])
     # Point1,2,4 Real map _x
    rx_2 = np.array([arr[2][0],arr[2][1],arr[2][3]])
     # Point1,3,4 Real map _x
    rx_3 = np.array([arr[2][0],arr[2][2],arr[2][3]])
     # Point2,3,4 Real map _x
    rx_4 = np.array([arr[2][1],arr[2][2],arr[2][3]])
    # Point1,2,3 Real map _y
    ry_1 = np.array([arr[3][0],arr[3][1],arr[3][2]])
     # Point1,2,4 Real map _y
    ry_2 = np.array([arr[3][0],arr[3][1],arr[3][3]])
     # Point1,3,4 Real map _y
    ry_3 = np.array([arr[3][0],arr[3][2],arr[3][3]])
     # Point2,3,4 Real map _y
    ry_4 = np.array([arr[3][1],arr[3][2],arr[3][3]])

    # calc reverse T
    reverse1 = np.linalg.inv(p_1)
    reverse2 = np.linalg.inv(p_2)
    reverse3 = np.linalg.inv(p_3)
    reverse4 = np.linalg.inv(p_4)
    
    # calc parameter a,b,c,d,e,f of Matrix T
    result_abc1 = np.dot(rx_1,reverse1)
    result_def1 = np.dot(ry_1,reverse1)
    result_abc2 = np.dot(rx_2,reverse2)
    result_def2 = np.dot(ry_2,reverse2)
    result_abc3 = np.dot(rx_3,reverse3)
    result_def3 = np.dot(ry_3,reverse3)
    result_abc4 = np.dot(rx_4,reverse4)
    result_def4 = np.dot(ry_4,reverse4)
    result_abc = (result_abc1 + result_abc2 + result_abc3 + result_abc4)/4
    result_def = (result_def1 + result_def2 + result_def3 + result_def4)/4

    # print("[a,b,c] : \n",result_abc)
    # print("[d,e,f] : \n", result_def)

    result = np.array([result_abc,result_def,[0,0,1]])
    return result

def calc_distance(a, b, arr_T):

    arr1 = np.dot(a, arr_T)
    arr2 = np.dot(b, arr_T)

    distance = ((arr1[0][0] - arr2[0][0])**2 + (arr1[0][1] - arr2[0][1])**2)**(1/2)
    return distance

array = input_dataset("./input2/ch02_pixel_info.txt")
homogrph_T = make_T(array)
# print(homogrph_T)

a = np.array([[938, 296, 1]])
b = np.array([[1026, 670, 1]])



print(calc_distance(a,b,homogrph_T))

