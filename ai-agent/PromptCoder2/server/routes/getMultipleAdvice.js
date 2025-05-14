const fs = require('fs');
const csv = require('csv-parser');
const express = require('express');
const router = express.Router();
const {
    fillMissingDates,
    calculateReturns,
    calculateStandardDeviation,
    calculateCorrelation,
    meanVarianceOptimization,
    predictOptimalWeights
} = require('../utils/multipleAdviceFunction');

router.get('/portfolio-recommendation', (req, res) => {
    const { investmentYears, maxPortfolioSize } = req.query;

    // 参数验证
    if (!investmentYears || !maxPortfolioSize) {
        return res.json({ success: false, message: 'investmentYears and maxPortfolioSize are required.' });
    }

    const investmentYearsInt = parseInt(investmentYears, 10);
    const maxPortfolioSizeInt = parseInt(maxPortfolioSize, 10);

    if (isNaN(investmentYearsInt) || isNaN(maxPortfolioSizeInt)) {
        return res.json({ success: false, message: 'investmentYears and maxPortfolioSize must be valid numbers.' });
    }

    const stocks = [];
    const stockPrices = {};
    const allDates = new Set();
    const startDate = 20190102;

    fs.createReadStream(__dirname + '/output.csv')
        .pipe(csv())
        .on('headers', (headers) => {
            // // Get all stock tickers from the headers (excluding the 'DATE/TICKER' column).
            headers.forEach(header => {
                if (header !== 'DATE/TICKER') {
                    stocks.push(header);
                    stockPrices[header] = [];
                }
            });
        })
        .on('data', (row) => {
            // Iterate through each row of data and read the price of each stock.
            const rowDate = parseInt(row['DATE/TICKER'], 10);

            if (rowDate >= startDate) {
                stocks.forEach(stock => {
                    const price = parseFloat(row[stock]);

                    if (!isNaN(price)) {
                        stockPrices[stock].push({ date: rowDate, price });
                        allDates.add(rowDate);
                    }
                });
            }
        })
        .on('end', () => {
            // Fill in the missing dates for each stock's data.
            stocks.forEach(stock => {
                fillMissingDates(stockPrices[stock], allDates);
            });

            // Analyze the stock data.
            const returnsData = {};
            const correlationMatrix = {};

            stocks.forEach(stock => {
                returnsData[stock] = calculateReturns(stockPrices[stock].map(d => d.price));
            });

            // Calculate the correlation matrix.
            for (let i = 0; i < stocks.length; i++) {
                for (let j = i + 1; j < stocks.length; j++) {
                    const stockA = stocks[i];
                    const stockB = stocks[j];

                    const correlation = calculateCorrelation(returnsData[stockA], returnsData[stockB]);

                    if (!correlationMatrix[stockA]) correlationMatrix[stockA] = {};
                    if (!correlationMatrix[stockB]) correlationMatrix[stockB] = {};

                    correlationMatrix[stockA][stockB] = correlation;
                    correlationMatrix[stockB][stockA] = correlation;
                }
            }

            // Classify the correlation pairs.
            const highCorrelationPairs = [];
            const lowCorrelationPairs = [];
            const negativeCorrelationPairs = [];

            for (let i = 0; i < stocks.length; i++) {
                for (let j = i + 1; j < stocks.length; j++) {
                    const stockA = stocks[i];
                    const stockB = stocks[j];
                    const correlation = correlationMatrix[stockA][stockB];

                    if (correlation > 0.8) {
                        highCorrelationPairs.push({ stockA, stockB, correlation });
                    } else if (correlation < 0.3 && correlation >= 0) {
                        lowCorrelationPairs.push({ stockA, stockB, correlation });
                    } else if (correlation < 0) {
                        negativeCorrelationPairs.push({ stockA, stockB, correlation });
                    }
                }
            }

            // Select an investment portfolio based on the investment horizon.
            const selectedStocks = new Set();

            if (investmentYearsInt > 3) {
                // Select highly correlated stocks.
                highCorrelationPairs.forEach(({ stockA, stockB }) => {
                    if (selectedStocks.size < maxPortfolioSizeInt) {
                        if (!selectedStocks.has(stockA)) {
                            selectedStocks.add(stockA);
                        }
                        if (selectedStocks.size < maxPortfolioSizeInt && !selectedStocks.has(stockB)) {
                            selectedStocks.add(stockB);
                        }
                    }
                });

                // Select low correlated stocks.
                lowCorrelationPairs.forEach(({ stockA, stockB }) => {
                    if (selectedStocks.size < maxPortfolioSizeInt) {
                        if (!selectedStocks.has(stockA)) {
                            selectedStocks.add(stockA);
                        }
                        if (selectedStocks.size < maxPortfolioSizeInt && !selectedStocks.has(stockB)) {
                            selectedStocks.add(stockB);
                        }
                    }
                });
            } else {
                lowCorrelationPairs.forEach(({ stockA, stockB }) => {
                    if (selectedStocks.size < maxPortfolioSizeInt) {
                        if (!selectedStocks.has(stockA)) {
                            selectedStocks.add(stockA);
                        }
                        if (selectedStocks.size < maxPortfolioSizeInt && !selectedStocks.has(stockB)) {
                            selectedStocks.add(stockB);
                        }
                    }
                });
            }

            const finalSelectedStocks = Array.from(selectedStocks).slice(0, maxPortfolioSizeInt);

            res.json({
                success: true,
                selectedStocks: finalSelectedStocks
            });

        })
        .on('error', (err) => {
            console.error(err);
            res.json({ success: false, message: 'Error processing stock data.' });
        });
});


router.get('/multiplestock-analysis', (req, res) => {
    const stockTickers = req.query.stocks;
    if (!stockTickers) {
        return res.json({ success: false, message: 'Stock tickers are required.' });
    }

    const tickers = stockTickers.split(',');
    const stocksData = [];
    const marketData = []; // Add market data array
    const startDate = 20190102;

    let count = 0;
    const allDates = new Set();

    // First, read market data (assuming market index data is available)
    fs.createReadStream(__dirname + '/output.csv')
        .pipe(csv())
        .on('data', (row) => {
            if (row['DATE/TICKER'] && row['MARKET']) { // Assuming 'MARKET' is the column for market index
                const price = parseFloat(row['MARKET']);
                if (!isNaN(price)) {
                    const rowDate = parseInt(row['DATE/TICKER'], 10);
                    if (rowDate >= startDate) {
                        marketData.push({ date: rowDate, price });
                        allDates.add(rowDate);
                    }
                }
            }
        })
        .on('end', () => {
            // Then process individual stocks
            tickers.forEach(ticker => {
                const stockData = [];
                fs.createReadStream(__dirname + '/output.csv')
                    .pipe(csv())
                    .on('data', (row) => {
                        if (row['DATE/TICKER'] && row[ticker]) {
                            const price = parseFloat(row[ticker]);
                            if (!isNaN(price)) {
                                const rowDate = parseInt(row['DATE/TICKER'], 10);
                                if (rowDate >= startDate) {
                                    stockData.push({ date: rowDate, price });
                                    allDates.add(rowDate);
                                }
                            }
                        }
                    })
                    .on('end', () => {
                        if (stockData.length === 0) {
                            return res.json({ success: false, message: `No data available for stock ${ticker} after 2019.` });
                        }

                        fillMissingDates(stockData, allDates);

                        stocksData.push({
                            ticker: ticker,
                            prices: stockData.map(data => data.price),
                            dates: stockData.map(data => data.date)
                        });

                        count++;

                        if (count === tickers.length) {
                            // Get traditional optimization weights
                            const traditionalWeights = meanVarianceOptimization(stocksData, { prices: marketData.map(d => d.price) });
                            
                            // Get AI-optimized weights
                            predictOptimalWeights(stocksData)
                                .then(aiWeights => {
                                    res.json({
                                        success: true,
                                        portfolioWeights: traditionalWeights,
                                        aiPortfolioWeights: aiWeights
                                    });
                                })
                                .catch(error => {
                                    console.error('Error in AI prediction:', error);
                                    // If AI prediction fails, return only traditional weights
                                    res.json({
                                        success: true,
                                        portfolioWeights: traditionalWeights,
                                        aiPortfolioWeights: traditionalWeights,
                                        message: 'AI optimization failed, using traditional weights instead'
                                    });
                                });
                        }
                    })
                    .on('error', (err) => {
                        console.error(err);
                        res.json({ success: false, message: 'Error reading stock data.' });
                    });
            });
        });
});





module.exports = router;