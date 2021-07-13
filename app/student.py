from flask import Blueprint, render_template, request, session,flash,jsonify,redirect,url_for
from app import get_faces_from_camera as gf
import base64
import os
from .models import Faces,Student,SC,Course,Attendance,Teacher
from app import features_extraction_to_csv as fc
from app import db
from datetime import datetime
from sqlalchemy import extract

student = Blueprint('student',__name__,static_folder='static')

@student.route('/home')
def home():
    records = {}
    student = Student.query.filter(Student.s_id==session['id']).first()
    session['flag'] = student.flag
    attendances = db.session.query(Attendance).filter(Attendance.s_id==session['id']).order_by(Attendance.time.desc()).limit(5).all()
    for i in attendances:
        course = db.session.query(Course).filter(Course.c_id==i.c_id).all()
        records[i]=course
    year = datetime.now().year
    month = datetime.now().month
    qj = db.session.query(Attendance).filter(Attendance.s_id == session['id'], extract('month', Attendance.time)==month,
                                             extract('year', Attendance.time) == year, Attendance.result == '请假').count()
    cd = db.session.query(Attendance).filter(Attendance.s_id == session['id'], extract('month', Attendance.time)==month,
                                             extract('year', Attendance.time) == year, Attendance.result == '迟到').count()
    qq = db.session.query(Attendance).filter(Attendance.s_id == session['id'], extract('month', Attendance.time)==month,
                                             extract('year', Attendance.time) == year, Attendance.result == '缺勤').count()
    yqd = db.session.query(Attendance).filter(Attendance.s_id == session['id'], extract('month', Attendance.time)==month,
                                             extract('year', Attendance.time) == year, Attendance.result == '已签到').count()
    num = {'qj':qj,'cd':cd,'qq':qq,'yqd':yqd}
    return render_template('student/student_home.html',flag=session['flag'],before=session['time'],records=records,name=session['name'],num=num)

def pre_work_mkdir(path_photos_from_camera):
    # 新建文件夹 / Create folders to save faces images and csv
    if os.path.isdir(path_photos_from_camera):
        pass
    else:
        print(path_photos_from_camera)
        os.mkdir(path_photos_from_camera)

@student.route("/get_faces", methods=["GET", "POST"])
def get_faces():
    '''
        功能:接收前端上传来的人脸图片,完成数据库的保存
        1、取上传来的数据的参数 request.form.get("myimg")
        2、上传的数据是base64格式,调用后端的base64进行解码
        3、存到后台变成图片
        4、调用face_reconginition的load_image-file读取文件
        5、调用 face-recognition的face_encodings对脸部进行编码
        6、利用bson和pickle模块组合把脸部编码数据变成128位bitdata数据
        7、利用mongo.db.myface.insert_one插入数据,存储到mongodb里面
        上面是逻辑,但逻辑发生在post方式上,不发生在get,
        限定一下上面逻辑的发生条件,不是POST方式,就是GET,GET请求页面
        :return:
    '''
    if request.method == "POST":
        imgdata = request.form.get("face")
        imgdata = base64.b64decode(imgdata)
        path = "app/static/data/data_faces_from_camera/" + session['id']
        up = gf.Face_Register()
        if session['num'] == 0:
            pre_work_mkdir(path)
        if session['num'] == 5:
            session['num'] = 0
        session['num'] += 1
        current_face_path =path + "/" + str(session['num']) + '.jpg'
        with open(current_face_path, "wb") as f:
            f.write(imgdata)
        flag = up.single_pocess(current_face_path)
        if flag != 'right':
            session['num'] -= 1
        msg = [{"result":flag,"code":session['num']}]
        return {"result":flag,"code":session['num']}
        # faceimg = face_recognition.load_image_file("a.png")
        # facedata = face_recognition.face_encodings(faceimg)[0]
        # print(facedata)
        # binary_data = Binary(pickle.dumps(facedata, protocol=-1), subtype=128)
        # mongo.db.myface.insert_one({'face': binary_data})

        # return {"result": "OK"}
    return render_template("student/get_faces.html")

#计算特征值存数据库
@student.route('/upload_faces',methods=['POST'])
def upload_faces():
    try:
        path_images_from_camera = "app/static/data/data_faces_from_camera/"
        path = path_images_from_camera + session['id']
        print(path)
        features_mean_personX = fc.return_features_mean_personX(path)
        features = str(features_mean_personX[0])
        for i in range(1,128):
            features = features + ',' + str(features_mean_personX[i])
        student = Faces.query.filter(Faces.s_id == session['id']).first()
        if student:
            student.feature = features
        else:
            face = Faces(s_id=session['id'],feature=features)
            db.session.add(face)
        db.session.commit()
    #writer.writerow(features_mean_personX)
        print(" >> 特征均值 / The mean of features:", list(features_mean_personX), '\n')
    # up = gf.Face_Register()
    # current_face_path = "app/static/data/data_faces_from_camera/" + session['id'] + "/"
    # up.process(current_face_path)
    # msg = 'success'
    # return render_template('student/student_home.html', msg = msg)
        msg = 'success'
        student = Student.query.filter(Student.s_id==session['id']).first()
        student.flag=0
        db.session.commit()
        flash("提交成功！")
        return redirect(url_for('student.home'))
    except Exception as e:
        print('Error:', e)
        flash("提交不合格照片，请拍摄合格后再重试")
        return redirect(url_for('student.home'))


@student.route('/my_faces')
def my_faces():
    current_face_path = "app/static/data/data_faces_from_camera/" + session['id'] + "/"
    face_path = "static/data/data_faces_from_camera/" + session['id'] + "/"
    photos_list = os.listdir(current_face_path)
    num = len(photos_list)
    paths = []
    for i in range(num):
        path =  face_path + str(i+1) + '.jpg'
        paths.append(path)
    return render_template('student/my_faces.html',face_paths=paths)

@student.route('/my_records',methods=['GET','POST'])
def my_records():
    sid = session['id']
    dict = {}
    if request.method == 'POST':
        cid = str(request.form.get('course_id'))
        time = str(request.form.get('time'))
        if cid != '' and time != '':
            course = Course.query.filter(Course.c_id==cid).first()
            one_course_records = db.session.query(Attendance).filter(Attendance.s_id==sid,Attendance.c_id==cid,Attendance.time.like(time+'%')).all()
            dict[course] = one_course_records
            courses = db.session.query(Course).join(SC).filter(SC.s_id == sid).order_by("c_id").all()
            return render_template('student/my_records.html', dict=dict, courses=courses)
        elif cid !='' and time == '':
            course = Course.query.filter(Course.c_id == cid).first()
            one_course_records = db.session.query(Attendance).filter(Attendance.s_id == sid, Attendance.c_id == cid).all()
            dict[course] = one_course_records
            courses = db.session.query(Course).join(SC).filter(SC.s_id == sid).order_by("c_id").all()
            return render_template('student/my_records.html', dict=dict, courses=courses)
        elif cid == '' and time !='':
            courses = db.session.query(Course).join(SC).filter(SC.s_id == sid).order_by("c_id").all()
            for course in courses:
                one_course_records = db.session.query(Attendance).filter(Attendance.s_id == sid,Attendance.c_id == course.c_id,Attendance.time.like(time+'%')).order_by("c_id").all()
                dict[course] = one_course_records
            courses = db.session.query(Course).join(SC).filter(SC.s_id == sid).order_by("c_id").all()
            return render_template('student/my_records.html', dict=dict, courses=courses)
        else: #cid =='' and time ==''
            pass
    # all_course_record = []
    courses = db.session.query(Course).join(SC).filter(SC.s_id==sid).order_by("c_id").all()
    # print(courses)
    for course in courses:
        one_course_records = db.session.query(Attendance).filter(Attendance.s_id==sid,Attendance.c_id==course.c_id).order_by("c_id").all()
        # all_course_record.append(one_course_records)
        dict[course] = one_course_records
    # print(dict)
    return render_template('student/my_records.html',dict = dict,courses=courses)

@student.route('/choose_course',methods=['GET','POST'])
def choose_course():
    try:
        sid = session['id']
        dict = {}
        if request.method == 'POST':
            cid = request.form.get('cid')
            sc = SC(s_id=sid, c_id=cid)
            db.session.add(sc)
            db.session.commit()

        now_have_courses_sc = SC.query.filter(SC.s_id==sid).all()
        cids = []
        for sc in now_have_courses_sc:
            cids.append(sc.c_id)
        not_hava_courses = Course.query.filter(Course.c_id.notin_(cids),Course.flag=='可选课').all()
        for ncourse in not_hava_courses:
            teacher = Teacher.query.filter(Teacher.t_id==ncourse.t_id).first()
            dict[ncourse] = teacher
        return render_template('student/choose_course.html',dict=dict)
    except Exception as e:
        print('Error:', e)
        flash("出发错误操作")
        return redirect(url_for('student.home'))


@student.route('/unchoose_course',methods=['GET','POST'])
def unchoose_course():
    try:
        sid = session['id']
        dict = {}
        if request.method == 'POST':
            cid = request.form.get('cid')
            sc = SC.query.filter(SC.c_id==cid,SC.s_id==sid).first()
            db.session.delete(sc)
            db.session.commit()
        now_have_courses_sc = SC.query.filter(SC.s_id == sid).all()
        cids = []
        for sc in now_have_courses_sc:
            cids.append(sc.c_id)
        hava_courses = Course.query.filter(Course.c_id.in_(cids),Course.flag=='可选课').all()
        for course in hava_courses:
            teacher = Teacher.query.filter(Teacher.t_id == course.t_id).first()
            dict[course] = teacher
        return render_template('student/unchoose_course.html', dict=dict)
    except Exception as e:
        print('Error:', e)
        flash("出发错误操作")
        return redirect(url_for('student.home'))

@student.route('/update_password',methods=['GET','POST'])
def update_password():
    sid = session['id']
    student = Student.query.filter(Student.s_id==sid).first()
    if request.method == 'POST':
        old = request.form.get('old')
        if old == student.s_password:
            new = request.form.get('new')
            student.s_password = new
            db.session.commit()
            flash('修改成功！')
        else:
            flash('旧密码错误，请重试')
    return render_template('student/update_password.html', student=student)