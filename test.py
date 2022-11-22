# file = open("./input/ch02_pixel_info.txt", "r")

# pixel = file.readline()
# p1x,p1y = pixel.split(sep=' ')
# # p1x,p2x,p3x,p4x,p1y,p2y,p3y,p4y = pixel
# print(pixel)
# print(int(p1x))
# print(int(p1y))
# file.close()

# file = open("./input2/ch02_pixel_info.txt", "r")

# pixel = file.readline()
# p1x,p1y,p2x,p2y,p3x,p3y,p4x,p4y = pixel.split(sep=' ')
# print(pixel)

# real_distance = file.readline()
# r1x,r1y,r2x,r2y,r3x,r3y,r4x,r4y = real_distance.split(sep=' ')
# print(real_distance)

# file.close()
import numpy as np

def input_dataset(location):
    file = open(location, "r")

    pixel = file.readline()
    p1x,p1y,p2x,p2y,p3x,p3y,p4x,p4y = pixel.split(sep=' ')
    print(pixel)

    real_distance = file.readline()
    r1x,r1y,r2x,r2y,r3x,r3y,r4x,r4y = real_distance.split(sep=' ')
    print(real_distance)

    file.close()

    result = np.array([[float(p1x),float(p2x),float(p3x),float(p4x)],[float(p1y),float(p2y),float(p3y),float(p4y)],[float(r1x),float(r2x),float(r3x),float(r4x)],[float(r1y),float(r2y),float(r3y),float(r4y)]])
    return result


array = input_dataset("./input2/ch02_pixel_info.txt")

print(array)

T = np.array([[ 1.43950250e-02,-1.46870844e-03,-1.35142245e+01],[-2.06401143e-03, -5.06024637e-02,  4.28567188e+01],[ 0.00000000e+00,  0.00000000e+00,  1.00000000e+00]])

a = np.array([[938, 296, 1]])
b = np.array([[1026, 670, 1]])

arr1 = np.dot(a, T)
arr2 = np.dot(b, T)

print("arr1 : " , arr1)
print("arr2 : " , arr2)

distance = ((arr1[0][0] - arr2[0][0])**2 + (arr1[0][1] - arr2[0][1])**2)**(1/2)
print(distance)

# def calc_distance(a, b, arr_T):

#     arr1 = np.dot(a, arr_T)
#     arr2 = np.dot(b, arr_T)

#     distance = ((arr1[0] - arr2[0])**2 + (arr1[1] - arr2[1])**2)**(1/2)
#     return distance

# array = input_dataset("./input2/ch02_pixel_info.txt")
# homogrph_T = make_T(array)
# # print(homogrph_T)

# a = np.array([[938, 296, 1]])
# b = np.array([[1026, 670, 1]])



