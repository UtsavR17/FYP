from flask import render_template, request, redirect, url_for
from app.modules.customer import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error
from app.utils.validators import required_fields, is_valid_email


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Customer')
            .select('*')
            .order('LastName')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load customers: {str(e)}')
        all_records = []

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('FirstName', '').lower()
            or q in r.get('LastName', '').lower()
            or q in f"{r.get('FirstName', '')} {r.get('LastName', '')}".lower()
            or q in r.get('PhoneNumber', '').lower()
            or q in r.get('Email', '').lower()
            or q in r.get('Town', '').lower()
            or q in r.get('NIC', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/customer/list.html',
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

        first_name   = form_data.get('FirstName', '').strip()
        last_name    = form_data.get('LastName', '').strip()
        phone        = form_data.get('PhoneNumber', '').strip()
        home_number  = form_data.get('HomeNumber', '').strip()
        email        = form_data.get('Email', '').strip()
        street       = form_data.get('Street', '').strip()
        town         = form_data.get('Town', '').strip()
        postcode     = form_data.get('PostCode', '').strip()
        nic          = form_data.get('NIC', '').strip()

        missing = required_fields(
            form_data,
            ['FirstName', 'LastName', 'PhoneNumber', 'Email', 'Street', 'Town', 'NIC']
        )

        if 'FirstName' in missing:
            errors['FirstName'] = 'First name is required.'
        elif len(first_name) > 50:
            errors['FirstName'] = 'First name must not exceed 50 characters.'

        if 'LastName' in missing:
            errors['LastName'] = 'Last name is required.'
        elif len(last_name) > 50:
            errors['LastName'] = 'Last name must not exceed 50 characters.'

        if 'PhoneNumber' in missing:
            errors['PhoneNumber'] = 'Phone number is required.'
        elif len(phone) > 20:
            errors['PhoneNumber'] = 'Phone number must not exceed 20 characters.'

        if home_number and len(home_number) > 20:
            errors['HomeNumber'] = 'Home number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email) > 100:
            errors['Email'] = 'Email must not exceed 100 characters.'
        elif not is_valid_email(email):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Street' in missing:
            errors['Street'] = 'Street address is required.'
        elif len(street) > 50:
            errors['Street'] = 'Street must not exceed 50 characters.'

        if 'Town' in missing:
            errors['Town'] = 'Town is required.'
        elif len(town) > 60:
            errors['Town'] = 'Town must not exceed 60 characters.'

        if postcode and len(postcode) > 10:
            errors['PostCode'] = 'Post code must not exceed 10 characters.'

        if 'NIC' in missing:
            errors['NIC'] = 'NIC number is required.'
        elif len(nic) > 20:
            errors['NIC'] = 'NIC must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Customer').insert({
                    'FirstName':   first_name,
                    'LastName':    last_name,
                    'PhoneNumber': phone,
                    'HomeNumber':  home_number or None,
                    'Email':       email,
                    'Street':      street,
                    'Town':        town,
                    'PostCode':    postcode or None,
                    'NIC':         nic,
                }).execute()
                flash_success(
                    f'Customer "{first_name} {last_name}" was added successfully.'
                )
                return redirect(url_for('customer.index'))
            except Exception as e:
                flash_error(f'Could not add customer: {str(e)}')

    return render_template(
        'modules/customer/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def edit(customer_id):
    try:
        result = (
            supabase.table('Customer')
            .select('*')
            .eq('CustomerID', customer_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Customer ID {customer_id} was not found.')
        return redirect(url_for('customer.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        first_name  = form_data.get('FirstName', '').strip()
        last_name   = form_data.get('LastName', '').strip()
        phone       = form_data.get('PhoneNumber', '').strip()
        home_number = form_data.get('HomeNumber', '').strip()
        email       = form_data.get('Email', '').strip()
        street      = form_data.get('Street', '').strip()
        town        = form_data.get('Town', '').strip()
        postcode    = form_data.get('PostCode', '').strip()
        nic         = form_data.get('NIC', '').strip()

        missing = required_fields(
            form_data,
            ['FirstName', 'LastName', 'PhoneNumber', 'Email', 'Street', 'Town', 'NIC']
        )

        if 'FirstName' in missing:
            errors['FirstName'] = 'First name is required.'
        elif len(first_name) > 50:
            errors['FirstName'] = 'First name must not exceed 50 characters.'

        if 'LastName' in missing:
            errors['LastName'] = 'Last name is required.'
        elif len(last_name) > 50:
            errors['LastName'] = 'Last name must not exceed 50 characters.'

        if 'PhoneNumber' in missing:
            errors['PhoneNumber'] = 'Phone number is required.'
        elif len(phone) > 20:
            errors['PhoneNumber'] = 'Phone number must not exceed 20 characters.'

        if home_number and len(home_number) > 20:
            errors['HomeNumber'] = 'Home number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email) > 100:
            errors['Email'] = 'Email must not exceed 100 characters.'
        elif not is_valid_email(email):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Street' in missing:
            errors['Street'] = 'Street address is required.'
        elif len(street) > 50:
            errors['Street'] = 'Street must not exceed 50 characters.'

        if 'Town' in missing:
            errors['Town'] = 'Town is required.'
        elif len(town) > 60:
            errors['Town'] = 'Town must not exceed 60 characters.'

        if postcode and len(postcode) > 10:
            errors['PostCode'] = 'Post code must not exceed 10 characters.'

        if 'NIC' in missing:
            errors['NIC'] = 'NIC number is required.'
        elif len(nic) > 20:
            errors['NIC'] = 'NIC must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Customer').update({
                    'FirstName':   first_name,
                    'LastName':    last_name,
                    'PhoneNumber': phone,
                    'HomeNumber':  home_number or None,
                    'Email':       email,
                    'Street':      street,
                    'Town':        town,
                    'PostCode':    postcode or None,
                    'NIC':         nic,
                }).eq('CustomerID', customer_id).execute()
                flash_success(
                    f'Customer "{first_name} {last_name}" was updated successfully.'
                )
                return redirect(url_for('customer.index'))
            except Exception as e:
                flash_error(f'Could not update customer: {str(e)}')

    return render_template(
        'modules/customer/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:customer_id>', methods=['POST'])
@login_required
def delete(customer_id):
    try:
        result = (
            supabase.table('Customer')
            .select('FirstName, LastName')
            .eq('CustomerID', customer_id)
            .single()
            .execute()
        )
        data = result.data
        full_name = (
            f"{data.get('FirstName', '')} {data.get('LastName', '')}".strip()
            or f'ID {customer_id}'
        )
    except Exception:
        full_name = f'ID {customer_id}'

    try:
        supabase.table('Customer').delete().eq('CustomerID', customer_id).execute()
        flash_success(f'Customer "{full_name}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{full_name}" because they have associated bike registrations or sales records. '
                f'Remove the records first before deleting this customer.'
            )
        else:
            flash_error(f'Could not delete customer: {error_msg}')

    return redirect(url_for('customer.index'))