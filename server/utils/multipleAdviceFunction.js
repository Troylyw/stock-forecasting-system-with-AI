const fs = require('fs');
const csv = require('csv-parser');
const express = require('express');
const router = express.Router();
const math = require('mathjs');
// fill the missing date
function fillMissingDates(stockData, allDates) {
    const dates = Array.from(allDates).sort((a, b) => a - b);  // Sort all the dates.
    const dateSet = new Set(dates);  // Create a date set for fast lookup.

    // Fill in the data for each stock.
    const filledData = [];
    let currentIndex = 0;

    // Iterate through all the dates.
    dates.forEach(date => {
        if (stockData[currentIndex] && stockData[currentIndex].date === date) {

            filledData.push(stockData[currentIndex]);
            currentIndex++;
        } else {

            const previousPrice = filledData[filledData.length - 1]?.price || 0;
            filledData.push({ date: date, price: previousPrice });
        }
    });

    // update stock data
    stockData.length = 0;
    stockData.push(...filledData);
}

// calculate the daily return of a stock, you can use the formula
function calculateReturns(prices) {
    const returns = [];
    for (let i = 1; i < prices.length; i++) {
        const dailyReturn = (prices[i] - prices[i - 1]) / prices[i - 1];
        returns.push(dailyReturn);
    }
    console.log(returns);
    return returns;
}


function calculateStandardDeviation(returns) {
    // check whether it contains Infinity 或 -Infinity
    const invalidValues = returns.filter(r => r === Infinity || r === -Infinity);
    if (invalidValues.length > 0) {
        console.error('Invalid values found in returns array:', invalidValues);
        return NaN;
    }

    // calculate means
    const mean = math.mean(returns);
    console.log('Mean:', mean);

    // calculate variance
    const variance = math.mean(returns.map(r => Math.pow(r - mean, 2)));
    console.log('Variance:', variance);

    // calculate stddev
    const stddev = Math.sqrt(variance);
    console.log('Standard Deviation:', stddev);

    return stddev;
}


// calculate correlation
function calculateCorrelation(returns1, returns2) {
    const minLength = Math.min(returns1.length, returns2.length);
    const adjustedReturns1 = returns1.slice(0, minLength);
    const adjustedReturns2 = returns2.slice(0, minLength);

    return math.corr(adjustedReturns1, adjustedReturns2);
}

// Mean-variance optimization with Sharpe Ratio
function meanVarianceOptimization(stocksData, marketData) {
    // Calculate returns for all stocks
    const returns = stocksData.map(stock => calculateReturns(stock.prices));
    
    // Calculate standard deviation (risk)
    const risks = stocksData.map(stock => calculateStandardDeviation(returns[stocksData.indexOf(stock)]));
    
    // Calculate Sharpe Ratios
    const riskFreeRate = 0.02; // 2% risk-free rate
    const sharpeRatios = returns.map(stockReturns => {
        const meanReturn = math.mean(stockReturns);
        const stdDev = math.std(stockReturns);
        return stdDev === 0 ? 0 : (meanReturn - riskFreeRate) / stdDev;
    });

    const n = stocksData.length;
    const correlationMatrix = [];

    // Calculate the correlation matrix between stocks
    for (let i = 0; i < n; i++) {
        let row = [];
        for (let j = 0; j < n; j++) {
            if (i === j) {
                row.push(1);
            } else {
                const correlation = calculateCorrelation(returns[i], returns[j]);
                row.push(correlation);
            }
        }
        correlationMatrix.push(row);
    }

    // Calculate initial weights considering risk and Sharpe Ratio
    const totalRisk = risks.reduce((acc, risk) => acc + risk, 0);
    const initialWeights = risks.map((risk, index) => {
        // Risk adjustment
        const riskAdjustment = risk / totalRisk;
        
        // Sharpe Ratio adjustment
        const sharpeAdjustment = 1 + (sharpeRatios[index] / 2);
        
        // Combine adjustments
        return riskAdjustment * sharpeAdjustment;
    });

    // Adjust weights based on correlation
    const adjustedWeights = initialWeights.map((weight, index) => {
        let adjustedWeight = weight;
        for (let j = 0; j < n; j++) {
            if (index !== j) {
                adjustedWeight *= (1 - Math.abs(correlationMatrix[index][j]));
            }
        }
        return adjustedWeight;
    });

    // Normalize weights
    const totalAdjustedWeight = adjustedWeights.reduce((acc, weight) => acc + weight, 0);
    const finalWeights = adjustedWeights.map(weight => weight / totalAdjustedWeight);

    return finalWeights;
}

// AI prediction function for optimal weights
async function predictOptimalWeights(stocksData) {
    try {
        // Prepare data for AI prediction
        const features = stocksData.map(stock => ({
            returns: calculateReturns(stock.prices),
            risk: calculateStandardDeviation(calculateReturns(stock.prices)),
            sharpeRatio: calculateSharpeRatio(calculateReturns(stock.prices))
        }));

        // Call AI model for prediction
        const response = await fetch('http://localhost:3000/api/ai-predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ features })
        });

        if (!response.ok) {
            throw new Error('AI prediction failed');
        }

        const prediction = await response.json();
        return prediction.weights;
    } catch (error) {
        console.error('Error in AI prediction:', error);
        // Fallback to traditional optimization if AI prediction fails
        return meanVarianceOptimization(stocksData);
    }
}

// Helper function to calculate Sharpe Ratio
function calculateSharpeRatio(returns, riskFreeRate = 0.02) {
    if (!returns || returns.length === 0) return 0;
    const meanReturn = math.mean(returns);
    const stdDev = math.std(returns);
    return stdDev === 0 ? 0 : (meanReturn - riskFreeRate) / stdDev;
}

module.exports = {
    fillMissingDates,
    calculateReturns,
    calculateStandardDeviation,
    calculateCorrelation,
    meanVarianceOptimization,
    predictOptimalWeights,
    calculateSharpeRatio
};