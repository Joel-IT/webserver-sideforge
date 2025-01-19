document.addEventListener('DOMContentLoaded', () => {
    // Sidebar Navigation
    const sidebarLinks = document.querySelectorAll('.security-sidebar-nav a');
    const sections = document.querySelectorAll('.security-section');

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

    // Two-Factor Authentication Toggle
    const twoFactorBtn = document.getElementById('toggle-2fa-btn');
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
                    twoFactorBtn.textContent = result.status === 'enabled' ? 'Disable Two-Factor Auth' : 'Enable Two-Factor Auth';
                    twoFactorBtn.classList.toggle('btn-success', result.status !== 'enabled');
                    twoFactorBtn.classList.toggle('btn-danger', result.status === 'enabled');

                    // Update status icon
                    const statusIcon = document.querySelector('.two-factor-status i');
                    statusIcon.classList.toggle('fa-check-circle', result.status === 'enabled');
                    statusIcon.classList.toggle('fa-times-circle', result.status !== 'enabled');
                    statusIcon.classList.toggle('text-success', result.status === 'enabled');
                    statusIcon.classList.toggle('text-danger', result.status !== 'enabled');

                    const statusText = document.querySelector('.two-factor-status span');
                    statusText.textContent = result.status === 'enabled' ? 'Enabled' : 'Disabled';
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

    // Revoke Session
    const revokeSessionBtns = document.querySelectorAll('.revoke-session');
    revokeSessionBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            const sessionId = btn.getAttribute('data-session-id');

            try {
                const response = await fetch('/security-settings/revoke-session', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `session_id=${encodeURIComponent(sessionId)}`
                });

                const result = await response.json();

                if (response.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Session Revoked',
                        text: result.message
                    }).then(() => {
                        // Remove the row from the table
                        btn.closest('tr').remove();
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Revoke Failed',
                        text: result.error
                    });
                }
            } catch (error) {
                console.error('Session revoke error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Could not revoke session. Please try again.'
                });
            }
        });
    });
});
