from flask import Blueprint

bp = Blueprint('brand', __name__)

from app.modules.brand import routes  # noqa: E402, F401