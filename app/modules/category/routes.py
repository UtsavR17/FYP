from flask import render_template, request, redirect, url_for
from app.modules.category import bp
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
        result = supabase.table('Category').select('*').order('CAT_desc').execute()
        all_records = result.data or []
    except Exception as e:
        flash_error(f'Could not load categories: {str(e)}')
        all_records = []

    if search_query:
        all_records = [
            r for r in all_records
            if search_query.lower() in r.get('CAT_desc', '').lower()
        ]

    pagination = paginate(all_records, page, per_page=10)

    return render_template(
        'modules/category/list.html',
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
        desc_value = form_data.get('CAT_desc', '').strip()

        missing = required_fields(form_data, ['CAT_desc'])
        if missing:
            errors['CAT_desc'] = 'Category description is required.'
        elif len(desc_value) > 20:
            errors['CAT_desc'] = 'Category description must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Category').insert(
                    {'CAT_desc': desc_value}
                ).execute()
                flash_success(f'Category "{desc_value}" was added successfully.')
                return redirect(url_for('category.index'))
            # except Exception as e:
            #     flash_error(f'Could not add category: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A category with this name already exists.')
                else:
                    flash_error(f'Could not add category: {error_msg}')

    return render_template(
        'modules/category/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=False
    )


@bp.route('/edit/<int:cat_id>', methods=['GET', 'POST'])
@login_required
def edit(cat_id):
    try:
        result = (
            supabase.table('Category')
            .select('*')
            .eq('CAT_ID', cat_id)
            .single()
            .execute()
        )
        record = result.data
    except Exception:
        flash_error(f'Category ID {cat_id} was not found.')
        return redirect(url_for('category.index'))

    errors = {}
    form_data = record.copy()

    if request.method == 'POST':
        form_data = request.form.to_dict()
        desc_value = form_data.get('CAT_desc', '').strip()

        missing = required_fields(form_data, ['CAT_desc'])
        if missing:
            errors['CAT_desc'] = 'Category description is required.'
        elif len(desc_value) > 20:
            errors['CAT_desc'] = 'Category description must not exceed 20 characters.'

        if not errors:
            try:
                supabase.table('Category').update(
                    {'CAT_desc': desc_value}
                ).eq('CAT_ID', cat_id).execute()
                flash_success(f'Category updated to "{desc_value}" successfully.')
                return redirect(url_for('category.index'))
            # except Exception as e:
            #     flash_error(f'Could not update category: {str(e)}')

            except Exception as e:
                error_msg = str(e)
                if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                    flash_error(f'A category with this name already exists.')
                else:
                    flash_error(f'Could not update category: {error_msg}')

    return render_template(
        'modules/category/form.html',
        form_data=form_data,
        errors=errors,
        is_edit=True,
        record=record
    )


@bp.route('/delete/<int:cat_id>', methods=['POST'])
@login_required
def delete(cat_id):
    try:
        result = (
            supabase.table('Category')
            .select('CAT_desc')
            .eq('CAT_ID', cat_id)
            .single()
            .execute()
        )
        desc_value = result.data.get('CAT_desc', f'ID {cat_id}')
    except Exception:
        desc_value = f'ID {cat_id}'

    try:
        supabase.table('Category').delete().eq('CAT_ID', cat_id).execute()
        flash_success(f'Category "{desc_value}" was deleted successfully.')
    except Exception as e:
        error_msg = str(e)
        if 'foreign key' in error_msg.lower() or 'violates' in error_msg.lower():
            flash_error(
                f'Cannot delete "{desc_value}" because it is used by one or more spare parts.'
            )
        else:
            flash_error(f'Could not delete category: {error_msg}')

    return redirect(url_for('category.index'))