from flask import render_template, request, redirect, url_for
from app.modules.spare_parts import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields


def _get_form_options():
    """
    Fetch dropdown options for the Spare Parts Create and Edit forms.

    Returns:
        category_options: list of (CAT_ID, CAT_desc) tuples
        model_options:    list of (Model_No, Description) tuples
    """
    category_options = []
    model_options = []

    try:
        cat_result = (
            supabase.table('Category')
            .select('CAT_ID, CAT_desc')
            .order('CAT_desc')
            .execute()
        )
        category_options = [
            (r['CAT_ID'], r['CAT_desc'])
            for r in (cat_result.data or [])
        ]
    except Exception:
        pass

    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Description')
            .order('Description')
            .execute()
        )
        model_options = [
            (r['Model_No'], r['Description'])
            for r in (model_result.data or [])
        ]
    except Exception:
        pass

    return category_options, model_options


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Spare_Parts')
            .select('*')
            .order('SP_name')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load spare parts: {str(e)}')
        all_records = []

    # Build Category lookup dict
    try:
        cat_result = (
            supabase.table('Category')
            .select('CAT_ID, CAT_desc')
            .execute()
        )
        category_lookup = {
            c['CAT_ID']: c['CAT_desc']
            for c in (cat_result.data or [])
        }
    except Exception:
        category_lookup = {}

    # Build Model lookup dict
    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Description')
            .execute()
        )
        model_lookup = {
            m['Model_No']: m['Description']
            for m in (model_result.data or [])
        }
    except Exception:
        model_lookup = {}

    # Enrich each record with resolved display values
    for part in all_records:
        part['_category_name'] = category_lookup.get(
            part.get('Category_CAT_ID'), '—'
        )
        model_no = part.get('Model_Model_No')
        part['_model_desc'] = (
            model_lookup.get(model_no, '—')
            if model_no is not None
            else 'Universal'
        )

    # Search across enriched fields
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('SP_name', '').lower()
            or q in r.get('SP_desc', '').lower()
            or q in r.get('_category_name', '').lower()
            or q in r.get('_model_desc', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/spare_parts/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    category_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        name_value      = form_data.get('SP_name', '').strip()
        desc_value      = form_data.get('SP_desc', '').strip()
        cat_id_raw      = form_data.get('Category_CAT_ID', '').strip()
        model_no_raw    = form_data.get('Model_Model_No', '').strip()

        missing = required_fields(
            form_data, ['SP_name', 'SP_desc', 'Category_CAT_ID']
        )

        if 'SP_name' in missing:
            errors['SP_name'] = 'Part name is required.'
        elif len(name_value) > 50:
            errors['SP_name'] = 'Part name must not exceed 50 characters.'

        if 'SP_desc' in missing:
            errors['SP_desc'] = 'Description is required.'
        elif len(desc_value) > 255:
            errors['SP_desc'] = 'Description must not exceed 255 characters.'

        cat_id = None
        if 'Category_CAT_ID' in missing:
            errors['Category_CAT_ID'] = 'Category is required.'
        else:
            try:
                cat_id = int(cat_id_raw)
            except ValueError:
                errors['Category_CAT_ID'] = 'Please select a valid category.'

        model_no = None
        if model_no_raw:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Invalid model selection.'

        if not errors:
            try:
                supabase.table('Spare_Parts').insert({
                    'SP_name':         name_value,
                    'SP_desc':         desc_value,
                    'Category_CAT_ID': cat_id,
                    'Model_Model_No':  model_no,
                }).execute()
                flash_success(f'Spare part "{name_value}" was added successfully.')
                return redirect(url_for('spare_parts.index'))
            except Exception as e:
                flash_error(f'Could not add spare part: {str(e)}')

    return render_template(
        'modules/spare_parts/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        category_options=category_options,
        model_options=model_options
    )


@bp.route('/edit/<int:sp_id>', methods=['GET', 'POST'])
@login_required
def edit(sp_id):
    try:
        result = (
            supabase.table('Spare_Parts')
            .select('*')
            .eq('SP_id', sp_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Spare part ID {sp_id} was not found.')
        return redirect(url_for('spare_parts.index'))

    errors = {}
    form_data = record.copy()
    category_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        name_value   = form_data.get('SP_name', '').strip()
        desc_value   = form_data.get('SP_desc', '').strip()
        cat_id_raw   = form_data.get('Category_CAT_ID', '').strip()
        model_no_raw = form_data.get('Model_Model_No', '').strip()

        missing = required_fields(
            form_data, ['SP_name', 'SP_desc', 'Category_CAT_ID']
        )

        if 'SP_name' in missing:
            errors['SP_name'] = 'Part name is required.'
        elif len(name_value) > 50:
            errors['SP_name'] = 'Part name must not exceed 50 characters.'

        if 'SP_desc' in missing:
            errors['SP_desc'] = 'Description is required.'
        elif len(desc_value) > 255:
            errors['SP_desc'] = 'Description must not exceed 255 characters.'

        cat_id = None
        if 'Category_CAT_ID' in missing:
            errors['Category_CAT_ID'] = 'Category is required.'
        else:
            try:
                cat_id = int(cat_id_raw)
            except ValueError:
                errors['Category_CAT_ID'] = 'Please select a valid category.'

        model_no = None
        if model_no_raw:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Invalid model selection.'

        if not errors:
            try:
                supabase.table('Spare_Parts').update({
                    'SP_name':         name_value,
                    'SP_desc':         desc_value,
                    'Category_CAT_ID': cat_id,
                    'Model_Model_No':  model_no,
                }).eq('SP_id', sp_id).execute()
                flash_success(f'Spare part "{name_value}" was updated successfully.')
                return redirect(url_for('spare_parts.index'))
            except Exception as e:
                flash_error(f'Could not update spare part: {str(e)}')

    return render_template(
        'modules/spare_parts/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        category_options=category_options,
        model_options=model_options
    )


@bp.route('/delete/<int:sp_id>', methods=['POST'])
@login_required
def delete(sp_id):
    try:
        result = (
            supabase.table('Spare_Parts')
            .select('SP_name')
            .eq('SP_id', sp_id)
            .single()
            .execute()
        )
        name_value = result.data.get('SP_name', f'ID {sp_id}')
    except Exception:
        name_value = f'ID {sp_id}'

    try:
        supabase.table('Spare_Parts').delete().eq('SP_id', sp_id).execute()
        flash_success(f'Spare part "{name_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is referenced by '
                f'one or more stock entries. '
                f'Remove those stock entries first before deleting this spare part.'
            )
        else:
            flash_error(f'Could not delete spare part: {error_msg}')

    return redirect(url_for('spare_parts.index'))