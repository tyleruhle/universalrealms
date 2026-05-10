# AWS Setup Guide — Universal Realms

## 1. Create DynamoDB Tables

Go to **AWS Console → DynamoDB → Create table** for each table below.

---

### Table: `ur_users`

| Setting | Value |
|---|---|
| Table name | `ur_users` |
| Partition key | `userId` (String) |
| Billing mode | On-demand (recommended for low traffic) |

**Global Secondary Indexes** (add after table is created → Indexes tab):

| Index name | Partition key | Type |
|---|---|---|
| `email-index` | `email` (String) | GSI |
| `username-index` | `username` (String) | GSI |

---

### Table: `ur_characters`

| Setting | Value |
|---|---|
| Table name | `ur_characters` |
| Partition key | `userId` (String) |
| Sort key | `characterId` (String) |
| Billing mode | On-demand |

---

## 2. Create an IAM User for the App

Go to **AWS Console → IAM → Users → Create user**.

- Username: `universal-realms-app`
- Access type: Programmatic access (Access key + Secret)

**Attach this inline policy** (or create a managed policy named `UniversalRealmsDynamo`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/ur_users",
        "arn:aws:dynamodb:us-east-1:*:table/ur_users/index/*",
        "arn:aws:dynamodb:us-east-1:*:table/ur_characters",
        "arn:aws:dynamodb:us-east-1:*:table/ur_characters/index/*"
      ]
    }
  ]
}
```

Replace `us-east-1` with your actual region if different.

After creating the user, copy the **Access Key ID** and **Secret Access Key** into your `.env` file.

---

## 3. Generate a JWT Secret

Run this on your EC2 instance:

```bash
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
```

Paste the output into `.env` as `JWT_SECRET`.

---

## 4. Deploy to EC2

```bash
# On your EC2 instance:

# Clone the repo
git clone https://github.com/tyleruhle/universal-realms.git
cd universal-realms

# Install dependencies
npm install --production

# Copy and fill in env file
cp .env.example .env
nano .env   # fill in JWT_SECRET, AWS keys

# Install PM2 to keep Node running
npm install -g pm2

# Start the app
pm2 start server.js --name universal-realms

# Save PM2 process list so it restarts on reboot
pm2 save
pm2 startup   # follow the instructions it prints

# Update Nginx config
sudo cp nginx.conf.example /etc/nginx/sites-available/universal-realms
sudo ln -sf /etc/nginx/sites-available/universal-realms /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 5. Future Deploys (from your machine)

```bash
# Push to GitHub from local
git push origin main

# SSH into EC2 and pull
ssh ec2-user@your-ec2-ip
cd universal-realms
git pull
npm install --production
pm2 restart universal-realms
```
