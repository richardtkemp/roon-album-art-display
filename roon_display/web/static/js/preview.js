/**
 * Live preview functionality for configuration changes.
 *
 * When the web UI form has unsaved changes that affect visual output,
 * the display image is rendered via the preview endpoint using the
 * form's current values.  This persists across art changes — every
 * periodic refresh re-fetches through the preview path until the user
 * saves or explicitly resets.
 */

// Global preview state
let previewMode = false;
let previewTimeout = null;
let previewConfig = {
    debounceMs: 500,
    refreshInterval: 10000
};

// ── Display image helpers ────────────────────────────────────────────

function updateDisplayImage() {
    if (previewMode) {
        // Form has unsaved visual changes — fetch via preview endpoint
        // so new art is also rendered with the form's config.
        fetchPreviewImage();
    } else {
        const img = document.getElementById('current-display-image');
        img.src = `/current-display-image?t=${Date.now()}`;
    }
}

const ROON_STATE_LABELS = {
    'searching':    'Searching for Roon...',
    'connecting':   'Connecting to Roon...',
    'connected':    'Connected to Roon',
    'disconnected': 'Roon disconnected',
};

function updateDisplayMetadata() {
    fetch('/display-status')
        .then(response => response.json())
        .then(data => {
            const metadataEl = document.getElementById('display-metadata');
            const connectionEl = document.getElementById('display-connection-status');
            const roonStatusEl = document.getElementById('roon-status');

            // Update connection dot (internal app reachability)
            if (data.internal_app_connected) {
                connectionEl.className = 'status-indicator connected';
                connectionEl.title = 'Connected to display app';
            } else {
                connectionEl.className = 'status-indicator disconnected';
                connectionEl.title = 'Display app not connected';
            }

            // Update Roon connection status heading
            if (roonStatusEl) {
                const label = ROON_STATE_LABELS[data.roon_state] || 'Connecting...';
                roonStatusEl.textContent = label;
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

// ── Preview logic ────────────────────────────────────────────────────

/**
 * Check whether the form has unsaved changes that affect visual output.
 */
function hasVisualChanges() {
    const form = document.querySelector('form');
    const fields = form.querySelectorAll('input, select, textarea');

    for (const field of fields) {
        const name = field.name;
        if (!name) continue;

        const section = name.includes('.') ? name.split('.')[0] : 'unknown';
        const fieldName = name.includes('.') ? name.split('.')[1] : name;
        if (!shouldTriggerPreview(section, fieldName)) continue;

        const saved = field.getAttribute('data-default');
        if (saved === null) continue;

        const current = field.type === 'checkbox' ? field.checked.toString() : field.value;
        if (current !== saved) return true;
    }
    return false;
}

/**
 * POST current form data to the preview endpoint and display the result.
 */
function fetchPreviewImage() {
    const formData = new FormData(document.querySelector('form'));

    fetch('/preview-image', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.ok) return response.blob();
        return response.json().then(data => {
            throw new Error(data.error || `Preview failed: HTTP ${response.status}`);
        });
    })
    .then(blob => {
        const img = document.getElementById('current-display-image');
        const container = document.querySelector('.display-container');
        const overlay = document.getElementById('display-overlay');

        img.src = URL.createObjectURL(blob);

        overlay.innerHTML = '<span class="overlay-text">PREVIEW</span>';
        overlay.classList.remove('hidden');
        container.classList.add('preview-active');
    })
    .catch(error => {
        console.error('Preview failed:', error);
        const overlay = document.getElementById('display-overlay');
        overlay.innerHTML = `<span class="overlay-text overlay-error">${error.message}</span>`;
        overlay.classList.remove('hidden');
    });
}

/**
 * Called when a visual config field changes.  Debounces, then enters
 * preview mode (if not already) and fetches a preview image.
 */
function generatePreview() {
    if (previewTimeout) {
        clearTimeout(previewTimeout);
    }

    previewTimeout = setTimeout(() => {
        const overlay = document.getElementById('display-overlay');

        if (!previewMode) {
            overlay.innerHTML = '<span class="overlay-text">Generating Preview...</span>';
            overlay.classList.remove('hidden');
        }

        previewMode = true;
        fetchPreviewImage();
    }, previewConfig.debounceMs);
}

/**
 * Exit preview mode and return to showing the live display image.
 */
function revertToLiveDisplay() {
    previewMode = false;
    if (previewTimeout) {
        clearTimeout(previewTimeout);
        previewTimeout = null;
    }
    const overlay = document.getElementById('display-overlay');
    const container = document.querySelector('.display-container');

    overlay.classList.add('hidden');
    container.classList.remove('preview-active');
    updateDisplayImage();
}

// ── Form change detection ────────────────────────────────────────────

function shouldTriggerPreview(section, fieldName) {
    const previewSections = ['ANNIVERSARIES', 'IMAGE_RENDER', 'IMAGE_POSITION', 'DISPLAY', 'LAYOUT', 'THUMBNAILS', 'TEXT_RENDERING'];

    const skipFields = ['ZONES', 'MONITORING', 'NETWORK', 'TIMEOUTS'];
    if (skipFields.includes(section)) return false;

    const skipSpecificFields = [
        'loop_time', 'log_level', 'performance_logging',
        'health_script', 'health_recheck_interval',
        'allowed_zone_names', 'forbidden_zone_names',
        'web_auto_refresh_seconds', 'anniversary_check_interval',
        'performance_threshold_seconds', 'eink_success_threshold',
        'preview_debounce_ms'
    ];
    if (skipSpecificFields.some(field => fieldName.includes(field))) return false;

    return previewSections.includes(section);
}

function getFormSection(inputElement) {
    const name = inputElement.name;
    if (name.includes('.')) return name.split('.')[0];
    if (name.startsWith('anniversary_')) return 'ANNIVERSARIES';
    return 'unknown';
}

function setupFormChangeDetection() {
    const form = document.querySelector('form');
    const inputs = form.querySelectorAll('input, select, textarea');

    inputs.forEach(input => {
        ['input', 'change'].forEach(eventType => {
            input.addEventListener(eventType, (e) => {
                const section = getFormSection(e.target);
                const fieldName = e.target.name || '';

                if (shouldTriggerPreview(section, fieldName)) {
                    // If the form is back to saved state, exit preview
                    if (!hasVisualChanges()) {
                        revertToLiveDisplay();
                        return;
                    }
                    generatePreview();
                }
            });
        });

        if (input.type === 'file' && input.name.startsWith('anniversary_images_')) {
            input.addEventListener('change', () => {
                if (input.files.length > 0) {
                    console.log(`File uploaded for ${input.name}, preview will use existing images`);
                    generatePreview();
                }
            });
        }
    });

    console.log(`Set up change detection for ${inputs.length} form inputs`);
}

// ── Sticky image shrinking ───────────────────────────────────────────

function setupStickyImageShrinking() {
    class ScrollShrinkEffect {
        constructor(containerSelector) {
            this.container = document.querySelector(containerSelector);
            this.positioningContainer = this.container.parentElement;

            this.containerHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--display-height')) || 600;

            this.initialContainerWidth = 0;
            this.initialContainerHeight = 0;

            this.minScale = 0.4;

            this.isFixed = false;
            this.shrinkStartY = 0;
            this.shrinkEndY = 0;
            this.containerRightEdge = 0;

            this.init();
        }

        init() {
            this.actualContainerWidth = this.container.getBoundingClientRect().width;

            const containerRect = this.container.getBoundingClientRect();
            this.initialContainerWidth = containerRect.width;

            const image = this.container.querySelector('img');
            const computed = getComputedStyle(this.container);
            const vpad = parseFloat(computed.paddingTop) + parseFloat(computed.paddingBottom);
            this.containerHeight = image.offsetHeight + vpad;
            this.initialContainerHeight = this.containerHeight;

            if (this.containerHeight > this.initialContainerWidth) {
                this.containerHeight = this.initialContainerWidth;
                this.initialContainerHeight = this.containerHeight;
            }
            console.log(`Setting container to ${this.containerHeight}px`);
            document.documentElement.style.setProperty('--display-height', `${this.containerHeight}px`);

            this.calculateScrollPositions();
            this.updateContainerPosition();

            this.boundScrollHandler = this.throttle(this.handleScroll.bind(this), 16);
            window.addEventListener('scroll', this.boundScrollHandler);
            window.addEventListener('resize', this.handleResize.bind(this));
        }

        calculateScrollPositions() {
            const positioningRect = this.positioningContainer.getBoundingClientRect();
            const positioningTop = positioningRect.top + window.pageYOffset;

            this.containerRightEdge = positioningRect.right;
            this.shrinkStartY = positioningTop;

            const maxShrinkDistance = this.containerHeight * (1 - this.minScale);
            this.shrinkEndY = this.shrinkStartY + maxShrinkDistance;
        }

        handleScroll() {
            this.updateContainerPosition();
        }

        handleResize() {
            if (!this.isFixed) {
                this.actualContainerWidth = this.container.getBoundingClientRect().width;

                const containerRect = this.container.getBoundingClientRect();
                this.initialContainerWidth = containerRect.width;
                this.initialContainerHeight = containerRect.height;
            }

            const oldContainerHeight = this.containerHeight;
            this.containerHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--display-height')) || 600;

            this.calculateScrollPositions();
            this.updateContainerPosition();
        }

        updateContainerPosition() {
            const scrollY = window.pageYOffset;

            if (scrollY < this.shrinkStartY) {
                this.container.classList.remove('fixed');
                this.container.style.transition = '';
                this.container.style.transform = 'none';
                this.container.style.right = 'auto';
                this.container.style.left = '0';
                this.container.style.width = '';
                this.container.style.height = '';
                this.isFixed = false;
            } else if (scrollY >= this.shrinkStartY && scrollY <= this.shrinkEndY) {
                if (!this.isFixed) {
                    this.container.classList.add('fixed');
                    this.container.style.transition = "transform 0.15s ease-out";
                    this.container.style.width = `${this.initialContainerWidth}px`;
                    this.container.style.height = `${this.initialContainerHeight}px`;
                    const rightDistance = window.innerWidth - this.containerRightEdge;
                    this.container.style.right = `${rightDistance}px`;
                    this.container.style.left = 'auto';
                    this.isFixed = true;
                }

                const progress = (scrollY - this.shrinkStartY) / (this.shrinkEndY - this.shrinkStartY);
                const scale = 1 - (progress * (1 - this.minScale));

                requestAnimationFrame(() => {
                    this.container.style.transform = `scale(${scale})`;
                });
            } else {
                this.container.classList.add('fixed');

                requestAnimationFrame(() => {
                    this.container.style.transform = `scale(${this.minScale})`;
                });

                if (!this.isFixed) {
                    const rightDistance = window.innerWidth - this.containerRightEdge;
                    this.container.style.right = `${rightDistance}px`;
                    this.container.style.left = 'auto';
                }

                this.container.style.width = `${this.initialContainerWidth}px`;
                this.container.style.height = `${this.initialContainerHeight}px`;
                this.isFixed = true;
            }
        }

        updateDimensions(newConfigWidth, newConfigHeight) {
            const oldContainerHeight = this.containerHeight;
            this.containerHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--display-height')) || 600;

            if (!this.isFixed) {
                this.actualContainerWidth = this.container.getBoundingClientRect().width;

                const containerRect = this.container.getBoundingClientRect();
                this.initialContainerWidth = containerRect.width;
                this.initialContainerHeight = containerRect.height;
            }

            this.calculateScrollPositions();
            this.updateContainerPosition();
        }

        throttle(func, limit) {
            let inThrottle;
            return function() {
                const args = arguments;
                const context = this;
                if (!inThrottle) {
                    func.apply(context, args);
                    inThrottle = true;
                    setTimeout(() => inThrottle = false, limit);
                }
            }
        }

        destroy() {
            window.removeEventListener('scroll', this.boundScrollHandler);
            window.removeEventListener('resize', this.handleResize);
        }
    }

    window.scrollShrinkEffect = new ScrollShrinkEffect('.display-container');
}

// ── Initialization ───────────────────────────────────────────────────

function initializePreview(config) {
    previewConfig = { ...previewConfig, ...config };

    updateDisplayImage();
    updateDisplayMetadata();
    setupFormChangeDetection();

    const displayImg = document.getElementById('current-display-image');
    const initShrink = () => { setupStickyImageShrinking(); };
    displayImg.addEventListener('load', initShrink, { once: true });
    displayImg.addEventListener('error', initShrink, { once: true });

    // Periodic refresh — uses preview endpoint when form is dirty
    setInterval(() => {
        updateDisplayImage();
        updateDisplayMetadata();
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
