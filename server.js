const path = require('path');
const express = require('express');
const compression = require('compression');

const app = express();

app.use(compression());
app.use(express.static(__dirname + '/dist'));
app.get('/*', function(req, res) {
  res.sendFile(path.join(__dirname + '/dist/mtd/index.html'));
});

app.listen(process.env.PORT || 8080);
