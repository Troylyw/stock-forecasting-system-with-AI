const mysql = require('mysql2/promise');

const pool = mysql.createPool({
    port: 3306,
    host: 'localhost',
    user: 'root',
    password: 'Chensiyi@010312', // 替换为你的 MySQL 密码
    database: 'Stock_analysis_system',
});

module.exports = { pool };