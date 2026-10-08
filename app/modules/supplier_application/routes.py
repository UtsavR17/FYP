"""
Supplier Applications (Task 46).

Applicants submit company details and a BRN document on the Client Side. Staff review them
here: approve (the database creates the Supplier and links the applicant's login, so they sign
in to the Supplier Portal with their shop email and password) or reject with a reason. There
are no create, edit or delete routes. The storage path and audit columns are never rendered.
"""
from datetime import datetime, timedelta, timezone

from flask import render_template, request, redirect, url_for
from app.modules.supplier_application import bp
from app.auth.decorators import login_required
from app.supabase_client import supabase
from app.utils.pagination import paginate
from app.utils.flash_messages import flash_success, flash_error


# Mauritius is UTC+4 all year (no DST).
MU_TZ = timezone(timedelta(hours=4))

STATUS_PENDING  = 'Pending'
STATUS_APPROVED = 'Approved'
STATUS_REJECTED = 'Rejected'
STATUSES = [STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED]
STATUS_ALL = 'all'
DEFAULT_STATUS = STATUS_PENDING

STATUS_CSS = {STATUS_PENDING: 'pending', STATUS_APPROVED: 'approved', STATUS_REJECTED: 'rejected'}

BUCKET = 'supplier-applications'
SIGNED_URL_SECONDS = 300

REASON_MIN = 5
REASON_MAX = 255
SEARCH_MAX = 60
PAGE_SIZE = 1000

# Explicit column lists: no audit columns. DocumentPath is read only on the view page to sign
# a URL and is never passed to a template.
LIST_COLUMNS = 'ApplicationID, CompanyName, ContactPerson, Email, Country, BRN, Status, SubmittedAt'
VIEW_COLUMNS = (
    'ApplicationID, CompanyName, ContactPerson, Phone, Email, Address, Country, BRN, '
    'ProductsDescription, DocumentPath, Status, RejectionReason, Supplier_SupplierID, '
    'SubmittedAt, ReviewedAt'
)

APPROVED_MSG = (
    "Supplier created and linked to the applicant's login. They can sign in to the Supplier "
    'Portal with their shop email and password. Add their products on the Supplier page.'
)
ALREADY_REVIEWED_MSG = 'This application has already been reviewed.'

APPROVE_ERRORS = {
    'ALREADY_SUPPLIER': 'This login already belongs to a supplier.',
    'SUPPLIER_EXISTS': ('A supplier with this company name already exists. Reject this application '
                        'or contact the applicant.'),
    'NOT_PENDING': ALREADY_REVIEWED_MSG,
    'APPLICANT_LOGIN_MISSING': "The applicant's account no longer exists. Reject this application.",
    'APPLICATION_NOT_FOUND': 'This application was not found. It may have been removed.',
    'NOT_STAFF': 'Only staff members can review applications. Sign in with a staff account.',
}
REJECT_ERRORS = {
    'INVALID_REASON': f'Enter a reason of {REASON_MIN} to {REASON_MAX} characters.',
    'NOT_PENDING': ALREADY_REVIEWED_MSG,
    'APPLICATION_NOT_FOUND': 'This application was not found. It may have been removed.',
    'NOT_STAFF': 'Only staff members can review applications. Sign in with a staff account.',
}


# -- Pure helpers (unit tested) ------------------------------------------------

def clean_status_filter(value):
    """Whitelisted status filter: Pending by default, 'all' or one of STATUSES."""
    value = (value or '').strip()
    if value == STATUS_ALL or value in STATUSES:
        return value
    return DEFAULT_STATUS


def clean_search(value):
    """Search text: trimmed and capped; only ever compared in Python, never sent as a filter."""
    return (value or '').strip()[:SEARCH_MAX]


def matches_search(row, query):
    """Company, contact person, email or BRN contains the query (case-insensitive)."""
    needle = query.lower()
    return any(
        needle in str(row.get(field) or '').lower()
        for field in ('CompanyName', 'ContactPerson', 'Email', 'BRN')
    )


def reason_error(reason):
    """Why a rejection reason is not acceptable, or None."""
    length = len(reason or '')
    if length < REASON_MIN or length > REASON_MAX:
        return f'Enter a reason of {REASON_MIN} to {REASON_MAX} characters.'
    return None


def map_rpc_error(error_text, table):
    """Friendly message for a function error, from the given token table."""
    text = error_text or ''
    for token, message in table.items():
        if token in text:
            return message
    return 'Could not complete the review. Please try again.'


def to_mauritius_time(value):
    """ISO timestamp (any offset; naive = UTC) -> 'YYYY-MM-DD HH:MM' in Mauritius time."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return str(value)[:16].replace('T', ' ')
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MU_TZ).strftime('%Y-%m-%d %H:%M')


# -- Data helpers ------------------------------------------------------------

def _fetch_applications(status_filter):
    """All applications for the (whitelisted) filter, newest first, paged past the row cap."""
    rows = []
    start = 0
    while True:
        query = supabase.table('Supplier_Application').select(LIST_COLUMNS)
        if status_filter in STATUSES:
            query = query.eq('Status', status_filter)
        batch = (
            query.order('SubmittedAt', desc=True)
            .order('ApplicationID', desc=True)
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        ).data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def _get_application(application_id):
    rows = (
        supabase.table('Supplier_Application')
        .select(VIEW_COLUMNS)
        .eq('ApplicationID', application_id)
        .limit(1)
        .execute()
    ).data or []
    return rows[0] if rows else None


def _signed_document_url(path):
    """A fresh short-lived signed URL for the BRN document, or None when it cannot be made."""
    if not path:
        return None
    try:
        result = supabase.storage.from_(BUCKET).create_signed_url(path, SIGNED_URL_SECONDS)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    return result.get('signedURL') or result.get('signedUrl') or None


def _view_url(application_id):
    return url_for('supplier_application.view', application_id=application_id)


def _load_pending_or_redirect(application_id):
    """(application, None) for a Pending application, else (None, redirect response)."""
    try:
        application = _get_application(application_id)
    except Exception as e:
        flash_error(f'Could not load the application: {str(e)}')
        return None, redirect(url_for('supplier_application.index'))
    if application is None:
        flash_error(f'Application ID {application_id} was not found.')
        return None, redirect(url_for('supplier_application.index'))
    if application.get('Status') != STATUS_PENDING:
        flash_error(ALREADY_REVIEWED_MSG)
        return None, redirect(_view_url(application_id))
    return application, None


# -- Routes ---------------------------------------------------------------------

@bp.route('/')
@login_required
def index():
    status_filter = clean_status_filter(request.args.get('status'))
    search_query = clean_search(request.args.get('q'))
    page = request.args.get('page', 1, type=int)

    try:
        records = _fetch_applications(status_filter)
    except Exception as e:
        flash_error(f'Could not load supplier applications: {str(e)}')
        records = []

    if search_query:
        records = [r for r in records if matches_search(r, search_query)]

    for r in records:
        r['_submitted'] = to_mauritius_time(r.get('SubmittedAt'))
        r['_status_css'] = STATUS_CSS.get(r.get('Status'), 'pending')

    pagination = paginate(records, page, per_page=10)

    return render_template(
        'modules/supplier_application/list.html',
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        statuses=STATUSES,
        status_all=STATUS_ALL,
    )


@bp.route('/view/<int:application_id>')
@login_required
def view(application_id):
    try:
        application = _get_application(application_id)
    except Exception as e:
        flash_error(f'Could not load the application: {str(e)}')
        return redirect(url_for('supplier_application.index'))
    if application is None:
        flash_error(f'Application ID {application_id} was not found.')
        return redirect(url_for('supplier_application.index'))

    # The storage path is used only to sign a URL; it never reaches the template.
    document_path = application.pop('DocumentPath', None)
    has_document = bool(document_path)
    document_url = _signed_document_url(document_path)

    status = application.get('Status')
    return render_template(
        'modules/supplier_application/view.html',
        application=application,
        status_css=STATUS_CSS.get(status, 'pending'),
        is_pending=status == STATUS_PENDING,
        submitted_at=to_mauritius_time(application.get('SubmittedAt')),
        reviewed_at=to_mauritius_time(application.get('ReviewedAt')),
        has_document=has_document,
        document_url=document_url,
        signed_url_minutes=SIGNED_URL_SECONDS // 60,
        reason_min=REASON_MIN,
        reason_max=REASON_MAX,
    )


@bp.route('/<int:application_id>/approve', methods=['POST'])
@login_required
def approve(application_id):
    application, redir = _load_pending_or_redirect(application_id)
    if redir:
        return redir

    try:
        result = supabase.rpc('approve_supplier_application',
                              {'p_application_id': application_id}).execute()
    except Exception as e:
        flash_error(map_rpc_error(str(e), APPROVE_ERRORS))
        return redirect(_view_url(application_id))

    try:
        supplier_id = int(result.data)
    except (TypeError, ValueError):
        supplier_id = None
    flash_success(APPROVED_MSG)
    if supplier_id and supplier_id > 0:
        return redirect(url_for('supplier.view', supplier_id=supplier_id))
    return redirect(_view_url(application_id))


@bp.route('/<int:application_id>/reject', methods=['POST'])
@login_required
def reject(application_id):
    reason = (request.form.get('reason') or '').strip()
    error = reason_error(reason)
    if error:
        flash_error(error)
        return redirect(_view_url(application_id))

    application, redir = _load_pending_or_redirect(application_id)
    if redir:
        return redir

    try:
        supabase.rpc('reject_supplier_application',
                     {'p_application_id': application_id, 'p_reason': reason}).execute()
    except Exception as e:
        flash_error(map_rpc_error(str(e), REJECT_ERRORS))
        return redirect(_view_url(application_id))

    flash_success(
        f'Application from "{application.get("CompanyName")}" was rejected. '
        'The applicant sees the reason on their account and may apply again.'
    )
    return redirect(_view_url(application_id))
