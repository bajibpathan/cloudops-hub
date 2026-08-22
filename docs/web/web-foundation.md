# Web Layer Foundation

This document captures the design decisions, manual implementation, troubleshooting, and validation of the CloudOps Hub V1 Web Layer.

---

## 1. Why a Web Layer?

### The Problem

The CloudOps Hub Application Layer runs on a private EC2 instance.

Users should not communicate directly with the private Flask application server.

We need a controlled public entry point that can:

- Serve the CloudOps Hub frontend
- Accept HTTP requests from users
- Forward API requests to the private Application Layer
- Keep the Application and Database servers private

### What I Learned

A three-tier architecture separates responsibilities between the Web, Application, and Database layers.

For CloudOps Hub V1:

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

The Web Layer is responsible for user-facing traffic.

The Application Layer handles application logic.

The Database Layer stores application data.

> A user does not need direct network access to every component involved in serving their request.

---

## 2. V1 Web Architecture Decision

Two designs were considered.

### Option A - Public Web EC2

```text
Internet
   │
   ▼
Public Web EC2
   │
   ▼
Private App EC2
   │
   ▼
Private DB EC2
```

### Option B - Application Load Balancer

```text
Internet
   │
   ▼
Application Load Balancer
   │
   ▼
Private Web EC2
   │
   ▼
Private App EC2
   │
   ▼
Private DB EC2
```

Option B provides a better foundation for high availability and production-oriented traffic management.

However, an internet-facing Application Load Balancer also introduces additional infrastructure, including multiple public subnets across Availability Zones, target groups, health checks, and additional security configuration.

For Manual V1, Option A was selected.

### Why?

The objective of V1 is to understand and manually validate the complete three-tier request flow before introducing additional infrastructure abstractions.

The Application Load Balancer design is intentionally deferred to a future architecture evolution.

> V1 asks: "Can I manually build and understand the complete three-tier application?"

> A future version can ask: "How do I make the architecture more resilient and production-ready?"

---

## 3. Web EC2 Design

The Web server was manually provisioned with the following design:

| Configuration | Decision |
|---|---|
| Instance | `cloudops-web-01` |
| Operating System | Amazon Linux 2023 |
| Instance Type | `t3.micro` |
| VPC | `cloudops-hub-vpc` |
| Subnet | `cloudops-web-subnet` |
| Public IPv4 | Enabled |
| Security Group | `cloudops-web-sg` |
| Administration | AWS Systems Manager Session Manager |
| SSH | Not exposed |
| Web Server | Nginx |
| Public Port | TCP 80 |

The Web EC2 instance is the only application tier directly reachable from the Internet in Manual V1.

The Application and Database EC2 instances remain private.

---

## 4. Security Group Flow

The V1 security model follows the application communication path.

```text
Internet
   │
   │ TCP 80
   ▼
cloudops-web-sg
   │
   │ TCP 5000
   ▼
cloudops-app-sg
   │
   │ TCP 5432
   ▼
cloudops-db-sg
```

### Web Layer

`cloudops-web-sg` allows:

```text
Internet → TCP 80
```

SSH is not exposed.

Administration is performed using AWS Systems Manager Session Manager.

### Application Layer

`cloudops-app-sg` allows application traffic from:

```text
cloudops-web-sg → TCP 5000
```

The Flask backend is not exposed directly to the Internet.

### Database Layer

`cloudops-db-sg` allows PostgreSQL traffic from:

```text
cloudops-app-sg → TCP 5432
```

### What I Learned

Security Groups can represent application relationships instead of depending on individual EC2 IP addresses.

The intended communication path becomes:

```text
Internet
   ↓
Web Security Group
   ↓
Application Security Group
   ↓
Database Security Group
```

> Allow communication based on which component needs access, not simply which ports happen to be in use.

---

## 5. Validate Web-to-App Connectivity First

Before installing or configuring the Web server, connectivity from the Web EC2 instance to the private Application Layer was tested.

From `cloudops-web-01`:

```bash
curl http://<APP_PRIVATE_IP>:5000/health
```

The Flask health endpoint responded successfully.

The database-backed API was also tested:

```bash
curl http://<APP_PRIVATE_IP>:5000/api/applications
```

This validated:

```text
Web EC2
   │
   ▼
Private VPC Network
   │
   ▼
App Security Group
   │
   ▼
Flask :5000
   │
   ▼
PostgreSQL
```

### What I Learned

Validate dependencies independently before introducing another component.

If Web-to-App connectivity already works before Nginx is introduced, later failures can be narrowed to the Web server configuration instead of troubleshooting the entire architecture.

---

## 6. Nginx Installation

Nginx was selected as the Web server for Manual V1.

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

The default Nginx page was tested locally:

```bash
curl http://localhost
```

Public connectivity was also validated using the Web EC2 public IPv4 address.

This proved:

```text
Internet
   │
   ▼
Internet Gateway
   │
   ▼
Public Web Subnet
   │
   ▼
cloudops-web-sg :80
   │
   ▼
Nginx
```

---

## 7. CloudOps Hub Frontend

The V1 frontend is intentionally small.

Repository structure:

```text
app/frontend/
├── index.html
├── styles.css
└── app.js
```

The frontend currently provides:

- CloudOps Hub landing page
- Application list
- Add Application form
- Refresh functionality

The frontend communicates with the backend using:

```javascript
fetch("/api/applications")
```

It does not use the private App EC2 address directly.

This is intentional.

The browser communicates only with the Web Layer.

---

## 8. Frontend Deployment

The CloudOps Hub Web root was created:

```bash
sudo mkdir -p /var/www/cloudops-hub
```

The frontend files were deployed to:

```text
/var/www/cloudops-hub/
├── index.html
├── styles.css
└── app.js
```

Nginx was configured to use:

```text
/var/www/cloudops-hub
```

as the CloudOps Hub document root.

---

## 9. Nginx Reverse Proxy

Nginx performs two responsibilities in Manual V1:

```text
/
│
└── Serve static frontend files

/api/*
│
└── Forward requests to private Flask backend
```

The CloudOps Hub Nginx configuration is stored at:

```text
/etc/nginx/conf.d/cloudops-hub.conf
```

Example:

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

The configuration was validated using:

```bash
sudo nginx -t
```

Nginx was then reloaded:

```bash
sudo systemctl reload nginx
```

---

## 10. Why the Browser Does Not Call Flask Directly

The frontend uses:

```javascript
fetch("/api/applications")
```

instead of:

```text
http://<APP_PRIVATE_IP>:5000/api/applications
```

The resulting request path is:

```text
Browser
   │
   │ /api/applications
   ▼
Nginx :80
   │
   │ Reverse Proxy
   ▼
Flask :5000
```

This keeps the Application EC2 instance private.

The user's browser does not need to know:

- The App EC2 private IP
- The Flask port
- The Database address
- The Database credentials

### What I Learned

A reverse proxy creates a controlled boundary between the public Web Layer and the private Application Layer.

---

## 11. Nginx Default Server Troubleshooting

### The Problem

After creating the CloudOps Hub Nginx configuration, requesting:

```bash
curl http://localhost/
```

still returned the default Nginx page.

At another point, Nginx returned the Amazon Linux default 404 page.

The configuration syntax itself was valid:

```bash
sudo nginx -t
```

returned:

```text
syntax is ok
test is successful
```

### Investigation

The active configuration was inspected using:

```bash
sudo nginx -T | grep -nE "server_name|root|listen 80"
```

This showed multiple server blocks listening on TCP 80.

The Amazon Linux Nginx configuration still contained its default server block while the CloudOps Hub configuration also listened on port 80.

At one point Nginx reported:

```text
conflicting server name "_" on 0.0.0.0:80, ignored
```

Commenting only:

```nginx
server_name _;
root /usr/share/nginx/html;
```

did not disable the original server block.

The surrounding:

```nginx
server {
    listen 80;
    ...
}
```

was still active.

### Solution

The CloudOps Hub server block was explicitly configured as the default:

```nginx
listen 80 default_server;
listen [::]:80 default_server;
```

The active configuration was then verified:

```bash
sudo nginx -T | grep -nE "listen.*80|root /var/www"
```

The output confirmed:

```text
listen 80 default_server;
listen [::]:80 default_server;
root /var/www/cloudops-hub;
```

After reloading Nginx:

```bash
sudo systemctl reload nginx
```

the CloudOps Hub frontend was successfully returned from:

```bash
curl http://localhost/
```

and from the browser.

### What I Learned

There is an important difference between:

```text
Configuration syntax is valid
```

and:

```text
Configuration behavior is correct
```

`nginx -t` validates configuration syntax but does not prove that the intended server block will handle a particular request.

I also learned that commenting individual directives such as `root` or `server_name` does not disable the surrounding `server` block.

> Troubleshooting configuration requires understanding which configuration is actually active, not only whether the configuration file passes syntax validation.

---

## 12. Reverse Proxy Validation

After configuring Nginx, the API path was tested through the Web Layer:

```bash
curl http://localhost/api/applications
```

The request successfully returned application data from PostgreSQL.

This proved:

```text
curl
  │
  ▼
Nginx :80
  │
  │ /api/applications
  ▼
Reverse Proxy
  │
  ▼
Flask :5000
  │
  ▼
PostgreSQL :5432
```

---

## 13. Browser End-to-End Validation

The CloudOps Hub frontend was opened using the Web EC2 public IPv4 address.

The application list was successfully retrieved.

A new application was then created using the browser form.

The complete write path was:

```text
Browser
   │
   │ POST /api/applications
   ▼
Nginx :80
   │
   │ Reverse Proxy
   ▼
Flask :5000
   │
   ▼
Psycopg
   │
   ▼
PostgreSQL :5432
   │
   ▼
applications table
```

The new record was then verified directly in PostgreSQL.

This confirmed that the complete CloudOps Hub Manual V1 request path works end to end.

---

## 14. Current Security Model

Manual V1 currently follows these principles:

- Only the Web EC2 instance is Internet-facing
- Application EC2 has no public IPv4 address
- Database EC2 has no public IPv4 address
- SSH is not exposed
- Administration uses Systems Manager Session Manager
- Internet traffic reaches only Nginx on TCP 80
- Web-to-App communication uses TCP 5000
- App-to-DB communication uses TCP 5432
- The browser does not communicate directly with Flask
- The browser does not communicate directly with PostgreSQL
- Database credentials are not stored in frontend code

---

## 15. Known V1 Limitations

Manual V1 intentionally remains simple.

### HTTP Only

The Web Layer currently uses HTTP.

HTTPS/TLS is not implemented.

### Public Web EC2

The Web EC2 instance itself is directly Internet-facing.

A future version can introduce an Application Load Balancer.

### Single Web Server

Only one Web EC2 instance exists.

Failure of this instance makes the Web Layer unavailable.

### Single Application Server

Only one App EC2 instance exists.

### Single Database Server

Only one PostgreSQL EC2 instance exists.

### Private IP Configuration

The Nginx reverse-proxy configuration currently references the App EC2 private IP.

Recreating the App EC2 may require updating this value.

### No Authentication

The application does not currently provide user authentication or authorization.

### Limited Observability

Centralized application monitoring, metrics, tracing, dashboards, and alerting are not yet implemented.

These limitations are intentional and provide future engineering problems for later CloudOps Hub phases.

---

## 16. Manual V1 Status

The complete three-tier application has now been manually implemented and validated.

- [x] VPC networking
- [x] Public Web subnet
- [x] Private Application subnet
- [x] Private Database subnet
- [x] Security Group tier relationships
- [x] Database EC2
- [x] PostgreSQL
- [x] Database schema
- [x] Application EC2
- [x] Flask backend
- [x] App-to-DB connectivity
- [x] systemd backend management
- [x] Application process recovery
- [x] Web EC2
- [x] Nginx
- [x] Static frontend
- [x] Nginx reverse proxy
- [x] Web-to-App connectivity
- [x] Browser read operation
- [x] Browser write operation
- [x] Database verification
- [x] End-to-end three-tier validation

---

## 17. Completed V1 Request Flow

```text
                     Internet
                        │
                        ▼
                ┌────────────────┐
                │   Web Layer    │
                │                │
                │ Nginx :80      │
                │ Public EC2     │
                └───────┬────────┘
                        │
                        │ HTTP :5000
                        ▼
                ┌────────────────┐
                │ App Layer      │
                │                │
                │ Flask          │
                │ Private EC2    │
                │ systemd        │
                └───────┬────────┘
                        │
                        │ TCP :5432
                        ▼
                ┌────────────────┐
                │ Database Layer │
                │                │
                │ PostgreSQL     │
                │ Private EC2    │
                └────────────────┘
```

## Milestone

> **CloudOps Hub Manual V1 - Complete**

The project now has a manually deployed and validated three-tier application.

The manual implementation provides the baseline for future automation and architecture improvements.