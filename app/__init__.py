from flask import Flask, jsonify, redirect, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from config import Config
from app.supabase_client import supabase
from app.utils.flash_messages import flash_error
from app.utils.product_images import REQUEST_TOO_LARGE_MSG


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Online order references (Task 40): {{ order_id | order_ref }} -> ORD-000012
    from app.utils.order_ref import format_order_ref
    app.add_template_filter(format_order_ref, 'order_ref')

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

    from app.modules.compatibility import bp as compatibility_bp
    app.register_blueprint(compatibility_bp, url_prefix='/compatibility')
    


    from app.modules.purchase_order import bp as purchase_order_bp
    app.register_blueprint(purchase_order_bp, url_prefix='/purchase-order')


    from app.modules.customer import bp as customer_bp
    app.register_blueprint(customer_bp, url_prefix='/customers')



    from app.modules.customer_bike import bp as customer_bike_bp
    app.register_blueprint(customer_bike_bp, url_prefix='/customer-bikes')

    

    from app.modules.new_motorbike import bp as new_motorbike_bp
    app.register_blueprint(new_motorbike_bp, url_prefix='/new-motorbikes')

    from app.modules.appointment import bp as appointment_bp
    app.register_blueprint(appointment_bp, url_prefix='/appointments')

    
    from app.modules.sale import bp as sale_bp
    app.register_blueprint(sale_bp, url_prefix='/sales')


    from app.modules.payment import bp as payment_bp
    app.register_blueprint(payment_bp, url_prefix='/payments')

    # Online Orders (Task 40): orders placed and paid on the Client Side
    from app.modules.online_order import bp as online_order_bp
    app.register_blueprint(online_order_bp, url_prefix='/online-orders')

    # Supplier Applications (Task 46): review requests submitted on the Client Side
    from app.modules.supplier_application import bp as supplier_application_bp
    app.register_blueprint(supplier_application_bp, url_prefix='/supplier-applications')

    # Supplier Portal (Task 35): separate login and session keys from the Admin Panel
    from app.modules.supplier_portal import bp as supplier_portal_bp
    app.register_blueprint(supplier_portal_bp, url_prefix='/supplier-portal')


    # ------------------------------------------------------------------
    # ROOT REDIRECT
    # Sends the browser to /dashboard when the root URL is visited.
    # ------------------------------------------------------------------
    @app.route('/')
    def index():
        return redirect(url_for('dashboard.index'))

    # ------------------------------------------------------------------
    # REQUEST TOO LARGE (Task 49)
    # On the Spare Parts and Model forms a body over MAX_CONTENT_LENGTH
    # (an oversized image) goes back to the same form with a flash
    # instead of an error page. Other pages keep the default 413.
    # ------------------------------------------------------------------
    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(error):
        if request.blueprint in ('spare_parts', 'model') and request.endpoint:
            flash_error(REQUEST_TOO_LARGE_MSG)
            return redirect(url_for(request.endpoint, **(request.view_args or {})))
        return error

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