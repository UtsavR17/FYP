from flask import Blueprint

bp = Blueprint('stock', __name__)

from app.modules.stock   import routes  # noqa: E402, F401