require("dotenv").config();
const express = require("express");
const router = express.Router();
const OpenAI = require("openai");



// 检查 API Key 是否正确加载
if (!process.env.OPENAI_API_KEY) {
    console.error("❌ ERROR: Missing OPENAI_API_KEY in .env file!");
    process.exit(1);
}

// 初始化 OpenAI（DeepSeek API）
const openai = new OpenAI({
    baseURL: "https://api.deepseek.com",
    apiKey: process.env.OPENAI_API_KEY,
});

// 打字机效果函数
async function typeWriterEffect(text, speed = 50) {
    for (const char of text) {
        process.stdout.write(char);
        await new Promise(resolve => setTimeout(resolve, speed));
    }
    console.log("\n");
}

// 创建 `/api/chat` 端点
router.post('/chat', async (req, res) => {
    try {
        const userMessage = req.body.message;
        if (!userMessage) {
            return res.status(400).json({ error: "Message is required" });
        }

        // 发送请求到 DeepSeek API
        const completion = await openai.chat.completions.create({
            messages: [{ role: "user", content: userMessage }],
            model: "deepseek-chat",
        });

        // 获取 AI 回复
        const aiResponse = completion.choices[0].message.content;

        // 模拟打字机效果（在服务器端输出）
        await typeWriterEffect(aiResponse, 30);

        // 返回 AI 回复给客户端
        res.json({ response: aiResponse });
    } catch (error) {
        console.error("❌ Error calling AI API:", error.message);
        res.status(500).json({ error: "Internal Server Error" });
    }
});

module.exports = router;
