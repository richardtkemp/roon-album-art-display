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

                // Handle web_image_max_width changes for layout updates
                if (fieldName === 'IMAGE_QUALITY.web_image_max_width') {
                    const newConfigWidth = parseInt(e.target.value) || 600;
                    
                    // Update global config width
                    window.configImageWidth = newConfigWidth;
                    
                    // Calculate responsive width for height (width is handled by JavaScript)
                    const responsiveWidth = window.calculateResponsiveWidth ? 
                        window.calculateResponsiveWidth(newConfigWidth) : newConfigWidth;
                    
                    document.documentElement.style.setProperty('--display-height', `${responsiveWidth}px`);
                    
                    // Update scroll effect with new config dimensions
                    if (window.scrollShrinkEffect) {
                        window.scrollShrinkEffect.updateDimensions(newConfigWidth, newConfigWidth);
                    }
                }

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
    class ScrollShrinkEffect {
        constructor(containerSelector) {
            this.container = document.querySelector(containerSelector);
            this.positioningContainer = this.container.parentElement;
            
            // Track config width (original user setting) vs responsive width (viewport-constrained)
            this.configWidth = window.configImageWidth || 600;
            this.configHeight = this.configWidth; // Assume square
            this.responsiveWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--display-width')) || 600;
            this.responsiveHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--display-height')) || 600;
            
            this.minScale = 0.4; // 40% of original size
            
            this.isFixed = false;
            this.shrinkStartY = 0;
            this.shrinkEndY = 0;
            this.containerRightEdge = 0;
            
            this.init();
        }
        
        init() {
            // Capture the container's actual rendered width before any scroll effects
            this.actualContainerWidth = this.container.getBoundingClientRect().width;
            
            // Calculate scroll positions
            this.calculateScrollPositions();
            
            // Set initial position
            this.updateContainerPosition();
            
            // Bind scroll event with throttling
            this.boundScrollHandler = this.throttle(this.handleScroll.bind(this), 16);
            window.addEventListener('scroll', this.boundScrollHandler);
            window.addEventListener('resize', this.handleResize.bind(this));
        }
        
        calculateScrollPositions() {
            const positioningRect = this.positioningContainer.getBoundingClientRect();
            const positioningTop = positioningRect.top + window.pageYOffset;
            
            // Calculate where the container's right edge is on the page
            this.containerRightEdge = positioningRect.right;
            
            // When positioning container top hits viewport top
            this.shrinkStartY = positioningTop;
            
            // Calculate how much scroll distance we need to shrink to minimum
            // Use responsive height for scroll distance calculation
            const maxShrinkDistance = this.responsiveHeight * (1 - this.minScale);
            this.shrinkEndY = this.shrinkStartY + maxShrinkDistance;
        }
        
        handleScroll() {
            this.updateContainerPosition();
        }
        
        handleResize() {
            // Recapture the container's actual rendered width after resize
            if (!this.isFixed) {
                this.actualContainerWidth = this.container.getBoundingClientRect().width;
            }
            
            // Recalculate responsive width on viewport changes using config width as base
            if (window.calculateResponsiveWidth) {
                const newResponsiveWidth = window.calculateResponsiveWidth(this.configWidth);
                const newResponsiveHeight = newResponsiveWidth; // Assume square
                
                if (newResponsiveWidth !== this.responsiveWidth) {
                    // Update dimensions if responsive width changed
                    document.documentElement.style.setProperty('--display-height', `${newResponsiveHeight}px`);
                    
                    // Update responsive dimensions but keep config dimensions unchanged
                    this.responsiveWidth = newResponsiveWidth;
                    this.responsiveHeight = newResponsiveHeight;
                    
                    this.calculateScrollPositions();
                    this.updateContainerPosition();
                } else {
                    // Just recalculate positions if width didn't change
                    this.calculateScrollPositions();
                    this.updateContainerPosition();
                }
            } else {
                this.calculateScrollPositions();
                this.updateContainerPosition();
            }
        }
        
        updateContainerPosition() {
            const scrollY = window.pageYOffset;
            
            if (scrollY < this.shrinkStartY) {
                // Before shrinking starts - normal position
                this.container.classList.remove('fixed');
                this.container.style.transform = 'scale(1)';
                this.container.style.right = 'auto';
                this.container.style.left = '0';
                this.container.style.width = '';  // Remove any inline width to use CSS
                this.isFixed = false;
            } else if (scrollY >= this.shrinkStartY && scrollY <= this.shrinkEndY) {
                // During shrinking phase
                if (!this.isFixed) {
                    this.container.classList.add('fixed');
                    // Set explicit width to maintain current size
                    this.container.style.width = `${this.actualContainerWidth}px`;
                    // Position container so its right edge stays in the same place
                    const rightDistance = window.innerWidth - this.containerRightEdge;
                    this.container.style.right = `${rightDistance}px`;
                    this.container.style.left = 'auto';
                    this.isFixed = true;
                }
                
                const progress = (scrollY - this.shrinkStartY) / (this.shrinkEndY - this.shrinkStartY);
                const scale = 1 - (progress * (1 - this.minScale));
                this.container.style.transform = `scale(${scale})`;
            } else {
                // After shrinking is complete - stay at minimum size
                this.container.classList.add('fixed');
                if (!this.isFixed) {
                    // Set explicit width to maintain current size
                    this.container.style.width = `${this.actualContainerWidth}px`;
                    const rightDistance = window.innerWidth - this.containerRightEdge;
                    this.container.style.right = `${rightDistance}px`;
                    this.container.style.left = 'auto';
                }
                this.container.style.transform = `scale(${this.minScale})`;
                this.isFixed = true;
            }
        }
        
        updateDimensions(newConfigWidth, newConfigHeight) {
            // Update config dimensions (user's original setting)
            this.configWidth = newConfigWidth;
            this.configHeight = newConfigHeight;
            
            // Recalculate responsive dimensions from new config
            if (window.calculateResponsiveWidth) {
                this.responsiveWidth = window.calculateResponsiveWidth(this.configWidth);
                this.responsiveHeight = this.responsiveWidth; // Assume square
                
                // Update CSS custom properties for height only (width handled by JavaScript)
                document.documentElement.style.setProperty('--display-height', `${this.responsiveHeight}px`);
            } else {
                // Fallback if responsive calculation not available
                this.responsiveWidth = newConfigWidth;
                this.responsiveHeight = newConfigHeight;
            }
            
            // Recapture actual container width after config change
            if (!this.isFixed) {
                this.actualContainerWidth = this.container.getBoundingClientRect().width;
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
    
    // Initialize the effect
    window.scrollShrinkEffect = new ScrollShrinkEffect('.display-container');
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