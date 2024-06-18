document.addEventListener("DOMContentLoaded", () => {
    const flashMessages = document.querySelectorAll(".flash");
    if (flashMessages.length > 0) {
      setTimeout(() => {
        flashMessages.forEach(flash => {
          flash.classList.add("hidden");
          flash.classList.add('error');
          flash.classList.add('success');
          flash.style.opacity = '0';
          flash.style.display = 'none';
          setTimeout(() => flash.remove(), 500);
        });
      }, 5000);
    }
  });
  
  

      