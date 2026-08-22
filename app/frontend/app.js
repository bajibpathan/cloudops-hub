// app/frontend/app.js

const applicationsContainer = document.getElementById("applications");
const applicationForm = document.getElementById("application-form");
const message = document.getElementById("message");
const refreshButton = document.getElementById("refresh-button");

async function loadApplications() {
    applicationsContainer.textContent = "Loading applications...";

    try {
        const response = await fetch("/api/applications");

        if (!response.ok) {
            throw new Error("Failed to load applications");
        }

        const applications = await response.json();

        if (applications.length === 0) {
            applicationsContainer.textContent = "No applications found.";
            return;
        }

        applicationsContainer.innerHTML = applications.map(app => `
            <div class="application-item">
                <h3>${app.name}</h3>
                <p>${app.description || "No description"}</p>
                <p><strong>Owner:</strong> ${app.owner_team}</p>
                <p><strong>Environment:</strong> ${app.environment}</p>
                <p class="status"><strong>Status:</strong> ${app.status}</p>
            </div>
        `).join("");

    } catch (error) {
        applicationsContainer.textContent = "Unable to load applications.";
        console.error(error);
    }
}

applicationForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
        name: document.getElementById("name").value,
        description: document.getElementById("description").value,
        owner_team: document.getElementById("owner_team").value,
        environment: document.getElementById("environment").value,
        status: document.getElementById("status").value
    };

    try {
        const response = await fetch("/api/applications", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Failed to create application");
        }

        message.textContent = "Application created successfully.";
        applicationForm.reset();

        await loadApplications();

    } catch (error) {
        message.textContent = error.message;
        console.error(error);
    }
});

refreshButton.addEventListener("click", loadApplications);

loadApplications();