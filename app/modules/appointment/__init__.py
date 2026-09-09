from flask import Blueprint

bp = Blueprint('appointment', __name__)

from app.modules.appointment import routes