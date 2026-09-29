// Authentication related JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Auth.js loaded');
    
    // Toggle password visibility
    const togglePassword = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    
    if (togglePassword && passwordInput) {
        togglePassword.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            // Toggle the eye icon
            const icon = this.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye');
                icon.classList.toggle('fa-eye-slash');
            }
        });
    }

    // ===== SIMPLIFIED TAB SWITCHING (NO ADMIN CODE) =====
    // Switch between member and admin login
    const authTabs = document.querySelectorAll('.auth-tab');
    const loginRoleInput = document.getElementById('loginRole');
    
    console.log('Auth tabs found:', authTabs.length);
    console.log('Login role input found:', loginRoleInput);
    
    if (authTabs.length > 0 && loginRoleInput) {
        // Add click event to each tab
        authTabs.forEach(tab => {
            tab.addEventListener('click', function(e) {
                // Prevent any default button behavior
                e.preventDefault();
                
                console.log('Tab clicked:', this.getAttribute('data-role'));
                
                // Remove active class from all tabs
                authTabs.forEach(t => {
                    t.classList.remove('active');
                });
                
                // Add active class to clicked tab
                this.classList.add('active');
                
                // Update hidden input with selected role
                const role = this.getAttribute('data-role');
                loginRoleInput.value = role;
                
                console.log('Login role set to:', role);
            });
        });
        
        // Trigger click on the active tab to ensure correct initial state
        const activeTab = document.querySelector('.auth-tab.active');
        if (activeTab) {
            setTimeout(() => {
                console.log('Triggering initial active tab');
                activeTab.click();
            }, 100);
        }
    } else {
        console.log('Auth tabs or login role input not found');
    }

   
    // Form validation
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            console.log('Form submission triggered');
            
            const username = document.getElementById('id-username');
            const password = document.getElementById('password');
            const loginRole = document.getElementById('loginRole');
            
            console.log('Username field:', username);
            console.log('Password field:', password);
            console.log('Login role:', loginRole ? loginRole.value : 'not found');
            
            // Check if fields exist
            if (!username || !password) {
                console.log('Form fields not found');
                return;
            }
            
            let isValid = true;
            let errorMessage = '';
            
            // Check if fields are empty
            if (!username.value.trim()) {
                errorMessage = 'Please enter your username or email';
                isValid = false;
                console.log('Validation failed: username empty');
            } else if (!password.value.trim()) {
                errorMessage = 'Please enter your password';
                isValid = false;
                console.log('Validation failed: password empty');
            }
            
            if (!isValid) {
                e.preventDefault();
                console.log('Form submission prevented due to validation error');
                if (typeof showNotification === 'function') {
                    showNotification(errorMessage, 'error');
                } else {
                    alert(errorMessage);
                }
            } else {
                console.log('Form is valid, allowing submission to Django...');
                // Don't prevent default - let the form submit normally
                // Show loading state
                const submitBtn = this.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Logging in...';
                    submitBtn.disabled = true;
                }
                return true; // Allow form submission
            }
        });
    }

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 500);
        }, 5000);
    });
});

// Optional: Add a function to show notifications
function showNotification(message, type = 'info') {
    // Check if notification container exists, if not create it
    let container = document.querySelector('.notification-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        document.body.appendChild(container);
    }
    
    // Create notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        background: ${type === 'error' ? '#f44336' : type === 'success' ? '#4CAF50' : '#2196F3'};
        color: white;
        padding: 15px 20px;
        margin-bottom: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    
    // Add to container
    container.appendChild(notification);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);