async function handleLogin(event) {
    event.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    const errorMessage = document.getElementById("errorMessage");

    if (!email || !password) {
        errorMessage.innerText = "Please fill in all fields.";
        return;
    }

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (response.ok) {
            window.location.href = "/";
        } else {
            errorMessage.innerText = data.error || data.message || "Invalid credentials.";
        }
    } catch (error) {
        console.error("Login error:", error);
        errorMessage.innerText = "Failed to connect to the server.";
    }
}
