from flask import render_template, url_for
from app.dashboard import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase


def _get_dashboard_counts():
    """
    Query the total record count for each Phase 1 table.
    Each query is wrapped individually so a single failure
    does not crash the entire dashboard.
    Returns a dict mapping a short key to an integer count.
    """
    queries = [
        ('color',       'Color'),
        ('category',    'Category'),
        ('brand',       'Brand'),
        ('model',       'Model'),
        ('spare_parts', 'Spare_Parts'),
        ('stock',       'Stock'),
        ('service',     'Service'),
        ('role',        'Role'),
        ('employee',    'Employee'),
        ('supplier',    'Supplier'),
    ]

    counts = {}
    for key, table_name in queries:
        try:
            result = supabase.table(table_name).select(
                '*', count='exact'
            ).execute()
            counts[key] = result.count if result.count is not None else 0
        except Exception:
            counts[key] = 0

    return counts


@bp.route('/')
@login_required
def index():
    counts = _get_dashboard_counts()

    cards = [
        {
            'label': 'Colors',
            'count': counts['color'],
            'icon':  'fa-palette',
            'url':   url_for('color.index'),
            'desc':  'Manage available motorbike colors',
        },
        {
            'label': 'Categories',
            'count': counts['category'],
            'icon':  'fa-tags',
            'url':   url_for('category.index'),
            'desc':  'Manage spare part categories',
        },
        {
            'label': 'Brands',
            'count': counts['brand'],
            'icon':  'fa-copyright',
            'url':   url_for('brand.index'),
            'desc':  'Manage bike and part brands',
        },
        {
            'label': 'Models',
            'count': counts['model'],
            'icon':  'fa-motorcycle',
            'url':   url_for('model.index'),
            'desc':  'Manage motorbike models',
        },
        {
            'label': 'Spare Parts',
            'count': counts['spare_parts'],
            'icon':  'fa-gears',
            'url':   url_for('spare_parts.index'),
            'desc':  'Manage spare parts catalogue',
        },
        {
            'label': 'Stock',
            'count': counts['stock'],
            'icon':  'fa-boxes-stacked',
            'url':   url_for('stock.index'),
            'desc':  'Manage stock inventory levels',
        },
        {
            'label': 'Services',
            'count': counts['service'],
            'icon':  'fa-wrench',
            'url':   url_for('service.index'),
            'desc':  'Manage workshop services',
        },
        {
            'label': 'Roles',
            'count': counts['role'],
            'icon':  'fa-id-badge',
            'url':   url_for('role.index'),
            'desc':  'Manage employee roles and rates',
        },
        {
            'label': 'Employees',
            'count': counts['employee'],
            'icon':  'fa-users',
            'url':   url_for('employee.index'),
            'desc':  'Manage staff records',
        },
        {
            'label': 'Suppliers',
            'count': counts['supplier'],
            'icon':  'fa-truck',
            'url':   url_for('supplier.index'),
            'desc':  'Manage supplier information',
        },
    ]

    return render_template('dashboard/index.html', cards=cards)