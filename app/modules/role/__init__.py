from flask import Blueprint

bp = Blueprint('role', __name__)

from app.modules.role import routes  # noqa: E402, F401