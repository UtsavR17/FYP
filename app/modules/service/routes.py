from flask import render_template, request, redirect, url_for
from app.modules.service import bp
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
        result = (
            supabase.table('Service')
            .select('*')
            .order('Service_Name')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load services: {str(e)}')
        all_records = []

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('Service_Name', '').lower()
            or q in r.get('Description', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/service/list.html',
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
        name_value = form_data.get('Service_Name', '').strip()
        desc_value = form_data.get('Description', '').strip()
        cost_value = form_data.get('Cost', '').strip()

        missing = required_fields(form_data, ['Service_Name', 'Description', 'Cost'])

        if 'Service_Name' in missing:
            errors['Service_Name'] = 'Service name is required.'
        elif len(name_value) > 50:
            errors['Service_Name'] = 'Service name must not exceed 50 characters.'

        if 'Description' in missing:
            errors['Description'] = 'Description is required.'
        elif len(desc_value) > 255:
            errors['Description'] = 'Description must not exceed 255 characters.'

        if 'Cost' in missing:
            errors['Cost'] = 'Cost is required.'
        elif not is_positive_number(cost_value):
            errors['Cost'] = 'Cost must be a valid number of 0 or more.'

        if not errors:
            try:
                supabase.table('Service').insert({
                    'Service_Name': name_value,
                    'Description':  desc_value,
                    'Cost':         float(cost_value),
                }).execute()
                flash_success(f'Service "{name_value}" was added successfully.')
                return redirect(url_for('service.index'))
            # except Exception as e:
            #     flash_error(f'Could not add service: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A service with this name already exists.')
                else:
                    flash_error(f'Could not add service: {error_msg}')

    return render_template(
        'modules/service/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:service_id>', methods=['GET', 'POST'])
@login_required
def edit(service_id):
    try:
        result = (
            supabase.table('Service')
            .select('*')
            .eq('ServiceID', service_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Service ID {service_id} was not found.')
        return redirect(url_for('service.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        name_value = form_data.get('Service_Name', '').strip()
        desc_value = form_data.get('Description', '').strip()
        cost_value = form_data.get('Cost', '').strip()

        missing = required_fields(form_data, ['Service_Name', 'Description', 'Cost'])

        if 'Service_Name' in missing:
            errors['Service_Name'] = 'Service name is required.'
        elif len(name_value) > 50:
            errors['Service_Name'] = 'Service name must not exceed 50 characters.'

        if 'Description' in missing:
            errors['Description'] = 'Description is required.'
        elif len(desc_value) > 255:
            errors['Description'] = 'Description must not exceed 255 characters.'

        if 'Cost' in missing:
            errors['Cost'] = 'Cost is required.'
        elif not is_positive_number(cost_value):
            errors['Cost'] = 'Cost must be a valid number of 0 or more.'

        if not errors:
            try:
                supabase.table('Service').update({
                    'Service_Name': name_value,
                    'Description':  desc_value,
                    'Cost':         float(cost_value),
                }).eq('ServiceID', service_id).execute()
                flash_success(f'Service "{name_value}" was updated successfully.')
                return redirect(url_for('service.index'))
            # except Exception as e:
            #     flash_error(f'Could not update service: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                flash_error(f'A service with this name already exists.')
            else:
                flash_error(f'Could not update service: {error_msg}')

    return render_template(
        'modules/service/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:service_id>', methods=['POST'])
@login_required
def delete(service_id):
    try:
        result = (
            supabase.table('Service')
            .select('Service_Name')
            .eq('ServiceID', service_id)
            .single()
            .execute()
        )
        name_value = result.data.get('Service_Name', f'ID {service_id}')
    except Exception:
        name_value = f'ID {service_id}'

    try:
        supabase.table('Service').delete().eq('ServiceID', service_id).execute()
        flash_success(f'Service "{name_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is referenced '
                f'by one or more appointment records. '
                f'Remove those records first before deleting this service.'
            )
        else:
            flash_error(f'Could not delete service: {error_msg}')

    return redirect(url_for('service.index'))