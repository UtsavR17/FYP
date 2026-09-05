from flask import Blueprint

bp = Blueprint('compatibility', __name__)
from app.modules.compatibility import routes 
