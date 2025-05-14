require("dotenv").config();
const express = require("express");
const router = express.Router();
const OpenAI = require("openai");
const { pool } = require('../utils/db');

// 初始化 DeepSeek AI
const openai = new OpenAI({
    baseURL: "https://api.deepseek.com",
    apiKey: process.env.OPENAI_API_KEY,
});

// 明确拒绝GET请求，返回405
router.get('/ai-personal-advice', (req, res) => {
    console.log('[aiPersonalAdvice.js] GET /api/ai-personal-advice called');
    res.status(405).json({ error: 'Method Not Allowed' });
});

router.post('/ai-personal-advice', async (req, res) => {
    console.log('[aiPersonalAdvice.js] POST /api/ai-personal-advice called, body:', req.body);
    try {
        const { email } = req.body;
        if (!email) {
            console.log('[aiPersonalAdvice.js] POST missing email in body');
            return res.status(400).json({ error: "Email is required" });
        }
        // 查询用户交易记录
        const [transactions] = await pool.query('SELECT * FROM stock_transactions WHERE email = ?', [email]);
        // 查询用户余额
        const [user] = await pool.query('SELECT * FROM users WHERE email = ?', [email]);
        if (!user[0]) {
            console.log('[aiPersonalAdvice.js] POST user not found:', email);
            return res.status(404).json({ error: "User not found" });
        }
        // 构建AI prompt
        const prompt = `
You are a professional stock investment advisor. Here are the user's historical stock transactions and current account balance. Please analyze the user's investment style and provide personalized investment advice (e.g., which stocks to buy/sell, suggested portfolio allocation, risk warnings, etc.). Please answer in English.

User's transaction history:
${JSON.stringify(transactions, null, 2)}

User's current balance: ${user[0].balance}
`;
        // 调用AI
        const completion = await openai.chat.completions.create({
            messages: [{ role: "user", content: prompt }],
            model: "deepseek-chat",
        });
        res.json({ advice: completion.choices[0].message.content });
    } catch (error) {
        console.error("[aiPersonalAdvice.js] Error generating AI personal advice:", error);
        res.status(500).json({ error: "Failed to generate advice", details: error.message });
    }
});

module.exports = router; 