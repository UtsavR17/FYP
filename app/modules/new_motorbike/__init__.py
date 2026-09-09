from flask import Blueprint

bp = Blueprint('new_motorbike', __name__)

from app.modules.new_motorbike import routes