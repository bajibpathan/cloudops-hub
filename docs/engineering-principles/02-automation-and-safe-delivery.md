# Automation and Safe Delivery

## Purpose

This document captures the engineering principles I learned while exploring how application servers can be configured consistently, how infrastructure changes can be managed safely, and how application releases can be introduced without unnecessarily increasing customer impact.

---
## 1. Manual Server Configuration and Automation

### The Problem

- Manually configuring application servers is time-consuming and error-prone. An engineer may forget a configuration step or configure servers differently, which can create application issues and potentially impact customers.

- Manual configuration also does not scale operationally. Configuring 50 servers manually is difficult, and the problem becomes much larger if the environment grows to hundreds of servers.

- As infrastructure scales dynamically, depending on engineers to manually prepare every new server is not a sustainable production design.

### What I Learned

- Instead of manually configuring every server, we can automate the setup using a script that contains the required installation, configuration, and application deployment steps.

- When a new server is launched, the script can automatically install the required software, apply configuration, deploy the application, and start the necessary services.

- However, automating the process with a script does not guarantee that every server will be configured successfully. If a package download, dependency installation, application deployment, or another step fails, the new server may not become ready to serve traffic.

- Performing all configuration during server launch can also increase the time required for new capacity to become available. This can become a problem when additional servers are required quickly during a sudden increase in demand.

- If software versions and dependencies are not controlled carefully, servers configured at different times could also end up with different configurations or software versions.

### Key Takeaway

Automation reduces manual effort and improves repeatability, but performing the entire server configuration during launch can introduce reliability, consistency, and scaling-speed challenges.

**Automate server configuration, but minimize the work required when new capacity is urgently needed.**

---

## 2. Standardized Machine Images

### The Problem

- Configuring an application entirely during server launch can introduce reliability problems. If a package installation, dependency download, configuration step, or application deployment fails, the new server may not become ready to serve traffic.

- If software and dependency versions are not carefully controlled, servers configured at different times could end up with different versions or configurations.

- Installing and configuring everything during launch also increases the amount of time required for a new server to become ready. This can reduce how quickly the application can respond to sudden increases in demand.

### What I Learned

- Instead of configuring everything from scratch whenever a new server is launched, we can prepare a standardized machine image containing the stable and reusable components required by the application.

- The image can include components such as the operating system, application runtime, required system packages, application binaries, monitoring components, and common base configuration.

- Sensitive information such as passwords, API keys, credentials, and secrets should not be permanently stored inside a reusable image.

- Configuration that differs between environments should also be supplied separately where appropriate instead of creating unnecessary differences in the base image.

- Because most of the required components are prepared and validated beforehand, new servers can become ready faster and start from a more consistent baseline.

- Faster server initialization also helps the platform respond more quickly when additional capacity is required.

### Key Takeaway

A standardized machine image provides a consistent and reusable starting point for application servers while reducing the amount of work required during launch.

**Prepare stable components beforehand and keep sensitive or environment-specific configuration separate.**

---

## 3. Immutable Infrastructure

### The Problem

- Continually modifying existing production servers can become time-consuming and error-prone, especially when the environment contains a large number of servers.

- Patching servers individually can also create consistency problems. Some servers may receive different changes, experience failed updates, or contain previous manual modifications.

- Over time, these differences can result in configuration drift, where the actual state of individual servers no longer matches the intended and tested state of the environment.

- Performing changes directly across the entire production environment can also increase the blast radius if a patch or configuration change introduces an unexpected problem.

### What I Learned

- Instead of continually modifying existing production servers, we can build a new machine image containing the required patch or application change.

- The new image should be tested and validated before it is introduced into the production environment.

- New servers can then be created from the updated image and gradually introduced into service instead of replacing the entire environment at once.

- After each stage of the rollout, application health, performance, errors, and customer-facing functionality should be validated before continuing.

- If the new servers show problems, the rollout should be stopped so that the blast radius does not increase.

- Traffic can be removed from the affected new servers while the known-good version continues serving customers, provided sufficient capacity remains available.

- Logs, metrics, traces, configuration information, and other relevant evidence should be preserved to investigate the failure before another deployment is attempted.

- Once the new version has been successfully validated, the remaining old servers can gradually be replaced.

### Key Takeaway

Immutable infrastructure treats running servers as replaceable rather than something that should be continually modified.

When a change is required, create and validate a new version, introduce it gradually, and replace the previous version only after proving that the new version is healthy.

**Replace with a known-good state instead of accumulating changes on long-lived servers.**

---

## 4. Desired State and Configuration Management

### The Problem

- Applications usually depend on multiple software components, packages, configuration files, services, and application versions to function correctly.

- Managing these configurations manually or through increasingly complex scripts can become difficult as the number of servers and dependencies grows.

- Failed or inconsistent configuration changes can cause servers to behave differently from one another and may eventually result in configuration drift.

- Automation should also avoid making unnecessary changes when a server is already configured correctly. Reinstalling packages, rewriting configuration, or restarting services unnecessarily can introduce risk and potentially affect application availability.

### What I Learned

- Instead of blindly executing configuration steps every time, we should define the desired state of the server and compare it with its current state.

- If the server does not match the desired state, the automation should make only the changes required to bring it into the expected state.

- If the server is already in the desired state, the automation should not make unnecessary changes.

- This behavior is known as idempotency.

- Idempotent configuration management makes automation safer to run repeatedly and helps maintain consistency across multiple servers.

### Key Takeaway

Configuration management should focus on maintaining the desired state rather than blindly repeating configuration steps.

**If the system is already in the desired state, don't change it unnecessarily.**

---

## 5. Git as the Source of Truth

### The Problem

- During a production incident, an engineer may manually change a server configuration to quickly restore application functionality or reduce customer impact.

- If that manual change is not reflected in the version-controlled configuration, the actual production state becomes different from the desired state defined by our automation.

- When the configuration automation runs again, it may detect the manual change as configuration drift and restore the previous configuration. This could reintroduce the same production problem.

- Undocumented manual changes also make it difficult for other engineers to understand what configuration is actually running in the environment.

### What I Learned

- Production configuration changes should normally be made through the version-controlled source and deployed using the defined automation process rather than being applied manually to individual servers.

- During a critical incident, an emergency manual change may sometimes be necessary to restore service quickly and reduce customer impact.

- When an emergency change is made, the change should be documented and incorporated into the version-controlled source of truth as soon as practical after the environment is stabilized.

- The updated configuration should then follow the appropriate review, testing, and deployment process so that future automation runs preserve the intended fix instead of reverting it.

### Key Takeaway

The version-controlled configuration should represent the intended state of the environment.

Emergency changes may temporarily create a difference between production and the source of truth, but that difference should not become permanent.

**A production fix is not complete until the source of truth reflects the intended change.**

---

## 6. CI/CD and Safe Change Delivery

### The Problem

- Changes stored in version control should not be deployed directly to production without appropriate validation. An untested or incorrectly configured change could affect application availability, customer experience, and business operations.

- Even when a change works successfully in a non-production environment, it may behave differently in production because the environments may have different traffic volumes, data, configurations, dependencies, integrations, or scaling characteristics.

- A successful deployment process also does not automatically mean that the release itself is healthy. The application may deploy successfully but begin showing errors, increased response times, or failures in critical customer functionality afterward.

### What I Learned

- Changes should be developed in a separate branch and go through appropriate testing and review before being merged into the main version-controlled source.

- The approved change should then move through a controlled delivery process where it can be built, validated, tested in non-production environments, and promoted toward production.

- Testing in lower environments reduces deployment risk but does not completely eliminate it. Production behavior should therefore be validated after deployment.

- Post-deployment validation should include relevant infrastructure, application, dependency, and customer-facing business signals.

- If the new version consistently shows problems, the rollout should be stopped to avoid increasing the blast radius.

- Traffic can be removed from the affected new version while the known-good version continues serving customers, where sufficient capacity exists.

- Relevant logs, metrics, traces, configuration details, and deployment evidence should be preserved so that the problem can be investigated and reproduced.

- After the issue is understood and corrected, the change should go through the appropriate testing and deployment process again.

### Key Takeaway

A successful deployment does not automatically mean a successful release.

Changes should be reviewed, tested, introduced through a controlled process, and validated after reaching production.

**Deployment finishes when the change is delivered. Release confidence comes from proving that the system and its critical business functions remain healthy.**

---

## 7. Gradual Rollouts and Blast Radius

### The Problem

- Deploying a new application version across the entire production environment at once creates a large blast radius.

- If the new version contains an unexpected application, configuration, performance, or dependency issue, a large portion of the customer base could be affected immediately.

- This could result in application downtime, poor customer experience, loss of customer trust, and potential business or revenue impact.

- Even when a release has been successfully tested in non-production environments, production may expose issues that were not identified during earlier testing.

### What I Learned

- Instead of exposing the entire production environment to a new version immediately, changes should be introduced gradually.

- For example, a small percentage of production traffic, such as 5%, can initially be routed to the new version while the known-good version continues serving the majority of customers.

- The new version should be monitored and validated before increasing its traffic exposure.

- Validation should include infrastructure health, application performance, error rates, dependency health, and critical customer-facing business functionality.

- If the new version remains healthy, traffic can gradually increase through stages such as 5%, 10%, 25%, 50%, and eventually 100%.

- If problems appear in the new version, the rollout should be stopped instead of increasing the blast radius.

- Traffic can be removed from the affected version and returned to the known-good version, while relevant evidence is preserved for investigation.

- Once the issue is understood, fixed, and successfully tested, the gradual deployment process can be attempted again.

### Key Takeaway

Gradual deployments reduce the blast radius by exposing only a small portion of production traffic to a new version before increasing its usage.

A release should progress only when both technical health and critical business functionality remain healthy.

**Introduce change gradually, observe carefully, and stop before a small problem becomes a large outage.**