document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('contentForm');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const generateButton = document.querySelector('button[type="submit"]');
    const description = document.getElementById('description');

    const socket = io();

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('generation_complete', (data) => {
        displayResult(data);
    });

    socket.on('generation_error', (data) => {
        displayError(data.error);
    });

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = {
            topic: document.getElementById('topic').value,
            contentType: document.getElementById('contentType').value,
            targetAudience: document.getElementById('targetAudience').value,
            tone: document.getElementById('tone').value
        };

        loading.classList.remove('hidden');
        result.classList.add('hidden');
        result.innerHTML = '';
        generateButton.disabled = true;
        generateButton.innerHTML = '<span class="spinner"></span> Generating...';

        // Move description
        description.classList.add('moved');

        // Start the generation process
        startGeneration(formData);
    });

    function startGeneration(formData) {
        fetch('/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            // The server has started the generation process
            loading.innerHTML = 'Generation started. Please wait...';
        })
        .catch((error) => {
            console.error('Error:', error);
            displayError(error.message || 'An error occurred. Please try again.');
        });
    }

    function displayResult(data) {
        loading.classList.add('hidden');
        result.classList.remove('hidden');
        generateButton.disabled = false;
        generateButton.innerHTML = 'Generate Content';
        
        let formattedResult = `<h2>Generated Content</h2>`;
        formattedResult += `<h3>Final Output:</h3><div>${data.result.final_output}</div>`;
        formattedResult += '<h3>Task Outputs:</h3>';
        data.result.task_outputs.forEach(task => {
            formattedResult += `<h4>Task ${task.task_id}:</h4><div>${task.output}</div>`;
        });
        
        result.innerHTML = formattedResult;
    }

    function displayError(message) {
        loading.classList.add('hidden');
        result.classList.remove('hidden');
        generateButton.disabled = false;
        generateButton.innerHTML = 'Generate Content';
        result.innerHTML = `<p class="error">${message}</p>`;
        
        // Move description back to original position
        description.classList.remove('moved');
    }
});