from flask import render_template, request, redirect, url_for
from app.modules.role import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_positive_number


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = supabase.table('Role').select('*').order('Role_Name').execute()
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load roles: {str(e)}')
        all_records = []

    if search_query:
        all_records = [
            r for r in all_records
            if search_query.lower() in r.get('Role_Name', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/role/list.html',
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
        name_value = form_data.get('Role_Name', '').strip()
        rate_value = form_data.get('HourlyRate', '').strip()

        missing = required_fields(form_data, ['Role_Name', 'HourlyRate'])
        if 'Role_Name' in missing:
            errors['Role_Name'] = 'Role name is required.'
        elif len(name_value) > 15:
            errors['Role_Name'] = 'Role name must not exceed 15 characters.'

        if 'HourlyRate' in missing:
            errors['HourlyRate'] = 'Hourly rate is required.'
        elif not is_positive_number(rate_value):
            errors['HourlyRate'] = 'Hourly rate must be a valid number of 0 or more.'

        if not errors:
            try:
                supabase.table('Role').insert({
                    'Role_Name':  name_value,
                    'HourlyRate': float(rate_value)
                }).execute()
                flash_success(f'Role "{name_value}" was added successfully.')
                return redirect(url_for('role.index'))
            # except Exception as e:
            #     flash_error(f'Could not add role: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A role with this name already exists.')
                else:
                    flash_error(f'Could not add role: {error_msg}')

    return render_template(
        'modules/role/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:role_id>', methods=['GET', 'POST'])
@login_required
def edit(role_id):
    try:
        result = (
            supabase.table('Role')
            .select('*')
            .eq('Role_ID', role_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Role ID {role_id} was not found.')
        return redirect(url_for('role.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        name_value = form_data.get('Role_Name', '').strip()
        rate_value = form_data.get('HourlyRate', '').strip()

        missing = required_fields(form_data, ['Role_Name', 'HourlyRate'])
        if 'Role_Name' in missing:
            errors['Role_Name'] = 'Role name is required.'
        elif len(name_value) > 15:
            errors['Role_Name'] = 'Role name must not exceed 15 characters.'

        if 'HourlyRate' in missing:
            errors['HourlyRate'] = 'Hourly rate is required.'
        elif not is_positive_number(rate_value):
            errors['HourlyRate'] = 'Hourly rate must be a valid number of 0 or more.'

        if not errors:
            try:
                supabase.table('Role').update({
                    'Role_Name':  name_value,
                    'HourlyRate': float(rate_value)
                }).eq('Role_ID', role_id).execute()
                flash_success(f'Role "{name_value}" was updated successfully.')
                return redirect(url_for('role.index'))
            # except Exception as e:
            #     flash_error(f'Could not update role: {str(e)}')

            # except Exception as e:
            #     flash_error(f'Could not update role: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A role with this name already exists.')
                else:
                    flash_error(f'Could not update role: {error_msg}')

    return render_template(
        'modules/role/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:role_id>', methods=['POST'])
@login_required
def delete(role_id):
    try:
        result = (
            supabase.table('Role')
            .select('Role_Name')
            .eq('Role_ID', role_id)
            .single()
            .execute()
        )
        name_value = result.data.get('Role_Name', f'ID {role_id}')
    except Exception:
        name_value = f'ID {role_id}'

    try:
        supabase.table('Role').delete().eq('Role_ID', role_id).execute()
        flash_success(f'Role "{name_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is assigned to '
                f'one or more employees. Reassign those employees first.'
            )
        else:
            flash_error(f'Could not delete role: {error_msg}')

    return redirect(url_for('role.index'))