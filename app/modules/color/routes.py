from flask import render_template, request, redirect, url_for
from app.modules.color import bp
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
        result = supabase.table('Color').select('*').order('Color').execute()
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load colors: {str(e)}')
        all_records = []

    if search_query:
        all_records = [
            r for r in all_records
            if search_query.lower() in r.get('Color', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/color/list.html',
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
        color_value = form_data.get('Color', '').strip()

        missing = required_fields(form_data, ['Color'])
        if missing:
            errors['Color'] = 'Color name is required.'
        elif len(color_value) > 20:
            errors['Color'] = 'Color name must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Color').insert({'Color': color_value}).execute()
                flash_success(f'Color "{color_value}" was added successfully.')
                return redirect(url_for('color.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Color'] = f'A color named "{color_value}" already exists.'
                else:
                    flash_error(f'Could not add color: {error_msg}')

    return render_template(
        'modules/color/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<string:color_id>', methods=['GET', 'POST'])
@login_required
def edit(color_id):
    try:
        result = (
            supabase.table('Color')
            .select('*')
            .eq('Color', color_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Color "{color_id}" was not found.')
        return redirect(url_for('color.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        color_value = form_data.get('Color', '').strip()

        missing = required_fields(form_data, ['Color'])
        if missing:
            errors['Color'] = 'Color name is required.'
        elif len(color_value) > 20:
            errors['Color'] = 'Color name must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Color').update(
                    {'Color': color_value}
                ).eq('Color', color_id).execute()
                flash_success(f'Color updated to "{color_value}" successfully.')
                return redirect(url_for('color.index'))
            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    errors['Color'] = f'A color named "{color_value}" already exists.'
                else:
                    flash_error(f'Could not update color: {error_msg}')

    return render_template(
        'modules/color/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<string:color_id>', methods=['POST'])
@login_required
def delete(color_id):
    try:
        supabase.table('Color').delete().eq('Color', color_id).execute()
        flash_success(f'Color "{color_id}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{color_id}" because it is used by other records.'
            )
        else:
            flash_error(f'Could not delete color: {error_msg}')

    return redirect(url_for('color.index'))