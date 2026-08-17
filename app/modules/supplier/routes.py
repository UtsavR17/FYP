from flask import render_template, request, redirect, url_for
from app.modules.supplier import bp
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
            supabase.table('Supplier')
            .select('*')
            .order('SupplierName')
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load suppliers: {str(e)}')
        all_records = []

    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in r.get('SupplierName', '').lower()
            or q in r.get('Email', '').lower()
            or q in r.get('Country', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/supplier/list.html',
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

        name_value    = form_data.get('SupplierName', '').strip()
        phone_value   = form_data.get('Phone', '').strip()
        email_value   = form_data.get('Email', '').strip()
        address_value = form_data.get('Address', '').strip()
        country_value = form_data.get('Country', '').strip()

        # Required field checks
        missing = required_fields(
            form_data,
            ['SupplierName', 'Phone', 'Email', 'Address', 'Country']
        )

        if 'SupplierName' in missing:
            errors['SupplierName'] = 'Supplier name is required.'
        elif len(name_value) > 100:
            errors['SupplierName'] = 'Supplier name must not exceed 100 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone_value) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email_value) > 100:
            errors['Email'] = 'Email address must not exceed 100 characters.'
        elif not is_valid_email(email_value):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Address' in missing:
            errors['Address'] = 'Address is required.'
        elif len(address_value) > 255:
            errors['Address'] = 'Address must not exceed 255 characters.'

        if 'Country' in missing:
            errors['Country'] = 'Country is required.'
        elif len(country_value) > 100:
            errors['Country'] = 'Country must not exceed 100 characters.'

        if not errors:
            try:
                supabase.table('Supplier').insert({
                    'SupplierName': name_value,
                    'Phone':        phone_value,
                    'Email':        email_value,
                    'Address':      address_value,
                    'Country':      country_value,
                }).execute()
                flash_success(f'Supplier "{name_value}" was added successfully.')
                return redirect(url_for('supplier.index'))
            # except Exception as e:
            #     flash_error(f'Could not add supplier: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A supplier with this name already exists.')
                else:
                    flash_error(f'Could not add supplier: {error_msg}')

    return render_template(
        'modules/supplier/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit(supplier_id):
    try:
        result = (
            supabase.table('Supplier')
            .select('*')
            .eq('SupplierID', supplier_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Supplier ID {supplier_id} was not found.')
        return redirect(url_for('supplier.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        name_value    = form_data.get('SupplierName', '').strip()
        phone_value   = form_data.get('Phone', '').strip()
        email_value   = form_data.get('Email', '').strip()
        address_value = form_data.get('Address', '').strip()
        country_value = form_data.get('Country', '').strip()

        missing = required_fields(
            form_data,
            ['SupplierName', 'Phone', 'Email', 'Address', 'Country']
        )

        if 'SupplierName' in missing:
            errors['SupplierName'] = 'Supplier name is required.'
        elif len(name_value) > 100:
            errors['SupplierName'] = 'Supplier name must not exceed 100 characters.'

        if 'Phone' in missing:
            errors['Phone'] = 'Phone number is required.'
        elif len(phone_value) > 20:
            errors['Phone'] = 'Phone number must not exceed 20 characters.'

        if 'Email' in missing:
            errors['Email'] = 'Email address is required.'
        elif len(email_value) > 100:
            errors['Email'] = 'Email address must not exceed 100 characters.'
        elif not is_valid_email(email_value):
            errors['Email'] = 'Please enter a valid email address.'

        if 'Address' in missing:
            errors['Address'] = 'Address is required.'
        elif len(address_value) > 255:
            errors['Address'] = 'Address must not exceed 255 characters.'

        if 'Country' in missing:
            errors['Country'] = 'Country is required.'
        elif len(country_value) > 100:
            errors['Country'] = 'Country must not exceed 100 characters.'

        if not errors:
            try:
                supabase.table('Supplier').update({
                    'SupplierName': name_value,
                    'Phone':        phone_value,
                    'Email':        email_value,
                    'Address':      address_value,
                    'Country':      country_value,
                }).eq('SupplierID', supplier_id).execute()
                flash_success(f'Supplier "{name_value}" was updated successfully.')
                return redirect(url_for('supplier.index'))
            # except Exception as e:
            #     flash_error(f'Could not update supplier: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A supplier with this name already exists.')
                else:
                    flash_error(f'Could not update supplier: {error_msg}')

    return render_template(
        'modules/supplier/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete(supplier_id):
    try:
        result = (
            supabase.table('Supplier')
            .select('SupplierName')
            .eq('SupplierID', supplier_id)
            .single()
            .execute()
        )
        name_value = result.data.get('SupplierName', f'ID {supplier_id}')
    except Exception:
        name_value = f'ID {supplier_id}'

    try:
        supabase.table('Supplier').delete().eq('SupplierID', supplier_id).execute()
        flash_success(f'Supplier "{name_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{name_value}" because it is referenced '
                f'by one or more purchase orders.'
            )
        else:
            flash_error(f'Could not delete supplier: {error_msg}')

    return redirect(url_for('supplier.index'))