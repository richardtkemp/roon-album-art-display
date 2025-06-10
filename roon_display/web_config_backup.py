#!/usr/bin/env python3
"""Minimalist web server for Roon display configuration management."""

import configparser
import io
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)
from PIL import Image
from werkzeug.utils import secure_filename

from .config.config_manager import ConfigManager
from .utils import (
    ensure_anniversary_dir_exists,
    get_current_image_key,
    get_extra_images_dir,
    get_last_track_time,
    get_saved_image_dir,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "roon-display-config-key"  # Simple key for flash messages

# HTML template for dynamic config interface
CONFIG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Roon Display Configuration</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .section { margin-bottom: 30px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        .section h2 { margin-top: 0; color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 5px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="number"], select, textarea {
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 3px; box-sizing: border-box;
        }
        input[type="checkbox"] { margin-right: 8px; }
        .comment { font-size: 0.9em; color: #666; font-style: italic; margin-top: 5px; }
        .button-group { text-align: center; margin-top: 30px; }
        button {
            background-color: #4CAF50; color: white; padding: 12px 24px;
            border: none; border-radius: 4px; cursor: pointer; margin: 0 10px;
        }
        button:hover { background-color: #45a049; }
        .apply-btn { background-color: #4CAF50; }
        .apply-btn:hover { background-color: #45a049; }
        .flash-messages { margin-bottom: 20px; }
        .flash-success { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 4px; }
        .flash-error { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 4px; }
        .form-message { margin-top: 15px; padding: 10px; border-radius: 4px; }
        .form-message.success { background-color: #d4edda; color: #155724; }
        .form-message.error { background-color: #f8d7da; color: #721c24; }
        .textarea-large { height: 120px; }
        .thumbnail-container {
            display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px;
            padding: 10px; background: #f8f8f8; border-radius: 4px;
        }
        .thumbnail-item {
            position: relative; display: inline-block; border: 2px solid #ddd;
            border-radius: 4px; overflow: hidden; background: white;
        }
        .thumbnail-item img {
            width: 100px; height: 100px; object-fit: cover; display: block;
            margin: 0; padding: 0;
        }
        .thumbnail-delete {
            position: absolute; top: 2px; right: 2px; background: rgba(244, 67, 54, 0.9);
            color: white; border: none; border-radius: 50%; width: 16px; height: 16px;
            cursor: pointer; font-size: 10px; line-height: 1; font-weight: bold;
            display: flex; align-items: center; justify-content: center;
            min-width: 16px; max-width: 16px; min-height: 16px; max-height: 16px;
            padding: 0; margin: 0; box-sizing: border-box;
        }
        .thumbnail-delete:hover { background: rgba(244, 67, 54, 1); }
        .thumbnail-filename {
            position: absolute; bottom: 0; left: 0; right: 0;
            background: rgba(0,0,0,0.7); color: white; font-size: 10px;
            padding: 2px 4px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;
        }
        .display-preview-section {
            background: #ffffff; border: 1px solid #ddd; border-radius: 8px;
            padding: 20px; margin-bottom: 30px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .display-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 15px; font-size: 1.3em; font-weight: bold;
        }
        .display-controls { display: flex; align-items: center; gap: 10px; }
        .control-btn {
            background: #f0f0f0; border: 1px solid #ccc; padding: 6px 12px;
            border-radius: 4px; cursor: pointer; font-size: 0.9em;
        }
        .control-btn:hover { background: #e0e0e0; }
        .display-container {
            position: relative; text-align: center; margin-bottom: 15px;
            background: #f8f8f8; border-radius: 6px; padding: 10px;
        }
        #current-display-image {
            max-width: 100%; max-height: 400px; border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .display-overlay {
            position: absolute; top: 15px; right: 15px;
            background: rgba(255, 152, 0, 0.9); color: white;
            padding: 4px 12px; border-radius: 12px; font-size: 0.8em; font-weight: bold;
        }
        .display-overlay.hidden { display: none; }
        .display-info {
            font-size: 0.9em; color: #666; text-align: center;
            padding: 8px; background: #f0f0f0; border-radius: 4px;
        }
        .status-indicator.connected { color: #4CAF50; }
        .status-indicator.disconnected { color: #f44336; }
        .preview-active {
            box-shadow: 0 0 20px rgba(255, 152, 0, 0.6) !important;
            transition: box-shadow 0.3s ease;
        }

        /* Tab styling */
        .tab-container { margin-top: 20px; }
        .tab-buttons {
            display: flex; border-bottom: 2px solid #ddd; background: #f8f8f8;
            border-radius: 8px 8px 0 0; overflow: hidden;
        }
        .tab-button {
            background: #f0f0f0; border: none; padding: 12px 24px; cursor: pointer;
            font-size: 1em; font-weight: bold; color: #666; transition: all 0.3s ease;
            flex: 1; text-align: center;
        }
        .tab-button:hover { background: #e0e0e0; color: #333; }
        .tab-button.active {
            background: #4CAF50; color: white; border-bottom: 3px solid #45a049;
        }
        .tab-content {
            display: none; background: white; border: 1px solid #ddd;
            border-top: none; padding: 20px; border-radius: 0 0 8px 8px;
        }
        .tab-content.active { display: block; }
    </style>
</head>
<body>
    <h1>Roon Display Configuration</h1>

    <!-- Current Display Preview -->
    <div class="display-preview-section">
        <div class="display-header">
            <span>Current Display</span>
            <div class="display-controls">
                <button id="refresh-display" class="control-btn">↻ Refresh</button>
                <span id="display-connection-status" class="status-indicator">●</span>
            </div>
        </div>
        <div class="display-container">
            <img id="current-display-image" src="/current-display-image" alt="Current Display" loading="lazy">
            <div id="display-overlay" class="display-overlay hidden">
                <span class="overlay-text">PREVIEW</span>
            </div>
        </div>
        <div class="display-info">
            <span id="display-metadata">Loading display info...</span>
        </div>
    </div>

    <!-- Flash messages for traditional form submission (fallback) -->

    <form method="POST" enctype="multipart/form-data" onsubmit="submitForm(event); return false;">

        <div class="tab-container">
            <div class="tab-buttons">
                {% for tab_name in tab_sections.keys() %}
                <button type="button" class="tab-button {{ 'active' if loop.first else '' }}" onclick="switchTab('{{ tab_name }}')" id="tab-{{ tab_name }}">
                    {{ tab_name }}
                </button>
                {% endfor %}
            </div>

            {% for tab_name, tab_sections_data in tab_sections.items() %}
            <div class="tab-content {{ 'active' if loop.first else '' }}" id="content-{{ tab_name }}">
                {% for section_name, section_data in tab_sections_data.items() %}
                {% if section_data %}
                <div class="section">
                    <h2>{{ section_name.replace('_', ' ').title() }}</h2>

            {% if section_name == 'ANNIVERSARIES' %}
                <!-- Special handling for anniversaries section -->
                {% for key, config_item in section_data.items() %}
                    {% if key in ['enabled'] %}
                    <div class="form-group">
                        <label for="{{ section_name }}_{{ key }}">{{ key.replace('_', ' ').title() }}:</label>

                        {% if config_item.type == 'boolean' %}
                            <input type="checkbox" id="{{ section_name }}_{{ key }}"
                                   name="{{ section_name }}.{{ key }}"
                                   value="true" {{ 'checked' if config_item.value else '' }}>
                        {% else %}
                            <input type="{{ config_item.input_type }}"
                                   id="{{ section_name }}_{{ key }}"
                                   name="{{ section_name }}.{{ key }}"
                                   value="{{ config_item.value }}"
                                   {% if config_item.min %}min="{{ config_item.min }}"{% endif %}
                                   {% if config_item.max %}max="{{ config_item.max }}"{% endif %}
                                   {% if config_item.step %}step="{{ config_item.step }}"{% endif %}>
                        {% endif %}

                        {% if config_item.comment %}
                            <div class="comment">{{ config_item.comment }}</div>
                        {% endif %}
                    </div>
                    {% endif %}
                {% endfor %}

                <!-- Anniversary entries -->
                <div class="form-group">
                    <h3>Anniversary Entries</h3>
                    <div class="comment">
                        Configure anniversaries with automatic year calculation. Use ${years} in your message for dynamic age.<br>
                        Images will be saved to extra_images/[name]/ directory and used randomly.
                    </div>

                    <div id="anniversary-entries">
                        {% for key, config_item in section_data.items() %}
                            {% if key not in ['enabled'] and not key.startswith('#') %}
                            {% set parts = config_item.value.split(',') %}
                            {% set date_part = parts[0] if parts|length > 0 else '' %}
                            {% set message_part = parts[1] if parts|length > 1 else '' %}
                            {% set wait_part = parts[2] if parts|length > 2 else '' %}
                            <div class="anniversary-entry" style="border: 1px solid #eee; padding: 15px; margin: 15px 0; border-radius: 5px; background: #fafafa;">
                                <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                                    <label style="min-width: 100px; font-weight: bold;">Name:</label>
                                    <input type="text" name="anniversary_name_{{ loop.index0 }}" value="{{ key }}" style="flex: 1;" placeholder="birthday_john">
                                    <button type="button" onclick="removeAnniversary(this)" style="background: #f44336; color: white; border: none; padding: 8px 12px; border-radius: 3px; cursor: pointer;">Remove</button>
                                </div>
                                <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                                    <label style="min-width: 100px; font-weight: bold;">Date:</label>
                                    <input type="text" name="anniversary_date_{{ loop.index0 }}" value="{{ date_part }}" style="width: 120px;" placeholder="15/03/1990">
                                    <span style="color: #666; font-size: 0.9em;">dd/mm/yyyy format</span>
                                </div>
                                <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                                    <label style="min-width: 100px; font-weight: bold;">Message:</label>
                                    <input type="text" name="anniversary_message_{{ loop.index0 }}" value="{{ message_part }}" style="flex: 1;" placeholder="Happy ${years} birthday John!">
                                    <span style="color: #666; font-size: 0.9em;">Use ${years} for age</span>
                                </div>
                                <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
                                    <label style="min-width: 100px; font-weight: bold;">Wait Time:</label>
                                    <input type="text" name="anniversary_wait_{{ loop.index0 }}" value="{{ wait_part }}" style="width: 150px;" placeholder="30 minutes">
                                    <span style="color: #666; font-size: 0.9em;">e.g., "30 minutes", "2 hours"</span>
                                </div>
                                <div style="display: flex; gap: 10px; align-items: center;">
                                    <label style="min-width: 100px; font-weight: bold;">Images:</label>
                                    <input type="file" name="anniversary_images_{{ loop.index0 }}" multiple accept="image/*" style="flex: 1;">
                                    <span style="color: #666; font-size: 0.9em;">Upload images (JPG, PNG, etc.)</span>
                                </div>
                                {% if anniversary_images and key in anniversary_images %}
                                <div style="margin-top: 10px;">
                                    <strong>Current Images ({{ anniversary_images[key]|length }}):</strong>
                                    <div class="thumbnail-container">
                                        {% for img in anniversary_images[key] %}
                                        <div class="thumbnail-item">
                                            <img src="/thumbnail/{{ key }}/{{ img }}" alt="{{ img }}" title="{{ img }}">
                                            <button type="button" class="thumbnail-delete"
                                                    onclick="deleteImage('{{ key }}', '{{ img }}')"
                                                    title="Delete {{ img }}">×</button>
                                            <div class="thumbnail-filename">{{ img }}</div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                </div>
                                {% endif %}
                            </div>
                            {% endif %}
                        {% endfor %}
                    </div>

                    <button type="button" onclick="addAnniversary()" style="background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 3px; cursor: pointer; margin-top: 15px;">Add Anniversary</button>
                </div>

            {% else %}
                <!-- Regular section handling -->
                {% for key, config_item in section_data.items() %}
                    {% if not key.startswith('#') %}
                    <div class="form-group">
                        <label for="{{ section_name }}_{{ key }}">{{ key.replace('_', ' ').title() }}:</label>

                        {% if config_item.type == 'boolean' %}
                            <input type="checkbox" id="{{ section_name }}_{{ key }}"
                                   name="{{ section_name }}.{{ key }}"
                                   value="true" {{ 'checked' if config_item.value else '' }}>
                        {% elif config_item.type == 'select' %}
                            <select id="{{ section_name }}_{{ key }}" name="{{ section_name }}.{{ key }}">
                                {% for option in config_item.options %}
                                    <option value="{{ option }}" {{ 'selected' if option == config_item.value else '' }}>
                                        {{ option }}
                                    </option>
                                {% endfor %}
                            </select>
                        {% elif config_item.type == 'textarea' %}
                            <textarea id="{{ section_name }}_{{ key }}" name="{{ section_name }}.{{ key }}"
                                      class="textarea-large">{{ config_item.value }}</textarea>
                        {% else %}
                            <input type="{{ config_item.input_type }}"
                                   id="{{ section_name }}_{{ key }}"
                                   name="{{ section_name }}.{{ key }}"
                                   value="{{ config_item.value }}"
                                   {% if config_item.min %}min="{{ config_item.min }}"{% endif %}
                                   {% if config_item.max %}max="{{ config_item.max }}"{% endif %}
                                   {% if config_item.step %}step="{{ config_item.step }}"{% endif %}>
                        {% endif %}

                        {% if config_item.comment %}
                            <div class="comment">{{ config_item.comment }}</div>
                        {% endif %}
                    </div>
                    {% endif %}
                {% endfor %}
            {% endif %}
        </div>
        {% endif %}
        {% endfor %}
            </div>
            {% endfor %}
        </div>

        <div class="button-group">
            <button type="submit" name="action" value="apply" class="apply-btn" id="apply-btn">Apply Changes</button>
            <div id="message-area" style="margin-top: 15px; display: none;">
                <div id="message-content" class="flash-success"></div>
            </div>
        </div>
    </form>

    <script>
        let anniversaryCounter = {{ anniversary_count }};

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

        function addAnniversary() {
            const container = document.getElementById('anniversary-entries');
            const div = document.createElement('div');
            div.className = 'anniversary-entry';
            div.style.cssText = 'border: 1px solid #eee; padding: 15px; margin: 15px 0; border-radius: 5px; background: #fafafa;';
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
                    <input type="text" name="anniversary_message_${anniversaryCounter}" value="" style="flex: 1;" placeholder="Happy $${years} birthday John!">
                    <span style="color: #666; font-size: 0.9em;">Use $${years} for age</span>
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

        function deleteImage(anniversaryName, filename) {
            if (confirm(`Are you sure you want to delete "${filename}"?`)) {
                const button = event.target;
                const thumbnailItem = button.closest('.thumbnail-item');

                fetch('/delete-image', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        anniversary_name: anniversaryName,
                        filename: filename
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Remove the thumbnail from the DOM
                        thumbnailItem.remove();

                        // Check if this was the last image in the container
                        const container = thumbnailItem.closest('.thumbnail-container');
                        if (container && container.children.length === 0) {
                            // If no thumbnails left, show "No images uploaded yet" message
                            container.innerHTML = '<p class="no-images">No images uploaded yet.</p>';
                        }
                    } else {
                        alert('Error deleting image: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error deleting image: ' + error);
                });
            }
        }

        // Display image and status update functionality
        let previewMode = false;
        let previewTimeout = null;

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
                    }, {{ preview_auto_revert_ms }});
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
            }, {{ preview_debounce_ms }}); // Configurable debounce from server
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

        // Initial load and periodic updates
        document.addEventListener('DOMContentLoaded', function() {
            // Hide legacy flash messages since we have AJAX enabled
            const legacyFlash = document.getElementById('legacy-flash-messages');
            if (legacyFlash) {
                legacyFlash.style.display = 'none';
            }

            updateDisplayImage();
            updateDisplayMetadata();
            setupFormChangeDetection();

            // Auto-refresh at configured interval
            const refreshInterval = {{ web_refresh_interval }};  // From server config
            setInterval(() => {
                if (!previewMode) {
                    updateDisplayImage();
                    updateDisplayMetadata();
                }
            }, refreshInterval);

            // Refresh button
            document.getElementById('refresh-display').addEventListener('click', () => {
                revertToLiveDisplay();
                updateDisplayMetadata();
            });
        });
    </script>
</body>
</html>
"""


class InternalAppClient:
    """HTTP client for communication with the main Roon display app."""

    def __init__(self, config_manager):
        """Initialize client with config manager."""
        self.config_manager = config_manager
        host = config_manager.get_internal_server_host()
        port = config_manager.get_internal_server_port()
        self.base_url = f"http://{host}:{port}"

    def get_current_image(self) -> Optional[bytes]:
        """Get current display image from main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.get(f"{self.base_url}/current-image", timeout=timeout)
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(
                    f"Failed to get current image: HTTP {response.status_code}"
                )
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to get current image: {e}")
            return None

    def get_current_status(self) -> Dict[str, Any]:
        """Get current display status from main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.get(f"{self.base_url}/current-status", timeout=timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Failed to get current status: HTTP {response.status_code}"
                )
                return {}
        except requests.RequestException as e:
            logger.debug(f"Failed to get current status: {e}")
            return {}

    def generate_preview(self, config_data: Dict) -> Optional[bytes]:
        """Generate preview image with config changes."""
        try:
            response = requests.post(
                f"{self.base_url}/preview",
                json=config_data,
                timeout=self.config_manager.get_web_request_timeout()
                * 2,  # Longer timeout for preview generation
            )
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(
                    f"Failed to generate preview: HTTP {response.status_code}"
                )
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to generate preview: {e}")
            return None

    def check_health(self) -> bool:
        """Check if main app is responsive."""
        try:
            timeout = max(2, self.config_manager.get_web_request_timeout() // 2)
            response = requests.get(f"{self.base_url}/health", timeout=timeout)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def update_config(self, config_updates: dict) -> dict:
        """Send configuration updates to main app."""
        try:
            timeout = self.config_manager.get_web_request_timeout()
            response = requests.post(
                f"{self.base_url}/update-config", json=config_updates, timeout=timeout
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to update config: HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except requests.RequestException as e:
            logger.debug(f"Failed to update config: {e}")
            return {"success": False, "error": str(e)}


# Global client instance (initialized in main)
internal_client = None


def validate_image_format(file_data: bytes, filename: str) -> bool:
    """Validate that uploaded file is a supported image format."""
    try:
        # Create a test image from the uploaded data
        with tempfile.NamedTemporaryFile() as tmp_file:
            tmp_file.write(file_data)
            tmp_file.flush()

            # Try to open and verify the image
            with Image.open(tmp_file.name) as img:
                img.verify()

        # Additional check: ensure it has a valid image extension
        valid_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".bmp",
            ".gif",
            ".tiff",
            ".tif",
            ".webp",
            ".avif",
        }
        file_ext = Path(filename).suffix.lower()
        return file_ext in valid_extensions

    except Exception as e:
        logger.warning(f"Image validation failed for {filename}: {e}")
        return False


def get_anniversary_images() -> Dict[str, List[str]]:
    """Get existing anniversary images organized by anniversary name."""
    anniversary_images = {}
    extra_images_dir = get_extra_images_dir()

    if extra_images_dir.exists():
        for anniversary_dir in extra_images_dir.iterdir():
            if anniversary_dir.is_dir():
                image_files = []
                valid_extensions = {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".bmp",
                    ".gif",
                    ".tiff",
                    ".tif",
                    ".webp",
                    ".avif",
                }

                for file_path in anniversary_dir.iterdir():
                    if (
                        file_path.is_file()
                        and file_path.suffix.lower() in valid_extensions
                    ):
                        image_files.append(file_path.name)

                if image_files:
                    anniversary_images[anniversary_dir.name] = sorted(image_files)

    return anniversary_images


def create_thumbnail(
    image_path: Path, max_size: Tuple[int, int] = (150, 150), jpeg_quality: int = 85
) -> Optional[bytes]:
    """Create a thumbnail from an image file."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for transparency handling)
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                rgb_img.paste(
                    img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
                )
                img = rgb_img

            # Create thumbnail
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to bytes
            import io

            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG", quality=jpeg_quality)
            thumb_io.seek(0)
            return thumb_io.getvalue()

    except Exception as e:
        logger.warning(f"Failed to create thumbnail for {image_path}: {e}")
        return None


def delete_anniversary_image(anniversary_name: str, filename: str) -> bool:
    """Delete a specific anniversary image file."""
    try:
        anniversary_dir = get_extra_images_dir() / anniversary_name
        image_path = anniversary_dir / filename

        if image_path.exists() and image_path.is_file():
            image_path.unlink()
            logger.info(f"Deleted anniversary image: {image_path}")

            # Remove directory if it's now empty
            if anniversary_dir.exists() and not any(anniversary_dir.iterdir()):
                anniversary_dir.rmdir()
                logger.info(f"Removed empty anniversary directory: {anniversary_dir}")

            return True
        else:
            logger.warning(f"Image file not found: {image_path}")
            return False

    except Exception as e:
        logger.error(
            f"Error deleting anniversary image {anniversary_name}/{filename}: {e}"
        )
        return False


class WebConfigServer:
    """Web configuration server for Roon display."""

    def __init__(self, config_path=None, port=None):
        """Initialize web config server."""
        self.config_path = config_path or Path("roon.cfg")
        self.config_manager = ConfigManager(self.config_path)
        self.port = port or self.config_manager.get_web_config_port()

    def _get_config_sections(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration sections with metadata for dynamic rendering."""
        sections = {}

        # Define metadata for each section and field
        field_metadata = {
            "NETWORK": {
                "internal_server_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for internal HTTP server (default: 9090)",
                },
                "web_config_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for web configuration server (default: 8080)",
                },
                "simulation_server_port": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Port for simulation server (default: 9999)",
                },
                "internal_server_host": {
                    "type": "text",
                    "comment": "Host address for internal server (default: 127.0.0.1)",
                },
                "web_config_host": {
                    "type": "text",
                    "comment": "Host address for web config server (default: 0.0.0.0)",
                },
            },
            "TIMEOUTS": {
                "roon_authorization_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Roon authorization timeout in seconds (default: 300)",
                },
                "health_script_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Health script execution timeout in seconds (default: 30)",
                },
                "reconnection_interval": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Time between reconnection attempts in seconds (default: 60)",
                },
                "web_request_timeout": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Web request timeout in seconds (default: 5)",
                },
            },
            "IMAGE_QUALITY": {
                "jpeg_quality": {
                    "type": "number",
                    "input_type": "number",
                    "min": "1",
                    "max": "100",
                    "comment": "JPEG quality for web images (1-100, default: 85)",
                },
                "web_image_max_width": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Maximum width for web images in pixels (default: 600)",
                },
                "thumbnail_size": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Thumbnail size in pixels (square, default: 100)",
                },
            },
            "DISPLAY_TIMING": {
                "web_auto_refresh_seconds": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Web interface auto-refresh interval in seconds (default: 10)",
                },
                "anniversary_check_interval": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary check interval in seconds (default: 60)",
                },
                "performance_threshold_seconds": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Performance logging threshold in seconds (default: 0.5)",
                },
                "eink_success_threshold": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "E-ink success threshold in seconds (default: 12.0)",
                },
                "eink_warning_threshold": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "E-ink warning threshold in seconds (default: 30)",
                },
                "eink_check_interval": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "E-ink check interval in seconds (default: 5)",
                },
                "preview_auto_revert_seconds": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Preview auto-revert time in seconds (default: 30)",
                },
                "preview_debounce_ms": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Preview debounce time in milliseconds (default: 500)",
                },
            },
            "LAYOUT": {
                "overlay_size_x_percent": {
                    "type": "number",
                    "input_type": "number",
                    "min": "5",
                    "max": "50",
                    "comment": "Overlay width percentage (5-50%, default: 33%)",
                },
                "overlay_size_y_percent": {
                    "type": "number",
                    "input_type": "number",
                    "min": "5",
                    "max": "50",
                    "comment": "Overlay height percentage (5-50%, default: 25%)",
                },
                "overlay_border_size": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Overlay border size in pixels (default: 20)",
                },
                "overlay_margin": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Overlay margin from screen edge in pixels (default: 20)",
                },
                "anniversary_border_percent": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary border percentage (default: 5%)",
                },
                "anniversary_text_percent": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Anniversary text area percentage (default: 15%)",
                },
                "font_size_ratio_base": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Base font size ratio for text rendering (default: 20)",
                },
                "line_spacing_ratio": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Line spacing ratio for text rendering (default: 8)",
                },
            },
            "DISPLAY": {
                "type": {
                    "type": "select",
                    "options": ["system_display", "epd13in3E"],
                    "comment": "Display type: system_display for regular monitors, epd13in3E for e-ink",
                },
                "tkinter_fullscreen": {
                    "type": "boolean",
                    "comment": "Enable fullscreen mode for system displays (ignored by e-ink)",
                },
            },
            "IMAGE_RENDER": {
                "colour_balance_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Color balance adjustment (0.1-3.0, default: 1.0)",
                },
                "contrast_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Contrast adjustment (0.1-3.0, default: 1.0)",
                },
                "sharpness_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Sharpness adjustment (0.1-3.0, default: 1.0)",
                },
                "brightness_adjustment": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Brightness adjustment (0.1-3.0, default: 1.0)",
                },
            },
            "IMAGE_POSITION": {
                "position_offset_x": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Horizontal position offset in pixels",
                },
                "position_offset_y": {
                    "type": "number",
                    "input_type": "number",
                    "comment": "Vertical position offset in pixels",
                },
                "scale_x": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Horizontal scale factor (0.1-3.0, default: 1.0)",
                },
                "scale_y": {
                    "type": "number",
                    "input_type": "number",
                    "step": "0.1",
                    "comment": "Vertical scale factor (0.1-3.0, default: 1.0)",
                },
                "rotation": {
                    "type": "select",
                    "options": ["0", "90", "180", "270"],
                    "comment": "Image rotation in degrees",
                },
            },
            "ZONES": {
                "allowed_zone_names": {
                    "type": "text",
                    "comment": "Comma-separated list of allowed zone names (leave blank for all)",
                },
                "forbidden_zone_names": {
                    "type": "text",
                    "comment": "Comma-separated list of forbidden zone names",
                },
            },
            "ANNIVERSARIES": {
                "enabled": {
                    "type": "boolean",
                    "comment": "Enable anniversary notifications",
                },
            },
            "MONITORING": {
                "log_level": {
                    "type": "select",
                    "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "comment": "Logging level",
                },
                "loop_time": {
                    "type": "text",
                    "comment": 'Event loop sleep time (e.g., "10 minutes", "30 seconds")',
                },
                "performance_logging": {
                    "type": "select",
                    "options": ["", "info", "debug"],
                    "comment": "Enable performance logging (empty = disabled)",
                },
                "health_script": {
                    "type": "text",
                    "comment": "Path to health monitoring script (optional)",
                },
                "health_recheck_interval": {
                    "type": "text",
                    "comment": 'Time between health script calls (e.g., "30 minutes")',
                },
            },
        }

        # Define mapping from fields to config_manager getter methods
        field_getters = {
            "NETWORK": {
                "internal_server_port": self.config_manager.get_internal_server_port,
                "web_config_port": self.config_manager.get_web_config_port,
                "simulation_server_port": self.config_manager.get_simulation_server_port,
                "internal_server_host": self.config_manager.get_internal_server_host,
                "web_config_host": self.config_manager.get_web_config_host,
            },
            "TIMEOUTS": {
                "roon_authorization_timeout": self.config_manager.get_roon_authorization_timeout,
                "health_script_timeout": self.config_manager.get_health_script_timeout,
                "reconnection_interval": self.config_manager.get_reconnection_interval,
                "web_request_timeout": self.config_manager.get_web_request_timeout,
            },
            "IMAGE_QUALITY": {
                "jpeg_quality": self.config_manager.get_jpeg_quality,
                "web_image_max_width": self.config_manager.get_web_image_max_width,
                "thumbnail_size": self.config_manager.get_thumbnail_size,
            },
            "DISPLAY_TIMING": {
                "web_auto_refresh_seconds": self.config_manager.get_web_auto_refresh_seconds,
                "anniversary_check_interval": self.config_manager.get_anniversary_check_interval,
                "performance_threshold_seconds": self.config_manager.get_performance_threshold_seconds,
                "eink_success_threshold": self.config_manager.get_eink_success_threshold,
                "eink_warning_threshold": self.config_manager.get_eink_warning_threshold,
                "eink_check_interval": self.config_manager.get_eink_check_interval,
                "preview_auto_revert_seconds": self.config_manager.get_preview_auto_revert_seconds,
                "preview_debounce_ms": self.config_manager.get_preview_debounce_ms,
            },
            "LAYOUT": {
                "overlay_size_x_percent": self.config_manager.get_overlay_size_x_percent,
                "overlay_size_y_percent": self.config_manager.get_overlay_size_y_percent,
                "overlay_border_size": self.config_manager.get_overlay_border_size,
                "overlay_margin": self.config_manager.get_overlay_margin,
                "anniversary_border_percent": self.config_manager.get_anniversary_border_percent,
                "anniversary_text_percent": self.config_manager.get_anniversary_text_percent,
                "font_size_ratio_base": self.config_manager.get_font_size_ratio_base,
                "line_spacing_ratio": self.config_manager.get_line_spacing_ratio,
            },
            "IMAGE_RENDER": {
                "colour_balance_adjustment": self.config_manager.get_colour_balance_adjustment,
                "contrast_adjustment": self.config_manager.get_contrast_adjustment,
                "sharpness_adjustment": self.config_manager.get_sharpness_adjustment,
                "brightness_adjustment": self.config_manager.get_brightness_adjustment,
            },
            "IMAGE_POSITION": {
                "position_offset_x": self.config_manager.get_position_offset_x,
                "position_offset_y": self.config_manager.get_position_offset_y,
                "scale_x": self.config_manager.get_scale_x,
                "scale_y": self.config_manager.get_scale_y,
                "rotation": self.config_manager.get_rotation,
            },
            "ZONES": {
                "allowed_zone_names": self.config_manager.get_allowed_zone_names,
                "forbidden_zone_names": self.config_manager.get_forbidden_zone_names,
            },
            "MONITORING": {
                "log_level": self.config_manager.get_log_level_string,
                "loop_time": self.config_manager.get_loop_time_string,
                "performance_logging": self.config_manager.get_performance_logging_string,
                "health_script": self.config_manager.get_health_script,
                "health_recheck_interval": self.config_manager.get_health_recheck_interval_string,
            },
            "ANNIVERSARIES": {
                "enabled": self.config_manager.get_anniversaries_enabled,
            },
        }

        # Build sections with current values from config_manager
        for section_name, section_fields in field_metadata.items():
            sections[section_name] = {}

            # Process all fields defined in metadata
            for field_name, field_metadata_item in section_fields.items():
                metadata = field_metadata_item.copy()

                # Get current value using config_manager getter method
                if (
                    section_name in field_getters
                    and field_name in field_getters[section_name]
                ):
                    try:
                        current_value = field_getters[section_name][field_name]()
                        metadata["value"] = current_value
                    except Exception as e:
                        logger.warning(
                            f"Error getting value for {section_name}.{field_name}: {e}"
                        )
                        metadata["value"] = ""
                elif section_name == "DISPLAY":
                    # Special handling for DISPLAY section using existing method
                    try:
                        display_config = self.config_manager.get_display_config()
                        if field_name == "type":
                            metadata["value"] = display_config.get("type", "epd13in3E")
                        elif field_name == "tkinter_fullscreen":
                            metadata["value"] = display_config.get(
                                "tkinter_fullscreen", False
                            )
                        else:
                            metadata["value"] = ""
                    except Exception as e:
                        logger.warning(
                            f"Error getting display config for {field_name}: {e}"
                        )
                        metadata["value"] = ""
                else:
                    # This shouldn't happen now that all sections have getters
                    logger.warning(
                        f"No getter method found for {section_name}.{field_name}"
                    )
                    metadata["value"] = ""

                # Set default input type if not specified
                if "input_type" not in metadata:
                    metadata["input_type"] = "text"

                # Handle boolean conversion
                if metadata["type"] == "boolean":
                    if isinstance(metadata["value"], bool):
                        # Already a boolean
                        pass
                    else:
                        # Convert string to boolean
                        metadata["value"] = str(metadata["value"]).lower() in (
                            "true",
                            "1",
                            "yes",
                            "on",
                        )

                sections[section_name][field_name] = metadata

            # Handle anniversary entries separately (existing logic)
            if section_name == "ANNIVERSARIES":
                anniversaries_config = self.config_manager.get_anniversaries_config()
                for anniversary in anniversaries_config.get("anniversaries", []):
                    name = anniversary["name"]
                    date = anniversary["date"]
                    message = anniversary["message"]
                    wait_minutes = anniversary["wait_minutes"]

                    # Convert wait minutes back to string format
                    if wait_minutes >= 60:
                        wait_str = (
                            f"{wait_minutes // 60} hours"
                            if wait_minutes >= 120
                            else f"{wait_minutes // 60} hour"
                        )
                        if wait_minutes % 60 > 0:
                            wait_str += f" {wait_minutes % 60} minutes"
                    else:
                        wait_str = f"{wait_minutes} minutes"

                    sections[section_name][name] = {
                        "type": "anniversary",
                        "value": f"{date},{message},{wait_str}",
                        "input_type": "text",
                    }

        return sections

    def _save_config(
        self, form_data: Dict[str, str], files: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, str]]:
        """Save configuration from form data and handle image uploads.

        Returns:
            Tuple of (success: bool, error_messages: List[str], config_updates: Dict[str, str])
        """
        error_messages = []
        config_updates = {}  # Track changes for live update

        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)

            # Process regular form data
            for field_name, value in form_data.items():
                if "." in field_name and not field_name.startswith("anniversary_"):
                    section_name, key = field_name.split(".", 1)

                    if section_name not in config:
                        config[section_name] = {}

                    # Track what's changing for live update
                    old_value = config[section_name].get(key, "")
                    if old_value != value:
                        config_updates[field_name] = value

                    config[section_name][key] = value

            # Handle anniversary entries separately
            anniversary_names = {}
            anniversary_dates = {}
            anniversary_messages = {}
            anniversary_waits = {}

            for field_name, value in form_data.items():
                if field_name.startswith("anniversary_name_"):
                    index = field_name.split("_")[-1]
                    anniversary_names[index] = value
                elif field_name.startswith("anniversary_date_"):
                    index = field_name.split("_")[-1]
                    anniversary_dates[index] = value
                elif field_name.startswith("anniversary_message_"):
                    index = field_name.split("_")[-1]
                    anniversary_messages[index] = value
                elif field_name.startswith("anniversary_wait_"):
                    index = field_name.split("_")[-1]
                    anniversary_waits[index] = value

            # Clear existing anniversary entries (except enabled/comments)
            if "ANNIVERSARIES" in config:
                keys_to_remove = []
                for key in config["ANNIVERSARIES"]:
                    if key not in ["enabled"] and not key.startswith("#"):
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del config["ANNIVERSARIES"][key]

            # Add new anniversary entries
            if "ANNIVERSARIES" not in config:
                config["ANNIVERSARIES"] = {}

            for index in anniversary_names:
                if (
                    index in anniversary_dates
                    and index in anniversary_messages
                    and index in anniversary_waits
                ):
                    name = anniversary_names[index].strip()
                    date = anniversary_dates[index].strip()
                    message = anniversary_messages[index].strip()
                    wait = anniversary_waits[index].strip()

                    if name and date and message and wait:
                        # Combine into the expected format
                        config_value = f"{date},{message},{wait}"

                        # Track anniversary changes for live update
                        old_value = config["ANNIVERSARIES"].get(name, "")
                        if old_value != config_value:
                            config_updates[f"ANNIVERSARIES.{name}"] = config_value

                        config["ANNIVERSARIES"][name] = config_value

                        # Handle image uploads for this anniversary
                        file_field = f"anniversary_images_{index}"
                        if file_field in files:
                            uploaded_files = files.getlist(file_field)
                            if uploaded_files and uploaded_files[0].filename:
                                # Ensure anniversary directory exists
                                anniversary_dir = ensure_anniversary_dir_exists(name)

                                for uploaded_file in uploaded_files:
                                    if uploaded_file.filename:
                                        # Validate image
                                        file_data = uploaded_file.read()
                                        if validate_image_format(
                                            file_data, uploaded_file.filename
                                        ):
                                            # Save the file
                                            safe_filename = secure_filename(
                                                uploaded_file.filename
                                            )
                                            file_path = anniversary_dir / safe_filename

                                            with open(file_path, "wb") as f:
                                                f.write(file_data)

                                            logger.info(
                                                f"Saved anniversary image: {file_path}"
                                            )
                                        else:
                                            error_messages.append(
                                                f"Invalid image format for {uploaded_file.filename}. "
                                                f"Supported formats: JPG, PNG, BMP, GIF, TIFF, WebP, AVIF"
                                            )

            # Handle unchecked checkboxes
            sections = self._get_config_sections()
            for section_name, section_data in sections.items():
                for key, config_item in section_data.items():
                    if config_item["type"] == "boolean":
                        field_name = f"{section_name}.{key}"
                        if field_name not in form_data:
                            if section_name not in config:
                                config[section_name] = {}

                            # Track checkbox changes for live update
                            old_value = config[section_name].get(
                                key, "true"
                            )  # Default might be true
                            if old_value != "false":
                                config_updates[field_name] = "false"

                            config[section_name][key] = "false"

            # Save config file
            with open(self.config_path, "w") as f:
                config.write(f)

            logger.info("Configuration saved successfully")
            return True, error_messages, config_updates

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            error_messages.append(f"Error saving configuration: {e}")
            return False, error_messages, {}


# Flask routes
@app.route("/", methods=["GET", "POST"])
def config_interface():
    """Main configuration interface."""
    web_server = app.config["web_server"]

    if request.method == "POST":
        action = request.form.get("action")

        # Check if this is an AJAX request
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        # Check for health_script specifically
        health_script_value = request.form.get("MONITORING.health_script")

        success, error_messages, config_updates = web_server._save_config(
            request.form, request.files
        )

        if is_ajax:
            # Return JSON response for AJAX requests
            if success:
                message = "Configuration updated successfully!"

                # Send config updates to main process for immediate effect
                if config_updates:
                    update_result = internal_client.update_config(config_updates)
                    if not update_result.get("success"):
                        message = f'Configuration saved but live update failed: {update_result.get("error", "Unknown error")}'
                        logger.warning(f"Live config update failed: {update_result}")
                    else:
                        logger.info(
                            f"Live config update successful: {update_result.get('updated_keys', [])}"
                        )

                # Include any image upload warnings in the message
                if error_messages:
                    warnings_text = "; ".join(error_messages)
                    message = f"{message} (Warnings: {warnings_text})"

                return jsonify({"success": True, "message": message})
            else:
                error_text = "Error saving configuration!"
                if error_messages:
                    error_text = "; ".join([error_text] + error_messages)

                return jsonify({"success": False, "message": error_text})
        else:
            # Traditional form submission - keep existing redirect behavior
            if success:
                # Send config updates to main process for immediate effect
                if config_updates:
                    update_result = internal_client.update_config(config_updates)
                    if update_result.get("success"):
                        flash("Configuration updated successfully!", "success")
                        logger.info(
                            f"Live config update successful: {update_result.get('updated_keys', [])}"
                        )
                    else:
                        flash(
                            f'Configuration saved but live update failed: {update_result.get("error", "Unknown error")}',
                            "error",
                        )
                        logger.warning(f"Live config update failed: {update_result}")
                else:
                    flash("Configuration saved successfully!", "success")

                # Show any image upload warnings
                for error_msg in error_messages:
                    flash(error_msg, "error")

            else:
                flash("Error saving configuration!", "error")
                for error_msg in error_messages:
                    flash(error_msg, "error")

            # Store current tab and scroll position for redirect
            current_tab = request.form.get("current_tab", "Image")
            scroll_position = request.form.get("scroll_position", "0")
            return redirect(
                url_for("config_interface", tab=current_tab, scroll=scroll_position)
            )

    # GET request - show form
    sections = web_server._get_config_sections()

    # Organize sections into tabs
    tab_sections = {
        "Image": {
            "IMAGE_RENDER": sections.get("IMAGE_RENDER", {}),
            "IMAGE_POSITION": sections.get("IMAGE_POSITION", {}),
            "LAYOUT": sections.get("LAYOUT", {}),
            "IMAGE_QUALITY": sections.get("IMAGE_QUALITY", {}),
        },
        "Features": {
            "ZONES": sections.get("ZONES", {}),
            "ANNIVERSARIES": sections.get("ANNIVERSARIES", {}),
        },
        "Advanced": {
            "DISPLAY": sections.get("DISPLAY", {}),
            "NETWORK": sections.get("NETWORK", {}),
            "TIMEOUTS": sections.get("TIMEOUTS", {}),
            "DISPLAY_TIMING": sections.get("DISPLAY_TIMING", {}),
            "MONITORING": sections.get("MONITORING", {}),
        },
    }

    # Count anniversary entries for JavaScript counter
    anniversary_count = 0
    if "ANNIVERSARIES" in sections:
        anniversary_count = len(
            [
                k
                for k in sections["ANNIVERSARIES"].keys()
                if k not in ["enabled"] and not k.startswith("#")
            ]
        )

    # Get existing anniversary images
    anniversary_images = get_anniversary_images()

    # Get web timing values from config
    web_server = app.config["web_server"]
    refresh_interval_seconds = web_server.config_manager.get_web_auto_refresh_seconds()
    debounce_ms = web_server.config_manager.get_preview_debounce_ms()
    auto_revert_seconds = web_server.config_manager.get_preview_auto_revert_seconds()

    return render_template_string(
        CONFIG_TEMPLATE,
        tab_sections=tab_sections,
        sections=sections,
        anniversary_count=anniversary_count,
        anniversary_images=anniversary_images,
        web_refresh_interval=refresh_interval_seconds * 1000,  # Convert to milliseconds
        preview_debounce_ms=debounce_ms,
        preview_auto_revert_ms=auto_revert_seconds * 1000,
    )  # Convert to milliseconds


@app.route("/thumbnail/<anniversary_name>/<filename>")
def serve_thumbnail(anniversary_name, filename):
    """Serve thumbnail images for anniversary photos."""
    try:
        # Validate the anniversary name and filename for security
        safe_anniversary = secure_filename(anniversary_name)
        safe_filename = secure_filename(filename)

        if not safe_anniversary or not safe_filename:
            return "Invalid filename", 400

        # Get the image path
        image_path = get_extra_images_dir() / safe_anniversary / safe_filename

        if not image_path.exists():
            return "Image not found", 404

        # Create and return thumbnail
        web_server = app.config["web_server"]
        thumbnail_size = web_server.config_manager.get_thumbnail_size()
        jpeg_quality = web_server.config_manager.get_jpeg_quality()
        thumbnail_data = create_thumbnail(
            image_path,
            max_size=(thumbnail_size, thumbnail_size),
            jpeg_quality=jpeg_quality,
        )
        if thumbnail_data:
            import io

            return send_file(
                io.BytesIO(thumbnail_data),
                mimetype="image/jpeg",
                as_attachment=False,
                download_name=f"thumb_{safe_filename}",
            )
        else:
            return "Could not create thumbnail", 500

    except Exception as e:
        logger.error(f"Error serving thumbnail {anniversary_name}/{filename}: {e}")
        return "Internal server error", 500


@app.route("/delete-image", methods=["POST"])
def delete_image():
    """Delete an anniversary image."""
    try:
        data = request.get_json()
        anniversary_name = data.get("anniversary_name")
        filename = data.get("filename")

        if not anniversary_name or not filename:
            return jsonify(
                {"success": False, "error": "Missing anniversary name or filename"}
            )

        # Validate and secure the filenames
        safe_anniversary = secure_filename(anniversary_name)
        safe_filename = secure_filename(filename)

        if not safe_anniversary or not safe_filename:
            return jsonify({"success": False, "error": "Invalid filename"})

        # Delete the image
        success = delete_anniversary_image(safe_anniversary, safe_filename)

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to delete image"})

    except Exception as e:
        logger.error(f"Error in delete image endpoint: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/display-status")
def display_status():
    """Get current display status from main app."""
    try:
        status_data = internal_client.get_current_status()

        # Add connection status
        status_data["internal_app_connected"] = internal_client.check_health()

        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Error getting display status: {e}")
        return jsonify(
            {
                "internal_app_connected": False,
                "track_info": "Connection error",
                "timestamp": None,
            }
        )


@app.route("/current-display-image")
def serve_current_display_image():
    """Proxy current display image from main app."""
    try:
        image_data = internal_client.get_current_image()
        if image_data:
            return send_file(
                io.BytesIO(image_data), mimetype="image/jpeg", as_attachment=False
            )
        else:
            # Return placeholder image when no image available
            web_server = app.config["web_server"]
            jpeg_quality = web_server.config_manager.get_jpeg_quality()
            return _create_placeholder_response(jpeg_quality)
    except Exception as e:
        logger.error(f"Error serving current display image: {e}")
        web_server = app.config["web_server"]
        jpeg_quality = web_server.config_manager.get_jpeg_quality()
        return _create_placeholder_response(jpeg_quality)


@app.route("/preview-image", methods=["POST"])
def generate_preview_image():
    """Generate preview image with form changes."""
    try:
        # Parse form data into config format, excluding file uploads for now
        config_data = _parse_form_to_config_for_preview(request.form, request.files)

        # Request preview from main app
        preview_data = internal_client.generate_preview(config_data)

        if preview_data:
            return send_file(
                io.BytesIO(preview_data), mimetype="image/jpeg", as_attachment=False
            )
        else:
            return jsonify({"error": "Preview generation failed"}), 500
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return jsonify({"error": str(e)}), 500


def _create_placeholder_response(jpeg_quality: int = 85):
    """Create placeholder image response when main app not available."""
    try:
        # Create simple placeholder image
        placeholder = Image.new("RGB", (400, 300), color=(200, 200, 200))

        # Convert to bytes
        img_io = io.BytesIO()
        placeholder.save(img_io, "JPEG", quality=jpeg_quality)
        img_io.seek(0)

        return send_file(img_io, mimetype="image/jpeg")
    except Exception as e:
        logger.error(f"Error creating placeholder: {e}")
        return jsonify({"error": "No image available"}), 404


def _parse_form_to_config(form_data, files) -> Dict[str, Any]:
    """Parse form data into configuration format for saving to config file."""
    config = {}

    try:
        # Parse regular configuration fields (section.field format)
        for key, value in form_data.items():
            if "." in key and not key.startswith("anniversary_"):
                # Handle nested config like IMAGE_RENDER.brightness_adjustment
                config[key] = value
            elif key.startswith("anniversary_"):
                # Handle anniversary fields
                config[key] = value
            else:
                # Handle other fields
                config[key] = value

        # Handle checkboxes that are only present when checked
        # For unchecked checkboxes, we need to detect them and set to false
        # This is a simplified approach - in full implementation we'd track all possible checkboxes
        checkbox_fields = ["ANNIVERSARIES.enabled", "DISPLAY.tkinter_fullscreen"]

        for checkbox_field in checkbox_fields:
            if checkbox_field not in config:
                config[checkbox_field] = "false"

        # Handle file uploads (for anniversary images)
        if files:
            for field_name, file_list in files.items():
                if field_name.startswith("anniversary_images_"):
                    config[f"{field_name}_files"] = file_list

        logger.debug(f"Parsed form to config with {len(config)} fields")
        return config

    except Exception as e:
        logger.error(f"Error parsing form data: {e}")
        return {}


def _parse_form_to_config_for_preview(form_data, files) -> Dict[str, Any]:
    """Parse form data for preview generation, excluding non-serializable file objects."""
    config = {}

    try:
        # Parse regular configuration fields (section.field format)
        for key, value in form_data.items():
            if "." in key and not key.startswith("anniversary_"):
                # Handle nested config like IMAGE_RENDER.brightness_adjustment
                config[key] = value
            elif key.startswith("anniversary_"):
                # Handle anniversary fields
                config[key] = value
            else:
                # Handle other fields
                config[key] = value

        # Handle checkboxes that are only present when checked
        checkbox_fields = ["ANNIVERSARIES.enabled", "DISPLAY.tkinter_fullscreen"]

        for checkbox_field in checkbox_fields:
            if checkbox_field not in config:
                config[checkbox_field] = "false"

        # For preview, we'll skip file uploads for now
        # TODO: In future, could convert files to base64 or handle differently
        if files:
            file_count = sum(
                len(file_list) if hasattr(file_list, "__len__") else 1
                for file_list in files.values()
                if file_list
            )
            if file_count > 0:
                config["_has_file_uploads"] = str(file_count)
                logger.debug(
                    f"Preview request has {file_count} file uploads (skipped for preview)"
                )

        logger.debug(f"Parsed form to preview config with {len(config)} fields")
        return config

    except Exception as e:
        logger.error(f"Error parsing form data for preview: {e}")
        return {}


def main():
    """Main entry point for web config server."""
    import argparse

    global internal_client

    parser = argparse.ArgumentParser(
        description="Roon Display Web Configuration Server"
    )
    parser.add_argument(
        "--port", type=int, help="Port to run server on (overrides config)"
    )
    parser.add_argument("--host", help="Host to bind to (overrides config)")
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create web server instance
    web_server = WebConfigServer(config_path=args.config, port=args.port)

    # Initialize global internal client with config
    internal_client = InternalAppClient(web_server.config_manager)

    # Store in Flask app config for route access
    app.config["web_server"] = web_server

    # Get host and port from config or command line
    host = args.host or web_server.config_manager.get_web_config_host()
    port = (
        web_server.port
    )  # Already set from config or args in WebConfigServer.__init__

    logger.info(f"Starting Roon Display web configuration server on {host}:{port}")

    try:
        app.run(host=host, port=port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Web configuration server stopped")


if __name__ == "__main__":
    main()
