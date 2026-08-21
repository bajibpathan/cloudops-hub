# ☁️ CloudOps Hub

> **A production-inspired cloud engineering project built from first principles.**

CloudOps Hub is a hands-on AWS project where I am learning to design, build, operate, troubleshoot, and gradually automate a cloud platform.

Instead of starting with tools and services, I start with the **engineering problem**, understand the principle behind it, build the solution manually, and introduce automation as the platform evolves.

---

## 🎯 Goal

The goal is not to memorize AWS services, but to understand **why they exist, what problems they solve, and what trade-offs they introduce.**

> **Learn the problem → Understand the principle → Design → Build → Validate → Troubleshoot → Automate → Improve**

---

## 🏗️ Architecture

![CloudOps Hub Target Architecture](docs/architecture/cloudops-hub-architecture.png)

CloudOps Hub follows a layered architecture with:

- Public Web Layer
- Private Application Layer
- Private Database Layer
- Multi-AZ design
- Controlled network access between layers
- Secure administrative access
- Observability and automation introduced incrementally

> The diagram represents the **target architecture**. Components are implemented gradually as the project evolves.

---

## 🚧 Project Progress

| Area | Status |
|---|---|
| Cloud Engineering Foundations | ✅ Completed |
| Network Foundation | ✅ Completed |
| Database Foundation | ✅ Implemented & Validated |
| App → Database Connectivity | ✅ Implemented & Validated |
| Application Layer | ✅ Implemented & Validated |
| Web Layer | 🔜 Next |
| Observability | ⏳ Planned |
| Automation / IaC | ⏳ Planned |
| CI/CD & Containers | ⏳ Planned |

---

## 🗄️ Current Milestone: Database Foundation

For V1, PostgreSQL was intentionally deployed on **Amazon EC2 instead of immediately using Amazon RDS**.

The purpose was to understand the operational responsibilities involved in managing a database ourselves.

### What was implemented

- Private Amazon Linux EC2 database server
- PostgreSQL 18
- AWS Systems Manager administrative access
- No public IP or inbound SSH
- Dedicated `cloudops_hub` database
- Dedicated `cloudops_app` identity
- SCRAM authentication
- Initial application schema
- INSERT and SELECT validation

This also provided hands-on experience with PostgreSQL installation, initialization, service management, authentication, permissions, and troubleshooting.

> **To appreciate a managed service, first understand the operational burden it removes.**

📖 [Database Foundation Documentation](docs/database/database-foundation.md)

---

## 📚 Documentation

Detailed implementation notes, commands, troubleshooting, and engineering decisions are maintained separately.

### Engineering Principles

- [Cloud Engineering Foundations](docs/engineering-principles/01-cloud-engineering-foundations.md)
- [Automation and Safe Delivery](docs/engineering-principles/02-automation-and-safe-delivery.md)

### Infrastructure

- [VPC Networking Foundation](docs/networking/vpc-foundation.md)
- [Database Foundation](docs/database/database-foundation.md)
- [Application Layer Foundation](docs/application/application-foundation.md)

Additional documentation will be added as each CloudOps Hub milestone is completed.

---

## 💰 Learning Environment & Cost

CloudOps Hub is a learning environment, so runtime infrastructure does not need to remain active when it is not being used.

```text
Build → Learn → Validate → Document → Destroy → Recreate
```

This reduces unnecessary cloud cost and creates a natural reason to introduce Infrastructure as Code and configuration automation later.

---

## 🔜 Next

The next milestone is:

### Web Layer → Application Layer Connectivity

```text
User
  ↓
Web Layer
  ↓
Application Layer
  ↓
PostgreSQL

---

## 🧠 Engineering Philosophy

CloudOps Hub follows one principle throughout the project:

> **Don't learn a tool first. Understand the problem first, solve it manually, experience the operational pain, and then automate with purpose.**

The objective is not to deploy as many AWS services as possible.

It is to learn how to **think, build, troubleshoot, and make trade-offs like a Cloud Engineer.**