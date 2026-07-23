document.addEventListener('DOMContentLoaded', function () {

    /* ---------- Navbar scroll effect ---------- */
    const header = document.getElementById('siteHeader');
    if (header) {
        window.addEventListener('scroll', () => {
            header.classList.toggle('scrolled', window.scrollY > 20);
        });
    }

    /* ---------- Mobile menu toggle ---------- */
    const mobileToggle = document.getElementById('mobileToggle');
    const navLinks = document.getElementById('navLinks');
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('mobile-open');
            const icon = mobileToggle.querySelector('i');
            icon.classList.toggle('fa-bars');
            icon.classList.toggle('fa-xmark');
        });
    }

    /* ---------- Toast auto-dismiss ---------- */
    document.querySelectorAll('.toast-item').forEach(toast => {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    });

    /* ---------- Add to cart animation ---------- */
    document.querySelectorAll('.add-to-cart').forEach(btn => {
        btn.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (!href || !href.startsWith('/add_to_cart/')) return;

            e.preventDefault();
            const rect = this.getBoundingClientRect();
            const cartBtn = document.querySelector('.cart-btn');
            const flying = document.createElement('div');
            flying.innerHTML = '<i class="fa-solid fa-cart-shopping" style="font-size:20px;color:#6366f1;"></i>';
            flying.style.cssText = 'position:fixed;left:' + rect.left + 'px;top:' + rect.top + 'px;z-index:10000;transition:all 0.7s cubic-bezier(0.4,0,0.2,1);pointer-events:none;';
            document.body.appendChild(flying);

            let dx = 300, dy = -200;
            if (cartBtn) {
                const cartRect = cartBtn.getBoundingClientRect();
                dx = cartRect.left - rect.left;
                dy = cartRect.top - rect.top;
            }

            requestAnimationFrame(() => {
                flying.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(0.3)';
                flying.style.opacity = '0';
            });

            setTimeout(() => {
                flying.remove();
                window.location.href = href;
            }, 700);
        });
    });

    /* ---------- Wishlist (localStorage) ---------- */
    const WISHLIST_KEY = 'faraashi_wishlist';
    function getWishlist() {
        try { return JSON.parse(localStorage.getItem(WISHLIST_KEY)) || []; }
        catch (e) { return []; }
    }
    function saveWishlist(list) { localStorage.setItem(WISHLIST_KEY, JSON.stringify(list)); }

    document.querySelectorAll('.wishlist-btn').forEach(btn => {
        const id = btn.dataset.productId;
        if (getWishlist().includes(id)) {
            btn.classList.add('active');
            btn.querySelector('i').classList.replace('fa-regular', 'fa-solid');
        }
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const list = getWishlist();
            const idx = list.indexOf(id);
            const icon = this.querySelector('i');
            if (idx > -1) {
                list.splice(idx, 1);
                this.classList.remove('active');
                icon.classList.replace('fa-solid', 'fa-regular');
            } else {
                list.push(id);
                this.classList.add('active');
                icon.classList.replace('fa-regular', 'fa-solid');
            }
            saveWishlist(list);
        });
    });

    /* ---------- Quantity stepper ---------- */
    document.querySelectorAll('.qty-stepper').forEach(stepper => {
        const input = stepper.querySelector('input');
        const max = parseInt(input?.dataset.max || '99', 10);
        stepper.querySelector('.qty-minus')?.addEventListener('click', () => {
            input.value = Math.max(1, (parseInt(input.value, 10) || 1) - 1);
        });
        stepper.querySelector('.qty-plus')?.addEventListener('click', () => {
            input.value = Math.min(max, (parseInt(input.value, 10) || 1) + 1);
        });
    });

    /* ---------- Product filters ---------- */
    const productGrid = document.getElementById('productGrid');
    if (productGrid) {
        const cards = Array.from(productGrid.querySelectorAll('.product-card-col'));
        const categoryChecks = document.querySelectorAll('.category-filter-check');
        const priceRange = document.getElementById('priceRangeInput');
        const priceValueLabel = document.getElementById('priceRangeValue');
        const sortSelect = document.getElementById('sortSelect');
        const searchBox = document.getElementById('productSearchBox');
        const noResults = document.getElementById('productsNoResults');

        function activeCategories() {
            const checked = Array.from(categoryChecks).filter(c => c.checked).map(c => c.value);
            return checked.length ? checked : null;
        }

        function applyFilters() {
            const cats = activeCategories();
            const maxPrice = priceRange ? parseInt(priceRange.value, 10) : Infinity;
            const query = (searchBox?.value || '').trim().toLowerCase();
            let visible = 0;
            cards.forEach(card => {
                const price = parseFloat(card.dataset.price || '0');
                const cat = card.dataset.category || '';
                const name = (card.dataset.name || '').toLowerCase();
                const show = (!cats || cats.includes(cat)) && price <= maxPrice && (!query || name.includes(query));
                card.style.display = show ? '' : 'none';
                if (show) visible++;
            });
            if (noResults) noResults.style.display = visible === 0 ? 'block' : 'none';
        }

        function applySort() {
            if (!sortSelect) return;
            const mode = sortSelect.value;
            const sorted = [...cards].sort((a, b) => {
                const pa = parseFloat(a.dataset.price || '0');
                const pb = parseFloat(b.dataset.price || '0');
                if (mode === 'price-low') return pa - pb;
                if (mode === 'price-high') return pb - pa;
                if (mode === 'name') return (a.dataset.name || '').localeCompare(b.dataset.name || '');
                return 0;
            });
            sorted.forEach(card => productGrid.appendChild(card));
        }

        categoryChecks.forEach(c => c.addEventListener('change', applyFilters));
        if (priceRange) {
            priceRange.addEventListener('input', () => {
                if (priceValueLabel) priceValueLabel.textContent = '₹' + priceRange.value;
                applyFilters();
            });
        }
        if (searchBox) searchBox.addEventListener('input', applyFilters);
        if (sortSelect) sortSelect.addEventListener('change', applySort);

        applyFilters();
    }

    /* ---------- Free shipping progress bar ---------- */
    const shippingFill = document.getElementById('freeShippingFill');
    if (shippingFill) {
        const total = parseFloat(shippingFill.dataset.total || '0');
        const threshold = parseFloat(shippingFill.dataset.threshold || '999');
        shippingFill.style.width = Math.min(100, (total / threshold) * 100) + '%';
    }
});
