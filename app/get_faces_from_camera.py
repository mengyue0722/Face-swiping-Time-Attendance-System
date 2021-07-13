# 进行人脸录入

import dlib
import numpy as np
import cv2
import os
from skimage import io

# Dlib 正向人脸检测器
detector = dlib.get_frontal_face_detector()


class Face_Register:
    def __init__(self):
        pass


    #将录入的图片进行人脸检测，分截取人脸部分
    def process(self, path):
        photos_list = os.listdir(path)
        if photos_list:
            for i in range(len(photos_list)):
                # 调用 return_128d_features() 得到 128D 特征
                current_face_path = path + photos_list[i]
                print("%-40s %-20s" % (" >> 正在检测的人脸图像 / Reading image:", current_face_path))
                img_rd = cv2.imread(current_face_path)
                faces = detector(img_rd, 0)  # detector = dlib.get_frontal_face_detector() & Dlib人脸检测器
                # 遇到没有检测出人脸的图片跳过
                if len(faces) == 0:
                    i += 1
                else:
                    for k, d in enumerate(faces):
                        # 计算人脸区域矩形框大小
                        height = (d.bottom() - d.top())
                        width = (d.right() - d.left())
                        hh = int(height / 2)
                        ww = int(width / 2)

                        # 判断人脸矩形框是否超出 480x640
                        if (d.right() + ww) > 640 or (d.bottom() + hh > 480) or (d.left() - ww < 0) or (
                                d.top() - hh < 0):
                            print("%-40s %-20s" % (" >>超出范围，该图作废", current_face_path))

                        else:
                            img_blank = np.zeros((int(height * 2), width * 2, 3), np.uint8)
                            for ii in range(height * 2):
                                for jj in range(width * 2):
                                    img_blank[ii][jj] = img_rd[d.top() - hh + ii][d.left() - ww + jj]
                            cv2.imwrite(path +  str(i+1) + ".jpg", img_blank)
                            print("写入本地 / Save into：", str(path) + str(i+1) + ".jpg")
        else:
            print(" >> 文件夹内图像文件为空 / Warning: No images in " + path , '\n')

    def single_pocess(self,path):
        #读取人脸图像
        img_rd = cv2.imread(path)
        # Dlib的人脸检测器
        faces = detector(img_rd, 0)
        # 遇到没有检测出人脸的图片跳过
        if len(faces) == 0:
               return "none"
        else:
             for k, d in enumerate(faces):
                # 计算人脸区域矩形框大小
                 height = (d.bottom() - d.top())
                 width = (d.right() - d.left())
                 hh = int(height / 2)
                 ww = int(width / 2)

                 # 6. 判断人脸矩形框是否超出 480x640 / If the size of ROI > 480x640
                 if (d.right() + ww) > 640 or (d.bottom() + hh > 480) or (d.left() - ww < 0) or (
                     d.top() - hh < 0):
                     print("%-40s %-20s" % (" >>超出范围，该图作废", path))
                     return "big"

                 else:
                     img_blank = np.zeros((int(height * 2), width * 2, 3), np.uint8)
                     for ii in range(height * 2):
                         for jj in range(width * 2):
                             img_blank[ii][jj] = img_rd[d.top() - hh + ii][d.left() - ww + jj]
                     cv2.imwrite(path , img_blank)
                     print("写入本地 / Save into：", path)
                     return "right"

