from flask import render_template, request, redirect, url_for
from app.modules.compatibility import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error, flash_warning
from app.utils.validators import required_fields
from app.utils.text import norm


DUPLICATE_MSG = 'A compatibility record for this stock item, model and year range already exists.'
NONE_CREATED_MSG = (
    'No compatibility records were created because every selected combination already exists.'
)
CHECK_FAILED_MSG = 'Could not check the existing compatibility records. Please try again.'


def _combo_key(model_no, year_from, year_to):
    """Comparison key; Python compares None == None, so blank years equal blank years."""
    return (model_no, year_from, year_to)


def _existing_combos(stock_id, exclude_com_id=None):
    """
    {(model, year_from, year_to)} already recorded for this stock item, leaving
    out exclude_com_id. Raises on a database error so nothing is inserted blind.
    """
    rows = (
        supabase.table('Compatibility')
        .select('Com_ID, Model_Model_No, Year_From, Year_To')
        .eq('Stock_Stock_ID', stock_id)
        .execute()
    ).data or []
    return {
        _combo_key(r.get('Model_Model_No'), r.get('Year_From'), r.get('Year_To'))
        for r in rows if r.get('Com_ID') != exclude_com_id
    }


def _years_text(year_from, year_to):
    if year_from is None and year_to is None:
        return 'any year'
    if year_to is None:
        return f'from {year_from}'
    if year_from is None:
        return f'up to {year_to}'
    return f'{year_from} to {year_to}'


def _is_unique_violation(error):
    text = str(error).lower()
    return '23505' in text or 'duplicate' in text or 'unique' in text


def _build_stock_label(sp_name, size, brand_name):
    """Build a human-readable label for a Stock record."""
    if size:
        return f"{sp_name} [{size}] \u2014 {brand_name}"
    return f"{sp_name} \u2014 {brand_name}"


def _get_form_options():
    """
    Fetch enriched dropdown options for the Compatibility Create and Edit forms.

    Stock options require three table lookups (Stock, Spare_Parts, Brand).
    Model options require two table lookups (Model, Brand).

    Returns:
        stock_options: list of (Stock_ID, enriched_label) tuples
        model_options: list of (Model_No, enriched_label) tuples
    """
    stock_options = []
    model_options = []
    brand_lookup = {}
    sp_lookup = {}

    # Brand lookup used by both Stock and Model labels
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
        pass

    # Spare Parts lookup for Stock labels
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
        pass

    # Build Stock options
    try:
        stock_result = (
            supabase.table('Stock')
            .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size')
            .order('Stock_ID')
            .execute()
        )
        for s in (stock_result.data or []):
            sp_name    = sp_lookup.get(s.get('Spare_Parts_SP_id'), 'Unknown Part')
            brand_name = brand_lookup.get(s.get('Brand_Brand_ID'), 'Unknown Brand')
            size       = s.get('Size') or ''
            label      = _build_stock_label(sp_name, size, brand_name)
            stock_options.append((s['Stock_ID'], label))
    except Exception:
        pass

    # Build Model options
    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .order('Description')
            .execute()
        )
        for m in (model_result.data or []):
            brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
            label      = f"{brand_name} \u2014 {m['Description']}"
            model_options.append((m['Model_No'], label))
    except Exception:
        pass

    return stock_options, model_options


def _validate_year(raw_value, field_label):
    """
    Validate an optional year field.

    Args:
        raw_value:   the raw string from request.form
        field_label: human-readable name for the error message

    Returns:
        (year_int_or_None, error_string_or_None)
    """
    value = (raw_value or '').strip()
    if not value:
        return None, None
    try:
        year = int(value)
        if year < 1900 or year > 2100:
            return None, f'{field_label} must be a valid year between 1900 and 2100.'
        return year, None
    except ValueError:
        return None, f'{field_label} must be a valid 4-digit year number.'


@bp.route('/')
@login_required
def index():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    try:
        result = (
            supabase.table('Compatibility')
            .select('*')
            .order('Com_ID', desc=True)
            .execute()
        )
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load compatibility records: {str(e)}')
        all_records = []

    # Build lookup dicts for enrichment
    brand_lookup = {}
    sp_lookup = {}
    stock_raw = []
    model_raw = []

    try:
        brand_result = (
            supabase.table('Brand').select('Brand_ID, Brand_Name').execute()
        )
        brand_lookup = {
            r['Brand_ID']: r['Brand_Name']
            for r in (brand_result.data or [])
        }
    except Exception:
        pass

    try:
        sp_result = (
            supabase.table('Spare_Parts').select('SP_id, SP_name').execute()
        )
        sp_lookup = {
            r['SP_id']: r['SP_name']
            for r in (sp_result.data or [])
        }
    except Exception:
        pass

    try:
        stock_result = (
            supabase.table('Stock')
            .select('Stock_ID, Spare_Parts_SP_id, Brand_Brand_ID, Size')
            .execute()
        )
        stock_raw = stock_result.data or []
    except Exception:
        pass

    try:
        model_result = (
            supabase.table('Model')
            .select('Model_No, Brand_Brand_ID, Description')
            .execute()
        )
        model_raw = model_result.data or []
    except Exception:
        pass

    stock_lookup = {}
    for s in stock_raw:
        sp_name    = sp_lookup.get(s.get('Spare_Parts_SP_id'), 'Unknown Part')
        brand_name = brand_lookup.get(s.get('Brand_Brand_ID'), 'Unknown Brand')
        size       = s.get('Size') or ''
        stock_lookup[s['Stock_ID']] = _build_stock_label(sp_name, size, brand_name)

    model_lookup = {}
    for m in model_raw:
        brand_name = brand_lookup.get(m.get('Brand_Brand_ID'), 'Unknown Brand')
        model_lookup[m['Model_No']] = f"{brand_name} \u2014 {m['Description']}"

    # Enrich each compatibility record
    for rec in all_records:
        rec['_stock_label'] = stock_lookup.get(
            rec.get('Stock_Stock_ID'), f"Stock ID {rec.get('Stock_Stock_ID')}"
        )
        rec['_model_label'] = model_lookup.get(
            rec.get('Model_Model_No'), f"Model ID {rec.get('Model_Model_No')}"
        )

    # Search across enriched fields and year values
    if search_query:
        q = search_query.lower()
        all_records = [
            r for r in all_records
            if q in norm(r.get('_stock_label'))
            or q in norm(r.get('_model_label'))
            or q in str(r.get('Year_From', '') or '')
            or q in str(r.get('Year_To', '') or '')
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/compatibility/list.html',
        pagination=pagination,
        search_query=search_query
    )


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form_data = {}
    errors = {}
    selected_model_nos = []
    stock_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data       = request.form.to_dict()
        selected_model_nos = request.form.getlist('Model_Model_No')

        stock_id_raw  = form_data.get('Stock_Stock_ID', '').strip()
        year_from_raw = form_data.get('Year_From', '')
        year_to_raw   = form_data.get('Year_To', '')

        stock_id = None
        if not stock_id_raw:
            errors['Stock_Stock_ID'] = 'Stock item is required.'
        else:
            try:
                stock_id = int(stock_id_raw)
            except ValueError:
                errors['Stock_Stock_ID'] = 'Please select a valid stock item.'

        if not selected_model_nos:
            errors['Model_Model_No'] = 'At least one motorbike model must be selected.'

        year_from, year_from_err = _validate_year(year_from_raw, 'Year From')
        year_to,   year_to_err   = _validate_year(year_to_raw,   'Year To')

        if year_from_err:
            errors['Year_From'] = year_from_err
        if year_to_err:
            errors['Year_To'] = year_to_err

        if (not year_from_err and not year_to_err
                and year_from is not None and year_to is not None
                and year_to < year_from):
            errors['Year_To'] = 'Year To must be equal to or after Year From.'

        existing = None
        if not errors:
            try:
                existing = _existing_combos(stock_id)
            except Exception:
                flash_error(CHECK_FAILED_MSG)

        if not errors and existing is not None:
            stock_label = dict(stock_options).get(stock_id, f'Stock ID {stock_id}')
            model_labels = dict(model_options)
            created, skipped, fail_count = 0, [], 0

            for model_no_str in dict.fromkeys(selected_model_nos):   # each model once
                try:
                    model_no = int(model_no_str)
                except ValueError:
                    fail_count += 1
                    continue
                label = (f"{stock_label} with {model_labels.get(model_no, f'Model ID {model_no}')} "
                         f"({_years_text(year_from, year_to)})")
                key = _combo_key(model_no, year_from, year_to)
                if key in existing:
                    skipped.append(label)          # never sent to the database
                    continue
                try:
                    supabase.table('Compatibility').insert({
                        'Stock_Stock_ID': stock_id,
                        'Model_Model_No': model_no,
                        'Year_From':      year_from,
                        'Year_To':        year_to,
                    }).execute()
                    existing.add(key)
                    created += 1
                except Exception as e:
                    if _is_unique_violation(e):    # created meanwhile by someone else
                        skipped.append(label)
                    else:
                        fail_count += 1

            if created:
                flash_success(f'{created} compatibility record{"s" if created != 1 else ""} added successfully.')
            elif skipped and not fail_count:
                flash_error(NONE_CREATED_MSG)
                errors['Model_Model_No'] = NONE_CREATED_MSG
            if skipped:
                flash_warning('Already exists: ' + '; '.join(skipped) + '.')
            if fail_count:
                flash_error(
                    f'{fail_count} record{"s" if fail_count != 1 else ""} '
                    f'could not be saved due to an unexpected error.'
                )

            if created:
                return redirect(url_for('compatibility.index'))

    return render_template(
        'modules/compatibility/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False,
        stock_options=stock_options,
        model_options=model_options,
        selected_model_nos=selected_model_nos
    )

@bp.route('/edit/<int:com_id>', methods=['GET', 'POST'])
@login_required
def edit(com_id):
    try:
        result = (
            supabase.table('Compatibility')
            .select('*')
            .eq('Com_ID', com_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Compatibility record ID {com_id} was not found.')
        return redirect(url_for('compatibility.index'))

    errors = {}
    form_data = record.copy()
    stock_options, model_options = _get_form_options()

    if request.method == 'POST':
        form_data = request.form.to_dict()

        stock_id_raw  = form_data.get('Stock_Stock_ID', '').strip()
        model_no_raw  = form_data.get('Model_Model_No', '').strip()
        year_from_raw = form_data.get('Year_From', '')
        year_to_raw   = form_data.get('Year_To', '')

        missing = required_fields(form_data, ['Stock_Stock_ID', 'Model_Model_No'])

        stock_id = None
        if 'Stock_Stock_ID' in missing:
            errors['Stock_Stock_ID'] = 'Stock item is required.'
        else:
            try:
                stock_id = int(stock_id_raw)
            except ValueError:
                errors['Stock_Stock_ID'] = 'Please select a valid stock item.'

        model_no = None
        if 'Model_Model_No' in missing:
            errors['Model_Model_No'] = 'Motorbike model is required.'
        else:
            try:
                model_no = int(model_no_raw)
            except ValueError:
                errors['Model_Model_No'] = 'Please select a valid model.'

        year_from, year_from_err = _validate_year(year_from_raw, 'Year From')
        year_to,   year_to_err   = _validate_year(year_to_raw,   'Year To')

        if year_from_err:
            errors['Year_From'] = year_from_err
        if year_to_err:
            errors['Year_To'] = year_to_err

        if (not year_from_err and not year_to_err
                and year_from is not None and year_to is not None
                and year_to < year_from):
            errors['Year_To'] = 'Year To must be equal to or after Year From.'

        if not errors:
            try:
                if _combo_key(model_no, year_from, year_to) in _existing_combos(stock_id, exclude_com_id=com_id):
                    errors['Model_Model_No'] = DUPLICATE_MSG
            except Exception:
                errors['Model_Model_No'] = CHECK_FAILED_MSG

        if not errors:
            try:
                supabase.table('Compatibility').update({
                    'Stock_Stock_ID': stock_id,
                    'Model_Model_No': model_no,
                    'Year_From':      year_from,
                    'Year_To':        year_to,
                }).eq('Com_ID', com_id).execute()
                flash_success(f'Compatibility record ID {com_id} was updated successfully.')
                return redirect(url_for('compatibility.index'))
            except Exception as e:
                if _is_unique_violation(e):
                    errors['Model_Model_No'] = DUPLICATE_MSG
                else:
                    flash_error(f'Could not update compatibility record: {str(e)}')

    return render_template(
        'modules/compatibility/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        stock_options=stock_options,
        model_options=model_options,
        selected_model_nos=[]
    )


@bp.route('/delete/<int:com_id>', methods=['POST'])
@login_required
def delete(com_id):
    try:
        supabase.table('Compatibility').delete().eq('Com_ID', com_id).execute()
        flash_success(f'Compatibility record ID {com_id} was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete compatibility record ID {com_id} because '
                f'it is referenced by other records.'
            )
        else:
            flash_error(f'Could not delete compatibility record: {error_msg}')

    return redirect(url_for('compatibility.index'))