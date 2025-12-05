from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import random
import string
import time
import json
import threading
import requests
from main import VID_IMG_EDIT  # Import the class for processing

app = Flask(__name__)

# Folder settings for storage
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
STATUS_FOLDER = 'task_statuses'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(STATUS_FOLDER, exist_ok=True)

# Initialize the class for uniqueness
video_image_editor = VID_IMG_EDIT(UPLOAD_FOLDER, PROCESSED_FOLDER)

def generate_unique_code():
    """Generate a unique code for task tracking."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

def save_task_status(task_id, status):
    """Save task status to file."""
    status_path = os.path.join(STATUS_FOLDER, f"{task_id}.json")
    with open(status_path, 'w') as status_file:
        json.dump(status, status_file)

def load_task_status(task_id):
    """Load task status from file."""
    status_path = os.path.join(STATUS_FOLDER, f"{task_id}.json")
    if os.path.exists(status_path):
        with open(status_path, 'r') as status_file:
            return json.load(status_file)
    return None

def process_file(file_path, output_path, task_id, is_video):
    """Process video or image file."""
    def update_progress(progress, stage=None):
        stages = {
            0: 'Initializing',
            10: 'Analyzing file',
            20: 'Starting process',
            100: 'Processing complete'
        }
        status = {
            'state': 'PROCESSING' if progress < 100 else 'COMPLETED',
            'progress': progress,
            'stage': stage or stages.get(progress, 'Processing')
        }
        save_task_status(task_id, status)

    try:
        if is_video:
            try:
                unique_file_path = video_image_editor.unique_video(file_path, task_id, progress_callback=update_progress)
            except Exception as e:
                status = {
                    'state': 'FAILED',
                    'progress': 0,
                    'stage': 'Error processing video',
                    'error': str(e)
                }
                save_task_status(task_id, status)
                return
        else:
            unique_file_path = video_image_editor.unique_image(file_path, task_id)
            update_progress(100, 'Image processing complete')

        if not unique_file_path or not os.path.exists(unique_file_path):
            status = {
                'state': 'FAILED',
                'progress': 0,
                'stage': 'Failed to create output file',
                'error': 'Processing failed'
            }
            save_task_status(task_id, status)
    except Exception as e:
        status = {
            'state': 'FAILED',
            'progress': 0,
            'stage': 'Unexpected error',
            'error': str(e)
        }
        save_task_status(task_id, status)

def process_file_async(file_path, output_path, task_id, is_video):
    """Asynchronous file processing."""
    thread = threading.Thread(target=process_file, args=(file_path, output_path, task_id, is_video))
    thread.start()

@app.route('/upload', methods=['POST'])
def upload_file_by_url():
    """Endpoint for uploading a file by URL."""
    data = request.get_json()

    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400

    file_url = data['url']
    
    # Get the file name from the URL
    filename = file_url.split("/")[-1]
    if not filename:
        return jsonify({'error': 'Invalid URL, no file found'}), 400
    
    try:
        # Download the file from the URL
        response = requests.get(file_url, stream=True)
        response.raise_for_status()  # Check if the request was successful
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f"Failed to download file from URL: {str(e)}"}), 400

    # Save the file to the server
    file_path = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
    with open(file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    # Generate a unique code for task tracking
    task_code = generate_unique_code()

    # Create the initial task status
    save_task_status(task_code, {
        'state': 'PROCESSING',
        'progress': 0,
        'stage': 'File upload complete'
    })

    # Determine the file type (image or video)
    is_video = filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))  # Can be extended to include more video types
    output_path = os.path.join(PROCESSED_FOLDER, f"{task_code}_{filename}")
    
    # Asynchronous file processing
    process_file_async(file_path, output_path, task_code, is_video)

    # Return the task code immediately
    return jsonify({'task_code': task_code, 'message': 'File uploaded successfully'}), 202

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """Endpoint for getting the task status."""
    status = load_task_status(task_id)
    if status:
        return jsonify(status)
    return jsonify({'error': 'Task not found'}), 404

@app.route('/download/<task_id>', methods=['GET'])
def download_file(task_id):
    """Endpoint for downloading the processed file."""
    status = load_task_status(task_id)
    if status and status['state'] == 'COMPLETED':
        # Generate the file path from the task_id
        output_path = os.path.join(PROCESSED_FOLDER, f"{task_id}.mp4")
        if not os.path.exists(output_path):
            output_path = os.path.join(PROCESSED_FOLDER, f"{task_id}_unique.png")
        if os.path.exists(output_path):
            return send_file(output_path, as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    elif status and status['state'] == 'PROCESSING':
        return jsonify({'error': 'File is still being processed, try again later.'}), 202
    else:
        return jsonify({'error': 'Task failed or does not exist.'}), 404


if __name__ == "__main__":
    app.run(debug=False)