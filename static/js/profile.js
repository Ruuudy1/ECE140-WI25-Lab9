document.addEventListener('DOMContentLoaded', () => {
    // Text Generation
    document.getElementById('generateTextButton').addEventListener('click', async () => {
        const prompt = document.getElementById('textPrompt').value;
        if (!prompt.trim()) return alert('Please enter a prompt.');

        try {
            const result = await generateText(prompt);
            document.getElementById('textResult').innerText = result;
        } catch (error) {
            document.getElementById('textResult').innerText = 'Failed to generate text. Please try again.';
        }
    });

    // Image Generation
    document.getElementById('generateImageButton').addEventListener('click', async () => {
        const prompt = document.getElementById('imagePrompt').value;
        const width = parseInt(document.getElementById('imageWidth').value, 10);
        const height = parseInt(document.getElementById('imageHeight').value, 10);

        if (!prompt.trim()) return alert('Please enter a prompt.');
        if (width < 128 || width > 1024 || height < 128 || height > 1024) {
            return alert('Width and height must be between 128 and 1024.');
        }

        try {
            const imageUrl = await generateImage(prompt, width, height);
            if (imageUrl) {
                document.getElementById('imageResult').innerHTML = `<img src="${imageUrl}" alt="Generated Image">`;
            } else {
                document.getElementById('imageResult').innerText = 'Failed to generate image.';
            }
        } catch (error) {
            document.getElementById('imageResult').innerText = 'Failed to generate image. Please try again.';
        }
    });
});