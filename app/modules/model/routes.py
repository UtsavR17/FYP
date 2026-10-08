from flask import render_template, request, redirect, url_for
from app.modules.model import bp
from app.auth.decorators import login_required
from app.utils.flash_messages import flash_warning
from app.utils.product_images import (
    read_image_upload, upload_image, remove_image, display_url,
    UPLOAD_FAILED_MSG, SAVED_WITHOUT_IMAGE_MSG, MAX_IMAGE_BYTES,
)
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


def _attach_image(model_no, image):
    """
    Upload the image for a newly created model and store its URL. Returns
    False on any failure, after removing an uploaded object (no orphans).
    """
    if not model_no:
        return False
    try:
        url = upload_image('models', image)
    except Exception:
        return False
    try:
        updated = supabase.table('Model').update({'ImageUrl': url}).eq('Model_No', model_no).execute()
        if updated.data:
            return True
    except Exception:
        pass
    remove_image(url)
    return False


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
        model['_image_src'] = display_url(model.get('ImageUrl'))

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

        image, image_err = read_image_upload(request.files.get('image'))
        if image_err:
            errors['image'] = image_err

        if not errors:
            try:
                created = supabase.table('Model').insert({
                    'Brand_Brand_ID': brand_id,
                    'Description':    desc_value,
                }).execute()
                flash_success(f'Model "{desc_value}" was added successfully.')
                # The row is kept even if the image cannot be attached
                if image and not _attach_image((created.data or [{}])[0].get('Model_No'), image):
                    flash_warning(SAVED_WITHOUT_IMAGE_MSG)
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
        brand_options=brand_options,
        image_max_bytes=MAX_IMAGE_BYTES,
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

        image, image_err = read_image_upload(request.files.get('image'))
        if image_err:
            errors['image'] = image_err
        remove_requested = form_data.get('remove_image') == '1'

        # A new image is uploaded first; the row update then points at it
        new_image_url = None
        if not errors and image:
            try:
                new_image_url = upload_image('models', image)
            except Exception:
                errors['image'] = UPLOAD_FAILED_MSG

        if not errors:
            payload = {
                'Brand_Brand_ID': brand_id,
                'Description':    desc_value,
            }
            if new_image_url:
                payload['ImageUrl'] = new_image_url
            elif remove_requested:
                payload['ImageUrl'] = None
            try:
                updated = supabase.table('Model').update(payload).eq('Model_No', model_no).execute()
                if 'ImageUrl' in payload and not updated.data:
                    raise Exception('the record was not changed.')
            # except Exception as e:
            #     flash_error(f'Could not update model: {str(e)}')

            except Exception as e:
                remove_image(new_image_url)   # keep the old image, drop the new object
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A model with this name already exists.')
                else:
                    flash_error(f'Could not update model: {error_msg}')
            else:
                if 'ImageUrl' in payload and payload['ImageUrl'] != record.get('ImageUrl'):
                    remove_image(record.get('ImageUrl'))
                flash_success(f'Model "{desc_value}" was updated successfully.')
                return redirect(url_for('model.index'))

    return render_template(
        'modules/model/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record,
        brand_options=brand_options,
        current_image_src=display_url(record.get('ImageUrl')),
        image_max_bytes=MAX_IMAGE_BYTES,
    )


@bp.route('/delete/<int:model_no>', methods=['POST'])
@login_required
def delete(model_no):
    try:
        result = (
            supabase.table('Model')
            .select('Description, ImageUrl')
            .eq('Model_No', model_no)
            .single()
            .execute()
        )
        desc_value = result.data.get('Description', f'ID {model_no}')
        image_url = result.data.get('ImageUrl')
    except Exception:
        desc_value = f'ID {model_no}'
        image_url = None

    try:
        deleted = supabase.table('Model').delete().eq('Model_No', model_no).execute()
        flash_success(f'Model "{desc_value}" was deleted successfully.')
        if deleted.data:
            remove_image(image_url)   # best effort, after the row is gone
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