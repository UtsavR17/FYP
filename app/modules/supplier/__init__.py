from flask import Blueprint

bp = Blueprint('supplier', __name__)

from app.modules.supplier import routes  # noqa: E402, F401