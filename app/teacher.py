from flask import Blueprint, render_template, redirect,request,Response,session,flash,jsonify,url_for
from app import db
from .models import Teacher,Faces,Course,SC,Attendance,Time_id,Student
from sqlalchemy.sql import exists
import base64
import os
from app import get_faces_from_camera as gf
from datetime import timedelta
import cv2
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import dlib
import time
import pandas as pd
import xlsxwriter
import xlwt
from io import BytesIO
from urllib.parse import quote
from flask import send_file
from sqlalchemy import create_engine
teacher = Blueprint('teacher',__name__,static_folder="static")
#本次签到的所有人员信息
attend_records = []
#本次签到的开启时间
the_now_time = ''

@teacher.route('/home')
def home():
    flag = session['id'][0]
    print(flag)
    courses = {}
    course = db.session.query(Course).filter(Course.t_id==session['id']).all()
    for c in course:
        num = db.session.query(SC).filter(SC.c_id==c.c_id).count()
        courses[c] = num
    return render_template('teacher/teacher_home.html',before=session['time'],flag=flag,name=session['name'],courses=courses)

# Dlib 正向人脸检测器
detector = dlib.get_frontal_face_detector()
# Dlib 人脸 landmark 特征点检测器
predictor = dlib.shape_predictor('app/static/data_dlib/shape_predictor_68_face_landmarks.dat')

# Dlib Resnet 人脸识别模型，提取 128D 的特征矢量
face_reco_model = dlib.face_recognition_model_v1("app/static/data_dlib/dlib_face_recognition_resnet_model_v1.dat")

class VideoCamera(object):
    def __init__(self):
        self.font = cv2.FONT_ITALIC
        # 通过opencv获取实时视频流
        self.video = cv2.VideoCapture(0)

        # 统计 FPS
        self.frame_time = 0
        self.frame_start_time = 0
        self.fps = 0

        # 统计帧数
        self.frame_cnt = 0

        # 用来存储所有录入人脸特征的数组
        self.features_known_list = []
        # 用来存储录入人脸名字
        self.name_known_list = []

        # 用来存储上一帧和当前帧 ROI 的质心坐标
        self.last_frame_centroid_list = []
        self.current_frame_centroid_list = []

        # 用来存储当前帧检测出目标的名字
        self.current_frame_name_list = []

        # 上一帧和当前帧中人脸数的计数器
        self.last_frame_faces_cnt = 0
        self.current_frame_face_cnt = 0

        # 用来存放进行识别时候对比的欧氏距离
        self.current_frame_face_X_e_distance_list = []

        # 存储当前摄像头中捕获到的所有人脸的坐标名字
        self.current_frame_face_position_list = []
        # 存储当前摄像头中捕获到的人脸特征
        self.current_frame_face_feature_list = []

        # 控制再识别的后续帧数
        # 如果识别出 "unknown" 的脸, 将在 reclassify_interval_cnt 计数到 reclassify_interval 后, 对于人脸进行重新识别
        self.reclassify_interval_cnt = 0
        self.reclassify_interval = 10

    def __del__(self):
        self.video.release()

        # 从 "features_all.csv" 读取录入人脸特征 / Get known faces from "features_all.csv"
    def get_face_database(self,cid):
        # print(cid)
        # course_sid = SC.query.filter(SC.c_id==cid).all()
        # all_sid = []
        # for sc in course_sid:
        #     all_sid.append(sc.s_id)
        # from_db_all_features = Faces.query.filter(Faces.s_id.in_(all_sid)).all()
        from_db_all_features = Faces.query.all()
        if from_db_all_features:
            for from_db_one_features in from_db_all_features:
                someone_feature_str = str(from_db_one_features.feature).split(',')
                self.name_known_list.append(from_db_one_features.s_id)
                features_someone_arr = []
                for one_feature in someone_feature_str:
                    if one_feature == '':
                        features_someone_arr.append('0')
                    else:
                        features_someone_arr.append(float(one_feature))
                self.features_known_list.append(features_someone_arr)
            # print("Faces in Database：", len(self.features_known_list))
            return 1
        else:
            # print('##### Warning #####', '\n')
            # print("'features' is empty")
            # print('##### End Warning #####')
            return 0

        # 更新 FPS / Update FPS of video stream
    def update_fps(self):
        now = time.time()
        self.frame_time = now - self.frame_start_time
        self.fps = 1.0 / self.frame_time
        self.frame_start_time = now

    # 计算两个128D向量间的欧式距离
    @staticmethod
    def return_euclidean_distance(feature_1, feature_2):
        feature_1 = np.array(feature_1)
        feature_2 = np.array(feature_2)
        dist = np.sqrt(np.sum(np.square(feature_1 - feature_2)))
        return dist

    # 生成的 cv2 window 上面添加说明文字 / putText on cv2 window
    def draw_note(self, img_rd):
        # 添加说明 (Add some statements
        cv2.putText(img_rd, "One person at a time:  ", (20, 40), self.font, 1, (255, 255, 255), 1,
                     cv2.LINE_AA)
        cv2.putText(img_rd, "FPS:   " + str(self.fps.__round__(2)), (20, 100), self.font, 0.8, (0, 255, 0), 1,
                    cv2.LINE_AA)
        # cv2.putText(img_rd, "Q: Quit", (20, 450), self.font, 0.8, (255, 255, 255), 1, cv2.LINE_AA)

    def draw_name(self, img_rd):
        # 在人脸框下面写人脸名字
        #print(self.current_frame_name_list)
        font = ImageFont.truetype("simsun.ttc", 30)
        img = Image.fromarray(cv2.cvtColor(img_rd, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img)
        draw.text(xy=self.current_frame_face_position_list[0], text=self.current_frame_name_list[0], font=font)
        img_rd = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return img_rd


        # 处理获取的视频流，进行人脸识别
    def get_frame(self,cid):
        stream = self.video
        # 1. 读取存放所有人脸特征的 csv / Get faces known from "features.all.csv"

        if self.get_face_database(cid):
            while stream.isOpened():
                self.frame_cnt += 1
                # print(">>> Frame " + str(self.frame_cnt) + " starts")
                flag, img_rd = stream.read()

                # 2. 检测人脸 / Detect faces for frame X
                faces = detector(img_rd, 0)

                # 3. 更新帧中的人脸数 / Update cnt for faces in frames
                self.last_frame_faces_cnt = self.current_frame_face_cnt
                self.current_frame_face_cnt = len(faces)
                filename = 'attendacnce.txt'
                with open(filename,'a') as file:
                    # 4.1 当前帧和上一帧相比没有发生人脸数变化 / If cnt not changes, 1->1 or 0->0
                    if self.current_frame_face_cnt == self.last_frame_faces_cnt:
                        # print("   >>> scene 1: 当前帧和上一帧相比没有发生人脸数变化 / No face cnt changes in this frame!!!")
                        if "unknown" in self.current_frame_name_list:
                            # print("   >>> 有未知人脸, 开始进行 reclassify_interval_cnt 计数")
                            self.reclassify_interval_cnt += 1

                        # 4.1.1 当前帧一张人脸 / One face in this frame
                        if self.current_frame_face_cnt == 1:
                            if self.reclassify_interval_cnt == self.reclassify_interval:
                                # print("   >>> scene 1.1 需要对于当前帧重新进行人脸识别 / Re-classify for current frame")

                                self.reclassify_interval_cnt = 0
                                self.current_frame_face_feature_list = []
                                self.current_frame_face_X_e_distance_list = []
                                self.current_frame_name_list = []

                                for i in range(len(faces)):
                                    shape = predictor(img_rd, faces[i])
                                    self.current_frame_face_feature_list.append(
                                        face_reco_model.compute_face_descriptor(img_rd, shape))

                                # a. 遍历捕获到的图像中所有的人脸 / Traversal all the faces in the database
                                for k in range(len(faces)):
                                    self.current_frame_name_list.append("unknown")

                                    # b. 每个捕获人脸的名字坐标 / Positions of faces captured
                                    self.current_frame_face_position_list.append(tuple(
                                        [faces[k].left(),
                                         int(faces[k].bottom() + (faces[k].bottom() - faces[k].top()) / 4)]))

                                    # c. 对于某张人脸，遍历所有存储的人脸特征 / For every face detected, compare it with all the faces in the database
                                    for i in range(len(self.features_known_list)):
                                        # 如果 person_X 数据不为空 / If the data of person_X is not empty
                                        if str(self.features_known_list[i][0]) != '0.0':
                                            # print("            >>> with person", str(i + 1), "the e distance: ", end='')
                                            e_distance_tmp = self.return_euclidean_distance(
                                                self.current_frame_face_feature_list[k],
                                                self.features_known_list[i])
                                            # print(e_distance_tmp)
                                            self.current_frame_face_X_e_distance_list.append(e_distance_tmp)
                                        else:
                                            # 空数据 person_X / For empty data
                                            self.current_frame_face_X_e_distance_list.append(999999999)
                                    # print("            >>> current_frame_face_X_e_distance_list:",
                                    #       self.current_frame_face_X_e_distance_list)

                                    # d. 寻找出最小的欧式距离匹配 / Find the one with minimum e distance
                                    similar_person_num = self.current_frame_face_X_e_distance_list.index(
                                        min(self.current_frame_face_X_e_distance_list))
                                    #print("   >>> Minimum e distance with ", self.name_known_list[similar_person_num],
                                    #      ": ",
                                    #      min(self.current_frame_face_X_e_distance_list))

                                    if min(self.current_frame_face_X_e_distance_list) < 0.4:
                                        # 在这里更改显示的人名
                                        # self.show_chinese_name()
                                        self.current_frame_name_list[k] = self.name_known_list[similar_person_num]
                                        # print("            >>> recognition result for face " + str(k + 1) + ": " +
                                        #       self.name_known_list[similar_person_num])
                                        now = time.strftime("%Y-%m-%d %H:%M", time.localtime())
                                        mm = self.name_known_list[similar_person_num] + '  ' + now + '  已签到\n'
                                        file.write(self.name_known_list[similar_person_num] + '  ' + now + '     已签到\n')
                                        attend_records.append(mm)
                                        #session['attend'].append(mm)
                                    else:
                                        pass
                                       # print(
                                        #    "            >>> recognition result for face " + str(
                                        #        k + 1) + ": " + "unknown")
                            else:
                                #print("   >>> scene 1.2 不需要对于当前帧重新进行人脸识别 / No re-classification for current frame")
                                # 获取特征框坐标 / Get ROI positions
                                for k, d in enumerate(faces):
                                    # 计算矩形框大小 / Compute the shape of ROI
                                    height = (d.bottom() - d.top())
                                    width = (d.right() - d.left())
                                    hh = int(height / 2)
                                    ww = int(width / 2)

                                    cv2.rectangle(img_rd,
                                                  tuple([d.left() - ww, d.top() - hh]),
                                                  tuple([d.right() + ww, d.bottom() + hh]),
                                                  (255, 255, 255), 2)

                                    self.current_frame_face_position_list[k] = tuple(
                                        [faces[k].left(),
                                         int(faces[k].bottom() + (faces[k].bottom() - faces[k].top()) / 4)])

                                   # print("   >>> self.current_frame_name_list:              ",
                                   #       self.current_frame_name_list[k])
                                   # print("   >>> self.current_frame_face_position_list:     ",
                                   #       self.current_frame_face_position_list[k])

                                    img_rd = self.draw_name(img_rd)

                    # 4.2 当前帧和上一帧相比发生人脸数变化
                    else:
                        #print("   >>> scene 2: 当前帧和上一帧相比人脸数发生变化 / Faces cnt changes in this frame")
                        self.current_frame_face_position_list = []
                        self.current_frame_face_X_e_distance_list = []
                        self.current_frame_face_feature_list = []

                        # 4.2.1 人脸数从 0->1 / Face cnt 0->1
                        if self.current_frame_face_cnt == 1:
                           # print("   >>> scene 2.1 出现人脸，进行人脸识别
                            self.current_frame_name_list = []

                            for i in range(len(faces)):
                                shape = predictor(img_rd, faces[i])
                                self.current_frame_face_feature_list.append(
                                    face_reco_model.compute_face_descriptor(img_rd, shape))

                            # a. 遍历捕获到的图像中所有的人脸
                            for k in range(len(faces)):
                                self.current_frame_name_list.append("unknown")

                                # b. 每个捕获人脸的名字坐标
                                self.current_frame_face_position_list.append(tuple(
                                    [faces[k].left(),
                                     int(faces[k].bottom() + (faces[k].bottom() - faces[k].top()) / 4)]))

                                # c. 对于某张人脸，遍历所有存储的人脸特征
                                #print(len(self.features_known_list))
                                for i in range(len(self.features_known_list)):
                                    # 如果 person_X 数据不为空 / If data of person_X is not empty
                                    if str(self.features_known_list[i][0]) != '0.0':
                                      #  print("            >>> with person", str(i + 1), "the e distance: ", end='')
                                        e_distance_tmp = self.return_euclidean_distance(
                                            self.current_frame_face_feature_list[k],
                                            self.features_known_list[i])
                                        #print(e_distance_tmp)
                                        self.current_frame_face_X_e_distance_list.append(e_distance_tmp)
                                    else:
                                        # 空数据 person_X
                                        self.current_frame_face_X_e_distance_list.append(999999999)

                                # d. 寻找出最小的欧式距离匹配
                                similar_person_num = self.current_frame_face_X_e_distance_list.index(
                                    min(self.current_frame_face_X_e_distance_list))

                                if min(self.current_frame_face_X_e_distance_list) < 0.4:
                                    # 在这里更改显示的人名
                                    # self.show_chinese_name()
                                    self.current_frame_name_list[k] = self.name_known_list[similar_person_num]
                                    #print("            >>> recognition result for face " + str(k + 1) + ": " +
                                     #     self.name_known_list[similar_person_num])
                                    now = time.strftime("%Y-%m-%d %H:%M", time.localtime())
                                    mm = self.name_known_list[similar_person_num] + '  ' + now + '  已签到\n'
                                    file.write(self.name_known_list[similar_person_num] + '  ' + now + '  已签到\n')
                                    #session['attend'].append(mm)
                                    attend_records.append(mm)
                                else:
                                    pass
                                   # print(
                                    #    "            >>> recognition result for face " + str(k + 1) + ": " + "unknown")

                            if "unknown" in self.current_frame_name_list:
                                self.reclassify_interval_cnt += 1

                        # 4.2.1 人脸数从 1->0 / Face cnt 1->0
                        elif self.current_frame_face_cnt == 0:
                            #print("   >>> scene 2.2 人脸消失, 当前帧中没有人脸 / No face in this frame!!!")

                            self.reclassify_interval_cnt = 0
                            self.current_frame_name_list = []
                            self.current_frame_face_feature_list = []

                # 5. 生成的窗口添加说明文字 / Add note on cv2 window
                self.draw_note(img_rd)

                self.update_fps()

                # cv2.namedWindow("camera", 1)
                # cv2.imshow("camera", img_rd)
               # print(">>> Frame ends\n\n")
                ret, jpeg = cv2.imencode('.jpg', img_rd)
                return jpeg.tobytes()

#老师端
@teacher.route('/reco_faces')
def reco_faces():
    return render_template('teacher/index.html')



def gen(camera,cid):
    while True:
        frame = camera.get_frame(cid)
        # 使用generator函数输出视频流， 每次请求输出的content类型是image/jpeg
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')


@teacher.route('/video_feed',methods=['GET','POST'])  # 这个地址返回视频流响应
def video_feed():
    return Response(gen(VideoCamera(),session['course']),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@teacher.route('/all_course')
def all_course():
    teacher_all_course = Course.query.filter(Course.t_id == session['id'])
    return render_template('teacher/course_attend.html',courses=teacher_all_course)

#开启签到
@teacher.route('/records',methods=["POST"])
def records():
    #开启签到后，开始单次的记录
    global attend_records
    attend_records = []
    now = time.strftime("%Y-%m-%d %H:00:00", time.localtime())
    cid = request.form.get("id")
    print(cid)
    session['course'] = cid
    session['now_time'] = now
    #添加课程考勤记录
    course = Course.query.filter(Course.c_id==cid).first()
    course.times = course.times + '/' + str(now)
    db.session.commit()
    the_course_students = SC.query.filter(SC.c_id==cid)
    student_ids = []
    for sc in the_course_students:
        student_ids.append(sc.s_id)
    #考勤记录初始化，所有人未签到
    all_students_attend = []
    for i in range(len(student_ids)):
        someone_addtend = Attendance(s_id=student_ids[i],c_id=cid,time=now,result='缺勤')
        all_students_attend.append(someone_addtend)
    db.session.add_all(all_students_attend)
    db.session.commit()
    #right_attend = Attendance.query.filter(Attendance.c_id==cid,Attendance.result==1)
    return render_template("teacher/index.html")

#实时显示当前签到人员
@teacher.route('/now_attend')
def now_attend():
    return jsonify(attend_records)

#停止签到
@teacher.route('/stop_records',methods=['POST'])
def stop_records():
    all_sid = []
    all_cid = session['course']
    all_time = session['now_time']
    for someone_attend in attend_records:
        print(someone_attend)
        sid = someone_attend.split('  ')[0]

        all_sid.append(sid)
    Attendance.query.filter(Attendance.time==all_time,Attendance.c_id==all_cid,Attendance.s_id.in_(all_sid)).update({'result':'已签到'},synchronize_session=False)
    db.session.commit()
    return redirect(url_for('teacher.all_course'))

@teacher.route('/select_all_records',methods=['GET','POST'])
def select_all_records():
    tid = session['id']
    dict = {}
    num = 0
    if request.method == 'POST':
        cid = request.form.get('course_id')
        sid = request.form.get('sid')
        select_time = request.form.get('time')
        if cid != '' and select_time !='' :
            courses = db.session.query(Course).filter(Course.t_id==tid,Course.c_id==cid)
            num = 0
            for course in courses:
                times = course.times.split('/')
                one_course_all_time_attends = {}
                for i in range(1,len(times)):
                    one_time = times[i].split(' ')[0]
                    if one_time == select_time:
                        if sid!='':
                            one_time_attends = db.session.query(Attendance).filter(Attendance.c_id==course.c_id,Attendance.time==times[i],Attendance.s_id==sid).order_by('s_id').all()
                        else:
                            one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id,Attendance.time == times[i]).order_by('s_id').all()
                        tt = Time_id(id=num,time=times[i])
                        num += 1
                        one_course_all_time_attends[tt] = one_time_attends
                dict[course] = one_course_all_time_attends
            courses = db.session.query(Course).filter(Course.t_id == tid)
            return render_template("teacher/show_records.html", dict=dict, courses=courses)
        elif cid !='' and select_time =='':
            courses = db.session.query(Course).filter(Course.t_id == tid, Course.c_id == cid)
            num = 0
            for course in courses:
                times = course.times.split('/')
                one_course_all_time_attends = {}
                for i in range(1, len(times)):
                    if sid == '':
                        one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id,Attendance.time == times[i]).order_by('s_id').all()
                    else:
                        one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id,Attendance.time == times[i],Attendance.s_id == sid).order_by('s_id').all()
                    tt = Time_id(id=num, time=times[i])
                    num += 1
                    one_course_all_time_attends[tt] = one_time_attends
                dict[course] = one_course_all_time_attends
            return render_template("teacher/show_records.html", dict=dict, courses=courses)
        elif cid == '' and select_time !='':
            courses = db.session.query(Course).filter(Course.t_id == tid)
            num = 0
            for course in courses:
                times = course.times.split('/')
                one_course_all_time_attends = {}
                for i in range(1, len(times)):
                    one_time = times[i].split(' ')[0]
                    if one_time == select_time:
                        if sid != '':
                            one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id, Attendance.time == times[i],Attendance.s_id == sid).order_by( 's_id').all()
                        else:
                            one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id,Attendance.time == times[i]).order_by('s_id').all()
                        tt = Time_id(id=num, time=times[i])
                        num += 1
                        one_course_all_time_attends[tt] = one_time_attends
                dict[course] = one_course_all_time_attends
            return render_template("teacher/show_records.html", dict=dict, courses=courses)
        else:#cid = '' select=''
            courses = db.session.query(Course).filter(Course.t_id == tid)
            num = 0
            for course in courses:
                times = course.times.split('/')
                one_course_all_time_attends = {}
                for i in range(1, len(times)):
                    if sid == '':
                        one_time_attends = db.session.query(Attendance).filter(Attendance.c_id == course.c_id,Attendance.time == times[i]).order_by('s_id').all()
                    else:
                        one_time_attends = db.session.query(Attendance).filter(Attendance.c_id==course.c_id,Attendance.time==times[i],Attendance.s_id==sid).all()
                    tt = Time_id(id=num, time=times[i])
                    num += 1
                    one_course_all_time_attends[tt] = one_time_attends
                dict[course] = one_course_all_time_attends
            return render_template("teacher/show_records.html", dict=dict, courses=courses)
    courses = db.session.query(Course).filter(Course.t_id==tid)
    num = 0
    for course in courses:
        times = course.times.split('/')
        one_course_all_time_attends = {}
        for i in range(1,len(times)):
            one_time_attends = db.session.query(Attendance).filter(Attendance.c_id==course.c_id,Attendance.time==times[i]).order_by('s_id').all()
            tt = Time_id(id=num,time=times[i])
            num += 1
            one_course_all_time_attends[tt] = one_time_attends
        dict[course] = one_course_all_time_attends
    return render_template("teacher/show_records.html",dict=dict,courses=courses)



@teacher.route('/update_attend',methods=['POST'])
def update_attend():
    course = request.form.get('course_id')
    time = request.form.get('time')
    sid = request.form.get('sid')
    result = request.form.get('result')
    one_attend = Attendance.query.filter(Attendance.c_id==course,Attendance.s_id==sid,Attendance.time==time).first()
    one_attend.result = result
    db.session.commit()
    return redirect(url_for('teacher.select_all_records'))

@teacher.route('/course_management',methods=['GET','POST'])
def course_management():
    dict = {}
    if request.method == 'POST':
        cid = request.form.get('course_id')
        cname = request.form.get('course_name')
        sid = request.form.get('sid')
        sc = SC.query.filter(SC.c_id==cid,SC.s_id==sid).first()
        db.session.delete(sc)
        db.session.commit()
    teacher_all_course = Course.query.filter(Course.t_id == session['id'])
    for course in teacher_all_course:
        course_student = db.session.query(Student).join(SC).filter(Student.s_id==SC.s_id,SC.c_id==course.c_id).all()
        dict[course] = course_student
    return render_template('teacher/course_management.html', dict=dict)

@teacher.route('/new_course',methods=['POST'])
def new_course():
    max = db.session.query(Course).order_by(Course.c_id.desc()).first()
    if max:
        cid = int(max.c_id) + 1
        cid = str(cid)
    else:
        cid =str(100001)
    course = Course(c_id=cid,c_name=request.form.get('cname'),t_id=session['id'])
    db.session.add(course)
    db.session.commit()
    return redirect(url_for('teacher.course_management'))

@teacher.route('/open_course',methods=['POST'])
def open_course():
    cid = request.form.get('course_id')
    course = Course.query.filter(Course.c_id==cid).first()
    course.flag='可选课'
    db.session.commit()
    return redirect(url_for('teacher.course_management'))

@teacher.route('/close_course',methods=['POST'])
def close_course():
    cid = request.form.get('course_id')
    course = Course.query.filter(Course.c_id==cid).first()
    course.flag='不可选课'
    db.session.commit()
    return redirect(url_for('teacher.course_management'))

@teacher.route('/update_password',methods=['GET','POST'])
def update_password():
    tid = session['id']
    teacher = Teacher.query.filter(Teacher.t_id==tid).first()
    if request.method == 'POST':
        old = request.form.get('old')
        if old == teacher.t_password:
            new = request.form.get('new')
            teacher.t_password = new
            db.session.commit()
            flash('修改成功！')
        else:
            flash('旧密码错误，请重试')
    return render_template('teacher/update_password.html', teacher=teacher)

@teacher.route('/select_sc',methods=['GET','POST'])
def select_sc():
    dict = {}
    teacher_all_course = Course.query.filter(Course.t_id == session['id'])
    if request.method == 'POST':
        cid = request.form.get('course_id')
        sid = request.form.get('sid')
        if cid != '' and sid != '':
            course = Course.query.filter(Course.c_id==cid).first()
            dict[course] = db.session.query(Student).join(SC).filter(Student.s_id == SC.s_id,
                                                                   SC.c_id == course.c_id,SC.s_id==sid).all()
        elif cid != '' and sid == '':
            course = Course.query.filter(Course.c_id == cid).first()
            dict[course] = db.session.query(Student).join(SC).filter(Student.s_id == SC.s_id,
                                                                     SC.c_id == cid).all()
        elif cid == '' and sid != '':
            for course in teacher_all_course:
                course_student = db.session.query(Student).join(SC).filter(Student.s_id == SC.s_id,
                                                                           SC.c_id == course.c_id,SC.s_id==sid).all()
                dict[course] = course_student
        else:
            for course in teacher_all_course:
                course_student = db.session.query(Student).join(SC).filter(Student.s_id == SC.s_id,
                                                                           SC.c_id == course.c_id).all()
                dict[course] = course_student
        return render_template('teacher/student_getFace.html', dict=dict, courses=teacher_all_course)
    for course in teacher_all_course:
        course_student = db.session.query(Student).join(SC).filter(Student.s_id == SC.s_id,
                                                                   SC.c_id == course.c_id).all()
        dict[course] = course_student
    return render_template('teacher/student_getFace.html',dict=dict,courses=teacher_all_course)

@teacher.route('/open_getFace',methods=['POST'])
def open_getFace():
    sid = request.form.get('sid')
    student = Student.query.filter(Student.s_id==sid).first()
    student.flag = 1
    db.session.commit()
    return redirect(url_for('teacher.select_sc'))


@teacher.route('/close_getFace', methods=['POST'])
def close_getFace():
    sid = request.form.get('sid')
    student = Student.query.filter(Student.s_id == sid).first()
    student.flag = 0
    db.session.commit()
    return redirect(url_for('teacher.select_sc'))

@teacher.route('/delete_face',methods=['POST'])
def delete_face():
    sid = request.form.get('sid')
    student = Student.query.filter(Student.s_id == sid).first()
    student.flag = 1
    db.session.commit()
    os.remove('app/static/data/data_faces_from_camera/' + sid + '/1.jpg')
    os.remove('app/static/data/data_faces_from_camera/' + sid + '/2.jpg')
    os.remove('app/static/data/data_faces_from_camera/' + sid + '/3.jpg')
    os.remove('app/static/data/data_faces_from_camera/' + sid + '/4.jpg')
    os.remove('app/static/data/data_faces_from_camera/' + sid + '/5.jpg')
    return redirect(url_for('teacher.select_sc'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = set(['xlsx','xls'])
    return '.' in filename and \
        filename.rsplit('.',1)[1] in ALLOWED_EXTENSIONS
# 检测学号存在
def sid_if_exist(sid):
    num = Student.query.filter(Student.s_id.in_(sid)).count()
    return num
# 检测课程号存在
def cid_if_exist(cid):
    num = Course.query.filter(Course.c_id.in_(cid)).count()
    return num
# 检测工号存在
def tid_if_exist(tid):
    num = Teacher.query.filter(Teacher.t_id.in_(tid)).count()
    return num
@teacher.route('upload_sc',methods=['POST'])
def upload_sc():
    sc_file = request.files.get('sc_file')
    msg = 'error'
    if sc_file:
        if allowed_file(sc_file.filename):
            sc_file.save(sc_file.filename)
            df = pd.DataFrame(pd.read_excel(sc_file.filename))
            df1 = df[['学号', '课程号']]
            sid = df1[['学号']].values.T.tolist()[:][0]
            cid = df1[[ '课程号']].values.T.tolist()[:][0]
            if df.isnull().values.any():
                flash('存在空信息')
            else:
                sid_diff = len(set(sid)) - sid_if_exist(sid)
                cid_diff = len(set(cid)) - cid_if_exist(cid)
                if sid_diff==0 and cid_diff==0:
                    flash('success')
                    for i in range(len(sid)):
                        sc = SC(s_id=sid[i],c_id=cid[i])
                        db.session.merge(sc)
                        i += 1
                    db.session.commit()

                elif sid_diff==0 and cid_diff!=0:
                    flash('有课程号不存在')
                elif sid_diff!=0 and cid_diff==0:
                    flash('有学号不存在')
                else:
                    flash('有学号、课程号不存在')
            os.remove(sc_file.filename)
        else:
            flash("只能识别'xlsx,xls'文件")
    else:
        flash('请选择文件')
    return redirect(url_for('teacher.course_management'))

@teacher.route('/select_all_teacher',methods=['POST','GET'])
def select_all_teacher():
    if request.method == 'POST':
        try:
            id = request.form.get('id')
            flag = request.form.get('flag')
            teacher = Teacher.query.get(id)
            if flag:
                sc = db.session.query(SC).join(Course).filter(SC.c_id==Course.c_id,Course.t_id==id).all()
                [db.session.delete(u) for u in sc]
                Course.query.filter(Course.t_id == id).delete()
            db.session.delete(teacher)
            db.session.commit()
        except Exception as e:
            print('Error:', e)
            flash("出发错误操作")
            return redirect(url_for('teacher.home'))
    teachers = Teacher.query.all()
    dict = {}
    for t in teachers:
        tc = Course.query.filter(Course.t_id==t.t_id).all()
        if tc:
            dict[t]=1
        else:
            dict[t]=0
    return render_template('teacher/all_teacher.html',dict=dict)

@teacher.route('/select_all_student',methods=['POST','GET'])
def select_all_student():
    if request.method=='POST':
        try:
            id = request.form.get('id')
            flag = request.form.get('flag')
            student = Student.query.get(id)
            if flag:
                SC.query.filter(SC.s_id == id).delete()
            db.session.delete(student)
            db.session.commit()
        except Exception as e:
            print('Error:', e)
            flash("出发错误操作")
            return redirect(url_for('teacher.home'))
    students = Student.query.all()
    dict = {}
    for s in students:
        tc = SC.query.filter(SC.s_id == s.s_id).all()
        if tc:
            dict[s] = 1
        else:
            dict[s] = 0
    return render_template('teacher/all_student.html',dict=dict)


@teacher.route('/upload_teacher',methods=['POST'])
def upload_teacher():
    file = request.files.get('teacher_file')
    msg = 'error'
    if file:
        if allowed_file(file.filename):
            file.save(file.filename)
            df = pd.DataFrame(pd.read_excel(file.filename))
            df1 = df[['工号', '姓名','密码']]
            id = df1[['工号']].values.T.tolist()[:][0]
            name = df1[['姓名']].values.T.tolist()[:][0]
            pwd = df1[['密码']].values.T.tolist()[:][0]
            if df.isnull().values.any() or len(id)==0:
                flash('存在空信息')
            else:
                tid_diff =  tid_if_exist(id)
                if tid_diff != 0:
                    flash('工号存在重复')
                else:
                    flash('success')
                    for i in range(len(id)):
                        t = Teacher(t_id=id[i], t_name=name[i],t_password=pwd[i])
                        db.session.add(t)
                        i += 1
                    db.session.commit()
            os.remove(file.filename)

        else:
            flash("只能识别'xlsx,xls'文件")
    else:
        flash('请选择文件')
    return redirect(url_for('teacher.select_all_teacher'))

@teacher.route('/upload_student',methods=['POST'])
def upload_student():
    file = request.files.get('student_file')
    msg = 'error'
    if file:
        if allowed_file(file.filename):
            file.save(file.filename)
            df = pd.DataFrame(pd.read_excel(file.filename))
            df1 = df[['学号', '姓名', '密码']]
            id = df1[['学号']].values.T.tolist()[:][0]
            name = df1[['姓名']].values.T.tolist()[:][0]
            pwd = df1[['密码']].values.T.tolist()[:][0]
            if df.isnull().values.any() or len(id)==0:
                flash('存在空信息')
            else:
                sid_diff = sid_if_exist(id)
                if sid_diff != 0:
                    flash('学号存在重复')
                else:
                    flash('success')
                    for i in range(len(id)):
                        s = Student(s_id=id[i], s_name=name[i], s_password=pwd[i])
                        db.session.add(s)
                        i += 1
                    db.session.commit()
            os.remove(file.filename)

        else:
            flash("只能识别'xlsx,xls'文件")
    else:
        flash('请选择文件')

    return redirect(url_for('teacher.select_all_student'))
@teacher.route('/download',methods=['POST'])
def download():
    # url = str(request.url)
    # paras = url.split('?')[1]
    # print(paras)
    # nums = paras.split('&')
    # print(nums)
    # cid = nums[0].split('=')[1]
    # cname = nums[1].split('=')[1]
    # time = nums[2].split('=')[1]
    cid = request.form.get('cid')
    cname = request.form.get('cname')
    time = request.form.get('time')
    # 建立数据库引擎
    engine = create_engine('mysql+pymysql://root:990722@localhost:3306/test?charset=utf8')
    # 写一条sql
    sql = "select s_id 学号,result 考勤结果 from attendance where c_id='"+ str(cid) + "' and time='" + str(time) + "'"
    print(sql)
    # 建立dataframe
    df = pd.read_sql_query(sql, engine)
    out = BytesIO()
    writer = pd.ExcelWriter('out.xlsx', engine='xlsxwriter')
    df.to_excel(excel_writer=writer, sheet_name='Sheet1', index=False)
    writer.save()
    out.seek(0)
    # 文件名中文支持
    name = cname+time+'考勤.xlsx'
    file_name = quote(name)
    response = send_file(out, as_attachment=True, attachment_filename=file_name)
    response.headers['Content-Disposition'] += "; filename*=utf-8''{}".format(file_name)
    return send_file('../out.xlsx',as_attachment=True, attachment_filename=file_name)
