const express = require('express');
const { log } = require('mathjs');
const router = express.Router();
const OpenAI = require('openai');
require('dotenv').config(); // 确保加载环境变量

// 初始化 DeepSeek
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: "https://api.deepseek.com/v1"
});

// 首先添加 extractSectionContent 函数
function extractSectionContent(text, sectionTitle) {
    const sections = text.split('## **');
    const section = sections.find(s => s.includes(sectionTitle));
    if (!section) return '';

    // 找到下一个标题的位置
    const nextSectionIndex = sections.findIndex(s => s.includes(sectionTitle)) + 1;
    const nextSection = sections[nextSectionIndex];
    
    if (nextSection) {
        // 如果找到下一个标题，提取到下一个标题之前的内容
        const content = section.split(nextSection)[0];
        return content.trim();
    } else {
        // 如果没有下一个标题，返回整个部分
        return section.trim();
    }
}

router.post('/analyze-chart', async (req, res) => {
    try {
        const { basicAdvice, riskComponents,riskMetrics,stockData,stockTicker} = req.body;

        if (!stockData || !stockTicker) {
            return res.status(400).json({
                success: false,
                error: 'Missing required data'
            });
        }

        const prompt = `Analyze the following stock data and provide a detailed analysis:

Stock: ${stockTicker}
Current Price: ${stockData[stockData.length - 1].close}
Time Period: ${stockData.length} days
Historical Price: ${stockData}
Basic Advice: ${basicAdvice}
Risk Metrics: ${riskMetrics}
Risk Components: ${riskComponents}

Please provide a comprehensive analysis including:

1. Overall Market Analysis
- Historical market position
- Price trends

2. Risk Assessment
- Volatility analysis (${riskMetrics.volatility})
- Maximum drawdown (${riskMetrics.maxDrawdown})
- Risk score (${riskMetrics.riskScore})


3. Technical Analysis
- Moving averages
- Support and resistance levels


4. Investment Strategy
- Entry points
- Exit points
- Stop loss levels
- Trading frequency

Please provide specific numbers and actionable insights.`;

        const response = await openai.chat.completions.create({
            model: "deepseek-chat",
            messages: [
                {
                    role: "system",
                    content: "You are a professional stock market analyst. Provide detailed, actionable analysis with specific numbers and clear recommendations."
                },
                {
                    role: "user",
                    content: prompt
                }
            ],
            temperature: 0.7,
            max_tokens: 2000
        });

        // 直接返回完整的分析内容
        const result = {
            success: true,
            analysis: response.choices[0].message.content
        };

        return res.json(result);
    } catch (error) {
        console.error('Error in chart analysis:', error);
        return res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 辅助函数：提取关键点
function extractKeyPoints(text) {
    console.log('Extracting key points from text');
    const points = [];
    const lines = text.split('\n');
    
    for (const line of lines) {
        if (line.trim() !== '') {
            points.push(line.trim());
        }
    }
    
    console.log(`Found ${points.length} key points:`, points);
    return points;
}

module.exports = router; 