/* =============================================================================
   admin.js — Shared JavaScript for the Motorbike Admin Panel
   ============================================================================= */

console.log('[MotoAdmin] admin.js loaded successfully.');

document.addEventListener('DOMContentLoaded', function () {

    // -------------------------------------------------------------------------
    // SIDEBAR TOGGLE (Fix Phase 7, ISS-22)
    // Desktop (992px and wider): the hamburger collapses or expands the sidebar;
    // the choice is kept in localStorage ('adminSidebar') and applied before the
    // first paint by the inline script in admin_layout.html.
    // Smaller screens: an off-canvas drawer, closed by default, with a backdrop.
    // It closes on Escape, on a backdrop click and when a link is chosen; focus
    // moves into it when it opens and back to the button when it closes.
    // -------------------------------------------------------------------------
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar       = document.getElementById('sidebar');
    const overlay       = document.getElementById('sidebarOverlay');
    const rootEl        = document.documentElement;
    const desktopQuery  = window.matchMedia('(min-width: 992px)');
    const STORAGE_KEY   = 'adminSidebar';

    function isDesktop() {
        return desktopQuery.matches;
    }

    function drawerIsOpen() {
        return !!sidebar && sidebar.classList.contains('open');
    }

    function syncToggleState() {
        if (!sidebarToggle) return;
        const expanded = isDesktop()
            ? !rootEl.classList.contains('sidebar-collapsed')
            : drawerIsOpen();
        sidebarToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }

    function rememberCollapsed(collapsed) {
        try {
            window.localStorage.setItem(STORAGE_KEY, collapsed ? 'collapsed' : 'open');
        } catch (e) { /* storage unavailable: the state lasts for this page only */ }
    }

    // Charts and other width-dependent widgets re-measure after the slide.
    function announceResize() {
        window.setTimeout(function () {
            window.dispatchEvent(new Event('resize'));
        }, 250);
    }

    function focusables() {
        return sidebar
            ? Array.from(sidebar.querySelectorAll('a[href], button:not([disabled])'))
            : [];
    }

    function openSidebar() {
        if (!sidebar) return;
        sidebar.classList.add('open');
        if (overlay) {
            overlay.classList.add('active');
        }
        document.body.style.overflow = 'hidden';
        syncToggleState();
        const first = sidebar.querySelector('.nav-link.active') || focusables()[0];
        if (first) {
            window.setTimeout(function () { first.focus(); }, 50);
        }
    }

    function closeSidebar(returnFocus) {
        if (!sidebar) return;
        const wasOpen = drawerIsOpen();
        sidebar.classList.remove('open');
        if (overlay) {
            overlay.classList.remove('active');
        }
        document.body.style.overflow = '';
        syncToggleState();
        if (wasOpen && returnFocus && sidebarToggle) {
            sidebarToggle.focus();
        }
    }

    function toggleDesktop() {
        const collapsed = rootEl.classList.toggle('sidebar-collapsed');
        rememberCollapsed(collapsed);
        syncToggleState();
        announceResize();
    }

    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            if (isDesktop()) {
                toggleDesktop();
            } else if (drawerIsOpen()) {
                closeSidebar(true);
            } else {
                openSidebar();
            }
        });

        // Choosing a link in the drawer closes it (the page then navigates).
        sidebar.addEventListener('click', function (e) {
            if (!isDesktop() && e.target.closest('a[href]')) {
                closeSidebar(false);
            }
        });

        // Keep keyboard focus inside the open drawer.
        sidebar.addEventListener('keydown', function (e) {
            if (e.key !== 'Tab' || isDesktop() || !drawerIsOpen()) return;
            const items = focusables();
            if (!items.length) return;
            const first = items[0];
            const last = items[items.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });

        // Crossing the 992px breakpoint: drop the drawer state, keep the desktop choice.
        desktopQuery.addEventListener('change', function () {
            closeSidebar(false);
            if (isDesktop()) {
                let stored = null;
                try { stored = window.localStorage.getItem(STORAGE_KEY); } catch (e) { stored = null; }
                rootEl.classList.toggle('sidebar-collapsed', stored === 'collapsed');
            } else {
                rootEl.classList.remove('sidebar-collapsed');
            }
            syncToggleState();
        });

        syncToggleState();
    }

    if (overlay) {
        overlay.addEventListener('click', function () { closeSidebar(true); });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && drawerIsOpen()) {
            closeSidebar(true);
        }
    });

    // -------------------------------------------------------------------------
    // AUTO-DISMISS FLASH ALERTS after 5 seconds
    // Only success and info messages hide themselves; errors (danger) and
    // warnings stay until the user closes them, so they can always be read.
    // -------------------------------------------------------------------------
    const alerts = document.querySelectorAll('.flash-container .alert-success, .flash-container .alert-info');
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
            const detailsText    = triggerButton.getAttribute('data-delete-details');
            const detailsPara    = document.getElementById('deleteModalDetails');

            if (modalForm)      { modalForm.action          = deleteUrl  || ''; }
            if (recordNameSpan) { recordNameSpan.textContent = recordName || ''; }
            if (detailsPara) {
                detailsPara.textContent = detailsText || '';
                detailsPara.hidden      = !detailsText;
            }

            console.log('[MotoAdmin] Delete modal opened for:', recordName, '| URL:', deleteUrl);
        });
        console.log('[MotoAdmin] Delete modal listener attached.');
    }




        // -------------------------------------------------------------------------
    // RECEIVE FORM: Mode toggle between existing stock and new stock
    // Toggles visibility of the two receiving sections when radio buttons change.
    // Since Task 48 the radios are only rendered for legacy items (no supplier
    // catalogue brand); otherwise the page offers a single method.
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

    // -------------------------------------------------------------------------
    // MARKUP HELPER — fills a selling-price input from base price + chosen %.
    // Used on the PO receive forms. Config via data attributes:
    //   #markup-percent  data-base="<buying price>"  data-target="<input id>"
    // "Custom" (empty value) leaves the target untouched.
    // -------------------------------------------------------------------------
    const markupSelect = document.getElementById('markup-percent');
    if (markupSelect) {
        const markupTarget = document.getElementById(markupSelect.dataset.target);
        const markupBase   = parseFloat(markupSelect.dataset.base);
        if (markupTarget && !isNaN(markupBase)) {
            markupSelect.addEventListener('change', function () {
                const pct = parseFloat(this.value);
                if (isNaN(pct)) return;
                markupTarget.value = (markupBase * (1 + pct / 100)).toFixed(2);
            });
        }
    }



});


/* ---------------------------------------------------------------------------
   Bootstrap tooltips (Task 40). Only elements that opt in with
   data-bs-toggle="tooltip" are affected; their title attribute is the
   fallback when JavaScript is unavailable.
   --------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', function () {
    if (!window.bootstrap || !bootstrap.Tooltip) {
        return;
    }
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        bootstrap.Tooltip.getOrCreateInstance(el);
    });
});


/* ---------------------------------------------------------------------------
   Product image inputs (Task 49): refuse a file over data-max-bytes before
   the form is sent, so a large photo does not hit the request size limit.
   The server validates size, type and content again.
   --------------------------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input[type="file"][data-max-bytes]').forEach(function (input) {
        const maxBytes = parseInt(input.dataset.maxBytes, 10);
        const feedback = input.parentElement.querySelector('[data-image-error]');
        input.addEventListener('change', function () {
            const file = input.files && input.files[0];
            if (file && maxBytes && file.size > maxBytes) {
                input.value = '';
                input.classList.add('is-invalid');
                if (feedback) {
                    feedback.textContent = 'The image must be 2 MB or smaller.';
                }
            } else {
                input.classList.remove('is-invalid');
            }
        });
    });
});
