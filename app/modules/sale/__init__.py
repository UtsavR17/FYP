from flask import Blueprint

bp = Blueprint('sale', __name__)

from app.modules.sale import routes  