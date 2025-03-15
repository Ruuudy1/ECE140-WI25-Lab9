async function generateText(prompt) {
    try {
        const response = await fetch('/api/ai/text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ prompt })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to generate text');
        }

        const data = await response.json();
        return data.text;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

async function generateImage(prompt, width = 512, height = 512) {
    try {
        const response = await fetch('/api/ai/image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({ prompt, width, height })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to generate image');
        }

        const data = await response.json();
        if (data.success && data.result && data.result.imageData) {
            return data.result.imageData;
        } else {
            throw new Error('Invalid response format');
        }
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
}

// Generate AI Text
document.getElementById('generateTextButton').addEventListener('click', async () => {
    const promptInput = document.getElementById('textPrompt');
    const resultDiv = document.getElementById('textResult');
    const prompt = promptInput.value.trim();
    
    if (!prompt) {
        alert('Please enter a prompt');
        return;
    }
    
    try {
        resultDiv.innerText = 'Generating response...';
        const text = await generateText(prompt);
        resultDiv.innerText = text;
    } catch (err) {
        console.error(err);
        resultDiv.innerText = `Error: ${err.message}`;
    }
});

// Generate AI Image
document.getElementById('generateImageButton').addEventListener('click', async () => {
    const prompt = document.getElementById('imagePrompt').value;
    const width = parseInt(document.getElementById('imageWidth').value) || 512;
    const height = parseInt(document.getElementById('imageHeight').value) || 512;
    
    if (!prompt) {
        alert('Please enter an image prompt');
        return;
    }
    
    try {
        // Show loading state
        document.getElementById('imageResult').innerHTML = 'Generating image...';
        
        const imageData = await generateImage(prompt, width, height);
        document.getElementById('imageResult').innerHTML = `
            <img src="${imageData}" alt="Generated Image" style="max-width: 100%; height: auto;">
        `;
    } catch (error) {
        document.getElementById('imageResult').innerText = error.message || 'Failed to generate image.';
    }
});
