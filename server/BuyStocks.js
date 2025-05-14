// stockPriceService.js
const axios = require('axios');
const cheerio = require('cheerio');

async function fetchRealTimeStockPrice(symbol) {
  const url = `https://stooq.com/q/?s=${symbol}`;

  try {
    const response = await axios.get(url);
    const $ = cheerio.load(response.data);
    const realTimePriceElement = $(`#aq_${symbol}_c2`);
    if (realTimePriceElement.length > 0) {
      return parseFloat(realTimePriceElement.text().trim());
    } else {
      throw new Error(`No price data found for ${symbol}`);
    }
  } catch (error) {
    console.error(`Error fetching price for ${symbol}:`, error.message);
    throw error;
  }
}

module.exports = { fetchRealTimeStockPrice };
