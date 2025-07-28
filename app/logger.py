import logging
import os
from datetime import datetime

LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create a file handler
    log_file = os.path.join(LOG_DIR, 'vehicle_log.csv')
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.INFO)

    # Create a logging format
    formatter = logging.Formatter('%(asctime)s,%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)

    # Add the handlers to the logger
    if not logger.handlers:
        # Add header if the file is new
        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            with open(log_file, 'a') as f:
                f.write('timestamp,number_plate,registration_state,registration_year,vehicle_type,fuel_type,vehicle_category,image_path,tariff\n')
        logger.addHandler(handler)

    return logger

def log_vehicle_data(logger, data, image_path):
    log_message = f"{data['number_plate']},{data['registration_state']},{data['registration_year']},{data['vehicle_type']},{data['fuel_type']},{data['vehicle_category']},{image_path},{data['tariff']}"
    logger.info(log_message)

def save_best_frame(image_bytes):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_dir = os.path.join(LOG_DIR, 'images')
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    image_path = os.path.join(image_dir, f'frame_{timestamp}.jpg')
    with open(image_path, 'wb') as f:
        f.write(image_bytes)

    return image_path
