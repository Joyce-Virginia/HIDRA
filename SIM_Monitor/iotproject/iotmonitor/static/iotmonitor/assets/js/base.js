// Base JavaScript functionality

document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize AOS if available
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 600,
            easing: 'ease-in-out',
            once: true,
            mirror: false
        });
    }

    // Scroll top button functionality
    const scrollTop = document.querySelector('.scroll-top');
    
    function toggleScrollTop() {
        if (scrollTop) {
            window.scrollY > 100 ? scrollTop.classList.add('active') : scrollTop.classList.remove('active');
        }
    }
    
    if (scrollTop) {
        scrollTop.addEventListener('click', (e) => {
            e.preventDefault();
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    window.addEventListener('load', toggleScrollTop);
    document.addEventListener('scroll', toggleScrollTop);

    // Mobile nav toggle
    const mobileNavToggle = document.querySelector('.mobile-nav-toggle');
    const navmenu = document.querySelector('.navmenu');

    if (mobileNavToggle && navmenu) {
        mobileNavToggle.addEventListener('click', function() {
            navmenu.classList.toggle('mobile-nav-active');
            this.classList.toggle('fa-bars');
            this.classList.toggle('fa-times');
        });

        // Close mobile nav when clicking on a nav link
        const navLinks = navmenu.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (navmenu.classList.contains('mobile-nav-active')) {
                    navmenu.classList.remove('mobile-nav-active');
                    mobileNavToggle.classList.add('fa-bars');
                    mobileNavToggle.classList.remove('fa-times');
                }
            });
        });
    }

    // Header scroll effect
    const header = document.querySelector('.header');
    if (header) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 50) {
                header.classList.add('header-scrolled');
            } else {
                header.classList.remove('header-scrolled');
            }
        });
    }

    // Add loading state to buttons
    function addButtonLoadingState() {
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(button => {
            button.addEventListener('click', function(e) {
                if (this.type === 'submit' || this.closest('form')) {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Carregando...';
                    this.disabled = true;
                    
                    // Restore button after 3 seconds (adjust as needed)
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.disabled = false;
                    }, 3000);
                }
            });
        });
    }

    // Initialize button loading states
    addButtonLoadingState();

    // Utility function for smooth transitions
    function smoothTransition(element, property, value, duration = 300) {
        element.style.transition = `${property} ${duration}ms ease`;
        element.style[property] = value;
    }

    // Add this function to global scope for use in other scripts
    window.smoothTransition = smoothTransition;
});