from flask import render_template, request, redirect, url_for
from app.modules.stock import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import (
    required_fields, is_positive_number, is_positive_integer
)


def _get_form_options():
    """
    Fetch dropdown options for the Stock Create and Edit forms.

    Returns:
        spare_part_options: list of (SP_id, SP_name) tuples
        brand_options:      list of (Brand_ID, Brand_Name) tuples
    """
    spare_part_options = []
    brand_options = []

    try:
        sp_result = (
            supabase.table('Spare_Parts')
            .select('SP_id, SP_name')
            .order('SP_name')
            .execute()
        )
        spare_part_options = [
            (r['SP_id'], r['SP_name'])
            for r in (sp_result.data or [])
        ]
    except Exception:
        pass

    try:
        brand_result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .order('Brand_Name')
            .execute()
        )
        brand_options = [
            (r['Brand_ID'], r['Brand_Name'])
            for r in (brand_result.data or [])
        ]
    except Exception:
        pass

    return spare_part_options, brand_options


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Stock')
            .select('*')
            .order('Stock_ID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load stock entries: {str(e)}')
        all_records = []

    # Build Spare Parts lookup dict
    try:
        sp_result = (
            supabase.table('Spare_Parts')
            .select('SP_id, SP_name')
            .execute()
        )
        sp_lookup = {
            r['SP_id']: r['SP_name']
            for r in (sp_result.data or [])
        }
    except Exception:
        sp_lookup = {}

    # Build Brand lookup dict
    try:
        brand_result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .execute()
        )
        brand_lookup = {
            r['Brand_ID']: r['Brand_Name']
            for r in (brand_result.data or [])
        }
    except Exception:
        brand_lookup = {}

    # Enrich each record with resolved display values
    for entry in all_records:
        entry['_spare_part_name'] = sp_lookup.get(
            entry.get('Spare_Parts_SP_id'), '—'
        )
        entry['_brand_name'] = brand_lookup.get(
            entry.get('Brand_Brand_ID'), '—'
        )

    # Search across enriched fields
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('Size', '').lower()
            or q in r.get('_spare_part_name', '').lower()
            or q in r.get('_brand_name', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/stock/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    spare_part_options, brand_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_id_raw      = form_data.get('Spare_Parts_SP_id', '').strip()
        brand_id_raw   = form_data.get('Brand_Brand_ID', '').strip()
        size_value     = form_data.get('Size', '').strip()
        qoh_value      = form_data.get('QOH', '').strip()
        price_value    = form_data.get('S_Price', '').strip()
        warranty_value = form_data.get('Warranty', '').strip()

        missing = required_fields(
            form_data,
            ['Spare_Parts_SP_id', 'Brand_Brand_ID', 'Size', 'QOH',
             'S_Price', 'Warranty']
        )

        sp_id = None
        if 'Spare_Parts_SP_id' in missing:
            errors['Spare_Parts_SP_id'] = 'Spare part is required.'
        else:
            try:
                sp_id = int(sp_id_raw)
            except ValueError:
                errors['Spare_Parts_SP_id'] = 'Please select a valid spare part.'

        brand_id = None
        if 'Brand_Brand_ID' in missing:
            errors['Brand_Brand_ID'] = 'Brand is required.'
        else:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                errors['Brand_Brand_ID'] = 'Please select a valid brand.'

        if 'Size' in missing:
            errors['Size'] = 'Size is required.'
        elif len(size_value) > 20:
            errors['Size'] = 'Size must not exceed 20 characters.'

        if 'QOH' in missing:
            errors['QOH'] = 'Quantity on hand is required.'
        elif not is_positive_integer(qoh_value):
            errors['QOH'] = 'Quantity must be a whole number of 0 or more.'

        if 'S_Price' in missing:
            errors['S_Price'] = 'Selling price is required.'
        elif not is_positive_number(price_value):
            errors['S_Price'] = 'Selling price must be a valid number of 0 or more.'

        if 'Warranty' in missing:
            errors['Warranty'] = 'Warranty is required.'
        elif not is_positive_integer(warranty_value):
            errors['Warranty'] = 'Warranty must be a whole number of 0 or more.'

        if not errors:
            try:
                supabase.table('Stock').insert({
                    'Spare_Parts_SP_id': sp_id,
                    'Brand_Brand_ID':    brand_id,
                    'Size':              size_value,
                    'QOH':              int(qoh_value),
                    'S_Price':           float(price_value),
                    'Warranty':          int(warranty_value),
                }).execute()
                flash_success(
                    f'Stock entry for "{sp_lookup_name(sp_id, spare_part_options)}" '
                    f'(Size: {size_value}) was added successfully.'
                )
                return redirect(url_for('stock.index'))
            except Exception as e:
                flash_error(f'Could not add stock entry: {str(e)}')

    return render_template(
        'modules/stock/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        spare_part_options=spare_part_options,
        brand_options=brand_options
    )


def sp_lookup_name(sp_id, spare_part_options):
    """Return the spare part name for a given SP_id from the options list."""
    for opt_id, opt_name in spare_part_options:
        if opt_id == sp_id:
            return opt_name
    return f'ID {sp_id}'


@bp.route('/edit/<int:stock_id>', methods=['GET', 'POST'])
@login_required
def edit(stock_id):
    try:
        result = (
            supabase.table('Stock')
            .select('*')
            .eq('Stock_ID', stock_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Stock entry ID {stock_id} was not found.')
        return redirect(url_for('stock.index'))

    errors = {}
    form_data = record.copy()
    spare_part_options, brand_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        sp_id_raw      = form_data.get('Spare_Parts_SP_id', '').strip()
        brand_id_raw   = form_data.get('Brand_Brand_ID', '').strip()
        size_value     = form_data.get('Size', '').strip()
        qoh_value      = form_data.get('QOH', '').strip()
        price_value    = form_data.get('S_Price', '').strip()
        warranty_value = form_data.get('Warranty', '').strip()

        missing = required_fields(
            form_data,
            ['Spare_Parts_SP_id', 'Brand_Brand_ID', 'Size', 'QOH',
             'S_Price', 'Warranty']
        )

        sp_id = None
        if 'Spare_Parts_SP_id' in missing:
            errors['Spare_Parts_SP_id'] = 'Spare part is required.'
        else:
            try:
                sp_id = int(sp_id_raw)
            except ValueError:
                errors['Spare_Parts_SP_id'] = 'Please select a valid spare part.'

        brand_id = None
        if 'Brand_Brand_ID' in missing:
            errors['Brand_Brand_ID'] = 'Brand is required.'
        else:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                errors['Brand_Brand_ID'] = 'Please select a valid brand.'

        if 'Size' in missing:
            errors['Size'] = 'Size is required.'
        elif len(size_value) > 20:
            errors['Size'] = 'Size must not exceed 20 characters.'

        if 'QOH' in missing:
            errors['QOH'] = 'Quantity on hand is required.'
        elif not is_positive_integer(qoh_value):
            errors['QOH'] = 'Quantity must be a whole number of 0 or more.'

        if 'S_Price' in missing:
            errors['S_Price'] = 'Selling price is required.'
        elif not is_positive_number(price_value):
            errors['S_Price'] = 'Selling price must be a valid number of 0 or more.'

        if 'Warranty' in missing:
            errors['Warranty'] = 'Warranty is required.'
        elif not is_positive_integer(warranty_value):
            errors['Warranty'] = 'Warranty must be a whole number of 0 or more.'

        if not errors:
            try:
                supabase.table('Stock').update({
                    'Spare_Parts_SP_id': sp_id,
                    'Brand_Brand_ID':    brand_id,
                    'Size':              size_value,
                    'QOH':              int(qoh_value),
                    'S_Price':           float(price_value),
                    'Warranty':          int(warranty_value),
                }).eq('Stock_ID', stock_id).execute()
                flash_success(
                    f'Stock entry ID {stock_id} was updated successfully.'
                )
                return redirect(url_for('stock.index'))
            except Exception as e:
                flash_error(f'Could not update stock entry: {str(e)}')

    return render_template(
        'modules/stock/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        spare_part_options=spare_part_options,
        brand_options=brand_options
    )


@bp.route('/delete/<int:stock_id>', methods=['POST'])
@login_required
def delete(stock_id):
    try:
        result = (
            supabase.table('Stock')
            .select('Stock_ID, Size, Spare_Parts_SP_id')
            .eq('Stock_ID', stock_id)
            .single()
            .execute()
        )
        data = result.data
        size_value = data.get('Size', '')
        sp_id = data.get('Spare_Parts_SP_id')
    except Exception:
        size_value = ''
        sp_id = None

    # Resolve spare part name for the flash message
    display_name = f'Stock ID {stock_id}'
    if sp_id:
        try:
            sp_result = (
                supabase.table('Spare_Parts')
                .select('SP_name')
                .eq('SP_id', sp_id)
                .single()
                .execute()
            )
            sp_name = sp_result.data.get('SP_name', '')
            if sp_name and size_value:
                display_name = f'{sp_name} (Size: {size_value})'
            elif sp_name:
                display_name = sp_name
        except Exception:
            pass

    try:
        supabase.table('Stock').delete().eq('Stock_ID', stock_id).execute()
        flash_success(f'Stock entry "{display_name}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{display_name}" because it is referenced '
                f'by one or more purchase order or appointment records. '
                f'Remove those records first before deleting this stock entry.'
            )
        else:
            flash_error(f'Could not delete stock entry: {error_msg}')

    return redirect(url_for('stock.index'))