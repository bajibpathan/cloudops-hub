# Cloud Engineering Foundations

## Purpose

This document captures the foundational engineering principles I learned while exploring why cloud computing exists and how reliable, scalable systems should be designed.

The goal is not to memorize cloud services, but to understand the engineering problems those services are designed to solve.

---

## 1. Why Cloud Computing?

### The Problem

- Maintaining physical infrastructure creates significant operational overhead. Companies need to invest considerable time, money, and resources to operate and maintain their own data centers and servers.

- Managing infrastructure can take focus away from solving business problems and building new products and services.

- Companies often provision infrastructure for peak demand, which means a significant amount of capacity may remain underutilized during normal or low-traffic periods. The infrastructure is already purchased regardless of how much it is actually being used.

- Handling unexpected traffic spikes or special events may require additional infrastructure. With traditional physical infrastructure, companies cannot easily increase and decrease capacity as demand changes.


### What I Learned

- Cloud computing allows organizations to focus more on solving business problems and innovation instead of spending significant time managing physical infrastructure.

- Organizations can reduce the time and effort involved in procuring hardware, installing servers, configuring data center infrastructure, and maintaining physical equipment.

- Instead of making large upfront infrastructure investments based on predicted future demand, cloud resources can be consumed when required and charged according to their usage and pricing model.

- Cloud infrastructure can scale up when demand increases and scale down when demand decreases, helping organizations balance application performance with infrastructure cost.

### Key Takeaway

Cloud computing is not simply about moving servers from our data center to someone else's data center. It changes how infrastructure is consumed. Organizations can provision resources when needed, adapt capacity as demand changes, and spend more time solving business problems instead of managing physical infrastructure.

---

## 2. Capacity Planning and Elasticity

### The Problem

- To handle peak traffic during special events such as Black Friday, organizations traditionally had to procure additional infrastructure upfront.

- However, these peak events may occur only a few times during the year. For the rest of the year, much of that additional capacity may remain underutilized.

- Even when the infrastructure is not fully utilized, the organization has already invested money to purchase it and must continue paying the operational costs associated with maintaining it.

- This creates a capacity-planning challenge: under-provisioning can cause performance and availability problems during peak demand, while over-provisioning results in wasted capacity and unnecessary cost.

### What I Learned

- During normal traffic periods, the application should run with enough capacity to handle the expected workload without unnecessarily provisioning infrastructure for occasional peak demand.

- When demand increases, additional capacity should be added so that the application can continue providing acceptable performance and availability to customers.

- When demand decreases, the additional capacity should be removed so that the organization is not paying for resources that are no longer required.

- Instead of permanently provisioning infrastructure for the highest possible demand, cloud environments allow capacity to adjust based on changing workload requirements.

### Key Takeaway

Capacity should follow demand.

The goal of elasticity is to provide enough infrastructure to maintain customer experience when demand increases, while reducing unnecessary capacity and cost when demand decreases.

---

## 3. Design for Failure

### The Problem

- Running a business-critical application on a single server creates a single point of failure. If that server fails, the application may become unavailable and customers can be impacted.

- Application downtime can affect customer experience, reduce trust, and potentially result in business and revenue impact.

### What I Learned

- Instead of depending on a single server, applications should be designed with redundancy so that the failure of one server does not result in an application outage.

- When one server becomes unhealthy, the system should detect the failure, stop routing new traffic to that server, and continue serving customers using the remaining healthy servers.

- The failed server can then be recovered or replaced without requiring the entire application to become unavailable.

### Key Takeaway

Failures are inevitable. The goal is not to design systems that never fail, but to design systems that can continue operating when individual components fail.

**Design for failure, not for perfection.**

---

## 4. Horizontal vs. Vertical Scaling

### The Problem

- Increasing the CPU and memory of an existing server can provide additional capacity, but a server can only be scaled up to a certain limit. Eventually, we will reach the maximum configuration supported by the underlying infrastructure.

- Depending on one large server can also create a single point of failure. Regardless of how powerful the server is, if it fails and the application depends entirely on it, the application can become unavailable.

- Continuously increasing the size of one server may therefore create limitations in scalability, availability, and flexibility.

### What I Learned

- Instead of continuously making one server larger, we can distribute the application across multiple servers.

- If one server fails, the system can stop routing traffic to the failed server and continue serving customers using the remaining healthy servers. This helps improve application availability and reduce customer impact.

- When demand increases, additional servers can be added to provide more capacity. When demand decreases, unnecessary capacity can be removed, provided the application is designed to support this safely.

- This approach provides greater flexibility for building scalable and highly available applications.

### Key Takeaway

Vertical scaling increases the capacity of an existing server, but it has physical limits and can still leave the application dependent on a single machine.

Horizontal scaling adds more servers, allowing the application to distribute workload, tolerate individual server failures, and adjust capacity as demand changes.

**Scale out for flexibility and resilience, not just up for more power.**

---

## 5. Load Balancing and Health Checks

### The Problem

- Adding multiple application servers creates another challenge because customers should not need to know which individual server they need to connect to.

- Traffic also needs to be distributed across the available servers so that one server does not unnecessarily receive all the workload while other servers remain underutilized.

- Some servers may become unhealthy or fail completely. If customer traffic continues to be routed to an unhealthy server, users may experience errors, slow responses, or application failures.

### What I Learned

- A load balancing component can provide a single entry point for customers and distribute incoming requests across the available application servers.

- Customers do not need to know how many application servers exist or which individual server processes their request.

- The load balancing component should regularly check the health of the application servers and route traffic only to servers that are healthy enough to serve customer requests.

- A server should not necessarily be marked unhealthy because of a single failed health check. Temporary network issues or short application delays can cause individual checks to fail.

- Health-check thresholds can be used so that a server is marked unhealthy only after a defined number of consecutive failures. Similarly, multiple successful health checks can be required before a recovered server is returned to service.

### Key Takeaway

Load balancing distributes customer traffic across available application servers, while health checks help determine which servers are safe to receive that traffic.

Together, they help improve availability, distribute workload, and prevent customer requests from being sent to unhealthy application instances.

**Distribute traffic across healthy capacity, not just available capacity.**


---

## 6. Auto Scaling

### The Problem

- Adding multiple servers behind a load balancer does not guarantee that the application will always have enough capacity to handle changing demand.

- During periods of high traffic, all available servers may become heavily utilized. Even though the servers are healthy and the load balancer is distributing traffic correctly, the application may experience increased response times, growing request queues, errors, or timeouts.

- A load balancer can distribute traffic across the existing servers, but it cannot solve a shortage of overall application capacity by itself.

### What I Learned

- When application demand consistently increases and the existing infrastructure does not have enough capacity, additional servers should be added automatically.

- The scaling decision should be based on meaningful workload signals such as CPU utilization, request volume, queue depth, response time, or other application-specific metrics.

- We should not add additional capacity simply because a metric crosses a threshold once. Short-lived spikes can occur, so the system should evaluate whether the condition persists long enough to represent a real increase in demand.

- When demand decreases and the additional capacity is no longer required, excess servers can be removed safely to avoid unnecessary infrastructure cost.

- Minimum and maximum capacity boundaries should also be defined so that the application maintains a safe baseline while preventing uncontrolled scaling.

### Key Takeaway

Load balancing determines **where traffic should go**.

Auto Scaling determines **how much capacity should exist**.

Together, they allow an application to distribute traffic across healthy servers while adjusting infrastructure capacity as demand changes.

**Scale based on sustained demand, not temporary noise.**