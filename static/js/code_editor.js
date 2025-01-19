document.addEventListener('DOMContentLoaded', function() {
    console.log('Code Editor: DOM fully loaded');

    // Ensure all required elements exist
    const requiredElements = [
        'code-editor', 'language-select', 'filename-input', 
        'cloud-file-list', 'local-file-list', 
        'save-button', 'new-file-btn', 
        'delete-file-button', 'new-file-form',
        'upload-cloud-file-btn'
    ];

    requiredElements.forEach(elementId => {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error(`Required element not found: ${elementId}`);
        }
    });

    // Initialize Ace Editor with robust error handling
    let editor;
    try {
        editor = ace.edit("code-editor");
        if (!editor) {
            throw new Error('Failed to initialize Ace Editor');
        }
        editor.setTheme("ace/theme/monokai");
        editor.session.setMode("ace/mode/text");
        editor.setOptions({
            fontSize: "14px",
            enableBasicAutocompletion: true,
            enableLiveAutocompletion: true
        });
        console.log('Ace Editor initialized successfully');
    } catch (error) {
        console.error('Ace Editor initialization error:', error);
        alert('Failed to load code editor. Please refresh the page.');
        return;
    }

    const languageSelect = document.getElementById('language-select');
    const filenameInput = document.getElementById('filename-input');
    const cloudFileList = document.getElementById('cloud-file-list');
    const localFileList = document.getElementById('local-file-list');
    const saveButton = document.getElementById('save-button');
    const newFileButton = document.getElementById('new-file-btn');
    const deleteFileButton = document.getElementById('delete-file-button');
    const newFileForm = document.getElementById('new-file-form');
    const createFileBtn = document.getElementById('create-file-btn');
    const cancelNewFileBtn = document.getElementById('cancel-new-file-btn');
    const newFilenameInput = document.getElementById('new-file-name');
    const newFileLanguageSelect = document.getElementById('new-file-language');
    const uploadCloudFileBtn = document.getElementById('upload-cloud-file-btn');

    // Track current file type (cloud or local)
    let currentFileType = 'cloud';

    // Detailed logging for network requests
    function logFetchError(operation, error) {
        console.error(`${operation} error:`, error);
        alert(`Failed to ${operation.toLowerCase()}: ${error.message || 'Unknown error'}`);
    }

    // Add event listeners to file lists
    function setupFileListListeners(fileList, isCloudList = true) {
        fileList.querySelectorAll('.list-group-item').forEach(item => {
            item.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                currentFileType = isCloudList ? 'cloud' : 'local';
                
                // Highlight selected file
                fileList.querySelectorAll('.list-group-item').forEach(el => 
                    el.classList.remove('active')
                );
                this.classList.add('active');

                // Load file based on type
                if (isCloudList) {
                    loadCloudFileContent(filename);
                } else {
                    loadLocalCodeFile(filename);
                }
            });
        });
    }

    // Initial setup of file list listeners
    setupFileListListeners(cloudFileList, true);
    setupFileListListeners(localFileList, false);

    // Load a cloud file
    function loadCloudFileContent(filename) {
        console.log(`Loading cloud file content: ${filename}`);
        fetch(`/cloud/file/content?filename=${encodeURIComponent(filename)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(fileData => {
                console.log('Cloud file content loaded:', fileData);
                
                // Set editor content
                editor.setValue(fileData.content, -1);  // -1 moves cursor to start
                
                // Set syntax highlighting based on file type
                const modeMap = {
                    'py': 'python',
                    'js': 'javascript',
                    'html': 'html',
                    'css': 'css',
                    'json': 'json',
                    'md': 'markdown',
                    'txt': 'text'
                };
                const mode = modeMap[fileData.file_type] || 'text';
                editor.session.setMode(`ace/mode/${mode}`);
                
                // Update file metadata display
                updateFileMetadata(fileData);
                
                // Mark current file as cloud file
                editor.currentFile = {
                    type: 'cloud',
                    filename: filename
                };
            })
            .catch(error => {
                console.error(`Error loading cloud file ${filename}:`, error);
                alert(`Failed to load cloud file: ${filename}`);
            });
    }

    // Load a local code file
    function loadLocalCodeFile(filename) {
        console.log(`Attempting to load local code file: ${filename}`);
        fetch(`/cloud/code/load/${encodeURIComponent(filename)}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Local code file loaded successfully:', data);
                filenameInput.value = data.filename;
                editor.setValue(data.content, -1);  // -1 moves cursor to the end
                languageSelect.value = data.language || 'text';
                editor.session.setMode(`ace/mode/${data.language || 'text'}`);
            })
            .catch(error => logFetchError('Load Local Code File', error));
    }

    // Save file (handles both cloud and local files)
    function saveFile() {
        const filename = filenameInput.value.trim();
        const content = editor.getValue();
        const language = languageSelect.value;

        if (!filename) {
            alert('Please enter a filename');
            return;
        }

        console.log('Attempting to save file:', { filename, language, type: currentFileType });

        const url = currentFileType === 'cloud' 
            ? '/cloud/file/save' 
            : '/cloud/code/save';

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                filename: filename,
                content: content,
                language: language
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('File save response:', data);
            if (data.success) {
                alert('File saved successfully!');
                // Refresh appropriate file list
                if (currentFileType === 'cloud') {
                    loadCloudFileList();
                } else {
                    refreshLocalCodeFileList();
                }
            } else {
                throw new Error(data.error || 'Unknown save error');
            }
        })
        .catch(error => logFetchError('Save File', error));
    }

    // Delete file (handles both cloud and local files)
    function deleteFile() {
        const filename = filenameInput.value.trim();
        
        if (!filename) {
            alert('Please select a file to delete');
            return;
        }

        if (!confirm(`Are you sure you want to delete ${filename}?`)) {
            return;
        }

        console.log('Attempting to delete file:', { filename, type: currentFileType });

        const url = currentFileType === 'cloud' 
            ? `/cloud/file/delete/${encodeURIComponent(filename)}` 
            : `/cloud/code/delete/${encodeURIComponent(filename)}`;

        fetch(url, {
            method: 'DELETE'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('File delete response:', data);
            if (data.success) {
                alert('File deleted successfully!');
                // Reset editor
                filenameInput.value = '';
                editor.setValue('', -1);
                
                // Refresh appropriate file list
                if (currentFileType === 'cloud') {
                    loadCloudFileList();
                } else {
                    refreshLocalCodeFileList();
                }
            } else {
                throw new Error(data.error || 'Unknown delete error');
            }
        })
        .catch(error => logFetchError('Delete File', error));
    }

    // Load cloud file list
    function loadCloudFileList() {
        console.log('Loading cloud file list');
        fetch('/cloud/files')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(files => {
                console.log('Cloud files received:', files);
                const cloudFileList = document.getElementById('cloud-file-list');
                cloudFileList.innerHTML = ''; // Clear existing list

                if (!files || files.length === 0) {
                    const noFilesMessage = document.createElement('li');
                    noFilesMessage.textContent = 'No cloud files found';
                    noFilesMessage.classList.add('list-group-item', 'text-muted');
                    cloudFileList.appendChild(noFilesMessage);
                } else {
                    files.forEach(file => {
                        const li = document.createElement('li');
                        li.classList.add('list-group-item', 'list-group-item-action');
                        li.setAttribute('data-filename', file.filename);
                        
                        // Convert size to human-readable format
                        const formatSize = (bytes) => {
                            if (bytes < 1024) return `${bytes} B`;
                            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
                            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
                        };

                        li.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                ${file.filename}
                                <div class="file-details">
                                    <span class="badge ${file.is_editable ? 'badge-success' : 'badge-secondary'} badge-pill mr-2">
                                        ${formatSize(file.size)}
                                    </span>
                                    <small class="text-muted">${file.type || 'Unknown'}</small>
                                </div>
                            </div>
                        `;
                        
                        // Only add click listener for editable files
                        if (file.is_editable) {
                            li.addEventListener('click', () => loadCloudFileContent(file.filename));
                        } else {
                            li.classList.add('text-muted');
                            li.setAttribute('title', 'This file type cannot be edited');
                        }
                        
                        cloudFileList.appendChild(li);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading cloud file list:', error);
                const cloudFileList = document.getElementById('cloud-file-list');
                const errorMessage = document.createElement('li');
                errorMessage.textContent = 'Failed to load cloud files. Please try again.';
                errorMessage.classList.add('list-group-item', 'text-danger');
                cloudFileList.appendChild(errorMessage);
            });
    }

    // Refresh local code file list
    function refreshLocalCodeFileList() {
        console.log('Refreshing local code file list');
        fetch('/cloud/code/list')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(files => {
                console.log('Local code files received:', files);
                const localFileList = document.getElementById('local-file-list');
                localFileList.innerHTML = ''; // Clear existing list

                if (!files || files.length === 0) {
                    const noFilesMessage = document.createElement('li');
                    noFilesMessage.textContent = 'No local code files found';
                    noFilesMessage.classList.add('list-group-item', 'text-muted');
                    localFileList.appendChild(noFilesMessage);
                } else {
                    files.forEach(file => {
                        const li = document.createElement('li');
                        li.classList.add('list-group-item', 'list-group-item-action');
                        li.setAttribute('data-filename', file.filename);
                        
                        // Convert size to human-readable format
                        const formatSize = (bytes) => {
                            if (bytes < 1024) return `${bytes} B`;
                            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
                            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
                        };

                        li.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                ${file.filename}
                                <div class="file-details">
                                    <span class="badge badge-primary badge-pill">
                                        ${formatSize(file.size)}
                                    </span>
                                </div>
                            </div>
                        `;
                        
                        li.addEventListener('click', () => loadLocalCodeFile(file.filename));
                        localFileList.appendChild(li);
                    });
                }
            })
            .catch(error => {
                console.error('Error refreshing local code file list:', error);
                const localFileList = document.getElementById('local-file-list');
                const errorMessage = document.createElement('li');
                errorMessage.textContent = 'Failed to load local code files. Please try again.';
                errorMessage.classList.add('list-group-item', 'text-danger');
                localFileList.appendChild(errorMessage);
            });
    }

    // Upload cloud file
    function uploadCloudFile() {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.onchange = function(event) {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            fetch('/cloud/file/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert('File uploaded successfully!');
                    loadCloudFileList();
                } else {
                    throw new Error(data.error || 'Unknown upload error');
                }
            })
            .catch(error => logFetchError('Upload Cloud File', error));
        };
        fileInput.click();
    }

    // New file button handler
    function newFile() {
        newFileForm.style.display = 'block';
        newFilenameInput.value = '';
        newFileLanguageSelect.value = 'text';
    }

    // Create new file
    function createNewFile() {
        const newFilename = newFilenameInput.value.trim();
        const newLanguage = newFileLanguageSelect.value;

        if (!newFilename) {
            alert('Please enter a filename');
            return;
        }

        filenameInput.value = newFilename;
        editor.setValue('', -1);
        languageSelect.value = newLanguage;
        editor.session.setMode(`ace/mode/${newLanguage}`);
        currentFileType = 'local';  // New files start as local

        // Hide new file form
        newFileForm.style.display = 'none';
    }

    // Language mode change
    languageSelect.addEventListener('change', function() {
        const selectedLanguage = this.value;
        editor.session.setMode(`ace/mode/${selectedLanguage}`);
    });

    // Event Listeners
    saveButton.addEventListener('click', saveFile);
    newFileButton.addEventListener('click', newFile);
    deleteFileButton.addEventListener('click', deleteFile);
    createFileBtn.addEventListener('click', createNewFile);
    cancelNewFileBtn.addEventListener('click', function() {
        newFileForm.style.display = 'none';
    });
    uploadCloudFileBtn.addEventListener('click', uploadCloudFile);

    // Initial load of files
    loadCloudFileList();
    refreshLocalCodeFileList();

    // Utility function to update file metadata display
    function updateFileMetadata(fileData) {
        const metadataContainer = document.getElementById('file-metadata');
        if (!metadataContainer) return;
        
        const formatDate = (dateString) => {
            if (!dateString) return 'Unknown';
            return new Date(dateString).toLocaleString();
        };
        
        const formatSize = (bytes) => {
            if (bytes < 1024) return `${bytes} B`;
            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        };
        
        metadataContainer.innerHTML = `
            <div class="file-info">
                <strong>Filename:</strong> ${fileData.filename}<br>
                <strong>Type:</strong> ${fileData.file_type}<br>
                <strong>Size:</strong> ${formatSize(fileData.size)}<br>
                <strong>Uploaded:</strong> ${formatDate(fileData.uploaded_at)}
            </div>
        `;
    }

    // Function to load cloud storage files
    function loadCloudStorageFiles() {
        console.log('Loading cloud storage files');
        fetch('/cloud/storage-files')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Cloud storage files received:', data);
                const cloudFileList = document.getElementById('cloud-file-list');
                const storageInfoContainer = document.getElementById('storage-info');
                
                // Clear existing lists
                cloudFileList.innerHTML = '';
                
                // Update storage info
                if (storageInfoContainer) {
                    storageInfoContainer.innerHTML = `
                        <div class="storage-summary">
                            <strong>Total Files:</strong> ${data.total_files}<br>
                            <strong>Storage Used:</strong> ${formatFileSize(data.total_storage_used)}
                        </div>
                    `;
                }

                // Populate file list
                if (!data.files || data.files.length === 0) {
                    const noFilesMessage = document.createElement('li');
                    noFilesMessage.textContent = 'No cloud files found';
                    noFilesMessage.classList.add('list-group-item', 'text-muted');
                    cloudFileList.appendChild(noFilesMessage);
                } else {
                    data.files.forEach(file => {
                        const li = document.createElement('li');
                        li.classList.add('list-group-item', 'list-group-item-action');
                        li.setAttribute('data-filename', file.filename);
                        
                        li.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                ${file.filename}
                                <div class="file-details">
                                    <span class="badge ${file.is_editable ? 'badge-success' : 'badge-secondary'} badge-pill mr-2">
                                        ${formatFileSize(file.size)}
                                    </span>
                                    <small class="text-muted">${file.type || 'Unknown'}</small>
                                </div>
                            </div>
                        `;
                        
                        // Only add click listener for editable files
                        if (file.is_editable) {
                            li.addEventListener('click', () => loadCloudFileContent(file.filename));
                        } else {
                            li.classList.add('text-muted');
                            li.setAttribute('title', 'This file type cannot be edited');
                        }
                        
                        cloudFileList.appendChild(li);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading cloud storage files:', error);
                const cloudFileList = document.getElementById('cloud-file-list');
                const errorMessage = document.createElement('li');
                errorMessage.textContent = 'Failed to load cloud files. Please try again.';
                errorMessage.classList.add('list-group-item', 'text-danger');
                cloudFileList.appendChild(errorMessage);
            });
    }

    // Utility function to format file size
    function formatFileSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    // Initialize cloud storage file loading
    document.addEventListener('DOMContentLoaded', () => {
        // Check if the cloud file list container exists
        const cloudFileList = document.getElementById('cloud-file-list');
        if (cloudFileList) {
            loadCloudStorageFiles();
        }
    });

    // Function to load cloud files
    function loadCloudFiles() {
        console.log('Loading cloud files');
        fetch('/cloud/files')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(files => {
                console.log('Cloud files received:', files);
                const cloudFileList = document.getElementById('cloud-file-list');
                
                // Clear existing list
                cloudFileList.innerHTML = '';

                if (!files || files.length === 0) {
                    const noFilesMessage = document.createElement('li');
                    noFilesMessage.textContent = 'No cloud files found';
                    noFilesMessage.classList.add('list-group-item', 'text-muted');
                    cloudFileList.appendChild(noFilesMessage);
                } else {
                    files.forEach(file => {
                        const li = document.createElement('li');
                        li.classList.add('list-group-item', 'list-group-item-action');
                        li.setAttribute('data-filename', file.filename);
                        
                        // Convert size to human-readable format
                        const formatSize = (bytes) => {
                            if (bytes < 1024) return `${bytes} B`;
                            if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
                            return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
                        };

                        li.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                ${file.filename}
                                <div class="file-details">
                                    <span class="badge ${file.is_editable ? 'badge-success' : 'badge-secondary'} badge-pill mr-2">
                                        ${formatSize(file.size)}
                                    </span>
                                    <small class="text-muted">${file.type || 'Unknown'}</small>
                                </div>
                            </div>
                        `;
                        
                        // Only add click listener for editable files
                        if (file.is_editable) {
                            li.addEventListener('click', () => loadCloudFileContent(file.filename));
                        } else {
                            li.classList.add('text-muted');
                            li.setAttribute('title', 'This file type cannot be edited');
                        }
                        
                        cloudFileList.appendChild(li);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading cloud files:', error);
                const cloudFileList = document.getElementById('cloud-file-list');
                const errorMessage = document.createElement('li');
                errorMessage.textContent = 'Failed to load cloud files. Please try again.';
                errorMessage.classList.add('list-group-item', 'text-danger');
                cloudFileList.appendChild(errorMessage);
            });
    }

    // Initialize cloud file loading when the page loads
    document.addEventListener('DOMContentLoaded', () => {
        const cloudFileList = document.getElementById('cloud-file-list');
        if (cloudFileList) {
            // If the list is currently empty, try to load cloud files
            if (cloudFileList.children.length === 0) {
                loadCloudFiles();
            }
        }
    });

    // Debugging: Log any unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
    });
});
