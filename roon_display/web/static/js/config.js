/**
 * Configuration form handling and tab functionality
 */

// Global variables
let anniversaryCounter = 0; // Will be set by template

// Tab switching functionality
function switchTab(tabName) {
    // Hide all tab contents
    const tabContents = document.querySelectorAll('.tab-content');
    tabContents.forEach(content => content.classList.remove('active'));

    // Remove active class from all tab buttons
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => button.classList.remove('active'));

    // Show selected tab content
    document.getElementById('content-' + tabName).classList.add('active');

    // Add active class to selected tab button
    document.getElementById('tab-' + tabName).classList.add('active');
}

// AJAX form submission
function submitForm(event) {
    event.preventDefault();

    const form = event.target;
    const submitButton = document.getElementById('apply-btn');
    const messageArea = document.getElementById('message-area');
    const messageContent = document.getElementById('message-content');

    // Show loading state
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Applying...';
    submitButton.disabled = true;

    // Hide any previous messages
    messageArea.style.display = 'none';

    // Create FormData from form
    const formData = new FormData(form);

    // Send AJAX request
    fetch(window.location.pathname, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        // Show success/error message
        messageContent.textContent = data.message;
        messageContent.className = data.success ? 'flash-success' : 'flash-error';
        messageArea.style.display = 'block';

        // Auto-hide success messages after 3 seconds
        if (data.success) {
            setTimeout(() => {
                messageArea.style.display = 'none';
            }, 3000);
        }
    })
    .catch(error => {
        console.error('Form submission error:', error);
        messageContent.textContent = `Error: ${error.message}`;
        messageContent.className = 'flash-error';
        messageArea.style.display = 'block';
    })
    .finally(() => {
        // Restore button state
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    });
}

// Anniversary management functions
function addAnniversary() {
    const container = document.getElementById('anniversary-entries');
    const div = document.createElement('div');
    div.className = 'anniversary-entry';
    div.innerHTML = `
        <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
            <label style="min-width: 100px; font-weight: bold;">Name:</label>
            <input type="text" name="anniversary_name_${anniversaryCounter}" value="" style="flex: 1;" placeholder="birthday_john">
            <button type="button" onclick="removeAnniversary(this)" style="background: #f44336; color: white; border: none; padding: 8px 12px; border-radius: 3px; cursor: pointer;">Remove</button>
        </div>
        <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
            <label style="min-width: 100px; font-weight: bold;">Date:</label>
            <input type="text" name="anniversary_date_${anniversaryCounter}" value="" style="width: 120px;" placeholder="15/03/1990">
            <span style="color: #666; font-size: 0.9em;">dd/mm/yyyy format</span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
            <label style="min-width: 100px; font-weight: bold;">Message:</label>
            <input type="text" name="anniversary_message_${anniversaryCounter}" value="" style="flex: 1;" placeholder="Happy \${years} birthday John!">
            <span style="color: #666; font-size: 0.9em;">Use \${years} for age</span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
            <label style="min-width: 100px; font-weight: bold;">Wait Time:</label>
            <input type="text" name="anniversary_wait_${anniversaryCounter}" value="" style="width: 150px;" placeholder="30 minutes">
            <span style="color: #666; font-size: 0.9em;">e.g., "30 minutes", "2 hours"</span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <label style="min-width: 100px; font-weight: bold;">Images:</label>
            <input type="file" name="anniversary_images_${anniversaryCounter}" multiple accept="image/*" style="flex: 1;">
            <span style="color: #666; font-size: 0.9em;">Upload images (JPG, PNG, etc.)</span>
        </div>
    `;
    container.appendChild(div);
    anniversaryCounter++;
}

function removeAnniversary(button) {
    button.closest('.anniversary-entry').remove();
}

// Initialize anniversary counter from template
function setAnniversaryCounter(count) {
    anniversaryCounter = count;
}

// Expose functions globally
window.switchTab = switchTab;
window.submitForm = submitForm;
window.addAnniversary = addAnniversary;
window.removeAnniversary = removeAnniversary;
window.setAnniversaryCounter = setAnniversaryCounter;