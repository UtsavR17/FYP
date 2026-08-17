from flask import Blueprint

bp = Blueprint('employee', __name__)

from app.modules.employee import routes  # noqa: E402, F401