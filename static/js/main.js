/**
 * Chess Tournament Management System - Client Side Logic
 */

document.addEventListener('DOMContentLoaded', function() {
    // 1. Table Quick Filter
    const searchInputs = document.querySelectorAll('.table-search-input');
    searchInputs.forEach(input => {
        input.addEventListener('input', function() {
            const targetTableId = this.getAttribute('data-target-table');
            const targetTable = document.getElementById(targetTableId);
            if (!targetTable) return;

            const filter = this.value.toLowerCase();
            const rows = targetTable.querySelectorAll('tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    });

    // 2. AJAX Match Result Update for Arbiters
    const ajaxResultSelects = document.querySelectorAll('.ajax-result-select');
    ajaxResultSelects.forEach(select => {
        select.addEventListener('change', function() {
            const form = this.closest('form');
            if (!form) return;

            const badge = form.querySelector('.save-status-badge');
            if (badge) {
                badge.innerHTML = '<span class="spinner-border spinner-border-sm text-warning"></span> Saving...';
                badge.className = 'save-status-badge text-warning small ms-2';
            }

            const formData = new FormData(form);
            const url = form.getAttribute('action');

            fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (badge) {
                        badge.innerHTML = '<i class="bi bi-check2-circle text-success"></i> Saved';
                        badge.className = 'save-status-badge text-success small ms-2';
                        setTimeout(() => {
                            badge.innerHTML = '';
                        }, 2500);
                    }
                }
            })
            .catch(error => {
                console.error('Error saving result:', error);
                if (badge) {
                    badge.innerHTML = '<i class="bi bi-exclamation-circle text-danger"></i> Failed';
                    badge.className = 'save-status-badge text-danger small ms-2';
                }
            });
        });
    });

    // 3. Share Tournament Link Button
    const shareBtns = document.querySelectorAll('.btn-share-tournament');
    shareBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            navigator.clipboard.writeText(window.location.href).then(() => {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="bi bi-check2 me-1"></i> Copied!';
                setTimeout(() => {
                    this.innerHTML = originalText;
                }, 2000);
            });
        });
    });
});
