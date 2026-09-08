from flask import Blueprint

bp = Blueprint('customer', __name__)

from app.modules.customer import routes

