curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
-d '{
  "httpMethod": "GET",
  "path": "/collections/lakes/items",
  "headers": {},
  "queryStringParameters": {},
  "body": null,
  "isBase64Encoded": false
}'
