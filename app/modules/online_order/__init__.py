from flask import Blueprint

bp = Blueprint('online_order', __name__)

from app.modules.online_order import routes  # noqa: E402,F401
