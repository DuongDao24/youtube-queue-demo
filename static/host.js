document.addEventListener("DOMContentLoaded", () => {
  const loginOverlay = document.createElement("div");
  loginOverlay.id = "host-login-overlay";
  loginOverlay.innerHTML = `
    <div class="host-login-modal">
      <h3>Host Login</h3>
      <input type="text" id="hostUser" placeholder="Username" value="Admin">
      <input type="password" id="hostPass" placeholder="Password">
      <button id="hostLoginBtn">Login</button>
      <p id="loginError"></p>
    </div>
  `;
  document.body.appendChild(loginOverlay);

  const loginBtn = document.getElementById("hostLoginBtn");
  const errMsg = document.getElementById("loginError");

  loginBtn.addEventListener("click", async () => {
    const u = document.getElementById("hostUser").value.trim();
    const p = document.getElementById("hostPass").value.trim();

    const res = await fetch("/api/host_login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    });

    if (res.ok) {
      localStorage.setItem("hostAuth", JSON.stringify({ username: u, password: p }));
      loginOverlay.remove();
      initHostPanel(); // chạy giao diện host
    } else {
      errMsg.textContent = "Sai tài khoản hoặc mật khẩu.";
      errMsg.style.color = "red";
    }
  });
});

function initHostPanel() {
  console.log("✅ Host authenticated — initializing dashboard");
  // thêm logic load queue, history, settings...
}
