/**
 * Live preview functionality for configuration changes
 */

// Global preview state
let previewMode = false;
let previewTimeout = null;
let previewConfig = {
    debounceMs: 500,
    autoRevertMs: 30000,
    refreshInterval: 10000
};

// Display image and status update functionality
function updateDisplayImage() {
    const img = document.getElementById('current-display-image');
    const timestamp = Date.now();

    if (!previewMode) {
        img.src = `/current-display-image?t=${timestamp}`;
    }
}

function updateDisplayMetadata() {
    fetch('/display-status')
        .then(response => response.json())
        .then(data => {
            const metadataEl = document.getElementById('display-metadata');
            const connectionEl = document.getElementById('display-connection-status');

            // Update connection status
            if (data.internal_app_connected) {
                connectionEl.className = 'status-indicator connected';
                connectionEl.title = 'Connected to display app';
            } else {
                connectionEl.className = 'status-indicator disconnected';
                connectionEl.title = 'Display app not connected';
            }

            // Update metadata
            const info = data.track_info || 'No track info';
            const timestamp = data.timestamp ?
                new Date(data.timestamp * 1000).toLocaleTimeString() :
                'Unknown time';

            metadataEl.textContent = `${info} (${timestamp})`;
        })
        .catch(error => {
            console.error('Failed to update display metadata:', error);
            const connectionEl = document.getElementById('display-connection-status');
            connectionEl.className = 'status-indicator disconnected';
            connectionEl.title = 'Connection error';
        });
}

function revertToLiveDisplay() {
    previewMode = false;
    const overlay = document.getElementById('display-overlay');
    const container = document.querySelector('.display-container');

    overlay.classList.add('hidden');
    container.classList.remove('preview-active');
    updateDisplayImage();
}

function generatePreview() {
    if (previewTimeout) {
        clearTimeout(previewTimeout);
    }

    previewTimeout = setTimeout(() => {
        const formData = new FormData(document.querySelector('form'));
        const overlay = document.getElementById('display-overlay');

        // Show loading state
        overlay.innerHTML = '<span class="overlay-text">Generating Preview...</span>';
        overlay.classList.remove('hidden');

        // Send preview request
        fetch('/preview-image', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                return response.blob();
            }
            throw new Error(`Preview generation failed: HTTP ${response.status}`);
        })
        .then(blob => {
            const img = document.getElementById('current-display-image');
            const container = document.querySelector('.display-container');

            // Show preview image
            const imageUrl = URL.createObjectURL(blob);
            img.src = imageUrl;

            // Update overlay to show preview state
            overlay.innerHTML = '<span class="overlay-text">PREVIEW</span>';
            container.classList.add('preview-active');
            previewMode = true;

            console.log('Preview generated successfully');

            // Auto-revert after configured time
            setTimeout(() => {
                revertToLiveDisplay();
            }, previewConfig.autoRevertMs);
        })
        .catch(error => {
            console.error('Preview failed:', error);

            // Show error in overlay briefly
            overlay.innerHTML = '<span class="overlay-text">Preview Failed</span>';
            overlay.style.background = 'rgba(244, 67, 54, 0.9)'; // Red background

            // Revert to live after error
            setTimeout(() => {
                overlay.style.background = 'rgba(255, 152, 0, 0.9)'; // Reset to orange
                revertToLiveDisplay();
            }, 2000);
        });
    }, previewConfig.debounceMs);
}

function shouldTriggerPreview(section, fieldName) {
    // Define which sections should trigger preview
    const previewSections = ['ANNIVERSARIES', 'IMAGE_RENDER', 'IMAGE_POSITION', 'DISPLAY', 'LAYOUT', 'IMAGE_QUALITY'];

    // Skip non-visual fields
    const skipFields = ['ZONES', 'MONITORING', 'NETWORK', 'TIMEOUTS'];
    if (skipFields.includes(section)) {
        return false;
    }

    // Skip specific fields that don't affect visual output
    const skipSpecificFields = [
        'loop_time', 'log_level', 'performance_logging',
        'health_script', 'health_recheck_interval',
        'allowed_zone_names', 'forbidden_zone_names',
        'web_auto_refresh_seconds', 'anniversary_check_interval',
        'performance_threshold_seconds', 'eink_success_threshold',
        'eink_warning_threshold', 'eink_check_interval',
        'preview_auto_revert_seconds', 'preview_debounce_ms'
    ];
    if (skipSpecificFields.some(field => fieldName.includes(field))) {
        return false;
    }

    return previewSections.includes(section);
}

function getFormSection(inputElement) {
    // Extract section name from input name
    const name = inputElement.name;
    if (name.includes('.')) {
        return name.split('.')[0];
    }
    if (name.startsWith('anniversary_')) {
        return 'ANNIVERSARIES';
    }
    return 'unknown';
}

function setupFormChangeDetection() {
    const form = document.querySelector('form');
    const inputs = form.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        // Use both 'input' and 'change' events for comprehensive coverage
        ['input', 'change'].forEach(eventType => {
            input.addEventListener(eventType, (e) => {
                const section = getFormSection(e.target);
                const fieldName = e.target.name || '';

                if (shouldTriggerPreview(section, fieldName)) {
                    // Add visual feedback
                    if (!previewMode) {
                        const overlay = document.getElementById('display-overlay');
                        overlay.innerHTML = '<span class="overlay-text">Generating Preview...</span>';
                        overlay.classList.remove('hidden');
                    }

                    generatePreview();
                }
            });
        });

        // Special handling for file inputs (anniversary images)
        if (input.type === 'file' && input.name.startsWith('anniversary_images_')) {
            input.addEventListener('change', () => {
                if (input.files.length > 0) {
                    // Note: File previews are limited - files aren't sent to preview
                    console.log(`File uploaded for ${input.name}, preview will use existing images`);
                    generatePreview();
                }
            });
        }
    });

    console.log(`Set up change detection for ${inputs.length} form inputs`);
}

function setupStickyImageShrinking() {
    // Functionality removed
}

function initializePreview(config) {
    previewConfig = { ...previewConfig, ...config };
    
    // Initial load and periodic updates
    updateDisplayImage();
    updateDisplayMetadata();
    setupFormChangeDetection();
    setupStickyImageShrinking();

    // Auto-refresh at configured interval
    setInterval(() => {
        if (!previewMode) {
            updateDisplayImage();
            updateDisplayMetadata();
        }
    }, previewConfig.refreshInterval);

    // Refresh button
    document.getElementById('refresh-display').addEventListener('click', () => {
        revertToLiveDisplay();
        updateDisplayMetadata();
    });
}

// Expose functions globally
window.updateDisplayImage = updateDisplayImage;
window.updateDisplayMetadata = updateDisplayMetadata;
window.revertToLiveDisplay = revertToLiveDisplay;
window.generatePreview = generatePreview;
window.initializePreview = initializePreview;