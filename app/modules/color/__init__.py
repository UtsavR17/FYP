from flask import Blueprint

bp = Blueprint('color', __name__)

from app.modules.color import routes  # noqa: E402, F401