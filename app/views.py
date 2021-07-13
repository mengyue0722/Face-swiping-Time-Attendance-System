from app import app

from .student import student
from .teacher import teacher


app.register_blueprint(student,url_prefix='/student')
app.register_blueprint(teacher,url_prefix='/teacher')