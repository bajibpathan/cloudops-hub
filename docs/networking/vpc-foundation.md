# VPC Networking Foundation

This document captures the networking concepts, design decisions, and manual implementation used to build the CloudOps Hub V1 network foundation.

---

## 1. Virtual Private Cloud (VPC)

### The Problem

Creating CloudOps Hub resources in the default VPC may not be ideal because we want more control over how our network is designed and how different application layers communicate.

The Web, Application, and Database layers have different connectivity and security requirements. For example, the Web layer may require internet connectivity, while the Application and Database layers should remain private.

We also need to plan our IP address range carefully. If CloudOps Hub needs to connect with other VPCs or corporate networks in the future, overlapping IP address ranges may create connectivity challenges.

### What I Learned

- We can create a logically isolated network for CloudOps Hub using an Amazon VPC (Virtual Private Cloud).

- While creating the VPC, we define an IP address range using CIDR notation. This address space can then be divided into smaller networks called subnets where we can deploy our resources.

- For CloudOps Hub, we created a dedicated VPC with the CIDR range:

  `10.0.0.0/16`

- A `/16` network has 16 bits available for host addresses, which provides 65,536 total IPv4 addresses.

- Having our own VPC gives us more control over IP addressing, network segmentation, routing, connectivity, and security.

---

## 2. Subnets

### The Problem

A VPC is a broader network, and deploying all resources without separating the network may make it difficult to manage the different connectivity requirements of the Web, Application, and Database layers.

For example, we want the Web layer to have internet connectivity, while the Application and Database layers should remain private.

### What I Learned

- We can divide the larger VPC network into smaller networks called subnets. This helps us separate resources based on their connectivity and routing requirements.

- For CloudOps Hub, we created separate subnets for each application layer:

  - Web Subnet: `10.0.1.0/24`
  - Application Subnet: `10.0.2.0/24`
  - Database Subnet: `10.0.3.0/24`

- Each `/24` subnet provides 256 total IPv4 addresses. AWS reserves five addresses in each subnet, leaving 251 addresses available for resources.

- Each subnet belongs to a single Availability Zone.

- Creating a subnet and naming it "public" or "private" does not actually make it public or private. The routing configuration determines whether the subnet has a direct path to the internet.

---

## 3. Availability Zones

### The Problem

Deploying all application resources in a single Availability Zone creates a single failure domain.

If that Availability Zone becomes unavailable, the entire application may become inaccessible to users, resulting in customer and business impact.

### What I Learned

- We can improve application availability by distributing resources across multiple Availability Zones instead of depending on a single AZ.

- Simply deploying resources in multiple Availability Zones does not automatically make an application highly available.

- We also need mechanisms such as load balancing, health checks, failover, and database redundancy.

- Database redundancy requires additional consideration because databases contain state. Simply creating another database server in another Availability Zone does not guarantee data consistency.

### CloudOps Hub V1 Decision

For the initial manual deployment, CloudOps Hub uses a single Availability Zone.

This is intentional so that we can understand and validate each component before introducing high-availability complexity.

We accept the Availability Zone-level failure risk in V1.

A future version will evolve the architecture across multiple Availability Zones.

---

## 4. Route Tables

### The Problem

When we create a VPC, AWS automatically creates a main route table with a local route for communication within the VPC CIDR.

However, the Web, Application, and Database layers have different routing requirements.

For example:

- The Web layer needs direct internet routing.
- The Application layer should remain private.
- The Database layer should remain private but currently requires controlled outbound connectivity for administration and software installation.

Using the same routing policy for every layer would provide connectivity that some workloads do not require.

### What I Learned

- Route tables define where network traffic should be directed based on the destination.

- AWS automatically creates a local route for the VPC CIDR:

  `10.0.0.0/16 → local`

- This provides a routing path between resources inside the VPC, subject to network security controls.

- We created dedicated route tables:

  - `cloudops-public-rt` → Web subnet
  - `cloudops-app-rt` → Application subnet
  - `cloudops-db-rt` → Database subnet

### Current Routing

The Web route table contains:

`0.0.0.0/0 → Internet Gateway`

The Database route table contains:

`0.0.0.0/0 → NAT Gateway`

The Application route table currently contains only:

`10.0.0.0/16 → local`

This gives each application layer an independent routing policy.

> **Different connectivity requirements should have different routing policies.**

---

## 5. Internet Gateway

### The Problem

Creating an Internet Gateway and attaching it to the VPC alone does not provide internet connectivity to resources.

A subnet must also have the appropriate routing configuration.

### What I Learned

- An Internet Gateway (IGW) provides a communication path between a VPC and the Internet.

- We created:

  `cloudops-hub-igw`

- The Internet Gateway was attached to:

  `cloudops-hub-vpc`

- The Web subnet's route table contains:

  `0.0.0.0/0 → cloudops-hub-igw`

- The Application and Database subnets do not have a direct route to the Internet Gateway.

- Even when a subnet has an Internet Gateway route, an EC2 instance still requires appropriate public addressing and security rules for direct internet communication.

> **Attaching an Internet Gateway to a VPC does not automatically make every resource in the VPC public.**

---

## 6. NAT Gateway

### Implementation Status

**Implemented for the Database subnet during the Database Foundation milestone.**

### The Original Problem

Initially, CloudOps Hub did not have a requirement for private resources to access the Internet.

Because a NAT Gateway introduces additional infrastructure and cost, we deliberately decided not to deploy one without a requirement.

That changed when we started building the Database layer.

The PostgreSQL EC2 instance was intentionally deployed:

- In the private Database subnet
- Without a public IPv4 address
- Without inbound SSH access

However, the server needed outbound connectivity for activities such as:

- Installing PostgreSQL packages
- Downloading operating system packages and updates
- Communicating with AWS services required for administration

The requirement became:

```text
DB EC2 → Outbound Connectivity      ✅
Internet → DB EC2 Directly          ❌
Public IPv4 on DB EC2               ❌
```

### What I Learned

A public NAT Gateway can provide outbound connectivity for resources in a private subnet without making those resources directly public.

The NAT Gateway is placed in a public subnet with connectivity to the Internet Gateway.

The private subnet then routes internet-bound traffic to the NAT Gateway.

### CloudOps Hub V1 Implementation

A NAT Gateway was created in the Web/public subnet.

The Database route table was updated with:

```text
0.0.0.0/0 → NAT Gateway
```

The resulting outbound path is:

```text
Private DB EC2
      │
      ▼
cloudops-db-rt
      │
      ▼
NAT Gateway
      │
      ▼
Internet Gateway
      │
      ▼
AWS Public Endpoints / Internet
```

The database server still:

- Has no public IPv4 address
- Has no direct route to the Internet Gateway
- Does not accept unsolicited inbound internet connections

### Why This Decision Changed

The original decision was:

> **Do not introduce NAT without a requirement.**

We followed that principle.

Later, a real requirement appeared during the Database Foundation implementation.

At that point, NAT became a solution to an actual problem rather than another AWS service added to the architecture without justification.

This reinforced an important engineering principle:

> **Architecture decisions are not permanent. When requirements change, revisit the decision and document why it changed.**

### Cost Consideration

NAT Gateway introduces ongoing cost.

Because CloudOps Hub is currently a learning environment, the NAT Gateway does not need to remain deployed while the environment is inactive.

It can be deleted when not required and recreated when learning continues.

This trade-off will later give us a reason to explore automation and potentially alternative private connectivity designs.

---

## 7. Security Groups

### The Problem

A valid network route does not mean every resource should be allowed to communicate with every other resource.

Each application layer should accept only the traffic required for its function.

### What I Learned

Security Groups act as virtual firewalls for AWS resources.

For CloudOps Hub, we created:

- `cloudops-web-sg`
- `cloudops-app-sg`
- `cloudops-db-sg`

The intended communication is:

```text
Internet
   │
   │ HTTP/HTTPS
   ▼
Web
   │
   │ Application Port
   ▼
Application
   │
   │ PostgreSQL 5432
   ▼
Database
```

Instead of allowing the entire VPC CIDR to access PostgreSQL, the Database Security Group can reference:

`cloudops-app-sg`

as the allowed source on port:

`5432`

This means the security policy represents the application architecture instead of depending on individual server IP addresses.

Security Groups are stateful. Response traffic for an allowed connection is automatically permitted.

Security Groups contain allow rules. Traffic that is not allowed by the applicable rules is not permitted.

> **Network membership does not imply network trust.**

---

## 8. Network ACLs (NACLs)

### Implementation Status

**Concept learned. Custom Network ACLs are not implemented in CloudOps Hub V1.**

### The Problem

Some architectures may require traffic to be controlled for an entire subnet rather than only individual resources.

For example, there may be a requirement to explicitly deny traffic from a particular network range.

### What I Learned

- Network ACLs provide traffic controls at the subnet level.

- NACLs support both **Allow** and **Deny** rules.

- NACLs are **stateless**, so inbound and outbound traffic are evaluated separately.

- Rules are evaluated in rule-number order starting with the lowest number.

- AWS created a default Network ACL when the CloudOps Hub VPC was created.

### CloudOps Hub V1 Decision

We have not created custom NACLs because the current architecture does not have a requirement for subnet-level Allow/Deny controls.

Security Groups currently provide the workload-level controls we require.

Custom NACLs will be introduced only when a requirement justifies them.

---

## 9. DNS

### Implementation Status

**Concept learned. Custom internal DNS is not implemented in CloudOps Hub V1.**

### The Problem

Hard-coding infrastructure IP addresses into application configuration creates unnecessary coupling.

If an EC2 instance is replaced, its private IP address may change.

For example:

```text
DB_HOST=10.0.3.25
```

could become invalid after the Database server is recreated.

### What I Learned

DNS allows applications to identify services using stable names instead of depending directly on infrastructure IP addresses.

For example, we could eventually use:

```text
DB_HOST=db.cloudopshub.internal
```

If the underlying infrastructure changes, the DNS record can be updated while the application continues using the same service name.

### CloudOps Hub V1 Decision

Custom internal DNS has not yet been implemented.

We will introduce it when the application architecture creates a real requirement for stable service discovery.

---

## 10. CloudOps Hub V1 Network Implementation

The CloudOps Hub V1 network was manually created in AWS.

The goal is to understand the networking components and their relationships before introducing infrastructure automation.

### VPC

| Resource | Configuration |
|---|---|
| VPC | `cloudops-hub-vpc` |
| IPv4 CIDR | `10.0.0.0/16` |

### Subnets

| Subnet | CIDR | Purpose |
|---|---|---|
| `cloudops-web-subnet` | `10.0.1.0/24` | Web/Public layer |
| `cloudops-app-subnet` | `10.0.2.0/24` | Private Application layer |
| `cloudops-db-subnet` | `10.0.3.0/24` | Private Database layer |

All three subnets are currently in a single Availability Zone for the initial V1 implementation.

### Route Tables

| Route Table | Associated Subnet | Default Route |
|---|---|---|
| `cloudops-public-rt` | Web subnet | `0.0.0.0/0 → Internet Gateway` |
| `cloudops-app-rt` | Application subnet | None |
| `cloudops-db-rt` | Database subnet | `0.0.0.0/0 → NAT Gateway` |

All route tables also contain:

```text
10.0.0.0/16 → local
```

### Internet Gateway

```text
cloudops-hub-igw
```

is attached to:

```text
cloudops-hub-vpc
```

The public route table contains:

```text
0.0.0.0/0 → cloudops-hub-igw
```

### NAT Gateway

A NAT Gateway was introduced when the private Database EC2 instance required outbound connectivity.

The Database route table contains:

```text
0.0.0.0/0 → NAT Gateway
```

The NAT Gateway itself is deployed in the public subnet and reaches the Internet through the Internet Gateway.

### Security Groups

| Security Group | Intended Inbound Access |
|---|---|
| `cloudops-web-sg` | Internet → HTTP `80` for initial V1 testing |
| `cloudops-app-sg` | Web Security Group → Application port |
| `cloudops-db-sg` | Application Security Group → PostgreSQL `5432` |

### Current Network Design

```text
                           Internet
                              │
                              ▼
                      Internet Gateway
                      cloudops-hub-igw
                         /          \
                        /            \
                       ▼              ▼
              Public Web Path     NAT Gateway
                       │              ▲
                       ▼              │
             cloudops-web-subnet      │
                  10.0.1.0/24         │
                       │              │
                       ▼              │
             cloudops-app-subnet      │
                  10.0.2.0/24         │
                       │              │
                 PostgreSQL 5432      │
                       ▼              │
              cloudops-db-subnet ─────┘
                  10.0.3.0/24
                       │
                       ▼
                 PostgreSQL EC2
                   No Public IP
```

The NAT path is for outbound connectivity from the private Database subnet.

The intended application traffic path remains:

```text
Internet → Web → Application → Database
```

### Not Yet Implemented

The following concepts have been studied but are not currently implemented:

- Custom Network ACLs
- Custom internal DNS
- Multi-AZ networking
- High-availability network architecture

---

## 11. Architecture Decisions

### 1. Use a Dedicated VPC

**Decision:**  
Create a dedicated VPC rather than using the default VPC.

**Reason:**  
This gives CloudOps Hub control over IP addressing, segmentation, routing, connectivity, and security boundaries.

---

### 2. Use `10.0.0.0/16` as the VPC CIDR

**Decision:**

```text
10.0.0.0/16
```

**Reason:**  
A `/16` provides enough private address space to divide the network into smaller subnets while leaving room for growth.

CIDR planning also reduces the risk of future network overlap.

---

### 3. Separate Web, Application, and Database Networks

**Decision:**

```text
Web          10.0.1.0/24
Application  10.0.2.0/24
Database     10.0.3.0/24
```

**Reason:**  
Each layer has different connectivity and security requirements.

Separating them allows those policies to evolve independently.

---

### 4. Use Dedicated Route Tables

**Decision:**  
Use separate route tables for Web, Application, and Database subnets.

**Reason:**  
Each layer can have a different routing policy.

This became particularly useful when the Database layer later required NAT connectivity while the Application subnet did not yet require it.

> **Different connectivity requirements should have different routing policies.**

---

### 5. Provide Direct Internet Routing Only Where Required

**Decision:**  
Only the Web/public subnet has a direct default route to the Internet Gateway.

**Reason:**  
The Application and Database workloads should not be directly internet-accessible.

The Database layer's outbound connectivity is instead provided through NAT.

> **Don't provide network connectivity simply because you can. Provide only the connectivity the workload actually requires.**

---

### 6. Use Separate Security Groups for Each Layer

**Decision:**  
Create separate Security Groups for Web, Application, and Database workloads.

**Reason:**  
Each layer should accept only the traffic required for its function.

The intended path is:

```text
Internet → Web → Application → Database
```

> **Network membership does not imply network trust.**

---

### 7. Use Security Group Relationships

**Decision:**  
Use Security Group references where possible instead of individual server IP addresses.

Example:

```text
cloudops-app-sg → cloudops-db-sg :5432
```

**Reason:**  
Infrastructure can be replaced or scaled and IP addresses can change.

The security policy should represent the application relationship rather than individual infrastructure addresses.

---

### 8. Introduce NAT Only When Required

**Original Decision:**  
Do not deploy a NAT Gateway without a confirmed requirement.

**What Changed:**  
During the Database Foundation implementation, the private PostgreSQL EC2 instance required controlled outbound connectivity while remaining without a public IP address.

**Updated Decision:**  
Introduce a NAT Gateway and route the Database subnet's outbound traffic through it.

**Reason:**  
The NAT Gateway now solves an actual connectivity requirement.

Because NAT Gateway has an ongoing cost, it may be deleted when the CloudOps Hub learning environment is not being used.

> **Architecture should evolve when requirements change.**

---

### 9. Do Not Create Custom NACLs Without a Requirement

**Decision:**  
Use the default Network ACL for V1.

**Reason:**  
Security Groups currently provide the required workload-level controls.

Custom NACLs will be introduced if a future requirement needs subnet-level Allow/Deny controls.

---

### 10. Start With a Single Availability Zone

**Decision:**  
Deploy the initial manual V1 architecture within one Availability Zone.

**Reason:**  
The current objective is to understand and validate individual components before introducing high-availability complexity.

This is a known trade-off rather than the target production architecture.

> **Redundancy doesn't automatically give you high availability. You have to architect the system to use that redundancy.**

---

### Engineering Principle

CloudOps Hub networking is built around application requirements rather than adding AWS services simply because they are commonly used.

For every new component, the first question is:

> **What problem are we trying to solve?**

Only then should we choose the AWS service or architecture pattern.

---

## 12. Current Limitations and Future Improvements

CloudOps Hub V1 is intentionally a simple manual implementation.

The following limitations are known and accepted.

### 1. Single Availability Zone

**Current Limitation:**  
The current subnets are deployed within a single Availability Zone.

**Future Improvement:**  
Distribute the architecture across multiple Availability Zones and introduce load balancing, health checks, and appropriate redundancy.

---

### 2. No High Availability

**Current Limitation:**  
V1 does not currently provide redundant Web, Application, or Database resources.

**Future Improvement:**  
Introduce redundancy after the single-instance architecture has been fully understood and validated.

---

### 3. HTTP During Initial Testing

**Current Limitation:**  
The initial Web layer design allows HTTP on port `80` for learning and testing.

**Future Improvement:**  
Introduce HTTPS/TLS when the Web layer is implemented and the end-to-end application flow is validated.

---

### 4. NAT Gateway Cost

**Current Limitation:**  
The NAT Gateway provides useful outbound connectivity but introduces an ongoing cost even in a small learning environment.

**Current Approach:**  
The NAT Gateway may be deleted when the environment is not being used and recreated when required.

**Future Improvement:**  
As the architecture evolves, evaluate the most appropriate outbound/private AWS service connectivity design based on requirements, security, and cost.

---

### 5. Custom Internal DNS Not Implemented

**Current Limitation:**  
CloudOps Hub does not yet have a custom internal DNS strategy.

**Future Improvement:**  
Introduce stable service names when application components require them.

---

### 6. Custom Network ACLs Not Implemented

**Current Limitation:**  
V1 currently relies primarily on Security Groups and the default Network ACL.

**Future Improvement:**  
Introduce custom NACLs if future security requirements require explicit subnet-level Allow or Deny controls.

---

### 7. Infrastructure Is Manually Recreated

**Current Limitation:**  
Network and runtime resources are currently being created and modified manually.

This is intentional during the first-principles learning phase.

**Future Improvement:**  
Once the manual process and its operational overhead are understood, introduce Infrastructure as Code to make infrastructure creation, modification, and teardown repeatable.

---

## V1 Networking Goal

The purpose of V1 is not to immediately build the final production architecture.

The goal is to:

1. Understand the networking components.
2. Deploy them manually.
3. Validate how traffic flows between application layers.
4. Troubleshoot real connectivity requirements.
5. Understand the cost and security implications of architecture decisions.
6. Identify limitations through practical experience.
7. Improve the architecture when there is a clear requirement.
8. Eventually automate the processes we already understand.

> **Build the simplest architecture that satisfies the current requirements, understand its limitations, and evolve it deliberately.**