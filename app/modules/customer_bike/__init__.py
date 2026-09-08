from flask import Blueprint
bp = Blueprint('customer_bike', __name__)

from app.modules.customer_bike import routes