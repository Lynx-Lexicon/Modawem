const http = require('http');

const port = process.env.PORT || 8080;

const server = http.createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
        status: 'ok',
        message: 'Placeholder API is running!',
        environment: process.env.APP_ENV,
        database_host: process.env.DB_HOST
    }));
});

server.listen(port, () => {
    console.log(`Server running on port ${port}`);
});