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

A VPC is a broader network, and deploying all the resources without separating the network may make it difficult to manage the different connectivity requirements of the Web, Application, and Database layers.

For example, we want the Web layer to have internet connectivity, while the Application and Database layers should remain private.

### What I Learned

- We can divide the larger VPC network into smaller networks called subnets. This helps us separate the resources based on their connectivity and routing requirements.

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

Deploying all the application resources in a single Availability Zone creates a single failure domain. If that Availability Zone becomes unavailable, the entire application may become inaccessible to users, resulting in customer and business impact.

### What I Learned

- We can improve application availability by distributing resources across multiple Availability Zones instead of depending on a single AZ.

- However, simply deploying resources in multiple Availability Zones does not automatically make the application highly available. We also need to ensure that traffic can be distributed across the healthy resources in those Availability Zones.

- For example, a load balancer can distribute traffic across resources in multiple Availability Zones and use health checks to avoid sending requests to unhealthy resources.

- If one Availability Zone becomes unavailable, resources in another healthy Availability Zone can continue serving user requests.

- Database redundancy requires additional consideration because databases contain state. Simply creating another database server in a different Availability Zone does not automatically ensure that both databases contain consistent data.

### CloudOps Hub V1 Decision

For the initial manual deployment, CloudOps Hub will use a single Availability Zone.

This is an intentional decision to keep V1 simple while we learn and validate each component manually.

We understand that this creates an Availability Zone-level failure risk. A future version of CloudOps Hub will evolve the architecture across multiple Availability Zones and introduce the required traffic distribution and redundancy mechanisms.

---

## 4. Route Tables

### The Problem

When we create a VPC, AWS automatically creates a main route table with a local route for communication within the VPC CIDR range.

However, the Web, Application, and Database layers of CloudOps Hub have different routing requirements.

For example:

- The Web layer needs a route to the Internet.
- The Application layer should remain private, but may later require controlled outbound Internet access.
- The Database layer should remain private and currently does not require Internet access.

Using the same routing policy for all the layers may provide connectivity that some workloads do not actually require.

### What I Learned

- Route tables define where network traffic should be directed based on the destination.

- AWS automatically creates a local route for the VPC CIDR. In our VPC, we observed:

  `10.0.0.0/16 → local`

  This provides a routing path between resources within the VPC address space, subject to network security controls.

- Instead of depending on the same route table for all the subnets, we created dedicated route tables for each layer:

  - `cloudops-public-rt` → Web subnet
  - `cloudops-app-rt` → Application subnet
  - `cloudops-db-rt` → Database subnet

- The Web route table has a default route to the Internet Gateway:

  `0.0.0.0/0 → Internet Gateway`

- The Application and Database route tables currently contain only the local VPC route and therefore do not have a direct route to the Internet.

- Having separate route tables gives us more control over the routing requirements of each layer. For example, if the Application layer later requires outbound Internet connectivity, we can add a route through a NAT Gateway without providing the same connectivity to the Database layer.

---

## 5. Internet Gateway

### The Problem

Creating an Internet Gateway and attaching it to the VPC alone does not provide Internet connectivity to the resources in our Web subnet.

The subnet also needs a routing path that directs Internet-bound traffic to the Internet Gateway.

### What I Learned

- An Internet Gateway (IGW) provides a path for communication between a VPC and the Internet.

- After creating the Internet Gateway, we attached it to our `cloudops-hub-vpc`.

- Attaching the Internet Gateway to the VPC alone does not automatically make all the subnets public.

- For our Web subnet, we added the following route to `cloudops-public-rt`:

  `0.0.0.0/0 → cloudops-hub-igw`

- We associated `cloudops-public-rt` only with the Web subnet. This gives the Web subnet a direct routing path to the Internet Gateway.

- We did not add this route to the Application or Database route tables because those layers should not have direct Internet connectivity.

- Even with a route to an Internet Gateway, an EC2 instance still requires appropriate public addressing and security rules before it can communicate with the Internet.

---

## 6. NAT

### Implementation Status

**Concept learned, not yet implemented in CloudOps Hub V1.**

### The Problem

In some situations, resources in a private subnet may need outbound Internet connectivity.

For example, our Application server may need to download OS security updates, install software packages, or communicate with an external service.

However, we do not want to make the Application server directly public or provide the private Application subnet with a direct route to the Internet Gateway.

Our requirement is:

- Application Server → Internet ✅
- Internet → Application Server directly ❌

### What I Learned

- NAT (Network Address Translation) can provide outbound Internet connectivity for resources in a private subnet without making those resources directly public.

- For Internet-bound connectivity using a public NAT Gateway, the NAT Gateway is placed in a public subnet that has a route to the Internet Gateway.

- The private Application subnet can then have a route such as:

  `0.0.0.0/0 → NAT Gateway`

- The traffic flow would be:

  `Application Server → NAT Gateway → Internet Gateway → Internet`

- The Application server initiates the outbound connection, and the response can return through the NAT Gateway. External Internet clients cannot use the NAT Gateway to initiate unsolicited connections directly to the private Application server.

- We should not automatically provide the Database subnet with the same NAT route if the Database layer does not require Internet connectivity.

### CloudOps Hub V1 Decision

A NAT Gateway has **not been implemented yet**.

We will introduce NAT only when the Application layer has a real requirement for outbound Internet connectivity. This avoids adding unnecessary infrastructure, complexity, and cost to V1.

---

## 7. Security Groups

### The Problem

Our resources should not accept all types of traffic just because a network path exists between them.

For example, users should be able to access the Web layer only on the required web ports. Similarly, the Application layer should accept application traffic only from the Web layer, and the Database layer should accept database traffic only from the Application layer.

Without these controls, we may unnecessarily expose our resources and increase the security risk.

### What I Learned

- Security Groups act as virtual firewalls for AWS resources and allow us to control inbound and outbound traffic.

- We can define which source is allowed to communicate with a resource and on which port.

- For CloudOps Hub, we created separate Security Groups for each layer:

  - `cloudops-web-sg`
  - `cloudops-app-sg`
  - `cloudops-db-sg`

- Our intended communication is:

  `Internet → Web :80`  
  `Web Security Group → Application :Application Port`  
  `Application Security Group → Database :5432`

- Instead of allowing the entire VPC CIDR to access the Database, we can use `cloudops-app-sg` as the source of the Database Security Group rule. This ensures that the Database accepts PostgreSQL traffic only from resources associated with the Application Security Group.

- Security Groups are stateful. When a connection is permitted, the response traffic associated with that connection is automatically allowed without requiring a separate rule specifically for the return traffic.

- Security Groups use allow rules. If traffic is not explicitly allowed by the applicable Security Group rules, it is not permitted.

---

## 8. Network ACLs (NACLs)

### Implementation Status

**Concept learned. Custom Network ACLs are not implemented in CloudOps Hub V1.**

### The Problem

In some situations, there may be a requirement to allow or deny certain network traffic for an entire subnet rather than controlling access only at the individual resource level.

For example, we may need to block traffic from a particular network range from reaching any resource within a subnet.

### What I Learned

- Network ACLs (NACLs) provide network traffic control at the subnet level.

- Unlike Security Groups, which are associated with resources/network interfaces, a NACL is associated with a subnet.

- NACLs support both **Allow** and **Deny** rules. This can be useful when we need to explicitly block traffic from a particular network range.

- NACLs are **stateless**, which means inbound and outbound traffic are evaluated separately. Return traffic must therefore be considered when designing the rules.

- NACL rules are evaluated in rule-number order, starting with the lowest number, and the first matching rule determines whether the traffic is allowed or denied.

- AWS automatically created a default Network ACL when we created the CloudOps Hub VPC.

### CloudOps Hub V1 Decision

We have not created a custom NACL for V1 because there is currently no requirement that needs subnet-level Allow/Deny rules.

For now, Security Groups provide the workload-level traffic controls required by CloudOps Hub. We will introduce custom NACLs only if a future requirement justifies them.

---

## 9. DNS

### Implementation Status

**Concept learned. Custom DNS is not implemented in CloudOps Hub V1.**

### The Problem

Hard-coding server IP addresses in application configuration can create problems because infrastructure may be replaced or recreated, causing IP addresses to change.

For example, if the Application layer is configured to connect to a Database server using a hard-coded IP address and that Database server is replaced with a new IP address, the Application may continue trying to connect to the old address.

### What I Learned

- Instead of unnecessarily depending on hard-coded IP addresses, we can use DNS names to identify services.

- DNS resolves the service name to its corresponding IP address.

- For example, instead of configuring:

  `DB_HOST=10.0.3.25`

  we could eventually use something like:

  `DB_HOST=db.cloudopshub.internal`

- If the underlying IP address changes, the DNS record can be updated while the Application continues using the same service name.

- DNS helps us separate the identity of a service from the underlying infrastructure address.


### CloudOps Hub V1 Decision

Custom DNS has not been implemented in V1 yet. We will introduce it when the application architecture creates a requirement for stable internal service names.

---

## 10. CloudOps Hub V1 Network Implementation

After understanding the core VPC networking concepts, the CloudOps Hub V1 network was manually created in AWS.

The goal of V1 is to build and understand the networking components manually before introducing automation or a more highly available architecture.

### VPC

| Resource | Configuration |
|---|---|
| VPC | `cloudops-hub-vpc` |
| IPv4 CIDR | `10.0.0.0/16` |

### Subnets

| Subnet | CIDR | Purpose |
|---|---|---|
| `cloudops-web-subnet` | `10.0.1.0/24` | Web layer |
| `cloudops-app-subnet` | `10.0.2.0/24` | Application layer |
| `cloudops-db-subnet` | `10.0.3.0/24` | Database layer |

Each subnet is currently deployed within a single Availability Zone as part of the initial V1 implementation.

### Route Tables

Dedicated route tables were created for each application layer so that their routing policies can evolve independently.

| Route Table | Associated Subnet | Internet Route |
|---|---|---|
| `cloudops-public-rt` | Web subnet | `0.0.0.0/0 → Internet Gateway` |
| `cloudops-app-rt` | Application subnet | None |
| `cloudops-db-rt` | Database subnet | None |

All three route tables also contain the local VPC route:

`10.0.0.0/16 → local`

This local route provides a routing path for communication within the VPC address space, subject to the configured network security controls.

### Internet Gateway

An Internet Gateway named:

`cloudops-hub-igw`

was created and attached to:

`cloudops-hub-vpc`

The Web subnet's route table contains the following default route:

`0.0.0.0/0 → cloudops-hub-igw`

This provides the Web subnet with a direct routing path to the Internet Gateway.

The Application and Database subnet route tables do not have a direct route to the Internet Gateway.

### Security Groups

Three Security Groups were created to represent the communication boundaries between the application layers:

| Security Group | Intended Inbound Access |
|---|---|
| `cloudops-web-sg` | Internet → HTTP `80` for initial V1 testing |
| `cloudops-app-sg` | Web Security Group → Application port |
| `cloudops-db-sg` | Application Security Group → PostgreSQL `5432` |

The intended communication flow is:

`Internet → Web → Application → Database`

The security design follows the principle that each layer should accept only the traffic required for its function.

Direct Internet access to the Application and Database layers is not part of the V1 design.

### Current Network Flow

```text
                         Internet
                            |
                            |
                     Internet Gateway
                   cloudops-hub-igw
                            |
                            |
                cloudops-public-rt
                  0.0.0.0/0 -> IGW
                            |
                            v
                  cloudops-web-subnet
                     10.0.1.0/24
                            |
                            | Application Port
                            v
                  cloudops-app-subnet
                     10.0.2.0/24
                            |
                            | PostgreSQL 5432
                            v
                   cloudops-db-subnet
                     10.0.3.0/24

```

### Not Implemented in V1

The following concepts were studied but have not been implemented because the current V1 architecture does not yet require them:

- NAT Gateway
- Custom Network ACLs
- Custom internal DNS
- Multi-AZ networking

---

---

## 11. Architecture Decisions

The following architecture decisions were made for the CloudOps Hub V1 networking foundation.

### 1. Use a Dedicated VPC

**Decision:**  
Create a dedicated VPC for CloudOps Hub instead of deploying the resources into the default VPC.

**Reason:**  
A dedicated VPC gives us control over IP addressing, subnet design, routing, connectivity, and security boundaries.

It also allows the CloudOps Hub network to evolve independently as the architecture grows.

---

### 2. Use `10.0.0.0/16` as the VPC CIDR

**Decision:**  
Use the following CIDR for the CloudOps Hub VPC:

`10.0.0.0/16`

**Reason:**  
A `/16` provides sufficient private IP address space to divide the network into multiple smaller subnets and leaves room for the architecture to grow.

IP address planning is also important because overlapping CIDR ranges can create challenges if CloudOps Hub needs to connect with other networks in the future.

---

### 3. Separate the Web, Application, and Database Networks

**Decision:**  
Create separate subnets for each application layer:

- Web: `10.0.1.0/24`
- Application: `10.0.2.0/24`
- Database: `10.0.3.0/24`

**Reason:**  
Each application layer has different connectivity requirements.

The Web layer requires public-facing connectivity, while the Application and Database layers should remain private.

Separating the layers allows their routing and connectivity requirements to be managed independently.

---

### 4. Use Dedicated Route Tables

**Decision:**  
Create separate route tables for the Web, Application, and Database subnets.

**Reason:**  
Different application layers may require different routing policies.

For example, the Application subnet may eventually require controlled outbound Internet access through a NAT Gateway, while the Database subnet may not require Internet connectivity.

Keeping their route tables separate allows one layer's routing policy to change without unnecessarily changing another layer.

> **Different connectivity requirements should have different routing policies.**

---

### 5. Provide Direct Internet Routing Only to the Web Subnet

**Decision:**  
Only the Web subnet has the following route:

`0.0.0.0/0 → Internet Gateway`

**Reason:**  
The Web layer needs to receive user traffic, while the Application and Database layers should not have direct Internet connectivity.

Providing Internet routing only where it is required reduces unnecessary network exposure.

> **Don't provide network connectivity simply because you can. Provide only the connectivity the workload actually requires.**

---

### 6. Use Separate Security Groups for Each Layer

**Decision:**  
Create separate Security Groups for the Web, Application, and Database layers.

**Reason:**  
Each layer should accept only the traffic required to perform its function.

The intended communication path is:

`Internet → Web → Application → Database`

For example, the Database layer should accept PostgreSQL traffic from the Application layer rather than accepting database connections from the entire VPC or Internet.

> **Network membership does not imply network trust.**

---

### 7. Use Security Group Relationships Between Application Layers

**Decision:**  
Use Security Group references where possible instead of depending on individual server IP addresses.

For example:

`cloudops-app-sg → cloudops-db-sg :5432`

**Reason:**  
Application servers may eventually be replaced or scaled, causing their IP addresses to change.

Using Security Group relationships allows the security policy to represent the application architecture instead of individual infrastructure addresses.

---

### 8. Do Not Implement NAT Without a Requirement

**Decision:**  
Do not deploy a NAT Gateway in the initial V1 network.

**Reason:**  
The current architecture does not yet have a confirmed requirement for private resources to access the Internet.

A NAT Gateway will be introduced if the Application layer requires controlled outbound Internet connectivity.

This avoids introducing unnecessary infrastructure, complexity, and cost.

---

### 9. Do Not Create Custom NACLs Without a Requirement

**Decision:**  
Use the default Network ACL for the initial V1 implementation.

**Reason:**  
Security Groups currently provide the workload-level traffic controls required by CloudOps Hub.

Custom NACL rules will be introduced only if a future requirement requires additional subnet-level Allow or Deny controls.

---

### 10. Start With a Single Availability Zone

**Decision:**  
Deploy the initial manual V1 architecture within a single Availability Zone.

**Reason:**  
The goal of V1 is to understand and manually validate the individual architecture components before introducing high-availability complexity.

This is a known trade-off rather than the target production architecture.

The architecture will later evolve to multiple Availability Zones when we introduce high availability and failure tolerance.

> **Redundancy doesn't automatically give you high availability. You have to architect the system to use that redundancy.**

---

### Engineering Principle

The networking architecture is being built around application requirements rather than adding AWS services simply because they are commonly used.

For every new component, the first question should be:

> **What problem are we trying to solve?**

Only then should we decide which AWS service or architecture pattern is appropriate.


---

---

## 12. Current Limitations and Future Improvements

CloudOps Hub V1 is intentionally designed as a simple manual implementation so that each networking component can be understood, deployed, and validated individually.

The following limitations are known and intentionally accepted for V1.

### 1. Single Availability Zone

**Current Limitation:**  
The Web, Application, and Database subnets are currently deployed within a single Availability Zone.

If that Availability Zone becomes unavailable, CloudOps Hub may become unavailable.

**Future Improvement:**  
Distribute the application across multiple Availability Zones and introduce the required load balancing, health checks, and redundancy mechanisms.

---

### 2. No High Availability

**Current Limitation:**  
V1 does not currently provide redundant Web, Application, or Database resources.

Individual server failures may therefore impact application availability.

**Future Improvement:**  
Introduce redundancy gradually after the manual single-instance architecture has been successfully deployed and validated.

The goal is not simply to create more servers, but to ensure traffic can be redirected to healthy resources when failures occur.

---

### 3. HTTP Used During Initial Testing

**Current Limitation:**  
The initial Web layer allows HTTP traffic on port `80` for learning and testing.

**Future Improvement:**  
Introduce HTTPS using TLS certificates once the basic end-to-end application flow has been validated.

The target architecture should not expose production application traffic over unencrypted HTTP.

---

### 4. NAT Gateway Not Implemented

**Current Limitation:**  
The Application subnet currently has no outbound Internet route.

**Future Improvement:**  
If the Application layer requires outbound Internet connectivity, evaluate and introduce an appropriate controlled outbound connectivity solution.

A NAT Gateway should only be introduced when there is a requirement that justifies the additional infrastructure and cost.

---

### 5. Custom Internal DNS Not Implemented

**Current Limitation:**  
CloudOps Hub does not currently have a custom internal DNS strategy for communication between application components.

**Future Improvement:**  
Introduce stable service names when required so application components do not unnecessarily depend on infrastructure IP addresses.

---

### 6. Custom Network ACLs Not Implemented

**Current Limitation:**  
CloudOps Hub V1 uses the default Network ACL and relies primarily on Security Groups for workload-level traffic control.

**Future Improvement:**  
Introduce custom Network ACL rules if future security requirements require explicit subnet-level Allow or Deny controls.

---

## V1 Networking Goal

The purpose of V1 is not to build the final production architecture immediately.

The goal is to:

1. Understand the networking components.
2. Deploy them manually.
3. Validate how traffic flows between application layers.
4. Identify limitations through practical experience.
5. Improve the architecture only when there is a clear requirement.

> **Build the simplest architecture that satisfies the current requirements, understand its limitations, and evolve it deliberately.**