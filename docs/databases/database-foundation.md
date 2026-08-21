# CloudOps Hub V1 - Database Foundation

## Overview

The CloudOps Hub V1 Database Layer is intentionally built using PostgreSQL running on Amazon EC2.

The objective of V1 is not simply to deploy a database. The goal is to understand the infrastructure, operating system, database, networking, security, and operational responsibilities involved in managing a database ourselves.

This foundation will later help us evaluate managed database services such as Amazon RDS based on the operational responsibilities they remove and the trade-offs they introduce.

---

## 1. Why PostgreSQL on EC2?

### The Problem

For CloudOps Hub V1, we want to understand the operational responsibilities involved in managing a database ourselves.

If we directly start with a managed database service such as Amazon RDS, AWS handles many of the underlying database management activities for us.

Without experiencing those responsibilities ourselves, it may be difficult to fully understand what operational overhead a managed service is removing.

Therefore, we intentionally chose to run PostgreSQL on an EC2 instance for V1.

### What I Learned

Managing a database involves more than simply creating a database and storing data.

By running PostgreSQL on EC2, we are responsible for activities such as:

- Provisioning and securing the server
- Installing PostgreSQL
- Initializing the database cluster
- Starting and managing the PostgreSQL service
- Configuring authentication
- Creating databases and application users
- Designing and creating tables
- Managing persistent storage
- Monitoring the database
- Patching and upgrades
- Backups and recovery
- Troubleshooting failures

During our initial implementation, we manually:

1. Provisioned the EC2 instance.
2. Installed PostgreSQL.
3. Initialized the database cluster.
4. Started and enabled the PostgreSQL service.
5. Created the `cloudops_hub` database.
6. Created the `cloudops_app` application user.
7. Configured authentication.
8. Created the first application table.
9. Validated the database using INSERT and SELECT operations.

Later, when we evaluate Amazon RDS, we will be able to understand which responsibilities AWS manages for us and which responsibilities still remain with us.

> **To appreciate a managed service, first understand the operational burden it removes.**

---

## 2. EC2 Design Decisions

### The Problem

Creating an EC2 instance using default options without understanding the workload requirements is not a good architecture approach.

Since this EC2 instance will host the CloudOps Hub PostgreSQL database, we need to understand the database requirements first and configure the instance accordingly.

### What I Learned

Each EC2 configuration represents an architecture decision and should be selected based on workload requirements.

Before launching an EC2 instance, we should ask questions such as:

- **AMI** - What operating system and baseline should the server start with?
- **Instance Type** - How much CPU and memory does the workload require?
- **Storage** - How much capacity, IOPS, and throughput does the workload need?
- **VPC/Subnet** - Where should the server be deployed?
- **Public IP** - Does this workload really need to be directly reachable from the Internet?
- **Security Group** - Which resources should be allowed to communicate with the server?
- **IAM Role** - Which AWS services does the server need permission to access?

### CloudOps Hub V1 Decision

| Configuration | Decision | Reason |
|---|---|---|
| AMI | Amazon Linux 2023 | Linux-based environment suitable for the PostgreSQL learning workload |
| Instance Type | `t3.micro` | Small, cost-conscious instance suitable for the initial V1 workload |
| Storage | `gp3` | General-purpose persistent SSD storage |
| VPC | `cloudops-hub-vpc` | Keeps resources inside the dedicated CloudOps Hub network |
| Subnet | `cloudops-db-subnet` | Database belongs in the private DB layer |
| Public IPv4 | Disabled | Database does not require direct Internet exposure |
| Security Group | `cloudops-db-sg` | Controls network access to the database |
| PostgreSQL Port | `5432` from `cloudops-app-sg` | Only the Application layer should communicate with PostgreSQL |
| Administration | AWS Systems Manager Session Manager | Allows administration without exposing SSH |
| IAM Role | `cloudops-db-ec2-role` | Provides required Systems Manager permissions |

> **Don't choose EC2 settings because they are defaults. Choose them because they satisfy the workload requirements.**

---

## 3. Private Administrative Access

### The Problem

We do not want our database server to be directly exposed to the Internet.

Therefore, the PostgreSQL EC2 instance is deployed in a private subnet without a public IP address.

However, administrators still need a secure way to access the server to perform tasks such as:

- Installing and configuring PostgreSQL
- Managing the database service
- Updating configuration files
- Checking logs
- Installing packages and updates
- Troubleshooting issues

Making the database public and opening SSH port `22` just for administrative convenience would unnecessarily increase the attack surface.

### What I Learned

Private servers still require a secure administrative access strategy.

One option is to deploy a **Bastion Host** in a public subnet. Administrators can connect to the Bastion Host first and then access the private database server.

Another option is **AWS Systems Manager Session Manager**, which allows us to manage the EC2 instance without assigning a public IP address or opening inbound SSH port `22`.

For CloudOps Hub V1, we selected **AWS Systems Manager Session Manager**.

The EC2 instance uses the `cloudops-db-ec2-role` IAM role with the required Systems Manager permissions instead of storing long-lived AWS credentials on the server.

Since the database subnet is private, the EC2 instance also requires an outbound network path to communicate with Systems Manager service endpoints.

We considered using VPC Interface Endpoints for private connectivity to AWS services.

For V1, we chose a **NAT Gateway** to provide the required outbound connectivity while keeping the database EC2 instance private.

### Administrative Path

```text
Administrator
      │
      ▼
AWS Systems Manager
      │
      ▼
Private DB EC2
cloudops-db-01

Public IP: No
Inbound SSH :22: No
Bastion Host: No
```

### Outbound Path

```text
Private DB EC2
      │
      ▼
DB Route Table
      │
      ▼
NAT Gateway
(Public Subnet)
      │
      ▼
Internet Gateway
      │
      ▼
AWS Public Service Endpoints / Internet
```

> **Keeping a server private does not mean administrators cannot manage it. It means administration should happen through a controlled management path rather than exposing the workload publicly.**

---

## 4. PostgreSQL Installation

### The Problem

After provisioning the EC2 instance, we needed to install PostgreSQL.

Instead of copying an installation command from an external tutorial, we first wanted to understand which PostgreSQL packages were available in the Amazon Linux 2023 repositories.

### What I Learned

- Package availability depends on the operating system and configured repositories.
- Before installing software, it is useful to inspect the packages available on the system.
- Installing PostgreSQL software does not automatically mean that a PostgreSQL database is ready to use.
- PostgreSQL installation, database initialization, and service startup are separate activities.

### Implementation

Search for PostgreSQL packages:

```bash
dnf search postgresql
```

For CloudOps Hub V1, PostgreSQL 18 was selected.

Install the PostgreSQL client and server packages:

```bash
sudo dnf install -y postgresql18 postgresql18-server
```

Verify the installation:

```bash
psql --version
```

Output during implementation:

```text
psql (PostgreSQL) 18.4
```

At this point, PostgreSQL software was installed, but the database cluster had not yet been initialized.

```text
Software Installed
       ≠
Database Ready
```

---

## 5. Database Cluster Initialization

### The Problem

Installing the PostgreSQL packages provides the database software, but a PostgreSQL database cluster still needs to be initialized before the database server can operate.

### What I Learned

PostgreSQL separates software installation from database initialization.

```text
Install PostgreSQL
       │
       ▼
PostgreSQL binaries available
       │
       ▼
Initialize database cluster
       │
       ▼
Data directory created
       │
       ▼
PostgreSQL ready to start
```

In PostgreSQL terminology, a database cluster is a collection of databases managed by a PostgreSQL server instance.

### Inspecting the Installation

Before initializing the database, we inspected the tools installed by the PostgreSQL server package:

```bash
rpm -ql postgresql18-server | grep -E 'postgresql-setup|initdb|systemd'
```

We inspected the available PostgreSQL systemd services:

```bash
systemctl list-unit-files | grep postgresql
```

We then checked the supported initialization syntax:

```bash
sudo postgresql-setup --help
```

### Initialize PostgreSQL

```bash
sudo postgresql-setup --initdb
```

The database cluster was initialized under:

```text
/var/lib/pgsql/data
```

Inspect the data directory:

```bash
sudo ls -la /var/lib/pgsql/data
```

Important files and directories included:

```text
PG_VERSION
postgresql.conf
pg_hba.conf
base/
global/
pg_wal/
```

### Important Configuration Files

#### `postgresql.conf`

The main PostgreSQL server configuration file.

#### `pg_hba.conf`

Controls client authentication, including who can connect, from where, and which authentication method should be used.

#### `PG_VERSION`

Identifies the PostgreSQL major version associated with the data directory.

> **Installing PostgreSQL gives us the software. Initializing PostgreSQL creates the database environment that the software will manage.**

---

## 6. PostgreSQL Service Management

### The Problem

Initializing PostgreSQL does not automatically mean that the database server is running.

The PostgreSQL service needs to be started and configured to start automatically when the EC2 instance reboots.

### Implementation

Start PostgreSQL:

```bash
sudo systemctl start postgresql
```

Check the service:

```bash
sudo systemctl status postgresql --no-pager
```

Enable PostgreSQL during system startup:

```bash
sudo systemctl enable postgresql
```

Validate the service:

```bash
sudo systemctl is-enabled postgresql
sudo systemctl is-active postgresql
```

Expected result:

```text
enabled
active
```

### Validate PostgreSQL

Connect using the PostgreSQL administrative account:

```bash
sudo -u postgres psql
```

Verify the version:

```sql
SELECT version();
```

Inspect the databases:

```sql
\l
```

The initialization process created the default databases:

```text
postgres
template0
template1
```

### What I Learned

Linux service management and database management are separate concerns.

`systemctl` can tell us whether the PostgreSQL process is running, but we should also connect to PostgreSQL itself to confirm that the database engine is functioning correctly.

> **Do not stop validation at "the service is running." Validate that the application behind the service actually works.**

---

## 7. Database and Application User

### The Problem

Using the PostgreSQL `postgres` superuser from the CloudOps Hub application would provide significantly more privileges than the application requires.

The application should have its own database identity.

### Implementation

Create the CloudOps Hub database:

```sql
CREATE DATABASE cloudops_hub;
```

Create the application user:

```sql
CREATE USER cloudops_app WITH PASSWORD '<STRONG_PASSWORD>';
```

> **Never commit the actual database password to Git.**

Initially grant database privileges:

```sql
GRANT ALL PRIVILEGES ON DATABASE cloudops_hub TO cloudops_app;
```

Make the application identity the owner of its database:

```sql
ALTER DATABASE cloudops_hub OWNER TO cloudops_app;
```

Verify:

```sql
\l cloudops_hub
```

### Responsibility Model

```text
postgres
   │
   └── Database administration / superuser

cloudops_app
   │
   └── CloudOps Hub application identity
             │
             ▼
       cloudops_hub
```

### What I Learned

Applications should not use database administrator accounts simply because doing so is easier.

The application should receive the permissions required for its workload while administrative privileges remain separate.

> **Least privilege applies inside the database just as it applies to IAM and network security.**

---

## 8. PostgreSQL Authentication

### The Problem

When we initially attempted to connect using the application user:

```bash
psql -U cloudops_app -d cloudops_hub -h localhost -W
```

the connection failed:

```text
FATAL: Ident authentication failed for user "cloudops_app"
```

Instead of assuming the password was incorrect, we investigated PostgreSQL authentication.

### Troubleshooting

Inspect active authentication rules:

```bash
sudo grep -vE '^\s*#|^\s*$' /var/lib/pgsql/data/pg_hba.conf
```

The relevant configuration was:

```text
local   all   all                     peer
host    all   all   127.0.0.1/32     ident
host    all   all   ::1/128          ident
```

The connection used:

```text
localhost
    │
    ▼
127.0.0.1
    │
    ▼
host rule
    │
    ▼
ident authentication
```

Therefore PostgreSQL attempted `ident` authentication instead of password authentication.

### Solution

Before changing the configuration, create a backup:

```bash
sudo cp /var/lib/pgsql/data/pg_hba.conf \
/var/lib/pgsql/data/pg_hba.conf.bak
```

Change:

```text
host    all    all    127.0.0.1/32    ident
host    all    all    ::1/128         ident
```

to:

```text
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

Reload PostgreSQL:

```bash
sudo systemctl reload postgresql
```

Retry the application connection:

```bash
psql -U cloudops_app -d cloudops_hub -h localhost -W
```

The connection succeeded.

### What I Learned

`pg_hba.conf` is an important PostgreSQL connection gatekeeper.

It helps determine:

- Which database can be accessed
- Which database user can connect
- Where the connection can originate
- Which authentication mechanism must be used

The troubleshooting process was:

```text
Connection Failure
       │
       ▼
Read the actual error
       │
       ▼
Inspect pg_hba.conf
       │
       ▼
Identify matching rule
       │
       ▼
Understand authentication method
       │
       ▼
Modify configuration
       │
       ▼
Reload PostgreSQL
       │
       ▼
Retest
       │
       ▼
Connection Successful
```

> **An authentication failure does not automatically mean the password is wrong. Understand which authentication rule is actually being applied.**

---

## 9. Application Schema

### The Problem

A running database alone does not provide useful application functionality.

CloudOps Hub needs a schema that represents the information the application will manage.

### Initial Schema

For V1, we created an `applications` table:

```sql
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    owner_team VARCHAR(100) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Verify the table:

```sql
\dt
```

Inspect the table structure:

```sql
\d applications
```

### What I Learned

Database design should begin with understanding what information the application needs to store rather than creating tables randomly.

The V1 schema is intentionally small and can evolve as CloudOps Hub application requirements become clearer.

---

## 10. Database Validation

### The Problem

Creating a table does not prove that the application database identity can actually use it.

We needed to validate a basic database operation end to end.

### Validation

Insert a test application:

```sql
INSERT INTO applications (
    name,
    description,
    owner_team,
    environment,
    status
)
VALUES (
    'Payment Service',
    'Processes customer payments',
    'Payments Team',
    'Production',
    'Healthy'
);
```

Query the table:

```sql
SELECT * FROM applications;
```

The record was successfully returned.

This validated:

```text
PostgreSQL
     │
     ▼
cloudops_hub
     │
     ▼
cloudops_app
     │
     ▼
Authentication
     │
     ▼
applications table
     │
     ▼
INSERT
     │
     ▼
SELECT
     │
     ▼
Successful Result
```

### What I Learned

Infrastructure creation is not the completion criteria.

The database layer should be tested from the perspective of the identity that will actually use it.

> **Build → Configure → Validate. Do not assume successful creation means successful operation.**

---

## 11. Architecture Decisions

The following decisions were intentionally made for CloudOps Hub V1.

| Decision | Reason |
|---|---|
| PostgreSQL on EC2 | Learn the operational responsibilities of self-managing a database |
| Amazon Linux 2023 | Linux environment for the V1 database workload |
| `t3.micro` | Small and cost-conscious starting point |
| `gp3` EBS | General-purpose persistent storage |
| Private DB subnet | Database should not be directly exposed to the Internet |
| No public IPv4 | No requirement for direct Internet access |
| Session Manager | Administrative access without inbound SSH |
| NAT Gateway | Outbound connectivity for Systems Manager and package access |
| Dedicated `cloudops_app` user | Application should not use the PostgreSQL superuser |
| SCRAM authentication | Password-based authentication for application connections |
| `cloudops-db-sg` | Network-level protection of PostgreSQL |
| Port `5432` from App SG only | Only the Application layer should reach PostgreSQL |

---

## 12. Current Limitations and Future Improvements

CloudOps Hub V1 is intentionally simple.

The goal is to understand and validate the database layer before introducing production-level complexity.

### 12.1 Single Database Server

#### Current Limitation

The current PostgreSQL deployment uses a single EC2 instance:

```text
cloudops-db-01
```

If the instance or Availability Zone becomes unavailable, the database may become unavailable.

#### Future Improvement

Evaluate database redundancy and high-availability options after the V1 architecture is operational.

---

### 12.2 Manual Database Administration

#### Current Limitation

PostgreSQL installation, initialization, configuration, patching, monitoring, backups, upgrades, and recovery remain our responsibility.

This is intentional for V1.

#### Future Improvement

After gaining experience operating PostgreSQL ourselves, evaluate Amazon RDS for PostgreSQL and compare:

- Operational responsibilities
- Availability
- Backup management
- Patching
- Monitoring
- Recovery
- Cost
- Control
- Operational complexity

---

### 12.3 Backup and Recovery

#### Current Limitation

A complete database backup and recovery strategy has not yet been implemented.

#### Future Improvement

Design, implement, and validate database backup and recovery procedures.

A backup should not be considered successful simply because it was created. Recovery should also be tested.

---

### 12.4 Monitoring

#### Current Limitation

PostgreSQL-specific monitoring and alerting have not yet been implemented.

#### Future Improvement

Introduce infrastructure and database observability after the basic application path is operational.

---

### 12.5 Remote Application Connectivity

Private Application → Database connectivity has now been implemented and validated.

The Application EC2 instance connects to PostgreSQL over the private VPC network:

```text
cloudops-app-01
       │
       │ TCP 5432
       ▼
cloudops-db-sg
       │
       ▼
cloudops-db-01
       │
       ▼
PostgreSQL
```

PostgreSQL was configured to listen for remote connections, and `pg_hba.conf` allows the `cloudops_app` identity to access `cloudops_hub` from the Application subnet using SCRAM authentication.

The connection was validated using both the PostgreSQL client and the CloudOps Hub Flask backend.

The backend successfully performed both SELECT and INSERT operations against the `applications` table.

---

## 13. Command Reference

### Package Discovery

```bash
dnf search postgresql
```

### PostgreSQL Installation

```bash
sudo dnf install -y postgresql18 postgresql18-server
```

Verify:

```bash
psql --version
```

---

### Inspect PostgreSQL Package

```bash
rpm -ql postgresql18-server | grep -E 'postgresql-setup|initdb|systemd'
```

```bash
systemctl list-unit-files | grep postgresql
```

```bash
sudo postgresql-setup --help
```

---

### Initialize PostgreSQL

```bash
sudo postgresql-setup --initdb
```

Inspect the data directory:

```bash
sudo ls -la /var/lib/pgsql/data
```

---

### PostgreSQL Service Management

Start:

```bash
sudo systemctl start postgresql
```

Enable:

```bash
sudo systemctl enable postgresql
```

Check status:

```bash
sudo systemctl status postgresql --no-pager
```

Validate:

```bash
sudo systemctl is-enabled postgresql
sudo systemctl is-active postgresql
```

Reload configuration:

```bash
sudo systemctl reload postgresql
```

---

### PostgreSQL Administrative Access

```bash
sudo -u postgres psql
```

Useful commands:

```sql
SELECT version();

\l

\du

\dt

\d applications

\conninfo

\q
```

---

### Application Database Connection

```bash
psql -U cloudops_app -d cloudops_hub -h localhost -W
```

Validate identity:

```sql
SELECT current_user;
```

Validate database:

```sql
SELECT current_database();
```

---

### Inspect PostgreSQL Authentication

```bash
sudo grep -vE '^\s*#|^\s*$' /var/lib/pgsql/data/pg_hba.conf
```

Backup the configuration:

```bash
sudo cp /var/lib/pgsql/data/pg_hba.conf \
/var/lib/pgsql/data/pg_hba.conf.bak
```

---

## Database Foundation Status

At this stage, CloudOps Hub V1 has:

- [x] Private PostgreSQL EC2 instance
- [x] Amazon Linux 2023
- [x] PostgreSQL 18.4 installed
- [x] PostgreSQL database cluster initialized
- [x] PostgreSQL service running
- [x] Automatic service startup enabled
- [x] Dedicated `cloudops_hub` database
- [x] Dedicated `cloudops_app` application identity
- [x] SCRAM password authentication
- [x] Initial `applications` table
- [x] INSERT validation
- [x] SELECT validation
- [x] Systems Manager administrative access
- [x] No public IPv4 on the DB server
- [x] No inbound SSH required
- [ ] Private App-to-DB connectivity
- [ ] Database backup and recovery
- [ ] Database monitoring
- [ ] High availability

---

## Next Milestone

The next CloudOps Hub milestone is:

> **Private Application Layer → PostgreSQL Connectivity**

The Application server will be deployed in the private Application subnet and will communicate with PostgreSQL over the VPC using TCP port `5432`.

The connection will need to pass through multiple controls:

```text
Application
     │
     ▼
App EC2
     │
     ▼
VPC Routing
     │
     ▼
DB Security Group
     │
     ▼
PostgreSQL Listener
     │
     ▼
pg_hba.conf
     │
     ▼
Database Authentication
     │
     ▼
cloudops_hub
```

This will allow us to validate the first real communication path between two CloudOps Hub application tiers.