import unittest
import sys
import os
from unittest.mock import patch, MagicMock, PropertyMock
import base64
import re # For completeness, though app.py uses it

# Add the parent directory to the Python path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['GEMINI_API_KEY'] = 'test_api_key_value' # Set dummy key before app import

from app import app, text_model, image_model # Import models for mocking

class ChatbotAppTestCase(unittest.TestCase):

    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        self.app_client = app.test_client()
        app.testing = True
        self.env_patch = patch.dict(os.environ, {'GEMINI_API_KEY': 'test_api_key_value'})
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        self.app_context.pop()

    def test_index_route(self):
        response = self.app_client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content_type.startswith('text/html'))

    @patch.object(text_model, 'generate_content')
    @patch.object(image_model, 'generate_content')
    def test_ai_suggests_image_and_image_succeeds(self, mock_image_gen, mock_text_gen):
        # 1. Mock text_model to return a response with an image tag
        mock_text_response_obj = MagicMock()
        ai_raw_text_with_tag = "That's a great idea! [GENERATE_IMAGE: a happy dog with a wagging tail]"

        # Simulate the structure of GenerateContentResponse
        mock_text_part = MagicMock()
        type(mock_text_part).text = ai_raw_text_with_tag
        mock_text_candidate = MagicMock()
        # Ensure parts is a list-like mock if app.py iterates over it
        type(mock_text_candidate.content).parts = PropertyMock(return_value=[mock_text_part])
        type(mock_text_response_obj).candidates = [mock_text_candidate]
        # Ensure prompt_feedback is None or a mock that evaluates to False in boolean context
        type(mock_text_response_obj).prompt_feedback = PropertyMock(return_value=None)
        # If the actual object has a direct .text attribute as a shortcut
        type(mock_text_response_obj).text = ai_raw_text_with_tag


        mock_text_gen.return_value = mock_text_response_obj

        # 2. Mock image_model to return a successful image
        mock_image_response_obj = MagicMock()
        dummy_image_bytes = b'test_image_bytes_for_happy_dog'

        img_resp_text_part = MagicMock()
        type(img_resp_text_part).text = "Here is the happy dog." # Text accompanying image
        type(img_resp_text_part).inline_data = None # Make it explicit

        img_resp_image_part_inline_data = MagicMock()
        type(img_resp_image_part_inline_data).data = dummy_image_bytes
        type(img_resp_image_part_inline_data).mime_type = 'image/jpeg'

        img_resp_image_part = MagicMock()
        type(img_resp_image_part).text = None # Make it explicit
        type(img_resp_image_part).inline_data = img_resp_image_part_inline_data

        mock_image_candidate = MagicMock()
        type(mock_image_candidate.content).parts = PropertyMock(return_value=[img_resp_text_part, img_resp_image_part])
        type(mock_image_response_obj).candidates = [mock_image_candidate]
        type(mock_image_response_obj).prompt_feedback = PropertyMock(return_value=None)


        mock_image_gen.return_value = mock_image_response_obj

        # 3. Make the request
        response = self.app_client.post('/send_message', json={'message': 'Tell me something fun'})
        data = response.get_json()

        # 4. Assertions
        self.assertEqual(response.status_code, 200)
        expected_cleaned_text = "That's a great idea!"
        expected_image_desc_from_model = "Here is the happy dog."
        self.assertIn(expected_cleaned_text, data['text'])
        self.assertIn(expected_image_desc_from_model, data['text'])

        expected_b64_image = base64.b64encode(dummy_image_bytes).decode('utf-8')
        self.assertEqual(data['image_url'], f"data:image/jpeg;base64,{expected_b64_image}")

        mock_text_gen.assert_called_once()
        # app.py was corrected to not pass generation_config if it only contained response_modalities
        mock_image_gen.assert_called_once_with(contents=['a happy dog with a wagging tail'])

    @patch.object(text_model, 'generate_content')
    @patch.object(image_model, 'generate_content') # Mock image_model even if not always called
    def test_ai_does_not_suggest_image(self, mock_image_gen, mock_text_gen):
        mock_text_response_obj = MagicMock()
        ai_raw_text_no_tag = "This is a simple text response."

        mock_text_part = MagicMock()
        type(mock_text_part).text = ai_raw_text_no_tag
        mock_text_candidate = MagicMock()
        type(mock_text_candidate.content).parts = PropertyMock(return_value=[mock_text_part])
        type(mock_text_response_obj).candidates = [mock_text_candidate]
        type(mock_text_response_obj).prompt_feedback = PropertyMock(return_value=None)
        type(mock_text_response_obj).text = ai_raw_text_no_tag


        mock_text_gen.return_value = mock_text_response_obj

        response = self.app_client.post('/send_message', json={'message': 'Just a normal chat'})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['text'], ai_raw_text_no_tag)
        self.assertIsNone(data['image_url'])
        mock_text_gen.assert_called_once()
        mock_image_gen.assert_not_called()

    @patch.object(text_model, 'generate_content')
    @patch.object(image_model, 'generate_content')
    def test_ai_suggests_image_but_image_gen_fails_due_to_block(self, mock_image_gen, mock_text_gen):
        mock_text_response_obj = MagicMock()
        ai_raw_text_with_tag = "Let's try this: [GENERATE_IMAGE: a controversial image]"

        mock_text_part = MagicMock()
        type(mock_text_part).text = ai_raw_text_with_tag
        mock_text_candidate = MagicMock()
        type(mock_text_candidate.content).parts = PropertyMock(return_value=[mock_text_part])
        type(mock_text_response_obj).candidates = [mock_text_candidate]
        type(mock_text_response_obj).prompt_feedback = PropertyMock(return_value=None)
        type(mock_text_response_obj).text = ai_raw_text_with_tag
        mock_text_gen.return_value = mock_text_response_obj

        # Mock image_model to return a blocked prompt feedback
        mock_image_response_obj = MagicMock()
        mock_prompt_feedback = MagicMock()
        type(mock_prompt_feedback).block_reason = "SAFETY"
        type(mock_prompt_feedback).block_reason_message = "Image prompt blocked by safety filter"
        # Ensure candidates might be missing or empty if prompt_feedback is set this way
        type(mock_image_response_obj).candidates = PropertyMock(return_value=[])
        type(mock_image_response_obj).prompt_feedback = mock_prompt_feedback

        mock_image_gen.return_value = mock_image_response_obj

        response = self.app_client.post('/send_message', json={'message': 'Give me an edgy image idea'})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Let's try this:", data['text'])
        self.assertIn("The suggested image 'a controversial image' was blocked by safety filters.", data['text'])
        self.assertIsNone(data['image_url'])
        # app.py was corrected to not pass generation_config if it only contained response_modalities
        mock_image_gen.assert_called_once_with(contents=['a controversial image'])


    @patch.object(text_model, 'generate_content')
    def test_initial_text_prompt_blocked(self, mock_text_gen):
        # Mock text_model to return a blocked prompt
        mock_text_response_obj = MagicMock()
        mock_prompt_feedback = MagicMock()
        type(mock_prompt_feedback).block_reason = "SAFETY"
        type(mock_prompt_feedback).block_reason_message = "Initial text prompt blocked"
        # Ensure candidates might be missing or empty if prompt_feedback is set this way
        type(mock_text_response_obj).candidates = PropertyMock(return_value=[])
        type(mock_text_response_obj).prompt_feedback = mock_prompt_feedback
        # No .text attribute if blocked this way, or it might be empty
        type(mock_text_response_obj).text = PropertyMock(return_value="")


        mock_text_gen.return_value = mock_text_response_obj

        response = self.app_client.post('/send_message', json={'message': 'A very offensive prompt'})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['text'], "I'm sorry, your request was blocked by the safety filters. Please try a different prompt.")
        self.assertIsNone(data['image_url'])
        mock_text_gen.assert_called_once()


    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_send_message_no_api_key_recheck(self):
        with patch('app.gemini_api_key', None): # Ensure the check within the route sees None
            response = self.app_client.post('/send_message', json={'message': 'Any message'})
            data = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(data['text'], "Error: API key not configured. Please set GEMINI_API_KEY.")
            self.assertIsNone(data['image_url'])

if __name__ == '__main__':
    unittest.main()
