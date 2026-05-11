const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient } = require('@aws-sdk/lib-dynamodb');

// On EC2 with an IAM role attached, credentials are picked up automatically.
// For local development, set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in .env.
const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'us-east-1',
});

module.exports = DynamoDBDocumentClient.from(client);
