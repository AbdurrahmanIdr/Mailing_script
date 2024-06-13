document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("login-form");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const usernameIcon = document.getElementById("username-icon");
  const passwordIcon = document.getElementById("password-icon");

  const handleFocus = (icon) => {
    icon.classList.add("hidden");
  };

  const handleBlur = (icon) => {
    icon.classList.remove("hidden");
  };

  usernameInput.addEventListener("focus", () => handleFocus(usernameIcon));
  usernameInput.addEventListener("blur", () => handleBlur(usernameIcon));

  passwordInput.addEventListener("focus", () => handleFocus(passwordIcon));
  passwordInput.addEventListener("blur", () => handleBlur(passwordIcon));

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const username = usernameInput.value;
    const password = passwordInput.value;
    console.log({ username, password });
    // Add your form submission logic here
  });
});
