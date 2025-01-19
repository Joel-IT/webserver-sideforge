document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners for server instance actions
    const manageButtons = document.querySelectorAll('.btn-group .btn-outline-primary');
    const stopButtons = document.querySelectorAll('.btn-group .btn-outline-danger');

    manageButtons.forEach(button => {
        button.addEventListener('click', function() {
            const serverName = this.closest('tr').querySelector('td:first-child').textContent;
            alert(`Manage server: ${serverName}`);
            // TODO: Implement server management functionality
        });
    });

    stopButtons.forEach(button => {
        button.addEventListener('click', function() {
            const serverName = this.closest('tr').querySelector('td:first-child').textContent;
            const confirmStop = confirm(`Are you sure you want to stop server: ${serverName}?`);
            
            if (confirmStop) {
                // TODO: Implement server stop functionality via AJAX
                alert(`Stopping server: ${serverName}`);
            }
        });
    });
});
