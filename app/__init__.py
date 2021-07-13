from flask import Flask, url_for, request, redirect, render_template,session,flash,abort
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
from time import strftime
from datetime import datetime

app = Flask(__name__)
app.config.from_object('config')
app.secret_key = '123456'
app.jinja_env.auto_reload = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(seconds=1)
db = SQLAlchemy(app)
from app import models,views
from .models import Student,Teacher

@app.route('/',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(time)
        if len(username)==13:
            students = Student.query.filter(Student.s_id == username).first()
            if students:
                if students.s_password == password:
                    flash("登陆成功")
                    session['username'] = username
                    session['id'] = students.s_id
                    session['num'] = 0 #students.num
                    session['name'] = students.s_name
                    session['role'] = "student"
                    session['flag'] = students.flag
                    if students.before:
                        session['time'] = students.before
                    else:
                        session['time'] = time
                    students.before = time
                    db.session.commit()
                    return redirect(url_for('student.home'))
                else:
                    flash("密码错误，请重试")
            else:
                flash("学号错误，请重试")
        elif len(username) ==8:
            teachers = Teacher.query.filter(Teacher.t_id == username).first()
            if teachers:
                if teachers.t_password == password:
                    flash("登陆成功")
                    session['username'] = username
                    session['id'] = teachers.t_id
                    session['name'] = teachers.t_name
                    session['role'] = "teacher"
                    session['attend'] = []
                    if teachers.before:
                        session['time'] = teachers.before
                    else:
                        session['time'] = time
                    teachers.before = time
                    db.session.commit()
                    return redirect(url_for('teacher.home'))
                else:
                    flash("密码错误，请重试")
            else:
                flash("工号错误，请重试")
        else:
            flash("账号不合法，请用学号/工号登录")
    return render_template('login.html')

@app.route('/logout')
def logout():
    # students = Student.query.filter(Student.s_id == session['id']).first()
    # students.num = session['num']
    # db.session.commit()
    session.clear()
    return render_template('login.html')


#拦截器
@app.before_request
def before():
    list = ['png','css','js','ico','xlsx','xls','jpg']
    url_after = request.url.split('.')[-1]
    if url_after in list:
        return None
    url = str(request.endpoint)
    if url == 'logout':
        return None
    if url == "login":
        if 'username' in session:
            return redirect("logout")
        else:
            return None
    else:
        if 'username' in session:
            role = url.split('.')[0]
            if role == session['role']:
                return None
            else:
                new_endpoint = session['role'] + '.' + 'home'
                print(role)
                flash('权限不足')
                return redirect(url_for(new_endpoint))
        else:
            flash("未登录")
            return redirect('/')