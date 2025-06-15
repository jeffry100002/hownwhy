document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatWindow = document.getElementById('chat-window');

    appendMessage("Hello! I'm your Gemini assistant. Ask me anything or try 'image of a cat'!", 'bot-message');

    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    function sendMessage() {
        const messageText = messageInput.value.trim();
        if (messageText === '') return;

        appendMessage(messageText, 'user-message');
        messageInput.value = '';

        let thinkingMessageDiv = null;
        // Check if it's likely an image generation request for the indicator
        const imageKeywords = ["image of", "picture of", "generate image", "draw a", "create an image"];
        if (imageKeywords.some(keyword => messageText.toLowerCase().includes(keyword))) {
            thinkingMessageDiv = appendMessage("<i>Generating image, this may take a moment...</i>", 'bot-message', true); // True to return the div
        } else {
            thinkingMessageDiv = appendMessage("<i>Thinking...</i>", 'bot-message', true);
        }


        fetch('/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageText }),
        })
        .then(response => {
            if (thinkingMessageDiv) thinkingMessageDiv.remove(); // Remove thinking/generating message
            if (!response.ok) {
                return response.json().then(errData => {
                    throw new Error(errData.text || `Server error: ${response.status}`);
                }).catch(() => {
                    throw new Error(`Server error: ${response.status} ${response.statusText}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.text) {
                appendMessage(data.text, 'bot-message');
            } else {
                appendMessage("Received an empty response from the bot.", 'error-message');
            }
            if (data.image_url) {
                appendImage(data.image_url, 'bot-message');
            }
        })
        .catch(error => {
            if (thinkingMessageDiv) thinkingMessageDiv.remove(); // Ensure removal on error too
            console.error('Error sending message:', error);
            appendMessage(`Sorry, an error occurred: ${error.message}`, 'error-message');
        });
    }

    function appendMessage(textOrHtml, className, returnDiv = false, isTyping = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', className);
        if (isTyping) { // A specific class for typing indicators if needed for styling
            messageDiv.classList.add('typing-indicator');
        }

        // Use innerHTML for messages that might contain <i> for italics (like thinking message)
        // Otherwise, prefer textContent for security with user/bot messages if they strictly contain text.
        // Given current usage, innerHTML is acceptable here.
        messageDiv.innerHTML = textOrHtml;

        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        if (returnDiv) return messageDiv;
    }

    function appendImage(url, className) {
        const imageContainer = document.createElement('div');
        imageContainer.classList.add('message', className);

        const img = document.createElement('img');
        img.src = url;
        img.alt = "Generated Image";
        img.onload = () => { chatWindow.scrollTop = chatWindow.scrollHeight; };
        img.onerror = () => {
            imageContainer.innerHTML = ''; // Clear previous img tag if any
            const errorText = document.createElement('p');
            errorText.textContent = "Failed to load generated image.";
            errorText.className = 'image-load-error'; // For specific styling
            imageContainer.appendChild(errorText);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        };
        imageContainer.appendChild(img);
        chatWindow.appendChild(imageContainer);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
});
