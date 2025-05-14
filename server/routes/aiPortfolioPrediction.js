const express = require('express');
const router = express.Router();
const OpenAI = require('openai');

// Initialize OpenAI
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});

// AI prediction endpoint
router.post('/ai-predict', async (req, res) => {
    try {
        const { features } = req.body;

        // Prepare prompt for AI
        const prompt = `Given the following stock features:
${features.map((f, i) => `Stock ${i + 1}:
- Returns: ${f.returns}
- Risk: ${f.risk}
- Sharpe Ratio: ${f.sharpeRatio}`).join('\n')}

Please analyze these stocks and suggest optimal portfolio weights that maximize the Sharpe Ratio while maintaining diversification. Consider:
1. Risk-adjusted returns (Sharpe Ratio)
2. Correlation between stocks
3. Overall portfolio risk
4. Market conditions

Return the weights as a JSON array of numbers that sum to 1.`;

        // Get AI prediction
        const completion = await openai.chat.completions.create({
            model: "gpt-4",
            messages: [
                {
                    role: "system",
                    content: "You are a professional portfolio manager. Analyze the given stock features and suggest optimal portfolio weights."
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            temperature: 0.7,
        });

        // Parse AI response
        const aiResponse = completion.choices[0].message.content;
        const weights = JSON.parse(aiResponse);

        // Validate weights
        const sum = weights.reduce((a, b) => a + b, 0);
        if (Math.abs(sum - 1) > 0.01) {
            // Normalize weights if they don't sum to 1
            const normalizedWeights = weights.map(w => w / sum);
            return res.json({ weights: normalizedWeights });
        }

        res.json({ weights });
    } catch (error) {
        console.error('Error in AI prediction:', error);
        res.status(500).json({ 
            success: false, 
            message: 'Error in AI prediction',
            error: error.message 
        });
    }
});

module.exports = router; 