// Fade out flash messages after 5 seconds
        document.addEventListener('DOMContentLoaded', function () {
            var flashes = document.querySelectorAll('.flash');
            flashes.forEach(function (flash) {
                setTimeout(function () {
                    flash.style.opacity = '0';
                    setTimeout(function () {
                        flash.style.display = 'none';
                    }, 1000);
                }, 5000);
            });
        });
