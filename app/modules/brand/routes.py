from flask import render_template, request, redirect, url_for
from app.modules.brand import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Brand')
            .select('*')
            .order('Brand_Name')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load brands: {str(e)}')
        all_records = []

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('Brand_Name', '').lower()
            or q in r.get('CountryOfOrigin', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/brand/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data = request.form.to_dict()
        name_value    = form_data.get('Brand_Name', '').strip()
        country_value = form_data.get('CountryOfOrigin', '').strip()

        missing = required_fields(form_data, ['Brand_Name', 'CountryOfOrigin'])

        if 'Brand_Name' in missing:
            errors['Brand_Name'] = 'Brand name is required.'
        elif len(name_value) > 50:
            errors['Brand_Name'] = 'Brand name must not exceed 50 characters.'

        if 'CountryOfOrigin' in missing:
            errors['CountryOfOrigin'] = 'Country of origin is required.'
        elif len(country_value) > 40:
            errors['CountryOfOrigin'] = 'Country of origin must not exceed 40 characters.'

        if not errors:
            try:
                supabase.table('Brand').insert({
                    'Brand_Name':      name_value,
                    'CountryOfOrigin': country_value,
                }).execute()
                flash_success(f'Brand "{name_value}" was added successfully.')
                return redirect(url_for('brand.index'))

            # except Exception as e:
            #     flash_error(f'Could not add brand: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A brand with this name already exists.')
                else:
                    flash_error(f'Could not add brand: {error_msg}')

    return render_template(
        'modules/brand/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:brand_id>', methods=['GET', 'POST'])
@login_required
def edit(brand_id):
    try:
        result = (
            supabase.table('Brand')
            .select('*')
            .eq('Brand_ID', brand_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Brand ID {brand_id} was not found.')
        return redirect(url_for('brand.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        name_value    = form_data.get('Brand_Name', '').strip()
        country_value = form_data.get('CountryOfOrigin', '').strip()

        missing = required_fields(form_data, ['Brand_Name', 'CountryOfOrigin'])

        if 'Brand_Name' in missing:
            errors['Brand_Name'] = 'Brand name is required.'
        elif len(name_value) > 50:
            errors['Brand_Name'] = 'Brand name must not exceed 50 characters.'

        if 'CountryOfOrigin' in missing:
            errors['CountryOfOrigin'] = 'Country of origin is required.'
        elif len(country_value) > 40:
            errors['CountryOfOrigin'] = 'Country of origin must not exceed 40 characters.'

        if not errors:
            try:
                supabase.table('Brand').update({
                    'Brand_Name':      name_value,
                    'CountryOfOrigin': country_value,
                }).eq('Brand_ID', brand_id).execute()
                flash_success(f'Brand "{name_value}" was updated successfully.')
                return redirect(url_for('brand.index'))
            # except Exception as e:
            #     flash_error(f'Could not update brand: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A brand with this name already exists.')
                else:
                    flash_error(f'Could not update brand: {error_msg}')

    return render_template(
        'modules/brand/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:brand_id>', methods=['POST'])
@login_required
def delete(brand_id):
    try:
        result = (
            supabase.table('Brand')
            .select('Brand_Name')
            .eq('Brand_ID', brand_id)
            .single()
            .execute()
        )
        name_value = result.data.get('Brand_Name', f'ID {brand_id}')
    except Exception:
        name_value = f'ID {brand_id}'

    try:
        supabase.table('Brand').delete().eq('Brand_ID', brand_id).execute()
        flash_success(f'Brand "{name_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is referenced by '
                f'one or more models or stock entries. '
                f'Remove those records first before deleting this brand.'
            )
        else:
            flash_error(f'Could not delete brand: {error_msg}')

    return redirect(url_for('brand.index'))