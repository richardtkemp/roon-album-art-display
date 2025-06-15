/**
 * Configuration form handling and tab functionality
 */

// Global variables
let anniversaryCounter = 0; // Will be set by template
let originalValues = {}; // Store original form values for restore
let defaultValues = {}; // Store default values for reset

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

// Store original and default values for restore/reset functionality
function storeFormValues() {
    const form = document.querySelector('form');
    const inputs = form.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        const name = input.name;
        if (name) {
            // Store original value
            if (input.type === 'checkbox') {
                originalValues[name] = input.checked;
            } else {
                originalValues[name] = input.value;
            }

            // Debug logging for image_offset fields
            if (name === 'IMAGE_POSITION.image_offset_x' || name === 'IMAGE_POSITION.image_offset_y') {
                console.log(`[DEBUG] storeFormValues: ${name} = "${input.value}" (type: ${input.type}, id: ${input.id})`);
            }

            // Store default value from data attribute (set by backend)
            const defaultValue = input.getAttribute('data-default');
            if (defaultValue !== null) {
                if (input.type === 'checkbox') {
                    defaultValues[name] = defaultValue.toLowerCase() === 'true';
                } else {
                    defaultValues[name] = defaultValue;
                }
            }
        }
    });

    // Log what got stored for our debug fields
    console.log('[DEBUG] storeFormValues complete - originalValues for image_offset fields:', {
        'IMAGE_POSITION.image_offset_x': originalValues['IMAGE_POSITION.image_offset_x'],
        'IMAGE_POSITION.image_offset_y': originalValues['IMAGE_POSITION.image_offset_y']
    });
}

// Get all form fields within a specific tab
function getTabFormFields(tabName) {
    const tabContent = document.getElementById(`content-${tabName}`);
    if (!tabContent) return [];

    return tabContent.querySelectorAll('input, select, textarea');
}

// Helper function to set field value and sync range inputs
function setFieldValue(field, value) {
    if (field.type === 'checkbox') {
        field.checked = value;
    } else {
        field.value = value;
        // If this is a range input, sync its corresponding text input
        if (field.type === 'range') {
            syncRangeToText(field);
        }
    }
}

// Generic function to update tab values from a values object
function updateTabValues(tabName, valuesObject, logMessage) {
    const fields = getTabFormFields(tabName);

    fields.forEach(field => {
        const name = field.name;
        if (name && valuesObject.hasOwnProperty(name)) {
            setFieldValue(field, valuesObject[name]);
        }
    });

    console.log(logMessage);
}

// Restore tab values to their saved (original) values
function restoreTabValues(tabName) {
    updateTabValues(tabName, originalValues, `Restored ${tabName} tab to saved values`);
}

// Reset tab values to defaults with confirmation
function resetTabToDefaults(tabName) {
    const confirmed = confirm(
        `Are you sure you want to reset all values in the "${tabName}" tab to their default values?\n\n` +
        'This will overwrite any unsaved changes in this tab.'
    );

    if (!confirmed) return;

    updateTabValues(tabName, defaultValues, `Reset ${tabName} tab to default values`);
}

// Initialize form value storage when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Store original and default values after form is fully loaded
    setTimeout(storeFormValues, 100);
});

// Range/text input synchronization functions
function syncRangeToText(rangeInput) {
    const textInputId = rangeInput.id + '_text';
    const textInput = document.getElementById(textInputId);
    if (textInput) {
        textInput.value = rangeInput.value;
    }
}

function syncTextToRange(textInput, rangeInputId) {
    const rangeInput = document.getElementById(rangeInputId);
    if (rangeInput) {
        // Validate the text input value against range constraints
        let value = parseFloat(textInput.value);
        const min = parseFloat(rangeInput.min);
        const max = parseFloat(rangeInput.max);
        const step = parseFloat(rangeInput.step) || 1;

        // Clamp value to min/max bounds
        if (!isNaN(min) && value < min) value = min;
        if (!isNaN(max) && value > max) value = max;

        // Round to nearest step if step is defined
        if (!isNaN(step) && step > 0) {
            value = Math.round(value / step) * step;
        }

        // Update both inputs with the validated value
        rangeInput.value = value;
        textInput.value = value;
    }
}

// Restore all values across all tabs
function restoreAllValues() {
    const form = document.querySelector('form');
    const fields = form.querySelectorAll('input, select, textarea');

    console.log('[DEBUG] restoreAllValues starting - using data-default attributes from config file');

    let previewRelevantChanges = false;

    fields.forEach(field => {
        const name = field.name;
        if (name) {
            // Get the saved config value from data-default attribute
            const savedValue = field.getAttribute('data-default');

            if (savedValue !== null) {
                const currentValue = field.type === 'checkbox' ? field.checked.toString() : field.value;

                // Check if this change affects preview and if the value actually changed
                if (currentValue !== savedValue) {
                    // Extract section from field name to check if it's preview-relevant
                    const section = name.includes('.') ? name.split('.')[0] : 'unknown';
                    const previewSections = ['IMAGE_RENDER', 'IMAGE_POSITION', 'DISPLAY', 'LAYOUT', 'IMAGE_QUALITY'];

                    if (previewSections.includes(section)) {
                        previewRelevantChanges = true;
                        console.log(`[DEBUG] Preview-relevant change detected: ${name} "${currentValue}" → "${savedValue}"`);
                    }
                }

                // Debug logging for image_offset fields
                if (name === 'IMAGE_POSITION.image_offset_x' || name === 'IMAGE_POSITION.image_offset_y') {
                    console.log(`[DEBUG] restoreAllValues: Found field ${name} (type: ${field.type}, id: ${field.id})`);
                    console.log(`[DEBUG] restoreAllValues: Current value: "${currentValue}", restoring to config value: "${savedValue}"`);
                }

                setFieldValue(field, savedValue);

                // Debug logging after restore
                if (name === 'IMAGE_POSITION.image_offset_x' || name === 'IMAGE_POSITION.image_offset_y') {
                    console.log(`[DEBUG] restoreAllValues: After restore, ${name} value is: "${field.value}"`);
                }
            } else if (name === 'IMAGE_POSITION.image_offset_x' || name === 'IMAGE_POSITION.image_offset_y') {
                // Special case: field found but no data-default attribute
                console.log(`[DEBUG] restoreAllValues: Field ${name} found but no data-default attribute! (type: ${field.type}, id: ${field.id})`);
            }
        }
    });

    // Trigger preview if any preview-relevant values were changed
    if (previewRelevantChanges) {
        console.log('Preview-relevant values were restored, triggering preview...');
        if (typeof generatePreview === 'function') {
            generatePreview();
        } else {
            console.warn('generatePreview function not available');
        }
    }

    console.log('Restored all tabs to saved config file values');
}

// Reset all values to defaults across all tabs with confirmation
function resetAllToDefaults() {
    const confirmed = confirm(
        'Are you sure you want to reset ALL configuration values to their default values?\n\n' +
        'This will overwrite any unsaved changes across all tabs.'
    );

    if (!confirmed) return;

    const form = document.querySelector('form');
    const fields = form.querySelectorAll('input, select, textarea');

    fields.forEach(field => {
        const name = field.name;
        if (name && defaultValues.hasOwnProperty(name)) {
            setFieldValue(field, defaultValues[name]);
        }
    });

    console.log('Reset all tabs to default values');
}

// Expose functions globally
window.switchTab = switchTab;
window.submitForm = submitForm;
window.addAnniversary = addAnniversary;
window.removeAnniversary = removeAnniversary;
window.setAnniversaryCounter = setAnniversaryCounter;
window.restoreTabValues = restoreTabValues;
window.resetTabToDefaults = resetTabToDefaults;
window.restoreAllValues = restoreAllValues;
window.resetAllToDefaults = resetAllToDefaults;
window.syncRangeToText = syncRangeToText;
window.syncTextToRange = syncTextToRange;
