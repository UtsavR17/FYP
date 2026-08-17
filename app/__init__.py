from flask import Flask, jsonify, redirect, url_for
from config import Config
from app.supabase_client import supabase


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ------------------------------------------------------------------
    # BLUEPRINT REGISTRATION
    # ------------------------------------------------------------------

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    from app.modules.color import bp as color_bp
    app.register_blueprint(color_bp, url_prefix='/colors')

    from app.modules.category import bp as category_bp
    app.register_blueprint(category_bp, url_prefix='/categories')

    from app.modules.brand import bp as brand_bp
    app.register_blueprint(brand_bp, url_prefix='/brands')

    from app.modules.model import bp as model_bp
    app.register_blueprint(model_bp, url_prefix='/models')

    from app.modules.spare_parts import bp as spare_parts_bp
    app.register_blueprint(spare_parts_bp, url_prefix='/spare-parts')

    from app.modules.stock import bp as stock_bp
    app.register_blueprint(stock_bp, url_prefix='/stock')

    from app.modules.service import bp as service_bp
    app.register_blueprint(service_bp, url_prefix='/services')

    from app.modules.role import bp as role_bp
    app.register_blueprint(role_bp, url_prefix='/roles')

    from app.modules.employee import bp as employee_bp
    app.register_blueprint(employee_bp, url_prefix='/employees')

    from app.modules.supplier import bp as supplier_bp
    app.register_blueprint(supplier_bp, url_prefix='/suppliers')

    # ------------------------------------------------------------------
    # ROOT REDIRECT
    # Sends the browser to /dashboard when the root URL is visited.
    # ------------------------------------------------------------------
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    # ------------------------------------------------------------------
    # TEMPORARY TEST ROUTE — Remove this before Task 17 (Auth + RLS)
    # Purpose: Verify Flask is running and Supabase connection is working
    # ------------------------------------------------------------------
    # @app.route('/health')
    # def health_check():
    #     try:
    #         result = supabase.table('Color').select('*', count='exact').execute()
    #         return jsonify({
    #             'status': 'ok',
    #             'message': 'Flask is running and Supabase connection is working.',
    #             'color_table_row_count': result.count
    #         })
    #     except Exception as e:
    #         return jsonify({
    #             'status': 'error',
    #             'message': str(e)
    #         }), 500
    # ------------------------------------------------------------------

    return app