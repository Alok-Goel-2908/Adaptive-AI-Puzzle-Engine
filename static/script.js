document.addEventListener('DOMContentLoaded', () => {
    // Dashboard Elements
    const dashScore = document.getElementById('dash-score');
    const dashSolved = document.getElementById('dash-solved');
    const dashDiff = document.getElementById('dash-diff');
    const badgeDifficulty = document.getElementById('badge-difficulty');
    
    // Puzzle generation
    const generateBtn = document.getElementById('generate-btn');
    const statusMsg = document.getElementById('status-msg');
    const puzzleContent = document.getElementById('puzzle-content');
    
    // Hint System
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const hintCounterText = document.getElementById('hint-counter-text');
    
    // Answer Submission
    const answerArea = document.getElementById('answer-area');
    const answerInput = document.getElementById('answer-input');
    const submitAnswerBtn = document.getElementById('submit-answer-btn');
    const gradingFeedback = document.getElementById('grading-feedback');
    
    // Load Dashboard Stats
    async function refreshDashboard() {
        try {
            const res = await fetch('/dashboard_stats');
            const data = await res.json();
            dashScore.textContent = data.score;
            dashSolved.textContent = data.solved_count;
            dashDiff.textContent = data.current_difficulty;
            
            // color dash
            let diffColor = 'rgba(34, 197, 94, 0.5)';
            if(data.current_difficulty === 'Medium') diffColor = 'rgba(234, 179, 8, 0.5)';
            if(data.current_difficulty === 'Hard') diffColor = 'rgba(239, 68, 68, 0.5)';
            dashDiff.style.color = diffColor;
        } catch (err) {
            console.error("Dashboard load failed", err);
        }
    }
    
    // Initial Load
    refreshDashboard();

    // Helper: Add message to chat box
    function addMessage(text, type='system') {
        const systemMsg = document.querySelector('.system-msg');
        if (systemMsg) systemMsg.remove();

        const msgDiv = document.createElement('div');
        msgDiv.className = `msg ${type}-msg`;
        msgDiv.innerHTML = text;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.id = 'typing-indicator';
        div.innerHTML = '<span></span><span></span><span></span>';
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function removeTyping() {
        const ind = document.getElementById('typing-indicator');
        if(ind) ind.remove();
    }

    // 1. Generate Puzzle
    generateBtn.addEventListener('click', async () => {
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Generating...';
        statusMsg.innerHTML = '';
        gradingFeedback.innerHTML = '';
        answerInput.value = '';
        hintCounterText.textContent = 'Hints used: 0';
        
        try {
            const res = await fetch('/generate_puzzle', { method: 'POST' });
            const data = await res.json();
            
            if (data.success && data.puzzle) {
                const diff = data.difficulty;
                
                badgeDifficulty.textContent = diff;
                if(diff === 'Easy') badgeDifficulty.style.background = 'rgba(34, 197, 94, 0.5)';
                else if(diff === 'Medium') badgeDifficulty.style.background = 'rgba(234, 179, 8, 0.5)';
                else badgeDifficulty.style.background = 'rgba(239, 68, 68, 0.5)';

                puzzleContent.innerHTML = `
                    <span class="type-tag">${data.puzzle.type || 'Logic Puzzle'}</span>
                    <h3>${data.puzzle.title}</h3>
                    <div style="font-size: 1.05rem;">${data.puzzle.content}</div>
                `;
                
                answerArea.classList.remove('hidden');
                submitAnswerBtn.disabled = false;
                answerInput.disabled = false;

                // Reset Chat
                chatInput.disabled = false;
                sendBtn.disabled = false;
                chatMessages.innerHTML = '';
                addMessage(`New ${diff} puzzle loaded! I'm HintBot, try analyzing the clues before asking me for hints!`, 'bot');

            } else {
                statusMsg.innerHTML = `<span class="error-text">API Error: ${data.error || 'Failed to generate'}</span>`;
            }
        } catch (err) {
            statusMsg.innerHTML = `<span class="error-text">Network Error: ${err.message}</span>`;
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ph ph-sparkle"></i> Generate Target Puzzle';
        }
    });

    // 2. Chat with Auto-grading HintBot
    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        chatInput.value = '';
        chatInput.disabled = true;
        sendBtn.disabled = true;

        showTyping();

        try {
            const res = await fetch('/get_hint', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await res.json();
            removeTyping();

            if (data.success && data.hint) {
                let formattedHint = data.hint.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                addMessage(formattedHint, 'bot');
                hintCounterText.textContent = `Hints used: ${data.hint_number || 0}`;
            } else {
                addMessage("Oops, I lost connection. Try again!", 'bot');
            }
        } catch (err) {
            removeTyping();
            addMessage("Network Error: Could not reach the server.", 'bot');
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
        }
    }

    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    
    // 3. Submit Formal Answer
    submitAnswerBtn.addEventListener('click', async () => {
        const answer = answerInput.value.trim();
        if (!answer) return;
        
        submitAnswerBtn.disabled = true;
        answerInput.disabled = true;
        gradingFeedback.innerHTML = '<i class="ph ph-spinner ph-spin"></i> Grading...';
        gradingFeedback.className = 'grading-feedback';
        
        try {
            const res = await fetch('/submit_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ answer: answer })
            });
            const data = await res.json();
            
            if (data.success) {
                // If correct
                if (data.is_correct) {
                    gradingFeedback.innerHTML = `<i class="ph-bold ph-check-circle"></i> <strong>Correct!</strong> +${data.points_earned} points. <br><small>${data.feedback}</small>`;
                    gradingFeedback.className = 'grading-feedback feedback-correct';
                    
                    // Chatbot celebration
                    addMessage("You got it right! Awesome logical deduction. Generate another puzzle!", 'bot');
                    chatInput.disabled = true;
                    sendBtn.disabled = true;
                    
                } else {
                    gradingFeedback.innerHTML = `<i class="ph-bold ph-x-circle"></i> <strong>Not quite.</strong> <br><small>${data.feedback}</small>`;
                    gradingFeedback.className = 'grading-feedback feedback-wrong';
                    submitAnswerBtn.disabled = false;
                    answerInput.disabled = false;
                }
                
                // Always refresh dashboard
                refreshDashboard();
                
            } else {
                gradingFeedback.innerHTML = `<span class="error-text">${data.error}</span>`;
                submitAnswerBtn.disabled = false;
                answerInput.disabled = false;
            }
            
        } catch (err) {
            gradingFeedback.innerHTML = `<span class="error-text">Network Error: ${err.message}</span>`;
            submitAnswerBtn.disabled = false;
            answerInput.disabled = false;
        }
    });
    
    answerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitAnswerBtn.click();
    });
});
