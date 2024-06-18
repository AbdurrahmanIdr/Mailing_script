document.addEventListener("DOMContentLoaded", () => {
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const usernameIcon = document.getElementById("username-icon");
  const passwordIcon = document.getElementById("password-icon");

  const handleFocus = (icon) => {
    icon.style.fill = "#4CAF50";
  };

  const handleBlur = (icon) => {
    icon.style.fill = "white";
  };

  usernameInput.addEventListener("focus", () => handleFocus(usernameIcon));
  usernameInput.addEventListener("blur", () => handleBlur(usernameIcon));

  passwordInput.addEventListener("focus", () => handleFocus(passwordIcon));
  passwordInput.addEventListener("blur", () => handleBlur(passwordIcon));
});

