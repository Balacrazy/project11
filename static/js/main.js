document.addEventListener('DOMContentLoaded', () => {
    // ===== Navigation Toggle (Mobile) =====
    const navToggle = document.getElementById('navToggle');
    const navLinks = document.getElementById('navLinks');

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
        });
        document.addEventListener('click', (e) => {
            if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('active');
            }
        });
    }

    // ===== Auto-dismiss Flash Messages =====
    setTimeout(() => {
        const flashes = document.querySelectorAll('.flash-alert');
        flashes.forEach(flash => {
            flash.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            flash.style.opacity = '0';
            flash.style.transform = 'translateX(100%)';
            setTimeout(() => flash.remove(), 400);
        });
    }, 4000);

    // ===== Search Input Live Filter =====
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.toLowerCase().trim();
                const foodCards = document.querySelectorAll('.food-card');
                foodCards.forEach(card => {
                    const name = card.getAttribute('data-name') || '';
                    if (query === '' || name.includes(query)) {
                        card.style.display = '';
                        card.style.animation = 'fadeIn 0.3s ease';
                    } else {
                        card.style.display = 'none';
                    }
                });
            }, 300);
        });
    }

    // ===== Add to Cart Animation =====
    document.querySelectorAll('.btn-add-cart').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const originalText = this.innerHTML;
            this.innerHTML = '<i class="fa-solid fa-check"></i> Added!';
            this.style.background = '#10B981';
            setTimeout(() => {
                this.innerHTML = originalText;
                this.style.background = '';
            }, 1000);
        });
    });

    // ===== Smooth Card Entrance Animations =====
    const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.food-card, .order-card, .cook-order-card, .delivery-task-card, .my-dish-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s cubic-bezier(.16,1,.3,1), transform 0.5s cubic-bezier(.16,1,.3,1)';
        observer.observe(card);
    });

    // ===== Payment Option Toggle =====
    document.querySelectorAll('.payment-option input[type="radio"]').forEach(radio => {
        radio.addEventListener('change', () => {
            document.querySelectorAll('.payment-card').forEach(card => card.classList.remove('active-payment'));
            radio.closest('.payment-option').querySelector('.payment-card').classList.add('active-payment');
        });
    });
});

// Fade-in keyframe
const style = document.createElement('style');
style.textContent = '@keyframes fadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }';
document.head.appendChild(style);
