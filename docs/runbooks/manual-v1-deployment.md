# CloudOps Hub V1 - Manual Deployment Runbook

This runbook provides the repeatable steps required to manually deploy and validate the complete CloudOps Hub V1 three-tier environment.

> This is an operational runbook. Architecture decisions, engineering reasoning, and lessons learned are documented separately in the foundation documents.

---

# 1. Deployment Overview

The CloudOps Hub Manual V1 architecture is:

```text
Internet
   │
   │ HTTP :80
   ▼
Web EC2 / Nginx
   │
   │ HTTP :5000
   ▼
Private App EC2 / Flask
   │
   │ TCP :5432
   ▼
Private DB EC2 / PostgreSQL
```

The deployment sequence is:

```text
NAT Gateway
     ↓
Database EC2
     ↓
PostgreSQL
     ↓
Database Schema
     ↓
Application EC2
     ↓
App → DB Validation
     ↓
Flask Backend
     ↓
systemd Service
     ↓
Backend API Validation
     ↓
Web EC2
     ↓
Web → App Validation
     ↓
Nginx
     ↓
Frontend
     ↓
Reverse Proxy
     ↓
End-to-End Browser Validation
```

The Web, Application, and Database layers are manually deployed and validated end to end.

---

# 2. Prerequisites

The following reusable infrastructure should already exist:

- `cloudops-hub-vpc`
- `cloudops-web-subnet`
- `cloudops-app-subnet`
- `cloudops-db-subnet`
- `cloudops-public-rt`
- `cloudops-app-rt`
- `cloudops-db-rt`
- `cloudops-hub-igw`
- `cloudops-web-sg`
- `cloudops-app-sg`
- `cloudops-db-sg`
- EC2 IAM role with AWS Systems Manager permissions

Repository files:

```text
app/
├── backend/
│   ├── app.py
│   └── requirements.txt
├── database/
│   └── schema.sql
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

---

# 3. Create NAT Gateway

Create:

```text
Name: cloudops-hub-nat
Subnet: cloudops-web-subnet
Connectivity Type: Public
Elastic IP: Allocate new Elastic IP
```

Wait until the NAT Gateway status becomes:

```text
Available
```

Add the following route to `cloudops-app-rt`:

```text
0.0.0.0/0 → cloudops-hub-nat
```

Add the following route to `cloudops-db-rt`:

```text
0.0.0.0/0 → cloudops-hub-nat
```

This provides outbound Internet connectivity to the private App and DB instances without making them publicly reachable.

---

# Database Layer

# 4. Deploy Database EC2

Launch:

```text
Name: cloudops-db-01
AMI: Amazon Linux 2023
Instance Type: t3.micro

VPC: cloudops-hub-vpc
Subnet: cloudops-db-subnet
Public IPv4: Disabled

Security Group:
cloudops-db-sg

Storage:
8 GiB gp3

SSH:
Disabled
```

Attach the EC2 IAM role with Systems Manager permissions.

Wait for EC2 status checks to pass.

Connect using:

```text
EC2 → Connect → Session Manager
```

---

# 5. Install PostgreSQL

Search available packages if required:

```bash
dnf search postgresql
```

Install PostgreSQL:

```bash
sudo dnf install -y postgresql18 postgresql18-server
```

Verify:

```bash
psql --version
```

Initialize PostgreSQL:

```bash
sudo postgresql-setup --initdb
```

Start PostgreSQL:

```bash
sudo systemctl start postgresql
```

Enable startup:

```bash
sudo systemctl enable postgresql
```

Validate:

```bash
sudo systemctl is-active postgresql
sudo systemctl is-enabled postgresql
```

Expected:

```text
active
enabled
```

---

# 6. Create Database and User

Connect as the PostgreSQL administrator:

```bash
sudo -u postgres psql
```

Create the database:

```sql
CREATE DATABASE cloudops_hub;
```

Create the application identity:

```sql
CREATE USER cloudops_app
WITH PASSWORD '<STRONG_DATABASE_PASSWORD>';
```

Assign ownership:

```sql
ALTER DATABASE cloudops_hub
OWNER TO cloudops_app;
```

Exit:

```sql
\q
```

> Never store the real database password in Git.

---

# 7. Configure PostgreSQL Authentication

Backup the existing configuration:

```bash
sudo cp /var/lib/pgsql/data/pg_hba.conf \
/var/lib/pgsql/data/pg_hba.conf.bak
```

Edit:

```bash
sudo vi /var/lib/pgsql/data/pg_hba.conf
```

Configure localhost TCP authentication:

```text
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

Allow the Application subnet:

```text
host    cloudops_hub    cloudops_app    10.0.2.0/24    scram-sha-256
```

Do not allow the entire VPC unless there is a specific requirement.

---

# 8. Configure PostgreSQL Network Listener

Edit:

```bash
sudo vi /var/lib/pgsql/data/postgresql.conf
```

Configure:

```text
listen_addresses = '*'
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

Validate:

```bash
sudo systemctl is-active postgresql
```

Check the listener:

```bash
sudo ss -lntp | grep 5432
```

Expected:

```text
0.0.0.0:5432
[::]:5432
```

This confirms PostgreSQL is listening on the server network interfaces.

Network access is still controlled by the Security Group and `pg_hba.conf`.

---

# 9. Apply Database Schema

The database schema is maintained in:

```text
app/database/schema.sql
```

Connect:

```bash
psql \
  -U cloudops_app \
  -d cloudops_hub \
  -h localhost \
  -W
```

Apply the contents of:

```text
app/database/schema.sql
```

The V1 schema creates the `applications` table.

Validate:

```sql
\dt
```

Expected:

```text
applications
```

Inspect:

```sql
\d applications
```

Exit:

```sql
\q
```

---

# 10. Record DB Private IP

Record the current private IPv4 address of:

```text
cloudops-db-01
```

Example:

```text
DB_PRIVATE_IP=<current-private-ip>
```

Do not assume that a previously used EC2 private IP will be reused after the instance is recreated.

---

# Application Layer

# 11. Deploy Application EC2

Launch:

```text
Name: cloudops-app-01
AMI: Amazon Linux 2023
Instance Type: t3.micro

VPC: cloudops-hub-vpc
Subnet: cloudops-app-subnet
Public IPv4: Disabled

Security Group:
cloudops-app-sg

Storage:
8 GiB gp3

SSH:
Disabled
```

Attach the Systems Manager IAM role.

Wait for EC2 status checks to pass.

Connect using:

```text
EC2 → Connect → Session Manager
```

---

# 12. Validate App-to-DB Connectivity

Install the PostgreSQL client:

```bash
sudo dnf install -y postgresql18
```

Connect:

```bash
psql \
  -U cloudops_app \
  -d cloudops_hub \
  -h <DB_PRIVATE_IP> \
  -W
```

Validate:

```sql
SELECT current_user;
SELECT current_database();
\dt
```

Expected:

```text
current_user     → cloudops_app
current_database → cloudops_hub
```

Exit:

```sql
\q
```

Do not deploy the backend until App-to-DB connectivity works.

---

# 13. Deploy Backend

Create the application directory:

```bash
mkdir -p ~/cloudops-hub/backend
cd ~/cloudops-hub/backend
```

Copy the repository versions of:

```text
app/backend/app.py
app/backend/requirements.txt
```

into:

```text
~/cloudops-hub/backend/
```

The resulting structure should resemble:

```text
~/cloudops-hub/backend/
├── app.py
└── requirements.txt
```

Create a Python virtual environment:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Upgrade pip:

```bash
pip install --upgrade pip
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 14. Configure Backend Environment

Create:

```bash
sudo mkdir -p /etc/cloudops-hub
sudo vi /etc/cloudops-hub/backend.env
```

Configure:

```text
DB_HOST=<DB_PRIVATE_IP>
DB_PORT=5432
DB_NAME=cloudops_hub
DB_USER=cloudops_app
DB_PASSWORD=<DATABASE_PASSWORD>
```

Protect the file:

```bash
sudo chmod 600 /etc/cloudops-hub/backend.env
```

Validate:

```bash
sudo ls -l /etc/cloudops-hub/backend.env
```

The database password must never be committed to Git.

---

# 15. Configure Backend systemd Service

Create:

```bash
sudo vi /etc/systemd/system/cloudops-hub-backend.service
```

Add:

```ini
[Unit]
Description=CloudOps Hub Backend
After=network.target

[Service]
Type=simple
User=ssm-user
WorkingDirectory=/home/ssm-user/cloudops-hub/backend
EnvironmentFile=/etc/cloudops-hub/backend.env
ExecStart=/home/ssm-user/cloudops-hub/backend/venv/bin/python /home/ssm-user/cloudops-hub/backend/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Start:

```bash
sudo systemctl start cloudops-hub-backend
```

Enable:

```bash
sudo systemctl enable cloudops-hub-backend
```

Validate:

```bash
sudo systemctl is-active cloudops-hub-backend
sudo systemctl is-enabled cloudops-hub-backend
```

Expected:

```text
active
enabled
```

---

# 16. Validate Backend

Test the health endpoint:

```bash
curl http://localhost:5000/health
```

Read applications:

```bash
curl http://localhost:5000/api/applications
```

Create a test application:

```bash
curl -X POST http://localhost:5000/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Payment Service",
    "description": "Processes customer payments",
    "owner_team": "Payments Team",
    "environment": "Production",
    "status": "Healthy"
  }'
```

Verify:

```bash
curl http://localhost:5000/api/applications
```

The backend should now be able to read from and write to PostgreSQL.

---

# Web Layer

# 17. Deploy Web EC2

Launch:

```text
Name: cloudops-web-01
AMI: Amazon Linux 2023
Instance Type: t3.micro

VPC: cloudops-hub-vpc
Subnet: cloudops-web-subnet
Public IPv4: Enabled

Security Group:
cloudops-web-sg

Storage:
8 GiB gp3

SSH:
Disabled
```

Attach the Systems Manager IAM role.

Wait until the EC2 instance passes its status checks.

Connect using:

```text
EC2 → Connect → Session Manager
```

---

# 18. Validate Web-to-App Connectivity

Find the current private IPv4 address of:

```text
cloudops-app-01
```

From `cloudops-web-01`, test:

```bash
curl http://<APP_PRIVATE_IP>:5000/health
```

Expected:

```json
{
  "service": "cloudops-hub-backend",
  "status": "healthy"
}
```

Test the database-backed endpoint:

```bash
curl http://<APP_PRIVATE_IP>:5000/api/applications
```

Successful responses confirm:

```text
Web EC2
   ↓
cloudops-web-sg
   ↓
cloudops-app-sg
   ↓
Flask :5000
   ↓
PostgreSQL
```

Do not continue with Nginx until Web-to-App connectivity works.

---

# 19. Install Nginx

Install:

```bash
sudo dnf install -y nginx
```

Start:

```bash
sudo systemctl start nginx
```

Enable automatic startup:

```bash
sudo systemctl enable nginx
```

Validate:

```bash
sudo systemctl is-active nginx
sudo systemctl is-enabled nginx
```

Expected:

```text
active
enabled
```

Test locally:

```bash
curl http://localhost
```

Verify the default Nginx page from the browser:

```text
http://<WEB_PUBLIC_IP>
```

This confirms:

```text
Internet
   ↓
Internet Gateway
   ↓
Public Web Subnet
   ↓
cloudops-web-sg :80
   ↓
Nginx
```

---

# 20. Deploy Frontend

Create the CloudOps Hub document root:

```bash
sudo mkdir -p /var/www/cloudops-hub
```

Deploy:

```text
app/frontend/index.html
app/frontend/styles.css
app/frontend/app.js
```

to:

```text
/var/www/cloudops-hub/
```

The final structure should be:

```text
/var/www/cloudops-hub/
├── index.html
├── styles.css
└── app.js
```

Verify:

```bash
sudo ls -la /var/www/cloudops-hub
```

The frontend should use relative API requests such as:

```javascript
fetch("/api/applications")
```

The App EC2 private IP should not be hardcoded into browser-side code.

---

# 21. Configure Nginx Reverse Proxy

Create:

```bash
sudo vi /etc/nginx/conf.d/cloudops-hub.conf
```

Configure:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    root /var/www/cloudops-hub;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://<APP_PRIVATE_IP>:5000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Replace:

```text
<APP_PRIVATE_IP>
```

with the current private IPv4 address of `cloudops-app-01`.

---

# 22. Validate Nginx Configuration

Validate syntax:

```bash
sudo nginx -t
```

Expected:

```text
syntax is ok
test is successful
```

Inspect the active server configuration:

```bash
sudo nginx -T | grep -nE "listen.*80|root /var/www"
```

The CloudOps Hub server should contain:

```text
listen 80 default_server;
listen [::]:80 default_server;
root /var/www/cloudops-hub;
```

Reload Nginx:

```bash
sudo systemctl reload nginx
```

---

# 23. Validate Frontend

Test locally:

```bash
curl http://localhost/
```

The response should contain the CloudOps Hub HTML instead of the default Nginx page.

Open:

```text
http://<WEB_PUBLIC_IP>
```

The CloudOps Hub frontend should load successfully.

---

# 24. Validate Nginx Reverse Proxy

From `cloudops-web-01`:

```bash
curl http://localhost/api/applications
```

The request should return application data from the Flask backend.

This validates:

```text
Nginx :80
   ↓
/api/*
   ↓
Reverse Proxy
   ↓
Flask :5000
   ↓
PostgreSQL :5432
```

---

# 25. End-to-End Browser Validation

Open:

```text
http://<WEB_PUBLIC_IP>
```

Verify that existing applications are displayed.

Create a new application using the Web form.

Example:

```text
Name: Inventory Service
Owner Team: Inventory Team
Environment: Production
Status: Healthy
Description: Manages product inventory
```

Verify that the new application appears in the browser.

The complete request path is now:

```text
Browser
   ↓
POST /api/applications
   ↓
Nginx :80
   ↓
Reverse Proxy
   ↓
Flask :5000
   ↓
PostgreSQL :5432
```

---

# 26. Verify Browser Write in PostgreSQL

Connect to `cloudops-db-01` using Session Manager.

Connect to PostgreSQL:

```bash
psql \
  -U cloudops_app \
  -d cloudops_hub \
  -h localhost \
  -W
```

Query:

```sql
SELECT
    id,
    name,
    owner_team,
    environment,
    status
FROM applications
ORDER BY id;
```

Verify that the application created through the browser exists.

This proves:

```text
Browser
   ↓
Nginx
   ↓
Flask
   ↓
PostgreSQL
   ↓
applications table
```

Exit:

```sql
\q
```

---

# 27. Final Manual V1 Validation

Before declaring Manual V1 complete, validate the complete environment.

## Networking

- [ ] VPC exists
- [ ] Internet Gateway attached
- [ ] Public Web subnet configured
- [ ] Private App subnet configured
- [ ] Private DB subnet configured
- [ ] Route tables configured correctly
- [ ] NAT Gateway available when required
- [ ] Web EC2 has public connectivity
- [ ] App EC2 has required outbound connectivity
- [ ] DB EC2 has required outbound connectivity

## Security

- [ ] Web EC2 allows Internet traffic only on the required Web port
- [ ] SSH is not publicly exposed
- [ ] App EC2 has no public IPv4 address
- [ ] DB EC2 has no public IPv4 address
- [ ] Web SG can reach App SG on TCP 5000
- [ ] App SG can reach DB SG on TCP 5432
- [ ] Session Manager works for administration
- [ ] Database credentials are not committed to Git

## Database

- [ ] PostgreSQL active
- [ ] PostgreSQL enabled at boot
- [ ] PostgreSQL listening on TCP 5432
- [ ] `cloudops_hub` database exists
- [ ] `cloudops_app` identity exists
- [ ] `applications` table exists
- [ ] App-to-DB connection works

## Application

- [ ] Flask backend installed
- [ ] Python dependencies installed
- [ ] Database environment configuration exists
- [ ] Environment file permissions restricted
- [ ] systemd service active
- [ ] systemd service enabled
- [ ] `/health` works
- [ ] `GET /api/applications` works
- [ ] `POST /api/applications` works

## Web

- [ ] Nginx installed
- [ ] Nginx active
- [ ] Nginx enabled at boot
- [ ] Frontend files deployed
- [ ] CloudOps Hub served on TCP 80
- [ ] `/api/` reverse proxy works
- [ ] Browser displays database records
- [ ] Browser can create an application

## End-to-End

- [ ] Browser → Web works
- [ ] Web → App works
- [ ] App → DB works
- [ ] Browser-created data appears in PostgreSQL

---

# 28. Troubleshooting

## Session Manager Unavailable

Check:

1. IAM instance role
2. SSM Agent
3. NAT/default route for private instances
4. Security Group outbound connectivity
5. Instance status checks

---

## PostgreSQL Connection Refused

Example:

```text
connection refused
```

Check PostgreSQL:

```bash
sudo systemctl status postgresql
```

Check the listener:

```bash
sudo ss -lntp | grep 5432
```

Verify:

```text
listen_addresses = '*'
```

A connection refusal normally indicates that the service is not reachable/listening rather than an authentication failure.

---

## `pg_hba.conf` Rejection

Example:

```text
no pg_hba.conf entry for host ...
```

Check:

- Source IP
- Source subnet
- Database
- PostgreSQL user
- Authentication method

Do not broaden the rule simply to make the error disappear.

For CloudOps Hub V1, the App subnet should be explicitly allowed:

```text
10.0.2.0/24
```

---

## Backend HTTP 500

Check the service logs:

```bash
sudo journalctl \
  -u cloudops-hub-backend \
  -n 50 \
  --no-pager
```

Check status:

```bash
sudo systemctl status cloudops-hub-backend --no-pager
```

Check the backend environment configuration.

For example:

```bash
sudo cat /etc/cloudops-hub/backend.env
```

Do not expose the output publicly because it contains the database password.

Validate the database independently using `psql` before modifying PostgreSQL configuration.

---

## Backend Reports Missing Environment Variable

Example:

```text
KeyError: 'DB_PASSWORD'
```

This indicates that the backend process does not have the required environment variable.

Check:

```text
/etc/cloudops-hub/backend.env
```

and verify that the systemd service contains:

```ini
EnvironmentFile=/etc/cloudops-hub/backend.env
```

After changes:

```bash
sudo systemctl daemon-reload
sudo systemctl restart cloudops-hub-backend
```

Then check:

```bash
sudo systemctl status cloudops-hub-backend
```

---

## Web Cannot Reach App

From `cloudops-web-01`:

```bash
curl http://<APP_PRIVATE_IP>:5000/health
```

If it fails, check:

1. Flask backend service
2. App EC2 private IP
3. `cloudops-app-sg`
4. Web-to-App TCP 5000 rule
5. App EC2 status
6. Backend listener

Check the backend:

```bash
sudo systemctl status cloudops-hub-backend
```

---

## Nginx Serves Default Page Instead of CloudOps Hub

If:

```bash
curl http://localhost/
```

returns:

```text
Welcome to nginx!
```

instead of CloudOps Hub, inspect the active configuration:

```bash
sudo nginx -T | grep -nE "listen.*80|root /var/www"
```

Verify that the CloudOps Hub server contains:

```nginx
listen 80 default_server;
listen [::]:80 default_server;

root /var/www/cloudops-hub;
```

Validate:

```bash
sudo nginx -t
```

Reload:

```bash
sudo systemctl reload nginx
```

Test:

```bash
curl http://localhost/
```

If the default page continues to appear, inspect all active server blocks:

```bash
sudo nginx -T
```

> A valid Nginx configuration does not necessarily mean that the intended server block is handling the request.

---

## Nginx Conflicting Server Name

Example:

```text
conflicting server name "_" on 0.0.0.0:80, ignored
```

Inspect:

```bash
sudo nginx -T | grep -nE "server_name|root|listen.*80"
```

Amazon Linux may already contain a default Nginx server block.

Commenting only:

```nginx
server_name _;
root /usr/share/nginx/html;
```

does not disable the surrounding server block.

CloudOps Hub should be explicitly configured as the default server:

```nginx
listen 80 default_server;
listen [::]:80 default_server;
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Nginx API Proxy Fails

First verify that the App server is reachable directly from Web:

```bash
curl http://<APP_PRIVATE_IP>:5000/api/applications
```

If that succeeds but:

```bash
curl http://localhost/api/applications
```

fails, investigate the Nginx reverse-proxy configuration.

Check:

```bash
sudo cat /etc/nginx/conf.d/cloudops-hub.conf
```

Verify:

```nginx
location /api/ {
    proxy_pass http://<APP_PRIVATE_IP>:5000;
}
```

Validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

# 29. Daily Cleanup

When the environment is no longer required:

1. Terminate `cloudops-web-01`
2. Terminate `cloudops-app-01`
3. Terminate `cloudops-db-01`
4. Verify attached EBS volumes were deleted
5. Delete `cloudops-hub-nat`
6. Release the unassociated NAT Gateway Elastic IP
7. Remove stale NAT routes from:
   - `cloudops-app-rt`
   - `cloudops-db-rt`

Keep the reusable VPC foundation:

- `cloudops-hub-vpc`
- `cloudops-web-subnet`
- `cloudops-app-subnet`
- `cloudops-db-subnet`
- `cloudops-public-rt`
- `cloudops-app-rt`
- `cloudops-db-rt`
- `cloudops-hub-igw`
- `cloudops-web-sg`
- `cloudops-app-sg`
- `cloudops-db-sg`
- Systems Manager IAM role

Before finishing cleanup, verify:

```text
Running EC2 instances: None
NAT Gateway: Deleted
Unused NAT Elastic IP: Released
Reusable VPC foundation: Retained
```

---

# 30. Manual V1 Complete

When all validation checks pass:

```text
Internet
   │
   │ HTTP :80
   ▼
┌─────────────────────┐
│ Web Layer           │
│                     │
│ EC2 + Nginx         │
│ Public Subnet       │
└──────────┬──────────┘
           │
           │ HTTP :5000
           ▼
┌─────────────────────┐
│ Application Layer   │
│                     │
│ EC2 + Flask         │
│ systemd             │
│ Private Subnet      │
└──────────┬──────────┘
           │
           │ TCP :5432
           ▼
┌─────────────────────┐
│ Database Layer      │
│                     │
│ EC2 + PostgreSQL    │
│ Private Subnet      │
└─────────────────────┘
```

The following has been manually validated:

```text
Browser
   ↓
Nginx
   ↓
Flask
   ↓
PostgreSQL
   ↓
Data persisted
   ↓
Returned to Browser
```

> **CloudOps Hub Manual V1 - Complete**

---

# 31. Next Milestone

Manual V1 is now frozen.

The next implementation phase will use the existing manual deployment process as the baseline for automation.

```text
Manual Deployment
       ↓
Understand each step
       ↓
Shell Scripting
       ↓
Repeatable deployment
```

The objective is not to redesign the application.

The objective is to automate the same deployment that was first understood and validated manually.

Future architecture improvements such as load balancing, Multi-AZ deployment, HTTPS, Auto Scaling, managed database services, advanced observability, and Infrastructure as Code remain outside the scope of Manual V1.