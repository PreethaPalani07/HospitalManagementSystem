// Hospital Management App script loaded.
console.log("Hospital Management App JS Loaded");

// Example for future confirmation dialogs
document.addEventListener('DOMContentLoaded', function() {
    const deleteForms = document.querySelectorAll('form[action*="/delete/"]'); // More specific selector
    deleteForms.forEach(form => {
        form.addEventListener('submit', function(event) {
            const message = this.getAttribute('data-confirm-message') || 'Are you sure you want to delete this item? This action cannot be undone.';
            if (!confirm(message)) {
                event.preventDefault(); // Stop the form submission
            }
        });
    });

    // You might update the onsubmit attribute in the HTML to call a function instead
    // or use data attributes to customize messages further.
});