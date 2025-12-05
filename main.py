import os
import random
import string
import subprocess
import time
import threading
from datetime import datetime, timedelta
from PIL import Image, ImageEnhance, ImageFilter
from config_reader import Config

class VID_IMG_EDIT():
    def __init__(self, upload_folder, processed_folder):
        self.upload_folder = upload_folder  # Folder for uploading source files
        self.processed_folder = processed_folder  # Folder for saving processed files
        self.task_statuses_folder = "task_statuses"  # Folder for task status files
        self.config = Config()
        self.ffmpeg_path = None  # путь к ffmpeg
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_files, daemon=True)
        self.cleanup_thread.start()

    def _cleanup_old_files(self):
        """Periodically clean up old files."""
        while True:
            try:
                current_time = datetime.now()
                
                # Clean uploads folder (1 hour retention)
                for filename in os.listdir(self.upload_folder):
                    file_path = os.path.join(self.upload_folder, filename)
                    if os.path.isfile(file_path):
                        creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if current_time - creation_time > timedelta(hours=1):
                            os.remove(file_path)
                            print(f"Removed old upload file: {filename}")

                # Clean processed folder (5 minutes retention)
                for filename in os.listdir(self.processed_folder):
                    file_path = os.path.join(self.processed_folder, filename)
                    if os.path.isfile(file_path):
                        creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                        if current_time - creation_time > timedelta(minutes=5):
                            os.remove(file_path)
                            print(f"Removed old processed file: {filename}")

                # Clean task_statuses folder (5 minutes retention)
                if os.path.exists(self.task_statuses_folder):
                    for filename in os.listdir(self.task_statuses_folder):
                        file_path = os.path.join(self.task_statuses_folder, filename)
                        if os.path.isfile(file_path):
                            creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                            if current_time - creation_time > timedelta(minutes=5):
                                os.remove(file_path)
                                print(f"Removed old task status file: {filename}")

            except Exception as e:
                print(f"Error during cleanup: {e}")

            # Check every 30 seconds
            time.sleep(30)

    def create_folder(self):
        """Create folders if they don't exist."""
        for folder in [self.processed_folder, self.task_statuses_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)

    def unique_image(self, file_path, task_code):
        """Image processing."""
        try:
            im = Image.open(file_path)  # Open the image
        except Exception as e:
            print(f"Error opening image {file_path}: {e}")
            return None

        # Random parameter changes with minimum values
        brightness_factor = 1.001  # minimum brightness change
        contrast_factor = 1.001    # minimum contrast change
        rotate_angle = 0           # remove rotation
        noise_level = 0.1          # minimum noise level

        # Image rotation
        im_rotate = im.rotate(rotate_angle)

        # Add random noise
        im_noise = im_rotate.filter(ImageFilter.GaussianBlur(noise_level))

        # Change brightness and contrast
        enhancer_brightness = ImageEnhance.Brightness(im_noise)
        im_bright = enhancer_brightness.enhance(brightness_factor)

        enhancer_contrast = ImageEnhance.Contrast(im_bright)
        im_contrast = enhancer_contrast.enhance(contrast_factor)

        # Generate output filename
        output_image_path = os.path.join(self.processed_folder, f"{task_code}_unique.png")

        # Save the image
        im_contrast.save(output_image_path)
        print(f"Image {file_path} processed and saved as {output_image_path}")

        return output_image_path

    def unique_video(self, file_path, task_code, progress_callback=None):
        """Video processing."""
        output_video_path = os.path.join(self.processed_folder, f"{task_code}.mp4")
        error_details = []

        try:
            if progress_callback:
                progress_callback(0, "Initializing")

            # Check if file exists and is accessible
            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")

            # Try to read the file to check if it's accessible
            try:
                with open(file_path, 'rb') as f:
                    f.read(1024)
            except Exception as e:
                raise Exception(f"Cannot access file: {str(e)}")

            # Get video duration using ffprobe
            duration_cmd = [
                'ffprobe',
                "-i", file_path,
                "-show_entries", "format=duration",
                "-v", "error",
                "-of", "csv=p=0"
            ]
            try:
                result = subprocess.run(duration_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                    raise Exception(f"FFprobe error: {error_msg}")
                duration = float(result.stdout.strip())
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode().strip() if e.stderr else "Unknown error"
                raise Exception(f"FFprobe error: {error_msg}")
            except ValueError as e:
                raise Exception("Could not parse video duration")

            if progress_callback:
                progress_callback(10, "Analyzing file")

            # Get parameters from config
            video_options = self.config.get_video_options()
            use_random = video_options.get('random_config', False)

            if progress_callback:
                progress_callback(20, "Starting process")

            # Set parameters
            if use_random:
                fps_random = random.randint(24, 30)
                contrast_random = round(random.uniform(0.95, 1.05), 3)
                saturation_random = round(random.uniform(0.95, 1.05), 3)
                rotate_random = random.randint(-2, 2)
            else:
                fps_random = video_options.get('fps', 24)
                contrast_random = max(0.95, min(1.05, video_options.get('contrast', 1.0)))
                saturation_random = max(0.95, min(1.05, video_options.get('saturation', 1.0)))
                rotate_random = max(-2, min(2, video_options.get('rotate', 0)))

            # Form filter string
            filter_str = (
                f"eq=contrast={contrast_random}:saturation={saturation_random},"
                f"rotate={rotate_random}*PI/180"
            )

            # FFmpeg command with progress
            cmd = [
                'ffmpeg',
                "-i", file_path,
                "-vf", filter_str,
                "-r", str(fps_random),
                "-c:a", "copy",
                "-preset", "fast",
                "-progress", "pipe:1",
                "-y",
                output_video_path
            ]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            # Track progress
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if line.startswith("out_time_ms="):
                    try:
                        current_time = float(line.split("=")[1].strip()) / 1000000
                        if progress_callback and duration > 0:
                            progress = min(int((current_time / duration) * 100), 100)
                            if progress > 20:  # Не перезаписываем начальные этапы
                                if progress < 30:
                                    stage = "Applying contrast adjustments"
                                elif progress < 45:
                                    stage = "Processing saturation"
                                elif progress < 60:
                                    stage = "Applying rotation effects"
                                elif progress < 75:
                                    stage = "Adjusting frame rate"
                                elif progress < 90:
                                    stage = "Encoding video"
                                else:
                                    stage = "Finalizing video"
                                progress_callback(progress, stage)
                    except:
                        pass

            if process.returncode == 0 and os.path.exists(output_video_path):
                if os.path.getsize(output_video_path) == 0:
                    raise Exception("Output file is empty")
                
                if progress_callback:
                    progress_callback(100, "Processing complete")
                return output_video_path
            else:
                raise Exception("FFmpeg processing failed")

        except Exception as e:
            if os.path.exists(output_video_path):
                os.remove(output_video_path)
            raise Exception(str(e))