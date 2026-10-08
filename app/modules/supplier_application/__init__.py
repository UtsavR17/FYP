from flask import Blueprint

bp = Blueprint('supplier_application', __name__)

from app.modules.supplier_application import routes  # noqa: E402,F401
