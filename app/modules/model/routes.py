from flask import render_template, request, redirect, url_for
from app.modules.model import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields


def _get_brand_options():
    """
    Fetch Brand dropdown options for the Model Create and Edit forms.

    Returns:
        list of (Brand_ID, Brand_Name) tuples ordered by Brand_Name.
        Returns an empty list if the fetch fails.
    """
    try:
        result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .order('Brand_Name')
            .execute()
        )
        return [
            (r['Brand_ID'], r['Brand_Name'])
            for r in (result.data or [])
        ]
    except Exception:
        return []


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Model')
            .select('*')
            .order('Description')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load models: {str(e)}')
        all_records = []

    # Build Brand lookup dict for display
    try:
        brand_result = (
            supabase.table('Brand')
            .select('Brand_ID, Brand_Name')
            .execute()
        )
        brand_lookup = {
            b['Brand_ID']: b['Brand_Name']
            for b in (brand_result.data or [])
        }
    except Exception:
        brand_lookup = {}

    # Enrich each record with resolved Brand Name
    for model in all_records:
        model['_brand_name'] = brand_lookup.get(
            model.get('Brand_Brand_ID'), '—'
        )

    # Search across enriched fields
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('Description', '').lower()
            or q in r.get('_brand_name', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/model/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    brand_options = _get_brand_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        brand_id_raw  = form_data.get('Brand_Brand_ID', '').strip()
        desc_value    = form_data.get('Description', '').strip()

        missing = required_fields(form_data, ['Brand_Brand_ID', 'Description'])

        brand_id = None
        if 'Brand_Brand_ID' in missing:
            errors['Brand_Brand_ID'] = 'Brand is required.'
        else:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                errors['Brand_Brand_ID'] = 'Please select a valid brand.'

        if 'Description' in missing:
            errors['Description'] = 'Model description is required.'
        elif len(desc_value) > 50:
            errors['Description'] = 'Model description must not exceed 50 characters.'

        if not errors:
            try:
                supabase.table('Model').insert({
                    'Brand_Brand_ID': brand_id,
                    'Description':    desc_value,
                }).execute()
                flash_success(f'Model "{desc_value}" was added successfully.')
                return redirect(url_for('model.index'))
            # except Exception as e:
            #     flash_error(f'Could not add model: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A model with this name already exists.')
                else:
                    flash_error(f'Could not add model: {error_msg}')

    return render_template(
        'modules/model/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        brand_options=brand_options
    )


@bp.route('/edit/<int:model_no>', methods=['GET', 'POST'])
@login_required
def edit(model_no):
    try:
        result = (
            supabase.table('Model')
            .select('*')
            .eq('Model_No', model_no)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Model ID {model_no} was not found.')
        return redirect(url_for('model.index'))

    errors = {}
    form_data = record.copy()
    brand_options = _get_brand_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        brand_id_raw = form_data.get('Brand_Brand_ID', '').strip()
        desc_value   = form_data.get('Description', '').strip()

        missing = required_fields(form_data, ['Brand_Brand_ID', 'Description'])

        brand_id = None
        if 'Brand_Brand_ID' in missing:
            errors['Brand_Brand_ID'] = 'Brand is required.'
        else:
            try:
                brand_id = int(brand_id_raw)
            except ValueError:
                errors['Brand_Brand_ID'] = 'Please select a valid brand.'

        if 'Description' in missing:
            errors['Description'] = 'Model description is required.'
        elif len(desc_value) > 50:
            errors['Description'] = 'Model description must not exceed 50 characters.'

        if not errors:
            try:
                supabase.table('Model').update({
                    'Brand_Brand_ID': brand_id,
                    'Description':    desc_value,
                }).eq('Model_No', model_no).execute()
                flash_success(f'Model "{desc_value}" was updated successfully.')
                return redirect(url_for('model.index'))
            # except Exception as e:
            #     flash_error(f'Could not update model: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A model with this name already exists.')
                else:
                    flash_error(f'Could not update model: {error_msg}')

    return render_template(
        'modules/model/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        brand_options=brand_options
    )


@bp.route('/delete/<int:model_no>', methods=['POST'])
@login_required
def delete(model_no):
    try:
        result = (
            supabase.table('Model')
            .select('Description')
            .eq('Model_No', model_no)
            .single()
            .execute()
        )
        desc_value = result.data.get('Description', f'ID {model_no}')
    except Exception:
        desc_value = f'ID {model_no}'

    try:
        supabase.table('Model').delete().eq('Model_No', model_no).execute()
        flash_success(f'Model "{desc_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{desc_value}" because it is referenced by '
                f'one or more spare parts. '
                f'Remove or reassign those spare parts first before '
                f'deleting this model.'
            )
        else:
            flash_error(f'Could not delete model: {error_msg}')

    return redirect(url_for('model.index'))