from app import db #db是在app/__init__.py生成的关联后的SQLAlchemy实例

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(320), unique=True)
    password = db.Column(db.String(32), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username


class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(320), unique=True)
    password = db.Column(db.String(32), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username

class Student(db.Model):
    __tablename__ = 'students'
    s_id= db.Column(db.String(13), primary_key=True)
    s_name = db.Column(db.String(80), nullable=False)
    s_password = db.Column(db.String(32), nullable=False)
    flag = db.Column(db.Integer, default=1)
    before = db.Column(db.DateTime)

    def __repr__(self):
        return '<Student %r,%r>' % (self.s_id,self.s_name)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    t_id= db.Column(db.String(8), primary_key=True)
    t_name = db.Column(db.String(80), nullable=False)
    t_password = db.Column(db.String(32), nullable=False)
    before = db.Column(db.DateTime)

    def __repr__(self):
        return '<Teacher %r,%r>' % (self.t_id,self.t_name)

class Faces(db.Model):
    __tablename__ = 'student_faces'
    s_id = db.Column(db.String(13), primary_key=True)
    feature = db.Column(db.Text,nullable=False)

    def __repr__(self):
        return '<Faces %r>' % self.s_id


class Course(db.Model):
    __tablename__ = 'courses'
    c_id = db.Column(db.String(6), primary_key=True)
    t_id = db.Column(db.String(8),db.ForeignKey('teachers.t_id'),nullable=False)
    c_name = db.Column(db.String(100),nullable=False)
    times = db.Column(db.Text,default="0000-00-00 00:00")
    flag = db.Column(db.String(50), default="不可选课")

    def __repr__(self):
        return '<Course %r,%r,%r>' % (self.c_id,self.t_id,self.c_name)

class SC(db.Model):
    __tablename__ = 'student_course'
    s_id = db.Column(db.String(13),db.ForeignKey('students.s_id'),primary_key=True)
    c_id = db.Column(db.String(100),db.ForeignKey('courses.c_id') ,primary_key=True)

    def __repr__(self):
        return '<SC %r,%r> '%( self.s_id,self.c_id)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer,primary_key=True)
    s_id = db.Column(db.String(13), db.ForeignKey('students.s_id'))
    c_id = db.Column(db.String(100), db.ForeignKey('courses.c_id'))
    time = db.Column(db.DateTime)
    result = db.Column(db.String(10),nullable=False)

    def __repr__(self):
        return '<Attendance %r,%r,%r,%r>' % (self.s_id,self.c_id,self.time,self.result)

class Time_id():
    id = ''
    time = ''

    def __init__(self,id,time):
        self.id = id
        self.time = time

class choose_course():
    __tablename___ = 'choose_course'
    c_id = db.Column(db.String(6), primary_key=True)
    t_id = db.Column(db.String(8), nullable=False)
    c_name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return '<Course %r,%r,%r>' % (self.c_id,self.t_id,self.c_name)