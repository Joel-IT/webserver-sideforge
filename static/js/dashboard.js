// Emergency Debugging
window.paymentMethodDebug = {
    logMessage: function(message) {
        console.log(`🔍 PAYMENT METHOD DEBUG: ${message}`);
        try {
            // Optional: Send debug info to server
            fetch('/log-client-error', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    message: message, 
                    timestamp: new Date().toISOString() 
                })
            }).catch(console.error);
        } catch(e) {
            console.error('Logging failed', e);
        }
    }
};

document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard JS: Document fully loaded');

    // Explicit Modal Debugging
    function debugModalSetup() {
        const addPaymentMethodBtn = document.getElementById('add-payment-method');
        const addPaymentMethodModal = document.getElementById('addPaymentMethodModal');
        const savePaymentMethodBtn = document.getElementById('save-payment-method');

        console.log('Modal Debug Information:');
        console.log('Add Payment Method Button:', addPaymentMethodBtn ? '✅ Found' : '❌ Not Found');
        console.log('Payment Method Modal:', addPaymentMethodModal ? '✅ Found' : '❌ Not Found');
        console.log('Save Payment Method Button:', savePaymentMethodBtn ? '✅ Found' : '❌ Not Found');
        
        // Explicit Bootstrap Modal Initialization
        if (addPaymentMethodBtn && addPaymentMethodModal) {
            try {
                const modalInstance = new bootstrap.Modal(addPaymentMethodModal, {
                    keyboard: true,
                    backdrop: 'static'
                });
                console.log('✅ Modal Instance Created Successfully');

                addPaymentMethodBtn.addEventListener('click', function(event) {
                    event.preventDefault();
                    console.log('🔍 Add Payment Method Button Clicked');
                    
                    try {
                        modalInstance.show();
                        console.log('✅ Modal Shown Successfully');
                    } catch (showError) {
                        console.error('❌ Modal Show Error:', showError);
                        alert('Fehler beim Öffnen des Modals: ' + showError.message);
                    }
                });
            } catch (initError) {
                console.error('❌ Modal Initialization Error:', initError);
                alert('Fehler bei der Modal-Initialisierung: ' + initError.message);
            }
        } else {
            console.error('❌ Cannot initialize modal - critical elements missing');
        }
    }

    // Validate Bootstrap Availability
    if (typeof bootstrap === 'undefined') {
        console.error('❌ Bootstrap is NOT available');
        alert('Bootstrap wurde nicht geladen. Bitte laden Sie die Seite neu.');
    } else {
        console.log('✅ Bootstrap is Available');
        debugModalSetup();
    }

    // Function to generate a consistent color based on the name
    function getColorFromName(name) {
        let hash = 0;
        for (let i = 0; i < name.length; i++) {
            hash = name.charCodeAt(i) + ((hash << 5) - hash);
        }
        
        const hue = hash % 360;
        return `hsl(${hue}, 70%, 50%)`;
    }

    // Function to generate avatar with initials
    function generateAvatar(name) {
        const avatarContainer = document.getElementById('avatar');
        
        if (!avatarContainer) return;

        // Split name into first and last name
        const nameParts = name.split(' ');
        const firstName = nameParts[0];
        const lastName = nameParts.length > 1 ? nameParts[nameParts.length - 1] : '';
        
        // Get initials
        const initials = `${firstName[0].toUpperCase()}${lastName ? lastName[0].toUpperCase() : ''}`;
        
        // Create canvas for avatar
        const canvas = document.createElement('canvas');
        canvas.width = 120;
        canvas.height = 120;
        const ctx = canvas.getContext('2d');
        
        // Set background color
        const backgroundColor = getColorFromName(name);
        ctx.fillStyle = backgroundColor;
        ctx.beginPath();
        ctx.arc(60, 60, 60, 0, 2 * Math.PI);
        ctx.fill();
        
        // Add initials
        ctx.fillStyle = 'white';
        ctx.font = 'bold 48px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(initials, 60, 60);
        
        // Replace img src with canvas data
        avatarContainer.src = canvas.toDataURL();
    }

    // Generate avatar for current user
    const userName = document.querySelector('.user-profile h3').textContent;
    generateAvatar(userName);

    // Tab switching logic with smooth transition
    const dashboardNav = document.querySelector('.dashboard-nav');
    const tabContents = document.querySelectorAll('.tab-content');

    dashboardNav.addEventListener('click', function(e) {
        if (e.target.tagName === 'LI') {
            // Remove active class from all nav items and tab contents
            dashboardNav.querySelectorAll('li').forEach(li => li.classList.remove('active'));
            tabContents.forEach(tab => {
                tab.classList.remove('active');
                tab.style.opacity = '0';
            });

            // Add active class to clicked nav item and corresponding tab
            e.target.classList.add('active');
            const tabId = e.target.getAttribute('data-tab');
            const activeTab = document.getElementById(tabId);
            activeTab.classList.add('active');
            
            // Animate tab content
            setTimeout(() => {
                activeTab.style.opacity = '1';
            }, 50);
        }
    });

    // Animated progress bars
    function animateProgressBars() {
        const progressBars = document.querySelectorAll('.progress-bar');
        progressBars.forEach(bar => {
            const width = bar.style.width;
            bar.style.width = '0';
            setTimeout(() => {
                bar.style.width = width;
            }, 100);
        });
    }
    animateProgressBars();

    // Function to download a cloud file
    function downloadCloudFile(fileId) {
        fetch(`/cloud/files/${fileId}/download`)
            .then(response => {
                if (!response.ok) {
                    // Try to parse error details
                    return response.json().then(errorData => {
                        const errorMessage = errorData.details 
                            ? `${errorData.error}: ${errorData.details}` 
                            : errorData.error || 'Download failed';
                        throw new Error(errorMessage);
                    });
                }
                
                // For file downloads, we use the blob method
                return response.blob().then(blob => {
                    const contentDisposition = response.headers.get('Content-Disposition');
                    const filename = contentDisposition
                        ? contentDisposition.split('filename=')[1]?.replace(/"/g, '')
                        : 'downloaded_file';
                    
                    const link = document.createElement('a');
                    link.href = window.URL.createObjectURL(blob);
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // Revoke the object URL to free up memory
                    window.URL.revokeObjectURL(link.href);
                });
            })
            .catch(error => {
                console.error('Download error:', error);
                alert(error.message || 'Failed to download file');
            });
    }

    // File deletion handler with confirmation and animation
    const fileDeleteButtons = document.querySelectorAll('.delete-file');
    fileDeleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const fileId = this.getAttribute('data-file-id');
            const row = this.closest('tr');
            
            Swal.fire({
                title: 'Are you sure?',
                text: 'You won\'t be able to revert this!',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, delete it!'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch(`/cloud/files/${fileId}`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': '{{ csrf_token() }}'
                        }
                    })
                    .then(response => {
                        if (response.ok) {
                            row.classList.add('table-danger');
                            row.style.transition = 'all 0.5s ease';
                            row.style.opacity = '0';
                            setTimeout(() => row.remove(), 500);
                            
                            Swal.fire(
                                'Deleted!',
                                'Your file has been deleted.',
                                'success'
                            );
                        } else {
                            Swal.fire(
                                'Error!',
                                'Failed to delete file.',
                                'error'
                            );
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        Swal.fire(
                            'Error!',
                            'An error occurred while deleting the file.',
                            'error'
                        );
                    });
                }
            });
        });
    });

    // Debug function to log elements
    function debugLogElements() {
        console.log('Debugging Payment Method Elements:');
        console.log('Payment Methods Section:', document.getElementById('payment-methods'));
        console.log('Add Payment Method Button:', document.getElementById('add-payment-method'));
        console.log('Payment Method Modal:', document.getElementById('addPaymentMethodModal'));
        console.log('Save Payment Method Button:', document.getElementById('save-payment-method'));
    }
    debugLogElements();

    // Extremely Robust Modal Initialization
    function initializePaymentMethodModal() {
        window.paymentMethodDebug.logMessage('Initializing Payment Method Modal');

        const addPaymentMethodBtn = document.getElementById('add-payment-method');
        const addPaymentMethodModal = document.getElementById('addPaymentMethodModal');
        const savePaymentMethodBtn = document.getElementById('save-payment-method');

        if (!addPaymentMethodBtn || !addPaymentMethodModal || !savePaymentMethodBtn) {
            window.paymentMethodDebug.logMessage('❌ Critical elements missing');
            return;
        }

        // Create modal with explicit error handling
        let modalInstance;
        try {
            modalInstance = new bootstrap.Modal(addPaymentMethodModal, {
                keyboard: true,
                backdrop: 'static'
            });
            window.paymentMethodDebug.logMessage('✅ Modal instance created');
        } catch (error) {
            window.paymentMethodDebug.logMessage(`❌ Modal initialization error: ${error.message}`);
            alert('Modal konnte nicht initialisiert werden: ' + error.message);
            return;
        }

        // Add click event with maximum error protection
        addPaymentMethodBtn.addEventListener('click', function(event) {
            window.paymentMethodDebug.logMessage('Add Payment Method Button Clicked');
            
            event.preventDefault();
            event.stopPropagation();

            try {
                const form = addPaymentMethodModal.querySelector('form');
                if (form) form.reset();

                window.paymentMethodDebug.logMessage('Attempting to show modal');
                modalInstance.show();
                window.paymentMethodDebug.logMessage('Modal should now be visible');
            } catch (error) {
                window.paymentMethodDebug.logMessage(`❌ Modal show error: ${error.message}`);
                alert('Fehler beim Öffnen des Modals: ' + error.message);
            }
        });

        // Save payment method with comprehensive error handling
        savePaymentMethodBtn.addEventListener('click', function(event) {
            event.preventDefault();
            window.paymentMethodDebug.logMessage('Save Payment Method Button Clicked');

            const cardNumber = document.getElementById('card-number').value.trim();
            const cardExpiry = document.getElementById('card-expiry').value.trim();
            const setAsDefault = document.getElementById('set-as-default').checked;

            window.paymentMethodDebug.logMessage(`Payment Method Details: 
                Card Number: ${cardNumber.replace(/\d{8}/, '********')}
                Expiry: ${cardExpiry}
                Set as Default: ${setAsDefault}`);

            const paymentData = {
                card_number: cardNumber.replace(/\D/g, ''),
                expiry_month: cardExpiry.split('/')[0],
                expiry_year: '20' + cardExpiry.split('/')[1],
                set_as_default: setAsDefault
            };

            fetch('/dashboard/add_payment_method', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                },
                body: JSON.stringify(paymentData)
            })
            .then(response => {
                window.paymentMethodDebug.logMessage(`Response Status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                window.paymentMethodDebug.logMessage('Server Response: ' + JSON.stringify(data));
                if (data.success) {
                    modalInstance.hide();
                    location.reload();
                } else {
                    alert(data.message || 'Fehler beim Hinzufügen der Zahlungsmethode');
                }
            })
            .catch(error => {
                window.paymentMethodDebug.logMessage(`❌ Fetch Error: ${error.message}`);
                alert('Ein unerwarteter Fehler ist aufgetreten: ' + error.message);
            });
        });
    }

    // Run initialization with error protection
    try {
        initializePaymentMethodModal();
    } catch (error) {
        window.paymentMethodDebug.logMessage(`❌ Initialization Error: ${error.message}`);
        alert('Fehler bei der Initialisierung: ' + error.message);
    }

    // Payment Methods Functionality
    const paymentMethodsSection = document.getElementById('payment-methods');
    const addPaymentMethodBtn = paymentMethodsSection ? paymentMethodsSection.querySelector('#add-payment-method') : null;
    const addPaymentMethodModal = document.getElementById('addPaymentMethodModal');
    const savePaymentMethodBtn = document.getElementById('save-payment-method');
    const paymentMethodErrorDiv = document.getElementById('payment-method-error');

    // Debug logging
    console.log('Payment Methods Elements:', {
        paymentMethodsSection,
        addPaymentMethodBtn,
        addPaymentMethodModal,
        savePaymentMethodBtn,
        paymentMethodErrorDiv
    });

    // Add Payment Method Modal Trigger
    if (addPaymentMethodBtn) {
        addPaymentMethodBtn.addEventListener('click', function(e) {
            console.log('Add Payment Method Button Clicked');
            
            // Prevent default behavior
            e.preventDefault();
            e.stopPropagation();

            // Ensure modal exists
            if (!addPaymentMethodModal) {
                console.error('Payment Method Modal not found!');
                alert('Fehler: Modal nicht gefunden');
                return;
            }

            // Reset form
            const cardNumberInput = document.getElementById('card-number');
            const cardExpiryInput = document.getElementById('card-expiry');
            const cardCVCInput = document.getElementById('card-cvc');
            const setAsDefaultCheckbox = document.getElementById('set-as-default');

            if (cardNumberInput) cardNumberInput.value = '';
            if (cardExpiryInput) cardExpiryInput.value = '';
            if (cardCVCInput) cardCVCInput.value = '';
            if (setAsDefaultCheckbox) setAsDefaultCheckbox.checked = false;

            // Show modal using Bootstrap 5
            try {
                const modalInstance = new bootstrap.Modal(addPaymentMethodModal);
                modalInstance.show();
                console.log('Modal should be showing');
            } catch (error) {
                console.error('Error showing modal:', error);
                alert('Fehler beim Öffnen des Modals: ' + error.message);
            }
        });
    } else {
        console.error('Add Payment Method Button not found!');
    }

    // Validate Card Number
    function validateCardNumber(cardNumber) {
        // Remove non-digit characters
        cardNumber = cardNumber.replace(/\D/g, '');
        
        // Basic length and pattern checks
        if (cardNumber.length < 13 || cardNumber.length > 19) {
            return false;
        }
        
        // Luhn algorithm validation
        let sum = 0;
        let isEven = false;
        
        for (let i = cardNumber.length - 1; i >= 0; i--) {
            let digit = parseInt(cardNumber.charAt(i), 10);
            
            if (isEven) {
                digit *= 2;
                if (digit > 9) {
                    digit -= 9;
                }
            }
            
            sum += digit;
            isEven = !isEven;
        }
        
        return (sum % 10 === 0);
    }

    // Validate Expiration Date
    function validateExpiryDate(expiry) {
        const [month, year] = expiry.split('/');
        const currentYear = new Date().getFullYear() % 100;
        const currentMonth = new Date().getMonth() + 1;
        
        const monthNum = parseInt(month, 10);
        const yearNum = parseInt(year, 10);
        
        return monthNum >= 1 && monthNum <= 12 && 
               yearNum >= currentYear && 
               (yearNum > currentYear || monthNum >= currentMonth);
    }

    // Save Payment Method
    if (savePaymentMethodBtn) {
        savePaymentMethodBtn.addEventListener('click', function() {
            const cardNumber = document.getElementById('card-number').value.trim();
            const cardExpiry = document.getElementById('card-expiry').value.trim();
            const cardCVC = document.getElementById('card-cvc').value.trim();
            const setAsDefault = document.getElementById('set-as-default').checked;

            // Reset error
            paymentMethodErrorDiv.style.display = 'none';
            paymentMethodErrorDiv.textContent = '';

            // Validate inputs
            if (!cardNumber || !cardExpiry || !cardCVC) {
                paymentMethodErrorDiv.textContent = 'Bitte alle Felder ausfüllen.';
                paymentMethodErrorDiv.style.display = 'block';
                return;
            }

            // Validate card number
            if (!validateCardNumber(cardNumber)) {
                paymentMethodErrorDiv.textContent = 'Ungültige Kartennummer.';
                paymentMethodErrorDiv.style.display = 'block';
                return;
            }

            // Validate expiry date
            if (!validateExpiryDate(cardExpiry)) {
                paymentMethodErrorDiv.textContent = 'Ungültiges Ablaufdatum.';
                paymentMethodErrorDiv.style.display = 'block';
                return;
            }

            // Validate CVC
            if (!/^\d{3,4}$/.test(cardCVC)) {
                paymentMethodErrorDiv.textContent = 'Ungültige Prüfziffer.';
                paymentMethodErrorDiv.style.display = 'block';
                return;
            }

            // Prepare data to send
            const paymentData = {
                card_number: cardNumber.replace(/\D/g, ''),
                expiry_month: cardExpiry.split('/')[0],
                expiry_year: '20' + cardExpiry.split('/')[1],
                set_as_default: setAsDefault
            };

            // Send to server
            fetch('/dashboard/add_payment_method', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(paymentData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Close modal
                    const modal = new bootstrap.Modal(addPaymentMethodModal);
                    modal.hide();
                    
                    // Reload to update UI
                    location.reload();
                } else {
                    // Show error
                    paymentMethodErrorDiv.textContent = data.message || 'Fehler beim Hinzufügen der Zahlungsmethode.';
                    paymentMethodErrorDiv.style.display = 'block';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                paymentMethodErrorDiv.textContent = 'Ein unerwarteter Fehler ist aufgetreten.';
                paymentMethodErrorDiv.style.display = 'block';
            });
        });
    }

    // Set Default Payment Method
    if (paymentMethodsSection) {
        paymentMethodsSection.addEventListener('click', function(e) {
            if (e.target.classList.contains('set-default')) {
                const methodId = e.target.getAttribute('data-method-id');
                
                fetch(`/dashboard/set_default_payment_method/${methodId}`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Reload to update UI
                        location.reload();
                    } else {
                        alert(data.message || 'Failed to set default payment method');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('An unexpected error occurred');
                });
            }

            // Delete Payment Method
            if (e.target.classList.contains('delete-method')) {
                const methodId = e.target.getAttribute('data-method-id');
                
                if (confirm('Are you sure you want to delete this payment method?')) {
                    fetch(`/dashboard/delete_payment_method/${methodId}`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': getCsrfToken()
                        }
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            // Reload to update UI
                            location.reload();
                        } else {
                            alert(data.message || 'Failed to delete payment method');
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An unexpected error occurred');
                    });
                }
            }
        });
    }

    // Utility function to get CSRF token
    function getCsrfToken() {
        return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    }
});
