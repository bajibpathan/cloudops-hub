# Application Layer Foundation

This document captures the design decisions, manual implementation, troubleshooting, and validation of the CloudOps Hub V1 Application Layer.

---

## 1. Why a Separate Application Layer?

### The Problem

The CloudOps Hub backend contains application logic and communicates with the database.

There is no requirement for users on the Internet to communicate directly with the Application server.

Exposing the Application EC2 instance directly to the Internet would unnecessarily increase the attack surface.

### What I Learned

The Application layer should remain private and receive application traffic only from the Web layer.

The intended architecture is:

```text
Internet
   │
   ▼
Web Layer
   │
   ▼
Application Layer
   │
   ▼
Database Layer
```

For CloudOps Hub V1:

- The App EC2 instance is deployed in `cloudops-app-subnet`.
- It does not have a public IPv4 address.
- SSH is not exposed to the Internet.
- Administration is performed using AWS Systems Manager Session Manager.
- Future inbound application traffic will originate from the Web layer.

> **A workload should not be Internet-facing simply because users eventually depend on it.**

---

## 2. Application EC2 Design

The Application server was manually provisioned with the following design.

| Configuration | Decision |
|---|---|
| Instance | `cloudops-app-01` |
| Operating System | Amazon Linux 2023 |
| Instance Type | `t3.micro` |
| VPC | `cloudops-hub-vpc` |
| Subnet | `cloudops-app-subnet` |
| Public IPv4 | Disabled |
| Security Group | `cloudops-app-sg` |
| Administration | AWS Systems Manager Session Manager |
| SSH | Not exposed |
| Storage | `gp3` |
| Backend | Python / Flask |
| Application Port | `5000` |

### What I Learned

EC2 configuration should follow workload requirements.

The Application server does not require direct Internet access from users, so it does not require a public IP address.

---

## 3. Private Administrative Access

### The Problem

The Application EC2 instance is private, but administrators still need a way to install software, configure the backend, inspect logs, and troubleshoot problems.

### Initial Result

The EC2 instance was launched with the required IAM permissions for Systems Manager.

However, Session Manager was initially unavailable.

The App subnet contained only the VPC local route:

```text
10.0.0.0/16 → local
```

### What I Learned

IAM permissions alone are not sufficient for Systems Manager connectivity.

The EC2 instance also requires a network path to the required AWS service endpoints.

For CloudOps Hub V1, the existing NAT Gateway was reused.

The App route table was updated to include:

```text
0.0.0.0/0 → cloudops-hub-nat
```

The resulting path is:

```text
Private App EC2
      │
      ▼
cloudops-app-rt
      │
      ▼
NAT Gateway
      │
      ▼
Internet Gateway
      │
      ▼
AWS Systems Manager endpoints
```

After adding the route, Session Manager connectivity was successfully validated.

The App server still has:

```text
Public IPv4: No
Inbound SSH: No
```

> **Authorization and network connectivity are separate requirements. IAM can allow an action, but the network must still provide a path to the service.**

---

## 4. App-to-Database Connectivity

### Goal

The Application server needs to communicate privately with PostgreSQL.

The intended path is:

```text
cloudops-app-01
      │
      │ TCP 5432
      ▼
cloudops-app-sg
      │
      ▼
cloudops-db-sg
      │
      ▼
cloudops-db-01
      │
      ▼
PostgreSQL
```

The Database Security Group allows PostgreSQL traffic on TCP `5432` from:

```text
cloudops-app-sg
```

This represents the application relationship instead of depending on a specific App EC2 IP address.

---

## 5. PostgreSQL Client Installation

The Application server does not need to run PostgreSQL itself.

It only requires PostgreSQL client utilities for connectivity testing and troubleshooting.

Install the client:

```bash
sudo dnf install -y postgresql18
```

Verify:

```bash
psql --version
```

Validated version during implementation:

```text
psql (PostgreSQL) 18.4
```

### What I Learned

Install software based on the responsibility of the server.

The App server needs to communicate with PostgreSQL, but it does not need to become another PostgreSQL server.

---

## 6. First Remote Database Connection

The initial remote connection was tested from the Application EC2 instance:

```bash
psql \
  -U cloudops_app \
  -d cloudops_hub \
  -h <DB_PRIVATE_IP> \
  -W
```

The connection failed with:

```text
connection to server at "<DB_PRIVATE_IP>", port 5432 failed:
Connection refused

Is the server running on that host and accepting TCP/IP connections?
```

### Troubleshooting

The failure was different from an authentication error.

The PostgreSQL service was running, and the AWS network path had been configured.

We investigated whether PostgreSQL itself was accepting remote TCP connections.

PostgreSQL was originally configured for local connectivity.

### PostgreSQL Listener

The following setting was updated in:

```text
/var/lib/pgsql/data/postgresql.conf
```

to:

```text
listen_addresses = '*'
```

This allowed PostgreSQL to listen on the server's network interfaces.

AWS Security Groups still control which resources can reach PostgreSQL on port `5432`.

### PostgreSQL Client Authentication

The following rule was added to:

```text
/var/lib/pgsql/data/pg_hba.conf
```

```text
host    cloudops_hub    cloudops_app    10.0.2.0/24    scram-sha-256
```

This allows the CloudOps Hub application identity to connect to the CloudOps Hub database from the Application subnet using SCRAM authentication.

PostgreSQL was then restarted:

```bash
sudo systemctl restart postgresql
```

Service status was validated:

```bash
sudo systemctl is-active postgresql
```

The listener was inspected using:

```bash
sudo ss -lntp | grep 5432
```

The remote `psql` connection from the App server then succeeded.

### Validation

```sql
SELECT current_user;
SELECT current_database();
SELECT * FROM applications;
```

Validated:

```text
current_user     → cloudops_app
current_database → cloudops_hub
```

The existing `Payment Service` application record was successfully retrieved.

### What I Learned

Successful App → DB connectivity depends on multiple layers:

```text
Application
     │
     ▼
VPC Routing
     │
     ▼
Security Groups
     │
     ▼
PostgreSQL Listener
     │
     ▼
pg_hba.conf
     │
     ▼
Authentication
     │
     ▼
Database
```

> **Opening a Security Group port does not automatically mean the application behind that port is ready to accept the connection.**

---

## 7. CloudOps Hub Backend

CloudOps Hub V1 uses a small Python Flask backend.

Repository structure:

```text
app/
├── backend/
│   ├── app.py
│   └── requirements.txt
├── database/
│   └── schema.sql
└── frontend/
```

The backend currently provides:

```text
GET  /health
GET  /api/applications
POST /api/applications
```

### Responsibilities

`GET /health`

Validates that the backend process is running.

`GET /api/applications`

Retrieves applications from PostgreSQL.

`POST /api/applications`

Creates a new application record in PostgreSQL.

The V1 backend is intentionally small.

Additional functionality will be introduced only when there is a requirement for it.

---

## 8. Python Virtual Environment

### The Problem

Installing application dependencies globally can mix application packages with operating-system Python packages.

### Implementation

Create the backend directory:

```bash
mkdir -p ~/cloudops-hub/backend
cd ~/cloudops-hub/backend
```

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Dependency Issue Encountered

The initial Psycopg version selected was not compatible with the Python environment available on the EC2 instance.

The dependency was changed to a compatible version and installation succeeded.

### What I Learned

A package being newer does not automatically make it appropriate for a workload.

Dependencies must be compatible with the runtime environment.

A Python virtual environment also provides isolation between application dependencies and system-level Python packages.

---

## 9. Application Configuration

Database configuration is provided to the backend through environment variables:

```text
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

The password is not hardcoded in `app.py` or committed to Git.

### Troubleshooting Experience

The first database API request returned:

```json
{"error":"Unable to retrieve applications"}
```

The Flask logs showed:

```text
KeyError: 'DB_PASSWORD'
```

The database itself was validated separately using `psql` and was working correctly.

The problem was that `DB_PASSWORD` had been exported in a different Session Manager shell.

### What I Learned

Shell environment variables are scoped to the shell/process environment.

A variable exported in one SSM session does not automatically exist in another session.

Processes inherit environment variables from the environment from which they are started.

The troubleshooting path was:

```text
API returned HTTP 500
       │
       ▼
Inspect application logs
       │
       ▼
KeyError: DB_PASSWORD
       │
       ▼
Validate DB independently
       │
       ▼
DB working
       │
       ▼
Inspect application environment
       │
       ▼
Missing environment variable
       │
       ▼
Correct configuration
       │
       ▼
API working
```

> **Troubleshoot the failing layer instead of changing components that have already been proven healthy.**

---

## 10. API Validation

### Health Check

```bash
curl http://localhost:5000/health
```

This validated that the Flask backend was running.

### Read From PostgreSQL

```bash
curl http://localhost:5000/api/applications
```

The backend successfully retrieved application records from PostgreSQL.

This validated:

```text
HTTP Request
     ↓
Flask
     ↓
Psycopg
     ↓
Private App → DB Connection
     ↓
PostgreSQL
     ↓
SELECT
     ↓
JSON Response
```

### Write to PostgreSQL

A new application was created:

```bash
curl -X POST http://localhost:5000/api/applications \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Order Service",
    "description": "Processes customer orders",
    "owner_team": "Orders Team",
    "environment": "Production",
    "status": "Healthy"
  }'
```

The applications endpoint was queried again:

```bash
curl http://localhost:5000/api/applications
```

Both read and write operations were successfully validated.

```text
GET  → Backend → PostgreSQL → Read   ✅
POST → Backend → PostgreSQL → Write  ✅
```

---

## 11. Running the Backend With systemd

### The Problem

Initially, Flask was started manually:

```bash
python app.py
```

This ties the application process to the interactive shell.

If the process stops or the server reboots, the application may no longer be available.

### Solution

The backend was configured as a Linux `systemd` service.

An environment configuration file was created:

```text
/etc/cloudops-hub/backend.env
```

Example structure:

```text
DB_HOST=<DB_PRIVATE_IP>
DB_PORT=5432
DB_NAME=cloudops_hub
DB_USER=cloudops_app
DB_PASSWORD=<DATABASE_PASSWORD>
```

The file is protected with:

```bash
sudo chmod 600 /etc/cloudops-hub/backend.env
```

The actual password must never be committed to Git.

### systemd Unit

```text
/etc/systemd/system/cloudops-hub-backend.service
```

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

Load the service definition:

```bash
sudo systemctl daemon-reload
```

Start:

```bash
sudo systemctl start cloudops-hub-backend
```

Enable automatic startup:

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

### What I Learned

`systemd` allows Linux to manage the lifecycle of the application instead of relying on an administrator keeping an interactive shell open.

It provides a consistent way to:

- Start
- Stop
- Restart
- Check status
- Automatically start during boot
- Recover from application process failures

---

## 12. Failure Recovery Test

The service was configured with:

```ini
Restart=on-failure
RestartSec=5
```

To validate this behavior, the running Flask process was deliberately terminated.

The expected behavior was:

```text
Flask running
     ↓
Process terminated
     ↓
systemd detects failure
     ↓
Wait approximately 5 seconds
     ↓
Backend restarted
     ↓
Health endpoint available again
```

This behavior was successfully validated.

### What I Learned

There is a difference between:

```text
Running an application
```

and:

```text
Operating an application
```

Running the application proves that the code works.

Operating the application also requires thinking about lifecycle management, failures, recovery, logging, configuration, and startup behavior.

> **Reliability starts by assuming processes will eventually fail.**

---

## 13. Current Security Model

The current Application Layer follows these principles:

- App EC2 has no public IPv4 address.
- SSH is not exposed.
- Administrative access uses Systems Manager.
- Database traffic uses the private VPC network.
- PostgreSQL port `5432` is allowed from the Application Security Group.
- The backend uses the dedicated `cloudops_app` database identity.
- Database credentials are not stored in source code.
- Application processes do not run as `root`.

### Current Limitation

For the manual V1 implementation, the database password is stored in a root-readable environment file on the App server.

This is intentionally temporary.

A future milestone can introduce a more appropriate secrets-management solution after we understand the problem being solved.

---

## 14. Current Limitations

CloudOps Hub V1 currently has several known Application Layer limitations.

### Single App EC2

There is currently one Application EC2 instance.

If the instance or Availability Zone fails, the backend becomes unavailable.

### Flask Development Server

The current V1 backend runs directly using Flask's built-in server.

This is sufficient for the manual learning milestone but is not the target production serving model.

### Local Environment File

Database credentials are currently stored locally in a protected environment file.

### No Application Authentication

The V1 API does not yet implement user authentication or authorization.

### No Load Balancing

There is currently no load balancer in front of the Application layer.

### No Application Observability

Application metrics, centralized logging, tracing, dashboards, and alerting have not yet been implemented.

These limitations will be addressed only when the corresponding project milestone creates the requirement.

---

## 15. Application Foundation Status

At this stage, CloudOps Hub V1 has:

- [x] Private Application EC2
- [x] No public IPv4
- [x] Session Manager administration
- [x] NAT-based outbound connectivity
- [x] PostgreSQL client
- [x] Private App → DB connectivity
- [x] PostgreSQL remote listener configuration
- [x] PostgreSQL App subnet authentication rule
- [x] Python backend
- [x] Python virtual environment
- [x] Flask health endpoint
- [x] Database GET endpoint
- [x] Database POST endpoint
- [x] Environment-based DB configuration
- [x] systemd service
- [x] Automatic service startup
- [x] Process failure recovery validation
- [ ] Web → App connectivity
- [ ] Production application server
- [ ] Application observability
- [ ] High availability

---

## Next Milestone

The next CloudOps Hub V1 milestone is:

> **Web Layer → Application Layer Connectivity**

The target path is:

```text
User
  │
  ▼
Web Layer
  │
  ▼
Private Application Layer
  │
  ▼
PostgreSQL Database Layer
```

Once this path is implemented and validated, CloudOps Hub will have its first complete manual three-tier application flow.