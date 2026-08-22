# CloudOps Hub V1 - Manual Deployment Runbook

This runbook provides the repeatable steps required to manually deploy and validate the CloudOps Hub V1 environment.

> This is an operational runbook. Architecture decisions, engineering reasoning, and lessons learned are documented separately in the foundation documents.

---

## 1. Deployment Overview

The current V1 architecture is:

```text
Internet
   │
   ▼
Web Layer
   │
   ▼
Application Layer
   │
   │ TCP 5432
   ▼
Database Layer
```

Current deployment sequence:

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
Python Backend
     ↓
systemd Service
     ↓
API Validation
```

The Web Layer will be added once its manual implementation is completed.

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
- EC2 IAM role with Systems Manager permissions

Repository files:

```text
app/
├── backend/
│   ├── app.py
│   └── requirements.txt
├── database/
│   └── schema.sql
└── frontend/
```

---

# 3. Create NAT Gateway

Create:

```text
Name: cloudops-hub-nat
Subnet: cloudops-web-subnet
Connectivity type: Public
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

---

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

Attach the required Systems Manager IAM role.

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

Start the service:

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

Backup:

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

Restart:

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

---

# 9. Apply Database Schema

Connect:

```bash
psql \
  -U cloudops_app \
  -d cloudops_hub \
  -h localhost \
  -W
```

Apply the schema from:

```text
app/database/schema.sql
```

Validate:

```sql
\dt
```

Expected table:

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

Do not assume the previous EC2 private IP will be reused after recreation.

---

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

Connect using Session Manager.

---

# 12. Validate App-to-DB Connectivity

Install PostgreSQL client:

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

into this directory.

Create the Python virtual environment:

```bash
python3 -m venv venv
```

Activate:

```bash
source venv/bin/activate
```

Upgrade pip:

```bash
pip install --upgrade pip
```

Install application dependencies:

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

Validate permissions:

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

Health:

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

---

# 17. Deployment Validation Checklist

Before continuing to the Web Layer:

- [ ] NAT Gateway available
- [ ] App subnet NAT route configured
- [ ] DB subnet NAT route configured
- [ ] DB EC2 running
- [ ] DB EC2 has no public IP
- [ ] PostgreSQL running
- [ ] PostgreSQL enabled at boot
- [ ] PostgreSQL listening on port 5432
- [ ] `cloudops_hub` database exists
- [ ] `cloudops_app` user exists
- [ ] `applications` table exists
- [ ] App EC2 running
- [ ] App EC2 has no public IP
- [ ] Session Manager working
- [ ] App → DB connectivity working
- [ ] Backend dependencies installed
- [ ] Backend systemd service active
- [ ] Backend systemd service enabled
- [ ] `/health` working
- [ ] `GET /api/applications` working
- [ ] `POST /api/applications` working

---

# 18. Troubleshooting

## Session Manager unavailable

Check:

1. IAM instance role
2. SSM Agent
3. NAT/default route
4. Security Group outbound connectivity

---

## PostgreSQL connection refused

Example:

```text
connection refused
```

Check:

```bash
sudo systemctl status postgresql
sudo ss -lntp | grep 5432
```

Verify:

```text
listen_addresses = '*'
```

---

## pg_hba.conf rejection

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

---

## Backend HTTP 500

Check service logs:

```bash
sudo journalctl -u cloudops-hub-backend -n 50 --no-pager
```

Check status:

```bash
sudo systemctl status cloudops-hub-backend --no-pager
```

Validate the DB independently using `psql` before changing PostgreSQL configuration.

---

# 19. Daily Cleanup

When the environment is no longer required:

1. Terminate `cloudops-app-01`
2. Terminate `cloudops-db-01`
3. Verify attached EBS volumes were deleted
4. Delete `cloudops-hub-nat`
5. Release its unassociated Elastic IP
6. Remove stale NAT routes from:
   - `cloudops-app-rt`
   - `cloudops-db-rt`

Keep the reusable VPC foundation.

---

# 20. Next Milestone

After successful validation:

```text
Web Layer
    ↓
Application Layer
    ↓
Database Layer
```

The next objective is to complete the CloudOps Hub V1 end-to-end manual deployment.