from flask import Blueprint

bp = Blueprint('payment', __name__)

from app.modules.payment import routes  