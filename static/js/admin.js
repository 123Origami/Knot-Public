// Admin Dashboard JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Shared admin navbar drawer behavior.
    const adminMobileBreakpoint = 1280;
    const hamburger = document.getElementById('hamburger');
    const navMenu = document.querySelector('.admin-navbar .nav-menu');

    if (hamburger && navMenu && !hamburger.hasAttribute('aria-expanded')) {
        let overlay = document.getElementById('adminNavOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'adminNavOverlay';
            overlay.className = 'admin-nav-overlay';
            document.body.appendChild(overlay);
        }

        const closeMobileMenu = () => {
            navMenu.classList.remove('active');
            overlay.classList.remove('active');
            document.body.style.overflow = '';
            hamburger.setAttribute('aria-expanded', 'false');
        };

        hamburger.setAttribute('aria-expanded', 'false');
        hamburger.addEventListener('click', function () {
            const isOpen = navMenu.classList.toggle('active');
            overlay.classList.toggle('active', isOpen);
            document.body.style.overflow = isOpen ? 'hidden' : '';
            hamburger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        overlay.addEventListener('click', closeMobileMenu);

        navMenu.querySelectorAll('a').forEach((link) => {
            link.addEventListener('click', function () {
                if (window.innerWidth <= adminMobileBreakpoint) {
                    closeMobileMenu();
                }
            });
        });

        window.addEventListener('resize', function () {
            if (window.innerWidth > adminMobileBreakpoint) {
                closeMobileMenu();
            }
        });

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && navMenu.classList.contains('active')) {
                closeMobileMenu();
            }
        });
    }

    // Tab switching functionality - only for buttons with data-tab attribute
    const tabButtons = document.querySelectorAll('.admin-nav-tab[data-tab]');
    const tabContents = document.querySelectorAll('.admin-tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Show corresponding content
            const tabId = this.getAttribute('data-tab');
            const targetContent = document.getElementById('tab-' + tabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // Filter buttons for user table (filter by admin request status)
    const filterButtons = document.querySelectorAll('.admin-nav-tab[data-filter]');
    filterButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remove active class from all filter buttons
            filterButtons.forEach(btn => btn.classList.remove('active'));
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Get the filter value
            const filterValue = this.getAttribute('data-filter');
            const tableRows = document.querySelectorAll('#tab-users tbody tr');
            
            tableRows.forEach(row => {
                // Get the admin request status from the 5th column (Admin Request)
                const adminRequestCell = row.querySelector('td:nth-child(5)');
                if (adminRequestCell) {
                    const statusText = adminRequestCell.textContent.toLowerCase();
                    let showRow = true;
                    
                    // Apply filter based on button clicked
                    if (filterValue === 'all') {
                        showRow = true;
                    } else if (filterValue === 'pending' && !statusText.includes('pending')) {
                        showRow = false;
                    } else if (filterValue === 'approved' && !statusText.includes('approved')) {
                        showRow = false;
                    } else if (filterValue === 'verified') {
                        // For "verified", show only users with active status
                        const statusCell = row.querySelector('td:nth-child(4)');
                        showRow = statusCell && statusCell.textContent.toLowerCase().includes('active');
                    }
                    
                    row.style.display = showRow ? '' : 'none';
                }
            });
        });
    });

    // Search functionality for users table
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const tableRows = document.querySelectorAll('tbody tr');

            tableRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Filter functionality
    const verificationFilter = document.getElementById('verificationFilter');
    const statusFilter = document.getElementById('statusFilter');

    function applyFilters() {
        const verificationValue = verificationFilter ? verificationFilter.value : '';
        const statusValue = statusFilter ? statusFilter.value : '';
        const tableRows = document.querySelectorAll('tbody tr');

        tableRows.forEach(row => {
            let showRow = true;

            // Verification level filter
            if (verificationValue) {
                const verificationCell = row.querySelector('td:nth-child(5)'); // Verification column
                if (verificationCell) {
                    const verificationText = verificationCell.textContent.toLowerCase();
                    if (verificationValue === '0' && !verificationText.includes('unverified')) showRow = false;
                    if (verificationValue === '1' && !verificationText.includes('email')) showRow = false;
                    if (verificationValue === '2' && !verificationText.includes('phone')) showRow = false;
                    if (verificationValue === '3' && !verificationText.includes('id')) showRow = false;
                }
            }

            // Status filter
            if (statusValue) {
                const statusCell = row.querySelector('td:nth-child(6)'); // Account status column
                if (statusCell) {
                    const statusText = statusCell.textContent.toLowerCase();
                    if (statusValue === 'active' && !statusText.includes('active')) showRow = false;
                    if (statusValue === 'inactive' && !statusText.includes('inactive')) showRow = false;
                    if (statusValue === 'pending' && !statusText.includes('pending')) showRow = false;
                    if (statusValue === 'approved' && !statusText.includes('approved')) showRow = false;
                }
            }

            row.style.display = showRow ? '' : 'none';
        });
    }

    if (verificationFilter) {
        verificationFilter.addEventListener('change', applyFilters);
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', applyFilters);
    }

    // View toggle for bookings (List/Calendar)
    const listViewBtn = document.getElementById('listViewBtn');
    const calendarViewBtn = document.getElementById('calendarViewBtn');
    const listView = document.getElementById('listView');
    const calendarView = document.getElementById('calendarView');

    if (listViewBtn && calendarViewBtn) {
        listViewBtn.addEventListener('click', function() {
            listViewBtn.classList.add('active');
            calendarViewBtn.classList.remove('active');
            if (listView) listView.style.display = 'block';
            if (calendarView) calendarView.style.display = 'none';
        });

        calendarViewBtn.addEventListener('click', function() {
            calendarViewBtn.classList.add('active');
            listViewBtn.classList.remove('active');
            if (calendarView) calendarView.style.display = 'block';
            if (listView) listView.style.display = 'none';
        });
    }

    // Action menu toggle
    const actionMenus = document.querySelectorAll('.action-menu');
    actionMenus.forEach(menu => {
        const button = menu.querySelector('.btn-icon');
        const dropdown = menu.querySelector('.action-dropdown');

        if (button && dropdown) {
            button.addEventListener('click', function(e) {
                e.stopPropagation();
                // Close other dropdowns
                document.querySelectorAll('.action-dropdown').forEach(d => {
                    if (d !== dropdown) d.classList.remove('show');
                });
                // Toggle this dropdown
                dropdown.classList.toggle('show');
            });
        }
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', function() {
        document.querySelectorAll('.action-dropdown').forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    });

    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('button[onclick*="confirm"]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to perform this action?')) {
                e.preventDefault();
            }
        });
    });

    // Payment sync buttons in admin bookings.
    const syncButtons = document.querySelectorAll('.js-sync-payment[data-booking-id]');
    syncButtons.forEach(button => {
        button.addEventListener('click', function() {
            const bookingId = this.getAttribute('data-booking-id');
            if (!bookingId) {
                return;
            }
            syncPaymentStatus(bookingId, this);
        });
    });
});

// Admin payment sync function
function syncPaymentStatus(bookingId, triggerElement) {
    if (!confirm('Sync payment status with PayHero? This will check if payment was received.')) {
        return;
    }

    const button = triggerElement && triggerElement.closest ? triggerElement.closest('button') : null;
    if (!button) {
        alert('Unable to start payment sync. Please refresh the page and try again.');
        return;
    }

    const originalContent = button.innerHTML;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    button.disabled = true;

    fetch(`/api/bookings/bookings/${bookingId}/verify_payment/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
        }
    })
    .then(response => response.json())
    .then(data => {
        button.innerHTML = originalContent;
        button.disabled = false;

        if (data.status === 'paid') {
            alert('✅ Payment has been confirmed! The booking status has been updated to Paid.');
            location.reload();
        } else {
            const code = data.verification?.code || data.verification?.ResultCode || 'N/A';
            const status = data.verification?.status || 'pending';
            alert(
                `⏳ Payment Status: ${status.toUpperCase()}\n\n` +
                `The payment has not been confirmed yet on PayHero.\n\n` +
                `PayHero Code: ${code}\n\n` +
                `Please:\n` +
                `1. Ask the borrower to check their M-Pesa messages\n` +
                `2. Try again in a few moments\n` +
                `3. If the issue persists, contact PayHero support`
            );
        }
    })
    .catch(error => {
        button.innerHTML = originalContent;
        button.disabled = false;
        console.error('Sync error:', error);
        alert('❌ Error syncing payment status. Please check the browser console and try again.');
    });
}