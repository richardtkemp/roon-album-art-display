/**
 * Thumbnail management functionality
 */

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

// Expose functions globally
window.deleteImage = deleteImage;