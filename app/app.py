from flask import Flask, render_template, Response, jsonify, request
import cv2
import google.generativeai as genai
import os
import json
from logger import get_logger, log_vehicle_data, save_best_frame
from tariff import calculate_tariff

app = Flask(__name__)
vehicle_logger = get_logger('vehicle_logger')

# Configure the Gemini API
# IMPORTANT: Replace with your actual API key
os.environ["GEMINI_API_KEY"] = "AIzaSyAgXFXqgLjjW_8OxMSi74BUz7fsQq4AXCw"
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
]

model = genai.GenerativeModel(model_name="gemini-1.0-pro-vision-latest",
                              generation_config=generation_config,
                              safety_settings=safety_settings)

@app.route('/')
def index():
    return render_template('index.html')

def gen_frames():
    camera = cv2.VideoCapture(0)
    while True:
        success, frame = camera.read()  # read the camera frame
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/analyze_vehicle', methods=['POST'])
def analyze_vehicle():
    # Get the image from the request
    image_file = request.files['image']
    image_bytes = image_file.read()

    image_parts = [
        {
            "mime_type": "image/jpeg",
            "data": image_bytes
        },
    ]

    prompt_parts = [
        "Analyze the following image of a vehicle and provide the following information in JSON format:\n"
        "- number_plate: The license plate number of the vehicle.\n"
        "- registration_state: The state where the vehicle is registered.\n"
        "- registration_year: The year the vehicle was registered.\n"
        "- vehicle_type: The type of vehicle (e.g., car, truck, motorcycle).\n"
        "- fuel_type: The fuel type of the vehicle (e.g., gasoline, diesel, electric).\n"
        "- vehicle_category: The category of the vehicle (e.g., commercial, domestic, government).\n"
        "If any of this information is not available in the image, please indicate 'N/A'.",
        image_parts[0],
    ]

    response = model.generate_content(prompt_parts)

    # Parse the JSON response
    try:
        # Clean the response to remove the ```json and ``` markers
        cleaned_response = response.text.replace('```json', '').replace('```', '').strip()
        vehicle_info = json.loads(cleaned_response)
    except json.JSONDecodeError:
        # Handle cases where the response is not valid JSON
        return jsonify({'error': 'Failed to parse Gemini API response.'}), 500

    # Calculate the tariff
    tariff = calculate_tariff(vehicle_info)
    vehicle_info['tariff'] = tariff

    # Save the best frame and log the data
    image_path = save_best_frame(image_bytes)
    log_vehicle_data(vehicle_logger, vehicle_info, image_path)

    return jsonify(vehicle_info)


if __name__ == '__main__':
    app.run(debug=True)
