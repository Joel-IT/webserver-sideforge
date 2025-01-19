document.addEventListener('DOMContentLoaded', () => {
    // Sidebar Navigation
    const sidebarLinks = document.querySelectorAll('.account-sidebar-nav a');
    const sections = document.querySelectorAll('.account-section');

    sidebarLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);

            // Update active states
            sidebarLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');

            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === targetId) {
                    section.classList.add('active');
                }
            });
        });
    });

    // Profile Form Submission
    const profileForm = document.getElementById('profile-form');
    if (profileForm) {
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(profileForm);
            
            try {
                const response = await fetch('/account/update-profile', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Profile Updated',
                        text: result.message
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Update Failed',
                        text: result.error
                    });
                }
            } catch (error) {
                console.error('Profile update error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Could not update profile. Please try again.'
                });
            }
        });
    }

    // Password Change Form
    const passwordForm = document.getElementById('password-change-form');
    if (passwordForm) {
        passwordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(passwordForm);
            
            // Validate password match
            const newPassword = formData.get('new_password');
            const confirmPassword = formData.get('confirm_password');
            
            if (newPassword !== confirmPassword) {
                Swal.fire({
                    icon: 'error',
                    title: 'Password Mismatch',
                    text: 'New passwords do not match'
                });
                return;
            }

            try {
                const response = await fetch('/account/change-password', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Password Changed',
                        text: result.message
                    });
                    passwordForm.reset();
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Change Failed',
                        text: result.error
                    });
                }
            } catch (error) {
                console.error('Password change error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Could not change password. Please try again.'
                });
            }
        });
    }

    // Two-Factor Authentication Toggle
    const twoFactorBtn = document.getElementById('2fa-toggle');
    if (twoFactorBtn) {
        twoFactorBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/account/toggle-2fa', { method: 'POST' });
                const result = await response.json();

                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: result.status === 'enabled' ? '2FA Enabled' : '2FA Disabled',
                        text: result.message
                    });

                    // Update button text and style
                    twoFactorBtn.textContent = result.status === 'enabled' ? 'Disable 2FA' : 'Enable 2FA';
                    twoFactorBtn.classList.toggle('btn-success', result.status === 'enabled');
                    twoFactorBtn.classList.toggle('btn-secondary', result.status !== 'enabled');
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: '2FA Toggle Failed',
                        text: result.error
                    });
                }
            } catch (error) {
                console.error('2FA toggle error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Could not toggle 2FA. Please try again.'
                });
            }
        });
    }

    // Preferences Form
    const preferencesForm = document.getElementById('preferences-form');
    if (preferencesForm) {
        preferencesForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(preferencesForm);
            
            try {
                const response = await fetch('/account/update-preferences', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                
                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Preferences Updated',
                        text: result.message
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Update Failed',
                        text: result.error
                    });
                }
            } catch (error) {
                console.error('Preferences update error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Could not update preferences. Please try again.'
                });
            }
        });
    }

    // Delete Account
    const deleteAccountBtn = document.getElementById('delete-account-btn');
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', async () => {
            const result = await Swal.fire({
                title: 'Delete Account',
                text: 'Are you sure? This action cannot be undone.',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Yes, delete my account'
            });

            if (result.isConfirmed) {
                try {
                    const response = await fetch('/account/delete', { method: 'POST' });
                    const data = await response.json();

                    if (response.ok) {
                        Swal.fire({
                            icon: 'success',
                            title: 'Account Deleted',
                            text: data.message
                        }).then(() => {
                            window.location.href = '/';  // Redirect to home
                        });
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Delete Failed',
                            text: data.error
                        });
                    }
                } catch (error) {
                    console.error('Account delete error:', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'Could not delete account. Please try again.'
                    });
                }
            }
        });
    }
});
