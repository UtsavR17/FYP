from flask import Blueprint

bp = Blueprint('category', __name__)

from app.modules.category import routes  # noqa: E402, F401