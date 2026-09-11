/* =============================================================================
   admin.js — Shared JavaScript for the Motorbike Admin Panel
   ============================================================================= */

console.log('[MotoAdmin] admin.js loaded successfully.');

document.addEventListener('DOMContentLoaded', function () {

    // -------------------------------------------------------------------------
    // SIDEBAR TOGGLE (mobile)
    // -------------------------------------------------------------------------
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar       = document.getElementById('sidebar');
    const overlay       = document.getElementById('sidebarOverlay');

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.add('open');
        if (overlay) {
            overlay.classList.add('active');
        }
        document.body.style.overflow = 'hidden';
        console.log('[MotoAdmin] Sidebar opened.');
    }

    function closeSidebar() {
        if (!sidebar) return;
        sidebar.classList.remove('open');
        if (overlay) {
            overlay.classList.remove('active');
        }
        document.body.style.overflow = '';
        console.log('[MotoAdmin] Sidebar closed.');
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            if (sidebar.classList.contains('open')) {
                closeSidebar();
            } else {
                openSidebar();
            }
        });
        console.log('[MotoAdmin] Sidebar toggle listener attached.');
    } else {
        console.warn('[MotoAdmin] sidebarToggle element not found.');
    }

    if (overlay) {
        overlay.addEventListener('click', closeSidebar);
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('open')) {
            closeSidebar();
        }
    });

    // -------------------------------------------------------------------------
    // AUTO-DISMISS FLASH ALERTS after 5 seconds
    // -------------------------------------------------------------------------
    const alerts = document.querySelectorAll('.flash-container .alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const instance = bootstrap.Alert.getOrCreateInstance(alert);
            if (instance) {
                instance.close();
            }
        }, 5000);
    });


    // -------------------------------------------------------------------------
    // DELETE MODAL — Dynamic population
    //
    // When a delete button triggers #deleteModal, this listener:
    //   1. Reads data-delete-url from the triggering button.
    //   2. Reads data-record-name from the triggering button.
    //   3. Sets the modal form's action to the delete URL.
    //   4. Sets the record name display text inside the modal.
    //
    // Every delete button in every CRUD list view must have:
    //   data-bs-toggle="modal"
    //   data-bs-target="#deleteModal"
    //   data-delete-url="{{ url_for('module.delete', id=row.ID) }}"
    //   data-record-name="{{ row.FieldName }}"
    // -------------------------------------------------------------------------
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', function (event) {
            const triggerButton  = event.relatedTarget;
            const deleteUrl      = triggerButton.getAttribute('data-delete-url');
            const recordName     = triggerButton.getAttribute('data-record-name');

            const modalForm      = document.getElementById('deleteModalForm');
            const recordNameSpan = document.getElementById('deleteModalRecordName');

            if (modalForm)      { modalForm.action          = deleteUrl  || ''; }
            if (recordNameSpan) { recordNameSpan.textContent = recordName || ''; }

            console.log('[MotoAdmin] Delete modal opened for:', recordName, '| URL:', deleteUrl);
        });
        console.log('[MotoAdmin] Delete modal listener attached.');
    }




        // -------------------------------------------------------------------------
    // RECEIVE FORM: Mode toggle between existing stock and new stock
    // Toggles visibility of the two receiving sections when radio buttons change.
    // -------------------------------------------------------------------------
    const modeExisting = document.getElementById('mode-existing');
    const modeNew      = document.getElementById('mode-new');
    const secExisting  = document.getElementById('section-existing');
    const secNew       = document.getElementById('section-new');
    const labelExisting = document.getElementById('mode-existing-label');
    const labelNew      = document.getElementById('mode-new-label');

    function applyReceiveMode(mode) {
        if (!secExisting || !secNew) return;
        if (mode === 'existing') {
            secExisting.style.display = '';
            secNew.style.display      = 'none';
            if (labelExisting) labelExisting.classList.add('active');
            if (labelNew)      labelNew.classList.remove('active');
        } else {
            secExisting.style.display = 'none';
            secNew.style.display      = '';
            if (labelExisting) labelExisting.classList.remove('active');
            if (labelNew)      labelNew.classList.add('active');
        }
        console.log('[MotoAdmin] Receive mode set to:', mode);
    }

    if (modeExisting && modeNew) {
        modeExisting.addEventListener('change', function () {
            applyReceiveMode('existing');
        });
        modeNew.addEventListener('change', function () {
            applyReceiveMode('new');
        });
        // Apply initial state
        if (modeNew.checked) {
            applyReceiveMode('new');
        } else {
            applyReceiveMode('existing');
        }
        console.log('[MotoAdmin] Receive form mode toggle initialised.');
    }



    // -------------------------------------------------------------------------
    // PAYMENT FORM — Reference type toggle (Sale / Appointment)
    // -------------------------------------------------------------------------
    const refTypeSale  = document.getElementById('ref-type-sale');
    const refTypeAppt  = document.getElementById('ref-type-appt');
    const refLabelSale = document.getElementById('ref-label-sale');
    const refLabelAppt = document.getElementById('ref-label-appt');
    const sectionPaySale = document.getElementById('section-sale');
    const sectionPayAppt = document.getElementById('section-appt');

    function applyPaymentRefMode(mode) {
        if (!sectionPaySale || !sectionPayAppt) return;
        if (mode === 'sale') {
            sectionPaySale.style.display = '';
            sectionPayAppt.style.display = 'none';
            if (refLabelSale) refLabelSale.classList.add('active');
            if (refLabelAppt) refLabelAppt.classList.remove('active');
        } else {
            sectionPaySale.style.display = 'none';
            sectionPayAppt.style.display = '';
            if (refLabelSale) refLabelSale.classList.remove('active');
            if (refLabelAppt) refLabelAppt.classList.add('active');
        }
        console.log('[MotoAdmin] Payment reference mode set to:', mode);
    }

    if (refTypeSale && refTypeAppt) {
        refTypeSale.addEventListener('change', function () {
            applyPaymentRefMode('sale');
        });
        refTypeAppt.addEventListener('change', function () {
            applyPaymentRefMode('appointment');
        });
        applyPaymentRefMode(refTypeSale.checked ? 'sale' : 'appointment');
        console.log('[MotoAdmin] Payment reference toggle initialised.');
    }


});


