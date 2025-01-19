document.addEventListener('DOMContentLoaded', () => {
    const fileUpload = document.getElementById('file-upload');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadProgress = document.getElementById('upload-progress');
    const storageProgress = document.getElementById('storage-progress');
    const storageInfo = document.getElementById('storage-info');
    const filesList = document.getElementById('files-list');

    // Debugging function
    function debugLog(message, data = null) {
        console.log(`[Cloud Storage Debug] ${message}`);
        if (data) console.log(data);
    }

    // Fetch storage info
    async function fetchStorageInfo() {
        try {
            const response = await fetch('/cloud/storage-info');
            const data = await response.json();
            
            // Safely handle storage info
            const usedGB = (data.used_storage / (1024 * 1024 * 1024)).toFixed(2);
            const totalGB = (data.total_storage / (1024 * 1024 * 1024)).toFixed(0);
            const percentUsed = data.percent_used || 0;
            
            // Update storage progress bar
            if (storageProgress) {
                storageProgress.style.width = `${percentUsed}%`;
                storageProgress.setAttribute('aria-valuenow', percentUsed);
                storageProgress.textContent = `${percentUsed}%`;
            }
            
            // Update storage info text
            if (storageInfo) {
                storageInfo.textContent = `${usedGB} / ${totalGB} GB used`;
            }
            
            // Optional: Log detailed storage info for debugging
            console.log('Storage Info:', {
                usedStorage: data.used_storage,
                totalStorage: data.total_storage,
                percentUsed: percentUsed,
                totalFiles: data.total_files
            });
            
            return data;
        } catch (error) {
            console.error('Error fetching storage info:', error);
            
            // Fallback display
            if (storageProgress) {
                storageProgress.style.width = '0%';
                storageProgress.setAttribute('aria-valuenow', 0);
                storageProgress.textContent = '0%';
            }
            
            if (storageInfo) {
                storageInfo.textContent = '0 / 5 GB used';
            }
            
            return null;
        }
    }

    // Fetch user files
    async function fetchUserFiles() {
        try {
            const response = await fetch('/cloud/files');
            if (!response.ok) {
                throw new Error('Fehler beim Abrufen von Dateien');
            }
            const files = await response.json();
            
            const filesList = document.getElementById('files-list');
            const noFilesMessage = document.getElementById('no-files');
            
            // Clear existing list
            filesList.innerHTML = '';
            
            if (!files || files.length === 0) {
                noFilesMessage.style.display = 'block';
                return;
            }
            
            noFilesMessage.style.display = 'none';
            
            files.forEach(file => {
                // Aggressive normalization of file properties
                const fileName = file.filename || file.file_name || 'Unnamed File';
                const fileSize = file.size || file.file_size || 0;
                const fileSizeKB = (fileSize / 1024).toFixed(2);
                const fileType = file.type || file.file_type || 'Unknown';
                const fileId = file.id || file.file_id;
                
                const row = document.createElement('tr');
                row.setAttribute('data-file-id', fileId);  // Add data attribute for easier selection
                row.innerHTML = `
                    <td>${fileName}</td>
                    <td>${fileSizeKB} KB</td>
                    <td>${fileType}</td>
                    <td>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-primary download-file" data-file-id="${fileId}">
                                <i class="fas fa-download"></i>
                            </button>
                            <button class="btn btn-sm btn-info share-file-btn" data-file-id="${fileId}">
                                <i class="fas fa-share-alt"></i>
                            </button>
                            <button class="btn btn-sm btn-danger delete-file" data-file-id="${fileId}">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                `;
                
                filesList.appendChild(row);
            });
            
            // Reattach event listeners
            attachFileActionListeners();
            
            // Update storage info
            await fetchStorageInfo();
        } catch (error) {
            console.error('Fehler beim Abrufen von Dateien:', error);
            showAlert('Fehler beim Laden der Dateien', 'error');
        }
    }

    // Centralized event listener attachment
    function attachFileActionListeners() {
        // Download buttons
        document.querySelectorAll('.download-file').forEach(btn => {
            btn.removeEventListener('click', downloadFileHandler);  // Prevent duplicate listeners
            btn.addEventListener('click', downloadFileHandler);
        });
        
        // Delete buttons
        document.querySelectorAll('.delete-file').forEach(btn => {
            btn.removeEventListener('click', deleteFileHandler);  // Prevent duplicate listeners
            btn.addEventListener('click', deleteFileHandler);
        });
        
        // Share buttons
        document.querySelectorAll('.share-file-btn').forEach(btn => {
            btn.removeEventListener('click', shareFileHandler);  // Prevent duplicate listeners
            btn.addEventListener('click', shareFileHandler);
        });
    }

    // Handlers with error handling
    async function downloadFileHandler(e) {
        const fileId = e.currentTarget.getAttribute('data-file-id');
        try {
            await downloadFile(fileId);
        } catch (error) {
            console.error('Download failed:', error);
            showAlert('Download fehlgeschlagen', 'error');
        }
    }

    async function deleteFileHandler(e) {
        const fileId = e.currentTarget.getAttribute('data-file-id');
        try {
            const success = await deleteFile(fileId);
            if (success) {
                await fetchUserFiles();  // Refresh list after deletion
            }
        } catch (error) {
            console.error('Deletion failed:', error);
            showAlert('Löschen fehlgeschlagen', 'error');
        }
    }

    async function shareFileHandler(e) {
        const fileId = e.currentTarget.getAttribute('data-file-id');
        try {
            await shareFileInteractive(fileId);
        } catch (error) {
            console.error('Sharing failed:', error);
            showAlert('Teilen fehlgeschlagen', 'error');
        }
    }

    // File Upload with Enhanced Error Handling
    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/cloud/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Upload failed');
            }

            // Show success message
            showAlert(result.message || 'Datei erfolgreich hochgeladen', 'success');

            // Refresh file list and storage info
            await fetchUserFiles();
            
            return result;
        } catch (error) {
            console.error('Upload error:', error);
            showAlert(error.message || 'Upload fehlgeschlagen', 'error');
            throw error;
        }
    }

    // Event Listeners
    fileUpload.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) {
            showAlert('Keine Datei ausgewählt', 'warning');
            return;
        }

        try {
            uploadProgress.style.width = '0%';
            uploadProgress.textContent = '0%';
            
            await uploadFile(file);
            
            // Reset file input
            fileUpload.value = '';
        } catch (error) {
            console.error('File upload error:', error);
        }
    });

    // Delete file
    async function deleteFile(fileId) {
        try {
            console.log(`Attempting to delete file with ID: ${fileId}`);
            
            const response = await fetch(`/cloud/files/${fileId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    // Include CSRF token if your app uses it
                    'X-CSRFToken': getCsrfToken ? getCsrfToken() : ''
                }
            });

            const responseData = await response.json();

            if (!response.ok) {
                console.error('Delete file error:', responseData);
                
                // More detailed error handling
                if (responseData.active_shares) {
                    showAlert('Cannot delete file with active shares. Please revoke shares first.', 'warning');
                } else {
                    showAlert(responseData.error || 'Failed to delete file', 'error');
                }
                
                return false;
            }

            // Remove the file row from the table
            const fileRow = document.querySelector(`tr[data-file-id="${fileId}"]`);
            if (fileRow) {
                fileRow.remove();
            }

            // Refresh file list or update UI
            showAlert('File deleted successfully', 'success');
            
            // Optional: Refresh file list
            await fetchUserFiles();

            return true;
        } catch (error) {
            console.error('Delete file network error:', error);
            showAlert('Network error. Unable to delete file.', 'error');
            return false;
        }
    }

    // Download file
    async function downloadFile(fileId) {
        try {
            const response = await fetch(`/cloud/files/${fileId}/download`);
            
            if (response.ok) {
                const contentDisposition = response.headers.get('Content-Disposition');
                const filename = contentDisposition
                    ? contentDisposition.split('filename=')[1]?.replace(/"/g, '')
                    : 'downloaded_file';
                
                const blob = await response.blob();
                const link = document.createElement('a');
                link.href = window.URL.createObjectURL(blob);
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                // Optional: Revoke the object URL to free up memory
                window.URL.revokeObjectURL(link.href);
            } else {
                const errorData = await response.json();
                console.error('Download error:', errorData);
                alert(errorData.error || errorData.details || 'Failed to download file');
            }
        } catch (error) {
            console.error('Error downloading file:', error);
            alert('An unexpected error occurred while downloading the file.');
        }
    }

    // Interactive file sharing function
    async function shareFileInteractive(fileId) {
        // Convert fileId to a number and validate
        const numericFileId = Number(fileId);
        
        console.log('Attempting to share file. Input fileId:', fileId, 'Numeric fileId:', numericFileId);
        
        if (!fileId || isNaN(numericFileId)) {
            console.error('Invalid file ID for sharing', { fileId, numericFileId });
            Swal.fire({
                icon: 'error',
                title: 'Invalid File',
                text: 'Please select a valid file to share',
                footer: `Received file ID: ${fileId}`
            });
            return;
        }

        const { value: searchQuery } = await Swal.fire({
            title: 'Share File',
            input: 'text',
            inputLabel: 'Search user by username or email',
            inputPlaceholder: 'Enter username or email',
            showCancelButton: true,
            inputValidator: (value) => {
                if (!value) {
                    return 'You need to enter a username or email!';
                }
            }
        });

        if (searchQuery) {
            // Search for users
            const users = await searchUsersForSharing(searchQuery);
            
            if (users.length === 0) {
                Swal.fire({
                    icon: 'info',
                    title: 'No Users Found',
                    text: 'No users match your search criteria'
                });
                return;
            }

            // If only one user found, directly share
            if (users.length === 1) {
                await shareFile(numericFileId, users[0].id);
                return;
            }

            // If multiple users, show selection
            const { value: selectedUsers } = await Swal.fire({
                title: 'Select User(s) to Share With',
                html: users.map(user => `
                    <label class="d-block">
                        <input type="checkbox" value="${user.id}" class="swal2-checkbox">
                        ${user.username} (${user.email})
                    </label>
                `).join(''),
                focusConfirm: false,
                preConfirm: () => {
                    const selected = Array.from(
                        document.querySelectorAll('input[type="checkbox"]:checked')
                    ).map(el => el.value);
                    
                    return selected.length ? selected : false;
                },
                showCancelButton: true
            });

            if (selectedUsers) {
                await shareFile(numericFileId, selectedUsers);
            }
        }
    }

    // Utility function to get CSRF token
    function getCsrfToken() {
        const csrfTokenElement = document.querySelector('meta[name="csrf-token"]');
        return csrfTokenElement ? csrfTokenElement.getAttribute('content') : null;
    }

    // Share a file with selected users
    async function shareFile(fileId, recipientIds) {
        try {
            const csrfToken = getCsrfToken();
            if (!csrfToken) {
                throw new Error('CSRF token is missing');
            }

            const response = await fetch(`/cloud/files/${fileId}/share`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    recipient_ids: Array.isArray(recipientIds) ? recipientIds : [recipientIds]
                }),
                credentials: 'same-origin'  // Important for sending cookies with the request
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Share file error response:', errorText);
                throw new Error(errorText || 'Failed to share file');
            }

            const result = await response.json();
            Swal.fire({
                icon: 'success',
                title: 'File Shared',
                text: result.message
            });
            return result.shared_files;
        } catch (error) {
            console.error('Error sharing file:', error);
            Swal.fire({
                icon: 'error',
                title: 'Share Failed',
                text: error.message || 'Could not share file'
            });
            return null;
        }
    }

    // Search users for file sharing
    async function searchUsersForSharing(query) {
        try {
            const csrfToken = getCsrfToken();
            const response = await fetch(`/cloud/files/search-users?query=${encodeURIComponent(query)}`, {
                headers: csrfToken ? { 'X-CSRFToken': csrfToken } : {},
                credentials: 'same-origin'
            });
            
            if (!response.ok) {
                throw new Error('Failed to search users');
            }
            const users = await response.json();
            console.log('Search users result:', users);
            return users;
        } catch (error) {
            console.error('Error searching users:', error);
            Swal.fire({
                icon: 'error',
                title: 'Search Failed',
                text: 'Could not search for users to share with'
            });
            return [];
        }
    }

    // Fetch shared files
    async function fetchSharedFiles() {
        try {
            const response = await fetch('/cloud/files/shared');
            if (!response.ok) {
                const errorData = await response.json();
                console.error('Failed to fetch shared files:', errorData);
                throw new Error(errorData.error || 'Failed to fetch shared files');
            }
            const sharedFiles = await response.json();
            
            const sharedFilesList = document.getElementById('shared-files-list');
            const noSharedFilesMessage = document.getElementById('no-shared-files');
            
            // Clear existing list
            sharedFilesList.innerHTML = '';
            
            if (!sharedFiles || sharedFiles.length === 0) {
                noSharedFilesMessage.style.display = 'block';
                return;
            }
            
            noSharedFilesMessage.style.display = 'none';
            
            sharedFiles.forEach(file => {
                // Handle potential error cases
                if (file.error) {
                    console.error('Shared file error:', file);
                    return;
                }

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${file.file_name || 'Unnamed File'}</td>
                    <td>${file.sender_username || 'Unknown Sender'}</td>
                    <td>${file.shared_at ? new Date(file.shared_at).toLocaleString() : 'Unknown Date'}</td>
                    <td>${file.status || 'Unknown Status'}</td>
                    <td>
                        <div class="btn-group" role="group">
                            <button class="btn btn-sm btn-success accept-shared-file" data-shared-file-id="${file.id}">
                                <i class="fas fa-check"></i> Accept
                            </button>
                            <button class="btn btn-sm btn-danger reject-shared-file" data-shared-file-id="${file.id}">
                                <i class="fas fa-times"></i> Reject
                            </button>
                        </div>
                    </td>
                `;
                
                sharedFilesList.appendChild(row);
            });
            
            // Add event listeners for accept/reject buttons
            document.querySelectorAll('.accept-shared-file').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const sharedFileId = e.currentTarget.getAttribute('data-shared-file-id');
                    await acceptSharedFile(sharedFileId);
                });
            });
            
            document.querySelectorAll('.reject-shared-file').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const sharedFileId = e.currentTarget.getAttribute('data-shared-file-id');
                    await rejectSharedFile(sharedFileId);
                });
            });
        } catch (error) {
            console.error('Error fetching shared files:', error);
            const noSharedFilesMessage = document.getElementById('no-shared-files');
            if (noSharedFilesMessage) {
                noSharedFilesMessage.textContent = 'Error loading shared files. Please try again later.';
                noSharedFilesMessage.style.display = 'block';
            }
        }
    }

    // Accept a shared file
    async function acceptSharedFile(sharedFileId) {
        try {
            const response = await fetch(`/cloud/files/shared/${sharedFileId}/accept`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });
            
            if (response.ok) {
                await fetchSharedFiles();
                await fetchUserFiles();
                await fetchStorageInfo();
                Swal.fire('Success', 'File accepted and added to your cloud storage', 'success');
            } else {
                const errorData = await response.json();
                Swal.fire('Error', errorData.error || 'Failed to accept file', 'error');
            }
        } catch (error) {
            console.error('Error accepting shared file:', error);
            Swal.fire('Error', 'An unexpected error occurred', 'error');
        }
    }

    // Reject a shared file
    async function rejectSharedFile(sharedFileId) {
        try {
            const response = await fetch(`/cloud/files/shared/${sharedFileId}/reject`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken()
                }
            });
            
            if (response.ok) {
                await fetchSharedFiles();
                Swal.fire('Success', 'File share request rejected', 'success');
            } else {
                const errorData = await response.json();
                Swal.fire('Error', errorData.error || 'Failed to reject file', 'error');
            }
        } catch (error) {
            console.error('Error rejecting shared file:', error);
            Swal.fire('Error', 'An unexpected error occurred', 'error');
        }
    }

    // Initial load
    fetchUserFiles();
    fetchStorageInfo();
    
    // Call fetchSharedFiles when the page loads
    if (document.getElementById('shared-files-list')) {
        fetchSharedFiles();
    }
});
