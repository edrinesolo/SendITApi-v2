from app.views.parcels import ap
from app.auth.views import auth
from flask import Flask
from flask_mail import Mail
from flasgger import Flasgger
app = Flask(__name__)
flasgger=Flasgger(app)

app.register_blueprint(ap)
app.register_blueprint(auth)
