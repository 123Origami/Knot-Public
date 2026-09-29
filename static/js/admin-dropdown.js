// Admin Dropdown Toggle Handler
document.addEventListener('DOMContentLoaded', function() {
    // Handle admin dropdown toggle
    const adminUserToggles = document.querySelectorAll('.admin-user-toggle');
    
    adminUserToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Find the parent dropdown container
            const dropdownContainer = this.closest('.admin-user-dropdown');
            if (!dropdownContainer) return;
            
            // Find the dropdown menu within the container
            const dropdownMenu = dropdownContainer.querySelector('.admin-dropdown-menu');
            if (!dropdownMenu) return;
            
            // Close all other dropdowns
            document.querySelectorAll('.admin-dropdown-menu').forEach(menu => {
                if (menu !== dropdownMenu) {
                    menu.classList.remove('active');
                }
            });
            
            // Toggle this dropdown
            dropdownMenu.classList.toggle('active');
        });
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        const isToggle = e.target.closest('.admin-user-toggle');
        const isMenu = e.target.closest('.admin-dropdown-menu');
        
        if (!isToggle && !isMenu) {
            document.querySelectorAll('.admin-dropdown-menu.active').forEach(menu => {
                menu.classList.remove('active');
            });
        }
    });
});
