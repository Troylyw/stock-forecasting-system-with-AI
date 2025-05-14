require("dotenv").config();
const express = require("express");
const router = express.Router();
const OpenAI = require("openai");

// Initialize OpenAI (DeepSeek API)
const openai = new OpenAI({
    baseURL: "https://api.deepseek.com",
    apiKey: process.env.OPENAI_API_KEY,
});

// Create Q&A endpoint
router.post('/ask', async (req, res) => {
    try {
        const { question } = req.body;
        if (!question) {
            return res.status(400).json({ error: "Question is required" });
        }

        // Build prompt in English
        const prompt = `
You are a professional stock investment advisor. Please answer the following question in English, ensuring your answer is professional, accurate and in English.

Question: ${question}

Please consider the following aspects:
1. If the question is about a specific stock, provide a detailed analysis.
2. If the question is about investment strategy, provide concrete advice.
3. If the question is about market trends, provide an objective analysis.
4. If the question is about risk control, provide practical suggestions.

Make sure your answer is:
1. Professional and accurate
2. Easy to understand
3. Specific and actionable
4. Includes necessary risk warnings

Please answer ONLY in English, no matter what language the question is.
`;

        // Call AI API
        const completion = await openai.chat.completions.create({
            messages: [{ role: "user", content: prompt }],
            model: "deepseek-chat",
        });

        const answer = completion.choices[0].message.content;

        // Return answer
        res.json({ 
            answer,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        console.error("Error generating AI answer:", error);
        res.status(500).json({ 
            error: "Failed to generate answer",
            details: error.message 
        });
    }
});

module.exports = router; 