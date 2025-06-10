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
from typing import Dict, Any, List, Tuple, Optional

import requests
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file, jsonify
from PIL import Image
from werkzeug.utils import secure_filename

from .config.config_manager import ConfigManager
from .utils import get_extra_images_dir, ensure_anniversary_dir_exists, get_current_image_key, get_last_track_time, get_saved_image_dir

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'roon-display-config-key'  # Simple key for flash messages

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
        .restart-btn { background-color: #ff9800; }
        .restart-btn:hover { background-color: #e68900; }
        .flash-messages { margin-bottom: 20px; }
        .flash-success { background-color: #d4edda; color: #155724; padding: 10px; border-radius: 4px; }
        .flash-error { background-color: #f8d7da; color: #721c24; padding: 10px; border-radius: 4px; }
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
        }
        .thumbnail-delete { 
            position: absolute; top: 2px; right: 2px; background: rgba(244, 67, 54, 0.9); 
            color: white; border: none; border-radius: 50%; width: 20px; height: 20px; 
            cursor: pointer; font-size: 12px; line-height: 1; font-weight: bold;
        }
        .thumbnail-delete:hover { background: rgba(244, 67, 54, 1); }
        .thumbnail-filename { 
            position: absolute; bottom: 0; left: 0; right: 0; 
            background: rgba(0,0,0,0.7); color: white; font-size: 10px; 
            padding: 2px 4px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;
        }
        .status-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 20px; margin-bottom: 30px; border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .status-header { font-size: 1.5em; font-weight: bold; margin-bottom: 15px; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .status-item { background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px; }
        .status-label { font-weight: bold; font-size: 0.9em; opacity: 0.8; margin-bottom: 5px; }
        .status-value { font-size: 1.1em; word-break: break-word; }
        .status-indicator { 
            display: inline-block; width: 10px; height: 10px; border-radius: 50%; 
            margin-right: 8px; animation: pulse 2s infinite;
        }
        .status-active { background-color: #4CAF50; }
        .status-error { background-color: #f44336; }
        .status-unknown { background-color: #ff9800; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
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
    
    <!-- Current Display Status -->
    <div class="status-section" id="status-section">
        <div class="status-header">
            <span class="status-indicator status-unknown" id="status-indicator"></span>
            Current Display Status
        </div>
        <div class="status-grid" id="status-grid">
            <div class="status-item">
                <div class="status-label">Display Type</div>
                <div class="status-value" id="status-display-type">Loading...</div>
            </div>
            <div class="status-item">
                <div class="status-label">Current Status</div>
                <div class="status-value" id="status-current">Loading...</div>
            </div>
            <div class="status-item">
                <div class="status-label">Last Track</div>
                <div class="status-value" id="status-last-track">Loading...</div>
            </div>
            <div class="status-item">
                <div class="status-label">Image Key</div>
                <div class="status-value" id="status-image-key">Loading...</div>
            </div>
        </div>
    </div>
    
    <div class="flash-messages">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>

    <form method="POST" enctype="multipart/form-data">
        {% for section_name, section_data in sections.items() %}
        <div class="section">
            <h2>{{ section_name.replace('_', ' ').title() }}</h2>
            
            {% if section_name == 'ANNIVERSARIES' %}
                <!-- Special handling for anniversaries section -->
                {% for key, config_item in section_data.items() %}
                    {% if key in ['enabled', 'border'] %}
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
                                   value="{{ config_item.value }}">
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
                            {% if key not in ['enabled', 'border'] and not key.startswith('#') %}
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
                                   value="{{ config_item.value }}">
                        {% endif %}
                        
                        {% if config_item.comment %}
                            <div class="comment">{{ config_item.comment }}</div>
                        {% endif %}
                    </div>
                    {% endif %}
                {% endfor %}
            {% endif %}
        </div>
        {% endfor %}
        
        <div class="button-group">
            <button type="submit" name="action" value="restart" class="restart-btn">Save</button>
        </div>
    </form>

    <script>
        let anniversaryCounter = {{ anniversary_count }};
        
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
        
        function deleteImage(anniversaryName, filename) {
            if (confirm(`Are you sure you want to delete "${filename}"?`)) {
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
                        // Reload the page to update the thumbnail display
                        location.reload();
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
                    
                    // Auto-revert after 30 seconds
                    setTimeout(() => {
                        revertToLiveDisplay();
                    }, 30000);
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
            }, 500); // 500ms debounce
        }

        // Status update functionality
        function updateStatus() {
            fetch('/display-status')
                .then(response => response.json())
                .then(data => {
                    // Update status indicator
                    const indicator = document.getElementById('status-indicator');
                    indicator.className = 'status-indicator';
                    
                    if (data.error || !data.internal_app_connected) {
                        indicator.classList.add('status-error');
                    } else if (data.current_image_key || data.has_image) {
                        indicator.classList.add('status-active');
                    } else {
                        indicator.classList.add('status-unknown');
                    }
                    
                    // Update status fields
                    document.getElementById('status-display-type').textContent = 
                        data.content_type || data.display_type || 'Unknown';
                    document.getElementById('status-current').textContent = 
                        data.track_info || data.status || 'No status available';
                    
                    // Format last track time
                    const lastTrackElement = document.getElementById('status-last-track');
                    if (data.time_since_last_track) {
                        lastTrackElement.textContent = data.time_since_last_track;
                    } else if (data.timestamp) {
                        const date = new Date(data.timestamp * 1000);
                        lastTrackElement.textContent = date.toLocaleString();
                    } else {
                        lastTrackElement.textContent = 'No track data';
                    }
                    
                    // Update image key
                    const imageKeyElement = document.getElementById('status-image-key');
                    if (data.image_key) {
                        imageKeyElement.textContent = data.image_key;
                        imageKeyElement.style.fontFamily = 'monospace';
                        imageKeyElement.style.fontSize = '0.9em';
                    } else {
                        imageKeyElement.textContent = 'No image key';
                    }
                })
                .catch(error => {
                    console.error('Error fetching status:', error);
                    
                    // Update to error state
                    const indicator = document.getElementById('status-indicator');
                    indicator.className = 'status-indicator status-error';
                    
                    document.getElementById('status-display-type').textContent = 'Error';
                    document.getElementById('status-current').textContent = 'Failed to fetch status';
                    document.getElementById('status-last-track').textContent = 'Error';
                    document.getElementById('status-image-key').textContent = 'Error';
                });
        }

        function shouldTriggerPreview(section, fieldName) {
            // Define which sections should trigger preview
            const previewSections = ['ANNIVERSARIES', 'IMAGE_RENDER', 'IMAGE_POSITION', 'DISPLAY'];
            
            // Skip non-visual fields
            const skipFields = ['APP', 'ZONES', 'MONITORING'];
            if (skipFields.includes(section)) {
                return false;
            }
            
            // Skip specific fields that don't affect visual output
            const skipSpecificFields = [
                'loop_time', 'log_level', 'performance_logging', 
                'health_script', 'health_recheck_interval',
                'allowed_zone_names', 'forbidden_zone_names'
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
            updateDisplayImage();
            updateDisplayMetadata();
            updateStatus();
            setupFormChangeDetection();
            
            // Auto-refresh every 10 seconds
            setInterval(() => {
                if (!previewMode) {
                    updateDisplayImage();
                    updateDisplayMetadata();
                }
                updateStatus();
            }, 10000);
            
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
    
    def __init__(self, base_url="http://127.0.0.1:9090"):
        """Initialize client with base URL of internal server."""
        self.base_url = base_url
        
    def get_current_image(self) -> Optional[bytes]:
        """Get current display image from main app."""
        try:
            response = requests.get(f"{self.base_url}/current-image", timeout=5)
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Failed to get current image: HTTP {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to get current image: {e}")
            return None
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current display status from main app."""
        try:
            response = requests.get(f"{self.base_url}/current-status", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get current status: HTTP {response.status_code}")
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
                timeout=10
            )
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Failed to generate preview: HTTP {response.status_code}")
                return None
        except requests.RequestException as e:
            logger.debug(f"Failed to generate preview: {e}")
            return None
    
    def check_health(self) -> bool:
        """Check if main app is responsive."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False


# Global client instance
internal_client = InternalAppClient()


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
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp', '.avif'}
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
                valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp', '.avif'}
                
                for file_path in anniversary_dir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                        image_files.append(file_path.name)
                
                if image_files:
                    anniversary_images[anniversary_dir.name] = sorted(image_files)
    
    return anniversary_images


def create_thumbnail(image_path: Path, max_size: Tuple[int, int] = (150, 150)) -> Optional[bytes]:
    """Create a thumbnail from an image file."""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for transparency handling)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img
            
            # Create thumbnail
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            import io
            thumb_io = io.BytesIO()
            img.save(thumb_io, format='JPEG', quality=85)
            thumb_io.seek(0)
            return thumb_io.getvalue()
            
    except Exception as e:
        logger.warning(f"Failed to create thumbnail for {image_path}: {e}")
        return None


def get_current_display_status() -> Dict[str, Any]:
    """Get current display status information."""
    try:
        status = {
            "timestamp": time.time(),
            "current_image_key": None,
            "last_track_time": None,
            "display_type": "Unknown",
            "status": "No data available",
            "image_path": None,
            "time_since_last_track": None
        }
        
        # Get current image key
        current_key = get_current_image_key()
        if current_key:
            status["current_image_key"] = current_key
            
            # Try to determine what's being displayed
            if "anniversary" in current_key.lower():
                status["display_type"] = "Anniversary"
                status["status"] = f"Showing anniversary content: {current_key}"
            elif current_key == "overlay_fullscreen":
                status["display_type"] = "Message"
                status["status"] = "Showing fullscreen message"
            elif current_key.startswith("album_art_"):
                status["display_type"] = "Album Art"
                status["status"] = f"Showing album art: {current_key}"
            else:
                status["display_type"] = "Content"
                status["status"] = f"Showing: {current_key}"
            
            # Check if image file exists
            image_dir = get_saved_image_dir()
            possible_paths = [
                image_dir / f"album_art_{current_key}.jpg",
                image_dir / f"{current_key}.jpg",
                image_dir / current_key
            ]
            
            for path in possible_paths:
                if path.exists():
                    status["image_path"] = str(path)
                    break
        else:
            status["status"] = "No current display information"
        
        # Get last track time
        last_track_time = get_last_track_time()
        if last_track_time:
            status["last_track_time"] = last_track_time
            time_diff = time.time() - last_track_time
            
            if time_diff < 60:
                status["time_since_last_track"] = f"{int(time_diff)} seconds ago"
            elif time_diff < 3600:
                status["time_since_last_track"] = f"{int(time_diff // 60)} minutes ago"
            else:
                hours = int(time_diff // 3600)
                minutes = int((time_diff % 3600) // 60)
                status["time_since_last_track"] = f"{hours}h {minutes}m ago"
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting display status: {e}")
        return {
            "timestamp": time.time(),
            "status": f"Error getting status: {e}",
            "display_type": "Error",
            "current_image_key": None,
            "last_track_time": None,
            "image_path": None,
            "time_since_last_track": None
        }


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
        logger.error(f"Error deleting anniversary image {anniversary_name}/{filename}: {e}")
        return False


class WebConfigServer:
    """Web configuration server for Roon display."""
    
    def __init__(self, config_path=None, port=8080):
        """Initialize web config server."""
        self.config_path = config_path or Path("roon.cfg")
        self.port = port
        self.config_manager = ConfigManager(self.config_path)
        
    def _get_config_sections(self) -> Dict[str, Dict[str, Any]]:
        """Get configuration sections with metadata for dynamic rendering."""
        sections = {}
        
        # Read the current config file
        config = configparser.ConfigParser()
        config.read(self.config_path)
        
        # Define metadata for each section and field
        field_metadata = {
            'APP': {
                'extension_id': {'type': 'text', 'comment': 'Unique identifier for Roon extension'},
                'display_name': {'type': 'text', 'comment': 'Display name shown in Roon'},
                'display_version': {'type': 'text', 'comment': 'Version number'},
                'publisher': {'type': 'text', 'comment': 'Publisher name'},
                'email': {'type': 'text', 'comment': 'Contact email'},
            },
            'DISPLAY': {
                'type': {
                    'type': 'select', 
                    'options': ['system_display', 'epd13in3E'], 
                    'comment': 'Display type: system_display for regular monitors, epd13in3E for e-ink'
                },
                'tkinter_fullscreen': {
                    'type': 'boolean', 
                    'comment': 'Enable fullscreen mode for system displays (ignored by e-ink)'
                },
            },
            'IMAGE_RENDER': {
                'colour_balance_adjustment': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Color balance adjustment (0.1-3.0, default: 1.0)'
                },
                'contrast_adjustment': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Contrast adjustment (0.1-3.0, default: 1.0)'
                },
                'sharpness_adjustment': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Sharpness adjustment (0.1-3.0, default: 1.0)'
                },
                'brightness_adjustment': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Brightness adjustment (0.1-3.0, default: 1.0)'
                },
            },
            'IMAGE_POSITION': {
                'position_offset_x': {
                    'type': 'number', 'input_type': 'number',
                    'comment': 'Horizontal position offset in pixels'
                },
                'position_offset_y': {
                    'type': 'number', 'input_type': 'number',
                    'comment': 'Vertical position offset in pixels'
                },
                'scale_x': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Horizontal scale factor (0.1-3.0, default: 1.0)'
                },
                'scale_y': {
                    'type': 'number', 'input_type': 'number', 'step': '0.1',
                    'comment': 'Vertical scale factor (0.1-3.0, default: 1.0)'
                },
                'rotation': {
                    'type': 'select',
                    'options': ['0', '90', '180', '270'],
                    'comment': 'Image rotation in degrees'
                },
            },
            'ZONES': {
                'allowed_zone_names': {
                    'type': 'text',
                    'comment': 'Comma-separated list of allowed zone names (leave blank for all)'
                },
                'forbidden_zone_names': {
                    'type': 'text',
                    'comment': 'Comma-separated list of forbidden zone names'
                },
            },
            'ANNIVERSARIES': {
                'enabled': {
                    'type': 'boolean',
                    'comment': 'Enable anniversary notifications'
                },
                'border': {
                    'type': 'number', 'input_type': 'number',
                    'comment': 'Border size for anniversary messages in pixels'
                },
            },
            'MONITORING': {
                'log_level': {
                    'type': 'select',
                    'options': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                    'comment': 'Logging level'
                },
                'loop_time': {
                    'type': 'text',
                    'comment': 'Event loop sleep time (e.g., "10 minutes", "30 seconds")'
                },
                'performance_logging': {
                    'type': 'select',
                    'options': ['', 'info', 'debug'],
                    'comment': 'Enable performance logging (empty = disabled)'
                },
                'health_script': {
                    'type': 'text',
                    'comment': 'Path to health monitoring script (optional)'
                },
                'health_recheck_interval': {
                    'type': 'text',
                    'comment': 'Time between health script calls (e.g., "30 minutes")'
                },
            }
        }
        
        # Build sections with current values and metadata
        for section_name in config.sections():
            if section_name not in field_metadata:
                continue
                
            sections[section_name] = {}
            section_config = config[section_name]
            
            for key, value in section_config.items():
                if key in field_metadata[section_name]:
                    metadata = field_metadata[section_name][key].copy()
                    metadata['value'] = value
                    
                    # Set default input type if not specified
                    if 'input_type' not in metadata:
                        metadata['input_type'] = 'text'
                        
                    # Handle boolean conversion
                    if metadata['type'] == 'boolean':
                        metadata['value'] = value.lower() in ('true', '1', 'yes', 'on')
                        
                    sections[section_name][key] = metadata
                elif section_name == 'ANNIVERSARIES' and not key.startswith('#'):
                    # Handle anniversary entries
                    sections[section_name][key] = {
                        'type': 'anniversary',
                        'value': value,
                        'input_type': 'text'
                    }
                    
        return sections
    
    def _save_config(self, form_data: Dict[str, str], files: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Save configuration from form data and handle image uploads.
        
        Returns:
            Tuple of (success: bool, error_messages: List[str])
        """
        error_messages = []
        
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path)
            
            # Process regular form data
            for field_name, value in form_data.items():
                if '.' in field_name and not field_name.startswith('anniversary_'):
                    section_name, key = field_name.split('.', 1)
                    
                    if section_name not in config:
                        config[section_name] = {}
                        
                    config[section_name][key] = value
            
            # Handle anniversary entries separately
            anniversary_names = {}
            anniversary_dates = {}
            anniversary_messages = {}
            anniversary_waits = {}
            
            for field_name, value in form_data.items():
                if field_name.startswith('anniversary_name_'):
                    index = field_name.split('_')[-1]
                    anniversary_names[index] = value
                elif field_name.startswith('anniversary_date_'):
                    index = field_name.split('_')[-1]
                    anniversary_dates[index] = value
                elif field_name.startswith('anniversary_message_'):
                    index = field_name.split('_')[-1]
                    anniversary_messages[index] = value
                elif field_name.startswith('anniversary_wait_'):
                    index = field_name.split('_')[-1]
                    anniversary_waits[index] = value
            
            # Clear existing anniversary entries (except enabled/border/comments)
            if 'ANNIVERSARIES' in config:
                keys_to_remove = []
                for key in config['ANNIVERSARIES']:
                    if key not in ['enabled', 'border'] and not key.startswith('#'):
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del config['ANNIVERSARIES'][key]
            
            # Add new anniversary entries
            if 'ANNIVERSARIES' not in config:
                config['ANNIVERSARIES'] = {}
                
            for index in anniversary_names:
                if (index in anniversary_dates and index in anniversary_messages and 
                    index in anniversary_waits):
                    name = anniversary_names[index].strip()
                    date = anniversary_dates[index].strip()
                    message = anniversary_messages[index].strip()
                    wait = anniversary_waits[index].strip()
                    
                    if name and date and message and wait:
                        # Combine into the expected format
                        config_value = f"{date},{message},{wait}"
                        config['ANNIVERSARIES'][name] = config_value
                        
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
                                        if validate_image_format(file_data, uploaded_file.filename):
                                            # Save the file
                                            safe_filename = secure_filename(uploaded_file.filename)
                                            file_path = anniversary_dir / safe_filename
                                            
                                            with open(file_path, 'wb') as f:
                                                f.write(file_data)
                                            
                                            logger.info(f"Saved anniversary image: {file_path}")
                                        else:
                                            error_messages.append(
                                                f"Invalid image format for {uploaded_file.filename}. "
                                                f"Supported formats: JPG, PNG, BMP, GIF, TIFF, WebP, AVIF"
                                            )
            
            # Handle unchecked checkboxes
            sections = self._get_config_sections()
            for section_name, section_data in sections.items():
                for key, config_item in section_data.items():
                    if config_item['type'] == 'boolean':
                        field_name = f"{section_name}.{key}"
                        if field_name not in form_data:
                            if section_name not in config:
                                config[section_name] = {}
                            config[section_name][key] = 'false'
            
            # Save config file
            with open(self.config_path, 'w') as f:
                config.write(f)
                
            logger.info("Configuration saved successfully")
            return True, error_messages
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            error_messages.append(f"Error saving configuration: {e}")
            return False, error_messages


# Flask routes
@app.route('/', methods=['GET', 'POST'])
def config_interface():
    """Main configuration interface."""
    web_server = app.config['web_server']
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        success, error_messages = web_server._save_config(request.form, request.files)
        
        if success:
            flash('Configuration saved successfully! Restarting service...', 'success')
            
            # Show any image upload warnings
            for error_msg in error_messages:
                flash(error_msg, 'error')
            
            # Import here to avoid circular imports
            import subprocess
            try:
                subprocess.run(['sudo', 'systemctl', 'restart', 'roon-album-art-display'], check=True)
                flash('Service restarted successfully!', 'success')
            except subprocess.CalledProcessError as e:
                flash(f'Error restarting service: {e}', 'error')
        else:
            flash('Error saving configuration!', 'error')
            for error_msg in error_messages:
                flash(error_msg, 'error')
            
        return redirect(url_for('config_interface'))
    
    # GET request - show form
    sections = web_server._get_config_sections()
    
    # Count anniversary entries for JavaScript counter
    anniversary_count = 0
    if 'ANNIVERSARIES' in sections:
        anniversary_count = len([k for k in sections['ANNIVERSARIES'].keys() 
                               if k not in ['enabled', 'border'] and not k.startswith('#')])
    
    # Get existing anniversary images
    anniversary_images = get_anniversary_images()
    
    return render_template_string(CONFIG_TEMPLATE, 
                                sections=sections, 
                                anniversary_count=anniversary_count,
                                anniversary_images=anniversary_images)


@app.route('/thumbnail/<anniversary_name>/<filename>')
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
        thumbnail_data = create_thumbnail(image_path)
        if thumbnail_data:
            import io
            return send_file(
                io.BytesIO(thumbnail_data),
                mimetype='image/jpeg',
                as_attachment=False,
                download_name=f"thumb_{safe_filename}"
            )
        else:
            return "Could not create thumbnail", 500
            
    except Exception as e:
        logger.error(f"Error serving thumbnail {anniversary_name}/{filename}: {e}")
        return "Internal server error", 500


@app.route('/delete-image', methods=['POST'])
def delete_image():
    """Delete an anniversary image."""
    try:
        data = request.get_json()
        anniversary_name = data.get('anniversary_name')
        filename = data.get('filename')
        
        if not anniversary_name or not filename:
            return jsonify({'success': False, 'error': 'Missing anniversary name or filename'})
        
        # Validate and secure the filenames
        safe_anniversary = secure_filename(anniversary_name)
        safe_filename = secure_filename(filename)
        
        if not safe_anniversary or not safe_filename:
            return jsonify({'success': False, 'error': 'Invalid filename'})
        
        # Delete the image
        success = delete_anniversary_image(safe_anniversary, safe_filename)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete image'})
            
    except Exception as e:
        logger.error(f"Error in delete image endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/current-display-image')
def serve_current_display_image():
    """Proxy current display image from main app."""
    try:
        image_data = internal_client.get_current_image()
        if image_data:
            return send_file(
                io.BytesIO(image_data),
                mimetype='image/jpeg',
                as_attachment=False
            )
        else:
            # Return placeholder image when no image available
            return _create_placeholder_response()
    except Exception as e:
        logger.error(f"Error serving current display image: {e}")
        return _create_placeholder_response()


@app.route('/display-status')
def get_display_status():
    """Get enhanced status including internal app data."""
    try:
        # Get status from internal app
        internal_status = internal_client.get_current_status()
        
        # Combine with existing file-based status
        file_status = get_current_display_status()
        
        # Check connection health
        is_connected = internal_client.check_health()
        
        return jsonify({
            **file_status,
            **internal_status,
            'internal_app_connected': is_connected,
            'internal_app_responsive': is_connected
        })
    except Exception as e:
        logger.error(f"Error getting display status: {e}")
        return jsonify({
            'error': str(e),
            'internal_app_connected': False,
            'internal_app_responsive': False
        })


@app.route('/preview-image', methods=['POST'])
def generate_preview_image():
    """Generate preview image with form changes."""
    try:
        # Parse form data into config format, excluding file uploads for now
        config_data = _parse_form_to_config_for_preview(request.form, request.files)
        
        # Request preview from main app
        preview_data = internal_client.generate_preview(config_data)
        
        if preview_data:
            return send_file(
                io.BytesIO(preview_data),
                mimetype='image/jpeg',
                as_attachment=False
            )
        else:
            return jsonify({'error': 'Preview generation failed'}), 500
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return jsonify({'error': str(e)}), 500


def _create_placeholder_response():
    """Create placeholder image response when main app not available."""
    try:
        # Create simple placeholder image
        placeholder = Image.new('RGB', (400, 300), color=(200, 200, 200))
        
        # Convert to bytes
        img_io = io.BytesIO()
        placeholder.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Error creating placeholder: {e}")
        return jsonify({'error': 'No image available'}), 404


def _parse_form_to_config(form_data, files) -> Dict[str, Any]:
    """Parse form data into configuration format for saving to config file."""
    config = {}
    
    try:
        # Parse regular configuration fields (section.field format)
        for key, value in form_data.items():
            if '.' in key and not key.startswith('anniversary_'):
                # Handle nested config like IMAGE_RENDER.brightness_adjustment
                config[key] = value
            elif key.startswith('anniversary_'):
                # Handle anniversary fields
                config[key] = value
            else:
                # Handle other fields
                config[key] = value
        
        # Handle checkboxes that are only present when checked
        # For unchecked checkboxes, we need to detect them and set to false
        # This is a simplified approach - in full implementation we'd track all possible checkboxes
        checkbox_fields = [
            'ANNIVERSARIES.enabled',
            'DISPLAY.tkinter_fullscreen'
        ]
        
        for checkbox_field in checkbox_fields:
            if checkbox_field not in config:
                config[checkbox_field] = 'false'
        
        # Handle file uploads (for anniversary images)
        if files:
            for field_name, file_list in files.items():
                if field_name.startswith('anniversary_images_'):
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
            if '.' in key and not key.startswith('anniversary_'):
                # Handle nested config like IMAGE_RENDER.brightness_adjustment
                config[key] = value
            elif key.startswith('anniversary_'):
                # Handle anniversary fields
                config[key] = value
            else:
                # Handle other fields
                config[key] = value
        
        # Handle checkboxes that are only present when checked
        checkbox_fields = [
            'ANNIVERSARIES.enabled',
            'DISPLAY.tkinter_fullscreen'
        ]
        
        for checkbox_field in checkbox_fields:
            if checkbox_field not in config:
                config[checkbox_field] = 'false'
        
        # For preview, we'll skip file uploads for now
        # TODO: In future, could convert files to base64 or handle differently
        if files:
            file_count = sum(len(file_list) if hasattr(file_list, '__len__') else 1 
                           for file_list in files.values() if file_list)
            if file_count > 0:
                config['_has_file_uploads'] = str(file_count)
                logger.debug(f"Preview request has {file_count} file uploads (skipped for preview)")
        
        logger.debug(f"Parsed form to preview config with {len(config)} fields")
        return config
        
    except Exception as e:
        logger.error(f"Error parsing form data for preview: {e}")
        return {}


@app.route('/status')
def get_status():
    """Get current display status as JSON."""
    try:
        status = get_current_display_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error in status endpoint: {e}")
        return jsonify({
            "timestamp": time.time(),
            "status": f"Error: {e}",
            "display_type": "Error",
            "current_image_key": None,
            "last_track_time": None,
            "image_path": None,
            "time_since_last_track": None
        })


def main():
    """Main entry point for web config server."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Roon Display Web Configuration Server')
    parser.add_argument('--port', type=int, default=8080, help='Port to run server on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create web server instance
    web_server = WebConfigServer(config_path=args.config, port=args.port)
    
    # Store in Flask app config for route access
    app.config['web_server'] = web_server
    
    logger.info(f"Starting Roon Display web configuration server on {args.host}:{args.port}")
    
    try:
        app.run(host=args.host, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Web configuration server stopped")


if __name__ == '__main__':
    main()
