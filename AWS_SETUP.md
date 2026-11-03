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

---

## 6. World Engine (Worlds, Atlas Studio, lore and history)

Everything below is additive: existing pages keep working if you skip it, and
`/worlds.html` shows a clear error until the table exists. Background:
`docs/WORLD_ENGINE.md`. Region below is `us-east-2`; change it if yours differs.

### 6.1 DynamoDB table `ur_worlds`

```bash
aws dynamodb create-table --region us-east-2 \
  --table-name ur_worlds \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions AttributeName=worldId,AttributeType=S \
                          AttributeName=ownerUserId,AttributeType=S \
                          AttributeName=updatedAt,AttributeType=S \
  --key-schema AttributeName=worldId,KeyType=HASH \
  --global-secondary-indexes '[{"IndexName":"owner-index","KeySchema":[{"AttributeName":"ownerUserId","KeyType":"HASH"},{"AttributeName":"updatedAt","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]'
aws dynamodb wait table-exists --region us-east-2 --table-name ur_worlds
```

(Console: partition key `worldId` (String), on-demand; then Indexes → Create index:
partition `ownerUserId` (String), sort `updatedAt` (String), name `owner-index`, projection All.)

### 6.2 S3 bucket for world files

```bash
aws s3api create-bucket --region us-east-2 --bucket universal-realms-worlds \
  --create-bucket-configuration LocationConstraint=us-east-2
aws s3api put-public-access-block --bucket universal-realms-worlds \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Bucket names are global: if this one is taken, pick another and use it in `WORLD_BUCKET`.
Files are only ever served through the app, which checks the signed-in owner.

### 6.3 IAM — let the app use the table and bucket

Add this statement to the policy attached to the EC2 instance role (or the app user):

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
             "dynamodb:DeleteItem", "dynamodb:Query"],
  "Resource": ["arn:aws:dynamodb:us-east-2:*:table/ur_worlds",
               "arn:aws:dynamodb:us-east-2:*:table/ur_worlds/index/*"]
},
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::universal-realms-worlds/*"
},
{
  "Effect": "Allow",
  "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::universal-realms-worlds"
}
```

### 6.4 Python for the engine (on the instance)

The engine needs Python 3.10 or newer (`python3 --version`).

```bash
# Amazon Linux 2023 ships 3.9; install 3.11 alongside it:
sudo dnf install -y python3.11
cd ~/universal-realms                       # the app directory PM2 runs
PYTHON=python3.11 npm run engine:setup     # creates engine/.venv with numpy, scipy, scikit-image, Pillow
# Ubuntu 22.04+/24.04:  sudo apt install -y python3-venv && npm run engine:setup

engine/.venv/bin/python engine/service.py vocab | tail -1    # should print {"ok": true, ...}
```

Each engine job peaks around 0.5 GB of memory. On a 1–2 GB instance add swap so a
job never pushes Node out of memory:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

### 6.5 Environment

Append to `.env` (see `.env.example` for every option):

```
ANTHROPIC_API_KEY=sk-ant-...          # console.anthropic.com → API keys
ANTHROPIC_MODEL=claude-sonnet-5-5
WORLD_DB=dynamo
WORLD_STORE=s3
WORLD_BUCKET=universal-realms-worlds
LORE_MAX_PER_HOUR=60
JOB_CONCURRENCY=1
```

Set a monthly spend limit for the key in the Claude Console.

### 6.6 nginx and restart

```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/universal-realms   # adds client_max_body_size 8m and proxy_read_timeout 120s
sudo nginx -t && sudo systemctl reload nginx
npm install --production
pm2 restart universal-realms --update-env
```

### 6.7 Check it

1. Open `https://universal-realms.com/worlds.html` signed in, create a world.
2. Lore tab: send a message; Draft the Overview; Save; Confirm.
3. Map tab: Suggest from the bible → Generate (small). The preview appears in about 10 s.
4. Open in Atlas Studio → draw a settlement → Save to world → Back to world: the Map tab lists it.
5. History tab: Run history (12 turns). Era maps and story seams appear.
6. `pm2 logs universal-realms --lines 50` shows no errors.
