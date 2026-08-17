from flask import Blueprint

bp = Blueprint('model', __name__)

from app.modules.model import routes  # noqa: E402, F401