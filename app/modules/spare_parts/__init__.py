from flask import Blueprint

bp = Blueprint('spare_parts', __name__)

from app.modules.spare_parts import routes  # noqa: E402, F401