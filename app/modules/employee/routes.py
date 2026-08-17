from flask import render_template, request, redirect, url_for
from app.modules.employee import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields


def _get_form_options(exclude_employee_id=None):
    """
    Fetch dropdown options for the Employee Create and Edit forms.

    Args:
        exclude_employee_id: EmployeeID to exclude from the Supervisor
                             dropdown. Pass the current employee's ID
                             on Edit to prevent self-referencing.

    Returns:
        role_options:       list of (Role_ID, Role_Name) tuples
        supervisor_options: list of (EmployeeID, Full Name) tuples
    """
    role_options = []
    supervisor_options = []

    try:
        role_result = (
            supabase.table('Role')
            .select('Role_ID, Role_Name')
            .order('Role_Name')
            .execute()
        )
        role_options = [
            (r['Role_ID'], r['Role_Name'])
            for r in (role_result.data or [])
        ]
    except Exception:
        pass

    try:
        emp_result = (
            supabase.table('Employee')
            .select('EmployeeID, FirstName, LastName')
            .order('LastName')
            .execute()
        )
        supervisor_options = [
            (
                e['EmployeeID'],
                f"{e['FirstName']} {e['LastName']}"
            )
            for e in (emp_result.data or [])
            if e['EmployeeID'] != exclude_employee_id
        ]
    except Exception:
        pass

    return role_options, supervisor_options


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        emp_result = (
            supabase.table('Employee')
            .select('*')
            .order('LastName')
            .execute()
        )
        all_records = emp_result.data or []
    except Exception as e:
        flash_error(f'Could not load employees: {str(e)}')
        all_records = []

    # Build lookup dicts for Role and Supervisor display
    try:
        role_result = (
            supabase.table('Role')
            .select('Role_ID, Role_Name')
            .execute()
        )
        role_lookup = {
            r['Role_ID']: r['Role_Name']
            for r in (role_result.data or [])
        }
    except Exception:
        role_lookup = {}

    emp_lookup = {
        e['EmployeeID']: f"{e['FirstName']} {e['LastName']}"
        for e in all_records
    }

    # Enrich each record with resolved display values
    for emp in all_records:
        emp['_role_name'] = role_lookup.get(
            emp.get('Role_Role_ID'), '—'
        )
        emp['_supervisor_name'] = emp_lookup.get(
            emp.get('SupervisorID'), '—'
        )

    # Search across enriched fields
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('FirstName', '').lower()
            or q in r.get('LastName', '').lower()
            or q in f"{r.get('FirstName', '')} {r.get('LastName', '')}".lower()
            or q in r.get('Phone', '').lower()
            or q in r.get('_role_name', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/employee/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    role_options, supervisor_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        first_name       = form_data.get('FirstName', '').strip()
        last_name        = form_data.get('LastName', '').strip()
        phone            = form_data.get('Phone', '').strip()
        role_id_raw      = form_data.get('Role_Role_ID', '').strip()
        supervisor_id_raw = form_data.get('SupervisorID', '').strip()

        missing = required_fields(
            form_data, ['FirstName', 'LastName', 'Phone', 'Role_Role_ID']
        )

        if 'FirstName' in missing:
            errors['FirstName'] = 'First name is required.'
        elif len(first_name) > 50:
            errors['FirstName'] = 'First name must not exceed 50 characters.'

        if 'LastName' in missing:
            errors['LastName'] = 'Last name is required.'
        elif len(last_name) > 50:
            errors['LastName'] = 'Last name must not exceed 50 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        role_id = None
        if 'Role_Role_ID' in missing:
            errors['Role_Role_ID'] = 'Role is required.'
        else:
            try:
                role_id = int(role_id_raw)
            except ValueError:
                errors['Role_Role_ID'] = 'Please select a valid role.'

        supervisor_id = None
        if supervisor_id_raw:
            try:
                supervisor_id = int(supervisor_id_raw)
            except ValueError:
                errors['SupervisorID'] = 'Invalid supervisor selection.'

        if not errors:
            try:
                supabase.table('Employee').insert({
                    'FirstName':    first_name,
                    'LastName':     last_name,
                    'Phone':        phone,
                    'Role_Role_ID': role_id,
                    'SupervisorID': supervisor_id,
                }).execute()
                flash_success(
                    f'Employee "{first_name} {last_name}" was added successfully.'
                )
                return redirect(url_for('employee.index'))
            except Exception as e:
                flash_error(f'Could not add employee: {str(e)}')

    return render_template(
        'modules/employee/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        role_options=role_options,
        supervisor_options=supervisor_options
    )


@bp.route('/edit/<int:employee_id>', methods=['GET', 'POST'])
@login_required
def edit(employee_id):
    try:
        result = (
            supabase.table('Employee')
            .select('*')
            .eq('EmployeeID', employee_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Employee ID {employee_id} was not found.')
        return redirect(url_for('employee.index'))

    errors = {}
    form_data = record.copy()

    # Exclude the current employee from their own Supervisor dropdown
    role_options, supervisor_options = _get_form_options(
        exclude_employee_id=employee_id
    )

    if request.method == 'POST':
        form_data = request.form.to_dict()

        first_name        = form_data.get('FirstName', '').strip()
        last_name         = form_data.get('LastName', '').strip()
        phone             = form_data.get('Phone', '').strip()
        role_id_raw       = form_data.get('Role_Role_ID', '').strip()
        supervisor_id_raw = form_data.get('SupervisorID', '').strip()

        missing = required_fields(
            form_data, ['FirstName', 'LastName', 'Phone', 'Role_Role_ID']
        )

        if 'FirstName' in missing:
            errors['FirstName'] = 'First name is required.'
        elif len(first_name) > 50:
            errors['FirstName'] = 'First name must not exceed 50 characters.'

        if 'LastName' in missing:
            errors['LastName'] = 'Last name is required.'
        elif len(last_name) > 50:
            errors['LastName'] = 'Last name must not exceed 50 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        role_id = None
        if 'Role_Role_ID' in missing:
            errors['Role_Role_ID'] = 'Role is required.'
        else:
            try:
                role_id = int(role_id_raw)
            except ValueError:
                errors['Role_Role_ID'] = 'Please select a valid role.'

        supervisor_id = None
        if supervisor_id_raw:
            try:
                supervisor_id = int(supervisor_id_raw)
            except ValueError:
                errors['SupervisorID'] = 'Invalid supervisor selection.'

        if not errors:
            try:
                supabase.table('Employee').update({
                    'FirstName':    first_name,
                    'LastName':     last_name,
                    'Phone':        phone,
                    'Role_Role_ID': role_id,
                    'SupervisorID': supervisor_id,
                }).eq('EmployeeID', employee_id).execute()
                flash_success(
                    f'Employee "{first_name} {last_name}" was updated successfully.'
                )
                return redirect(url_for('employee.index'))
            except Exception as e:
                flash_error(f'Could not update employee: {str(e)}')

    return render_template(
        'modules/employee/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        role_options=role_options,
        supervisor_options=supervisor_options
    )


@bp.route('/delete/<int:employee_id>', methods=['POST'])
@login_required
def delete(employee_id):
    try:
        result = (
            supabase.table('Employee')
            .select('FirstName, LastName')
            .eq('EmployeeID', employee_id)
            .single()
            .execute()
        )
        data = result.data
        full_name = f"{data.get('FirstName', '')} {data.get('LastName', '')}".strip()
        if not full_name:
            full_name = f'ID {employee_id}'
    except Exception:
        full_name = f'ID {employee_id}'

    try:
        supabase.table('Employee').delete().eq('EmployeeID', employee_id).execute()
        flash_success(f'Employee "{full_name}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{full_name}" because they are listed as a '
                f'supervisor for one or more other employees. '
                f'Reassign those employees to a different supervisor first.'
            )
        else:
            flash_error(f'Could not delete employee: {error_msg}')

    return redirect(url_for('employee.index'))