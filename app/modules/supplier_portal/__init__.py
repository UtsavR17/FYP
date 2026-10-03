from flask import Blueprint

bp = Blueprint('supplier_portal', __name__)

from app.modules.supplier_portal import routes  # noqa: E402, F401
