import os
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from google.generativeai import types # Ensure types is imported
from PIL import Image
import io
import base64
import logging
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

gemini_api_key = None # Initialize
try:
    gemini_api_key = os.environ['GEMINI_API_KEY']
    if not gemini_api_key:
        logging.critical("CRITICAL: GEMINI_API_KEY not found in environment or .env file.")
    else:
        genai.configure(api_key=gemini_api_key)
        logging.info("GEMINI_API_KEY loaded and configured successfully.")
except KeyError:
    logging.critical("CRITICAL: GEMINI_API_KEY environment variable not set and .env not loaded or key missing.")

text_model_name = "gemini-1.5-flash-latest"
image_model_name = "gemini-2.0-flash-preview-image-generation"
text_generation_config_dict = { # Renamed to avoid conflict with types.GenerationConfig instance
    "temperature": 0.8, "top_p": 0.9, "top_k": 50,
    "max_output_tokens": 4096, "response_mime_type": "text/plain",
}
text_safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]
text_model = genai.GenerativeModel(
    model_name=text_model_name,
    safety_settings=text_safety_settings,
    generation_config=text_generation_config_dict, # Use the dict here
)
image_model = genai.GenerativeModel(model_name=image_model_name)

SYSTEM_INSTRUCTION_FOR_AUTONOMOUS_IMAGE = """
You are a helpful and expressive conversational AI.
Your goal is to provide informative and engaging text responses.
In addition to your text response, suggest an image when you believe it can make the conversation more vivid, help explain something visually, or add a touch of appropriate emotion or humor.
To suggest an image, include a special tag in your response: `[GENERATE_IMAGE: <your descriptive prompt for the image here>]`.
For example, if you're describing a beautiful sunset, you might say: 'It was a breathtaking view. [GENERATE_IMAGE: A vibrant orange and purple sunset over a calm ocean]'.
While not for every message, be reasonably liberal in identifying good opportunities to enhance the chat with a relevant image.
If you suggest an image, make your main text response flow naturally around it or lead into it.
Your main text response should still be complete and make sense on its own.
Ensure the image prompt you provide within the tag is descriptive and suitable for an image generation model.
"""

@app.route('/')
def index():
    return render_template('index.html')

def parse_image_generation_tag(text_response):
    """
    Parses the AI's text response for the [GENERATE_IMAGE: ...] tag.
    Returns the extracted image prompt and the cleaned text response.
    """
    match = re.search(r"\[GENERATE_IMAGE:\s*(.*?)\s*\]", text_response, re.IGNORECASE | re.DOTALL)
    if match:
        image_prompt = match.group(1).strip()
        cleaned_text = text_response.replace(match.group(0), "").strip()
        cleaned_text = re.sub(r'^\n+|\n+$', '', cleaned_text)
        return image_prompt, cleaned_text
    return None, text_response

@app.route('/send_message', methods=['POST'])
def send_message():
    user_message = request.json.get('message')
    logging.info(f"Received message: {user_message}")

    current_api_key = gemini_api_key
    chatbot_text_response = "Sorry, I couldn't process your request."
    image_data_uri = None

    if not current_api_key:
        logging.error("API key not configured (not found in .env or environment).")
        chatbot_text_response = "Error: API key not configured. Please set GEMINI_API_KEY in your .env file or environment."
        return jsonify({'text': chatbot_text_response, 'image_url': None})

    try:
        logging.info(f"Generating text response for prompt: '{user_message}' with system instruction for autonomous images.")
        full_prompt_parts = [SYSTEM_INSTRUCTION_FOR_AUTONOMOUS_IMAGE, "User input: " + user_message]
        text_gen_response_object = text_model.generate_content(full_prompt_parts)
        ai_text_output = ""

        if text_gen_response_object.prompt_feedback and text_gen_response_object.prompt_feedback.block_reason:
            logging.warning(f"Text generation prompt was blocked: {text_gen_response_object.prompt_feedback.block_reason_message or text_gen_response_object.prompt_feedback.block_reason}")
            raise ValueError(f"Prompt was blocked by safety settings: {text_gen_response_object.prompt_feedback.block_reason_message or text_gen_response_object.prompt_feedback.block_reason}")

        if text_gen_response_object.candidates and text_gen_response_object.candidates[0].content.parts:
            ai_text_output = "".join(part.text for part in text_gen_response_object.candidates[0].content.parts if hasattr(part, 'text') and part.text)
        elif hasattr(text_gen_response_object, 'text'):
             ai_text_output = text_gen_response_object.text

        if not ai_text_output:
            logging.warning("AI text output was empty after generation attempt.")

        logging.info(f"AI Raw Text Output (before parsing for image tag): '{ai_text_output}'")
        image_prompt_from_ai, cleaned_text_response = parse_image_generation_tag(ai_text_output)
        chatbot_text_response = cleaned_text_response

        if image_prompt_from_ai:
            logging.info(f"AI suggested image generation with prompt: '{image_prompt_from_ai}'")
            try:
                # MODIFICATION HERE: Create GenerationConfig instance and set attribute
                image_gen_config = types.GenerationConfig()
                # Using order from documentation first: ['TEXT', 'IMAGE']
                image_gen_config.response_modalities = ['TEXT', 'IMAGE']

                image_gen_api_response = image_model.generate_content(
                    contents=[image_prompt_from_ai],
                    generation_config=image_gen_config # Pass the configured instance
                )
                image_generated_this_turn = False
                text_accompanying_image = []

                if image_gen_api_response.prompt_feedback and image_gen_api_response.prompt_feedback.block_reason:
                    logging.warning(f"AI-suggested image prompt was blocked: {image_gen_api_response.prompt_feedback.block_reason_message or image_gen_api_response.prompt_feedback.block_reason}")
                    chatbot_text_response += f"\n*(The suggested image '{image_prompt_from_ai}' was blocked by safety filters.)*"
                elif image_gen_api_response.candidates:
                    for part in image_gen_api_response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            text_accompanying_image.append(part.text)
                        elif hasattr(part, 'inline_data') and part.inline_data and hasattr(part.inline_data, 'data') and part.inline_data.data:
                            image_bytes = part.inline_data.data
                            mime_type = part.inline_data.mime_type if hasattr(part.inline_data, 'mime_type') else 'image/png'
                            base64_image_data = base64.b64encode(image_bytes).decode('utf-8')
                            image_data_uri = f"data:{mime_type};base64,{base64_image_data}"
                            image_generated_this_turn = True
                            logging.info(f"AI-suggested image generated successfully. Mime_type: {mime_type}")

                if image_generated_this_turn:
                    if text_accompanying_image:
                        chatbot_text_response += "\n\n---\n*Image description from model:* " + " ".join(text_accompanying_image)
                elif not (image_gen_api_response.prompt_feedback and image_gen_api_response.prompt_feedback.block_reason): # Avoid double message
                    logging.warning("AI suggested an image, but image model did not return image data (and not due to prompt block).")

            except Exception as img_e: # Catch potential AttributeError if response_modalities cannot be set
                logging.error(f"Error during AI-suggested image generation (could be AttributeError or API error): {img_e}", exc_info=True)
                if isinstance(img_e, AttributeError) and 'response_modalities' in str(img_e):
                    chatbot_text_response += f"\n*(Sorry, there's a configuration issue setting image properties: {str(img_e)})*"
                else: # For other errors, including potential 400 from API
                    chatbot_text_response += f"\n*(Sorry, I couldn't generate the suggested image: {str(img_e)})*"

        if not chatbot_text_response.strip() and not image_data_uri:
            logging.info("Response is empty after processing, using default.")
            chatbot_text_response = "I received your message and processed it, but I don't have a specific text reply or image for this."
        elif not chatbot_text_response.strip() and image_data_uri: # Image generated, but main text was only the tag
             chatbot_text_response = "Here's an image based on our conversation:"


    except ValueError as ve: # From text_model safety block usually
        logging.error(f"ValueError calling Gemini API (text model): {ve} (Prompt: '{user_message}')", exc_info=True)
        if "prompt" in str(ve).lower() and ("blocked" in str(ve).lower() or "safety" in str(ve).lower()):
            chatbot_text_response = "I'm sorry, your request was blocked by the safety filters. Please try a different prompt."
        elif "SAFETY" in str(ve).upper():
             chatbot_text_response = "I'm sorry, your request triggered a safety filter. Please rephrase."
        else:
            chatbot_text_response = "A value or configuration error occurred processing your request."
    except Exception as e: # Generic catch-all
        logging.error(f"Generic error for prompt '{user_message}': {e}", exc_info=True)
        chatbot_text_response = "An unexpected error occurred. Please try again."

    return jsonify({
        'text': chatbot_text_response,
        'image_url': image_data_uri
    })

if __name__ == '__main__':
    if not gemini_api_key:
        logging.critical("GEMINI_API_KEY is not set. App will likely fail if API calls are made.")
    app.run(debug=True, host='0.0.0.0', port=5000)
