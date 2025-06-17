import unittest
import sys
import os
from unittest.mock import patch, MagicMock, PropertyMock, ANY
import base64
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ['GEMINI_API_KEY'] = 'test_api_key_value'

from app import app, text_model, image_model, types

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
        # 1. Mock text_model response
        mock_text_response_obj = MagicMock()
        ai_raw_text_with_tag = "That's a great idea! [GENERATE_IMAGE: a happy dog with a wagging tail]"
        mock_text_part = MagicMock()
        type(mock_text_part).text = ai_raw_text_with_tag
        mock_text_candidate = MagicMock()
        type(mock_text_candidate.content).parts = PropertyMock(return_value=[mock_text_part])
        type(mock_text_response_obj).candidates = [mock_text_candidate]
        type(mock_text_response_obj).prompt_feedback = PropertyMock(return_value=None)
        type(mock_text_response_obj).text = ai_raw_text_with_tag # For simpler access if app.py uses it
        mock_text_gen.return_value = mock_text_response_obj

        # 2. Mock image_model response
        mock_image_response_obj = MagicMock()
        dummy_image_bytes = b'test_image_bytes_for_happy_dog'
        img_resp_text_part = MagicMock()
        type(img_resp_text_part).text = "Here is the happy dog."
        type(img_resp_text_part).inline_data = None
        img_resp_image_part_inline_data = MagicMock()
        type(img_resp_image_part_inline_data).data = dummy_image_bytes
        type(img_resp_image_part_inline_data).mime_type = 'image/jpeg'
        img_resp_image_part = MagicMock()
        type(img_resp_image_part).text = None
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

        # MODIFIED ASSERTION for image_model.generate_content()
        # image_model.generate_content is now called without generation_config
        mock_image_gen.assert_called_once_with(contents=['a happy dog with a wagging tail'])


    @patch.object(text_model, 'generate_content')
    @patch.object(image_model, 'generate_content')
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

        mock_image_response_obj = MagicMock()
        mock_prompt_feedback = MagicMock()
        type(mock_prompt_feedback).block_reason = "SAFETY"
        type(mock_prompt_feedback).block_reason_message = "Image prompt blocked by safety filter"
        type(mock_image_response_obj).prompt_feedback = mock_prompt_feedback
        type(mock_image_response_obj).candidates = PropertyMock(return_value=[]) # Ensure candidates is list-like
        mock_image_gen.return_value = mock_image_response_obj

        response = self.app_client.post('/send_message', json={'message': 'Give me an edgy image idea'})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Let's try this:", data['text'])
        self.assertIn("The suggested image 'a controversial image' was blocked by safety filters.", data['text'])
        self.assertIsNone(data['image_url'])

        # MODIFIED ASSERTION for image_model.generate_content()
        # image_model.generate_content is now called without generation_config
        mock_image_gen.assert_called_once_with(contents=['a controversial image'])

    @patch.object(text_model, 'generate_content')
    def test_initial_text_prompt_blocked(self, mock_text_gen):
        mock_text_response_obj = MagicMock()
        mock_prompt_feedback = MagicMock()
        type(mock_prompt_feedback).block_reason = "SAFETY"
        type(mock_prompt_feedback).block_reason_message = "Initial text prompt blocked"
        type(mock_text_response_obj).candidates = PropertyMock(return_value=[])
        type(mock_text_response_obj).prompt_feedback = mock_prompt_feedback
        type(mock_text_response_obj).text = PropertyMock(return_value="") # Ensure .text is empty or non-existent
        mock_text_gen.return_value = mock_text_response_obj

        response = self.app_client.post('/send_message', json={'message': 'A very offensive prompt'})
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        # The error message in app.py for this case is "I'm sorry, your request was blocked by the safety filters. Please try a different prompt."
        # This comes from the ValueError raised and caught.
        self.assertEqual(data['text'], "I'm sorry, your request was blocked by the safety filters. Please try a different prompt.")
        self.assertIsNone(data['image_url'])
        mock_text_gen.assert_called_once()

    @patch.dict(os.environ, {"GEMINI_API_KEY": ""})
    def test_send_message_no_api_key_recheck(self):
        with patch('app.gemini_api_key', None): # Patch the module-level variable in app
            response = self.app_client.post('/send_message', json={'message': 'Any message'})
            data = response.get_json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(data['text'], "Error: API key not configured. Please set GEMINI_API_KEY in your .env file or environment.")
            self.assertIsNone(data['image_url'])

if __name__ == '__main__':
    unittest.main()
