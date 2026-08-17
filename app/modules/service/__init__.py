from flask import Blueprint

bp = Blueprint('service', __name__)

from app.modules.service import routes  # noqa: E402, F401