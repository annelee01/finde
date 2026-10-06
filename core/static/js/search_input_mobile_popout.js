// ============================
// search_input_mobile_popout.js
// Mobile searchbar functionality for ALL pages. Keep in separate file keep it a global element.
// ============================


// ============================
// MOBILE UTILITIES
// ============================

function isMobileDevice() {
    return window.innerWidth <= 768;
}

function normalizeUrl(url) {
    return url.endsWith('/') ? url : url + '/';
}

function updateMobileNavIcons() {
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        const linkHref = normalizeUrl(link.getAttribute('href'));
        const currentPath = normalizeUrl(window.location.pathname);
        
        if (linkHref === currentPath) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });
}

// ============================
// SHARED FUNCTIONS (use from main file if available)
// ============================
function handleSearchInput() {
    // Use shared function if available, otherwise implement locally
    if (typeof window.handleSearchInput === 'function') {
        return window.handleSearchInput();
    }

    const searchInput = document.getElementById('opensearch-input');
    const resetSearchButton = document.getElementById('reset-search');
    const filterSearchIcon = document.getElementById('filter-search-icon'); // Add this line
    
    if (!searchInput) return;

    // Function to update blue dot visibility
    function updateBlueDot() {
        if (!filterSearchIcon) return;
        
        const hasText = searchInput.value.trim().length > 0;
        
        if (hasText) {
            filterSearchIcon.classList.add('blue-dot');
        } else {
            filterSearchIcon.classList.remove('blue-dot');
        }
    }

    let debounceTimeout;
    searchInput.addEventListener('input', function () {
        clearTimeout(debounceTimeout);
        const searchQuery = this.value.trim();
        
        if (resetSearchButton) {
            resetSearchButton.style.display = searchQuery.length > 0 ? 'block' : 'none';
        }
        
        updateBlueDot();
    });
    
    // Add paste and cut event listeners
    searchInput.addEventListener('paste', function() {
        setTimeout(updateBlueDot, 10);
    });
    
    searchInput.addEventListener('cut', function() {
        setTimeout(updateBlueDot, 10);
    });
    
    // Check initial state on page load - ONLY based on actual input value
    const checkInitialState = () => {
        updateBlueDot(); // This only checks searchInput.value.trim().length > 0
        
        // REMOVED: Don't check URL parameters for blue dot
        // The blue dot should ONLY appear when there's text in the input field
    };

    // Check immediately and after delays to catch browser autofill
    checkInitialState();
    setTimeout(checkInitialState, 100);
    setTimeout(checkInitialState, 500);
}

function getCategoryIds() {
    // Use shared function if available, otherwise implement locally
    if (typeof window.getCategoryIds === 'function') {
        return window.getCategoryIds();
    }

    const selectedButtons = document.querySelectorAll('.dropdown-category.selected');
    return Array.from(selectedButtons).map(button => button.value);
}


// MAIN SMART RESET FUNCTION 
function smartResetSearch() {
    const searchInput = document.getElementById('opensearch-input');
    const resetSearchButton = document.getElementById('reset-search');
    const isBrowsePage = window.location.pathname === '/browse/';
    const filterSearchIcon = document.getElementById('filter-search-icon');
    
    if (isBrowsePage) {
        // On browse page: Smart reset based on curated filter state
        console.log('Doing smart reset on browse page');
        
        const searchbarPopout = document.getElementById('searchbar-container');
        const closeSearchbar = document.getElementById('close-searchbar');
        const resetLink = document.querySelector('.reset-searchbar-link');

        const isSearchbarVisible = searchbarPopout?.style.display === 'flex';

        // Clear the search input
        if (searchInput) searchInput.value = '';
        if (resetSearchButton) resetSearchButton.style.display = 'none';

        // Remove blue dot when clearing search
        if (filterSearchIcon) filterSearchIcon.classList.remove('blue-dot');

        // Clear result messages
        const resultsMessage = document.getElementById('results-message')?.querySelector('p');
        const noResultsMessage = document.getElementById('no-results-message');

        if (resultsMessage) {
            resultsMessage.textContent = '';
            resultsMessage.style.display = 'none';
        }
        if (noResultsMessage) {
            noResultsMessage.textContent = '';
            noResultsMessage.style.display = 'none';
        }
        if (resetLink) resetLink.style.display = 'none';

        // Smart URL handling based on curated filter state
        const urlParams = new URLSearchParams(window.location.search);
        
        // Check if there's an active curated filter
        const hasCuratedFilter = typeof window.activeCuratedFilter !== 'undefined' && window.activeCuratedFilter;
        
        if (hasCuratedFilter) {
            // If curated filter is active, only remove user query but keep curated terms
            
            // Remove user_query parameter but keep the curated query
            urlParams.delete('user_query');
            
            // Keep the main query with just curated terms
            if (window.curatedFilterQuery) {
                urlParams.set('query', window.curatedFilterQuery);
            }
            
            // Keep curated_filter parameter
            // (it should already be there, but ensure it stays)
            
        } else {
            // No curated filter, remove query entirely
            urlParams.delete('query');
            urlParams.delete('user_query');
            urlParams.delete('curated_filter');
        }
        
        history.pushState({}, '', `${window.location.pathname}?${urlParams.toString()}`);

        // Try to reload items on browse page
        const tryLoadItems = async () => {
            try {
                // Method 1: Try window functions first
                if (typeof window.loadItems === 'function' && typeof window.getURLParams === 'function') {
                    const currentSortBy = document.getElementById('dropdown-sortby')?.value || 'newlyAdded';
                    const urlData = window.getURLParams();
                    const currentCategoryIds = urlData.categoryIds || [];
                    const sizes = urlData.sizes || {};
                    const colors = urlData.colors || [];
                    const minPrice = urlData.minPrice || '';
                    const maxPrice = urlData.maxPrice || '';

                    // Smart query handling
                    let queryToUse = '';
                    let curatedFilterToUse = null;
                    
                    if (hasCuratedFilter) {
                        // Use only curated terms, no user search
                        queryToUse = window.curatedFilterQuery || '';
                        curatedFilterToUse = window.activeCuratedFilter;
                    } else {
                        // No curated filter, empty search
                        queryToUse = '';
                        curatedFilterToUse = null;
                    }

                    return await window.loadItems(queryToUse, 1, currentSortBy, currentCategoryIds, sizes, colors, minPrice, maxPrice, curatedFilterToUse);
                }

                // Method 2: Try dynamic import as fallback
                console.log('Trying dynamic import for loadItems');
                const browseModule = await import(window.HASHED_BROWSE_PATH);
                const currentSortBy = document.getElementById('dropdown-sortby')?.value || 'newlyAdded';
                const urlData = browseModule.getURLParams();
                const currentCategoryIds = urlData.categoryIds || [];
                const sizes = urlData.sizes || {};
                const colors = urlData.colors || [];
                const minPrice = urlData.minPrice || '';
                const maxPrice = urlData.maxPrice || '';

                // Smart query handling for fallback
                let queryToUse = '';
                let curatedFilterToUse = null;
                
                if (hasCuratedFilter) {
                    queryToUse = window.curatedFilterQuery || '';
                    curatedFilterToUse = window.activeCuratedFilter;
                } else {
                    queryToUse = '';
                    curatedFilterToUse = null;
                }

                return await browseModule.loadItems(queryToUse, 1, currentSortBy, currentCategoryIds, sizes, colors, minPrice, maxPrice, curatedFilterToUse);

            } catch (error) {
                console.error('All methods failed, reloading page:', error);
                // Ultimate fallback: reload the page
                window.location.reload();
            }
        };

        // Execute the loading
        tryLoadItems().then(() => {
            // Restore searchbar visibility if it was visible before
            if (isSearchbarVisible && searchbarPopout) {
                searchbarPopout.style.display = 'flex';
                if (closeSearchbar) closeSearchbar.style.display = 'inline';
            }

            if (searchInput) searchInput.focus();
        }).catch(error => {
            console.error('Error in tryLoadItems:', error);
        });

    } else {
        // On other pages: Just clear the input, no reload/redirect
        
        if (searchInput) {
            searchInput.value = '';
            searchInput.focus(); // Keep focus for better UX
        }
        
        if (resetSearchButton) {
            resetSearchButton.style.display = 'none';
        }
        
        // Remove blue dot when clearing search
        if (filterSearchIcon) filterSearchIcon.classList.remove('blue-dot');
        
        // Clear any result messages that might be showing
        const resultsMessage = document.getElementById('results-message')?.querySelector('p');
        const noResultsMessage = document.getElementById('no-results-message');
        const resetLink = document.querySelector('.reset-searchbar-link');

        if (resultsMessage) {
            resultsMessage.textContent = '';
            resultsMessage.style.display = 'none';
        }
        if (noResultsMessage) {
            noResultsMessage.style.display = 'none';
        }
        if (resetLink) {
            resetLink.style.display = 'none';
        }
    }
}

// ============================
// MOBILE SEARCH BEHAVIOR
// ============================

const searchInput = document.getElementById('opensearch-input');
const searchbarPopout = document.getElementById('searchbar-container');
const resetSearchButton = document.getElementById('reset-search');

let lastScrollTop = 0;
let isInputFocused = false;
let isSearchbarManuallyClosed = false;

// Mobile focus/blur handlers
if (searchInput) {
    searchInput.addEventListener('focus', () => { 
        isInputFocused = true; 
    });
    searchInput.addEventListener('blur', () => { 
        isInputFocused = false; 
    });
}

// Mobile scroll behavior for searchbar
window.addEventListener('scroll', () => {
    if (!isMobileDevice()) return;
    if (isInputFocused || isSearchbarManuallyClosed) return;
    if (searchInput && searchInput.value.trim().length > 0) return;

    let currentScroll = window.scrollY;
    if (currentScroll > lastScrollTop && searchbarPopout) {
        // Hide searchbar
        searchbarPopout.style.display = 'none';
        
        // ADDED: Remove active state from all searchbar icons
        const searchbarIcons = document.querySelectorAll('.searchbar-icon');
        searchbarIcons.forEach(icon => {
            icon.classList.remove('active');
        });
    }
    lastScrollTop = currentScroll <= 0 ? 0 : currentScroll;
});

// ============================
// BOTTOM NAV SCROLL BEHAVIOR
// ============================

const bottomNav = document.querySelector('.bottomnav-container');
if (bottomNav) {
    let lastScroll = 0;
    const scrollThreshold = 50;
    
    window.addEventListener('scroll', () => {
        const currentScroll = window.scrollY || window.pageYOffset;
        const scrollDirection = currentScroll > lastScroll ? 'down' : 'up';
        
        if (scrollDirection === 'down' && currentScroll > scrollThreshold) {
            bottomNav.style.transform = 'translateY(100%)';
        } else {
            bottomNav.style.transform = 'translateY(0)';
        }
        
        lastScroll = currentScroll;
    }, { passive: true });
}

// ============================
// MOBILE INITIALIZATION
// ============================

handleSearchInput();


// Use smartResetSearch for the reset button
if (resetSearchButton) {
    resetSearchButton.addEventListener('click', function (event) {
        event.preventDefault();
        smartResetSearch(); // Use the smart function directly
    });
}

// Use smartResetSearch for the clear search link
document.addEventListener('click', function(e) {
    if (e.target && e.target.id === 'clear-search-link') {
        e.preventDefault();
        smartResetSearch(); // Use the smart function directly
    }
});


// Check for existing query on page load for mobile
const urlParams = new URLSearchParams(window.location.search);
const existingQuery = urlParams.get('query');
const userQuery = urlParams.get('user_query');

//  Check URL parameters to determine if there's actual user input
const hasActualUserInput = (userQuery && userQuery.trim().length > 0) || 
                          (existingQuery && existingQuery.trim().length > 0 && !urlParams.get('curated_filter'));

// ONLY RUN MOBILE-SPECIFIC SEARCHBAR LOGIC ON MOBILE DEVICES
if (isMobileDevice()) {
    if (existingQuery && existingQuery.trim().length > 0 && hasActualUserInput) {
        if (searchbarPopout) {
            searchbarPopout.classList.add('active');
            searchbarPopout.style.display = 'flex';
        }
        
        const searchbarIcons = document.querySelectorAll('.searchbar-icon');
        searchbarIcons.forEach(icon => {
            icon.classList.add('active');
        });
        
        isSearchbarManuallyClosed = false;
        
        if (searchInput) {
            // Check for user_query parameter first (clean user input)
            if (userQuery) {
                searchInput.value = userQuery;
            } else if (existingQuery && !urlParams.get('curated_filter')) {
                // Only use existingQuery if there's no curated filter
                searchInput.value = existingQuery;
            } else {
                searchInput.value = '';
            }
            
            // Update blue dot after setting the input value
            const filterSearchIcon = document.getElementById('filter-search-icon');
            if (filterSearchIcon && searchInput.value.trim().length > 0) {
                filterSearchIcon.classList.add('blue-dot');
            }
        }

        if (resetSearchButton) resetSearchButton.style.display = 'block';
    } else {
        // Ensure searchbar is hidden when there's no user input - ONLY ON MOBILE
        
        if (searchbarPopout) {
            searchbarPopout.classList.remove('active');
            searchbarPopout.style.display = 'none';
        }
        
        const searchbarIcons = document.querySelectorAll('.searchbar-icon');
        searchbarIcons.forEach(icon => {
            icon.classList.remove('active');
        });
        
        if (searchInput) searchInput.value = '';
        if (resetSearchButton) resetSearchButton.style.display = 'none';
        
        const filterSearchIcon = document.getElementById('filter-search-icon');
        if (filterSearchIcon) filterSearchIcon.classList.remove('blue-dot');
    }
} else {
    // DESKTOP: Don't touch searchbar display, let CSS handle it
    
    // Still handle input value and blue dot on desktop
    if (searchInput) {
        // Check for user_query parameter first (clean user input)
        if (userQuery) {
            searchInput.value = userQuery;
        } else if (existingQuery && !urlParams.get('curated_filter')) {
            // Only use existingQuery if there's no curated filter
            searchInput.value = existingQuery;
        } else {
            searchInput.value = '';
        }
        
        // Update blue dot after setting the input value
        const filterSearchIcon = document.getElementById('filter-search-icon');
        if (filterSearchIcon && searchInput.value.trim().length > 0) {
            filterSearchIcon.classList.add('blue-dot');
        }
    }

    if (resetSearchButton && searchInput && searchInput.value.trim().length > 0) {
        resetSearchButton.style.display = 'block';
    }
}

// Update mobile nav icons
updateMobileNavIcons();

// ============================
// FIX CLOSE BUTTON VISIBILITY ON PAGE LOAD
// ============================
// Ensure close button is visible if searchbar is active on page load
function ensureCloseButtonVisibility() {
    const searchbarPopout = document.getElementById('searchbar-container');
    const closeSearchbar = document.getElementById('close-searchbar');
    
    if (searchbarPopout && closeSearchbar) {
        // If searchbar is active/visible, make sure close button is visible
        const isSearchbarActive = searchbarPopout.classList.contains('active') || 
                                 searchbarPopout.style.display === 'flex';
        
        if (isSearchbarActive) {
            closeSearchbar.style.display = 'inline';
        }
    }
}

// Run the fix after DOM is ready and after mobile setup
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureCloseButtonVisibility);
} else {
    ensureCloseButtonVisibility();
}

// Also run after a short delay to catch any async setup
setTimeout(ensureCloseButtonVisibility, 100);

// ============================
// STICKY FILTER BUTTON (Mobile - All Pages) with Slide Animation
// ============================

(function initStickyFilterButton() {
    // Get elements for filter functionality
    const filterButton = document.getElementById('filter-button');
    const buttonContainer = document.getElementById('button-filter');
    const tabContentMobile = document.getElementById('tab-content-mobile');
    const slideAnimation = document.querySelector('.slide-animation'); // Add this
    
    let stickyFilterButton = null;

    // Get all elements with the filter button class
    const filterButtons = document.querySelectorAll('.filter-button-trigger');

    // Function to trigger slide animation
    function triggerSlideAnimation() {
        if (slideAnimation) {
            slideAnimation.classList.add('active');
        }
    }

    // Function to close slide animation
    function closeSlideAnimation() {
        if (slideAnimation) {
            slideAnimation.classList.remove('active');
        }
    }

    // Add click functionality to all filter buttons
    filterButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Trigger the slide animation
            triggerSlideAnimation();
            
            // Trigger the original filter button's click event
            if (filterButton) {
                filterButton.click();
            }
            
            // Show the mobile nav if needed
            if (tabContentMobile) {
                tabContentMobile.style.display = 'block';
            }
        });
    });

    // Use the first available filter button for the sticky functionality
    const targetButton = filterButton || filterButtons[0];

    if ((filterButton || filterButtons.length > 0) && buttonContainer) {
        function createStickyFilterButton() {
            const stickyBtn = targetButton.cloneNode(true);
            stickyBtn.id = 'sticky-filter-button';
            
            // Copy all classes and styling
            stickyBtn.className = targetButton.className;
            
            // Add click functionality - trigger the original button
            stickyBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Trigger the slide animation
                triggerSlideAnimation();
                
                // Always trigger the original filterButton
                if (filterButton) {
                    filterButton.click();
                }
                
                // Show the mobile nav
                if (tabContentMobile) {
                    tabContentMobile.style.display = 'block';
                }
            });
            
            document.body.appendChild(stickyBtn);
            return stickyBtn;
        }

        // Create the sticky button
        stickyFilterButton = createStickyFilterButton();

        // Add event listener to original filter button if it exists
        if (filterButton) {
            filterButton.addEventListener('click', function(e) {
                // Don't prevent default here, let the original behavior happen
                triggerSlideAnimation();
            });
        }

        // Add close button functionality
        document.addEventListener('click', function(e) {
            // Check if clicked element is a close button
            if (e.target.closest('.close-button')) {
                e.preventDefault();
                closeSlideAnimation();
                
                // Hide the mobile nav
                if (tabContentMobile) {
                    tabContentMobile.style.display = 'none';
                }
                
                // Only scroll to top if it's the "Done" button (contains text, not SVG)
                const closeButton = e.target.closest('.close-button');
                const hasText = closeButton.textContent.trim().length > 0;

                // Scroll to top only if it has text content (Done button)
                if (hasText) {
                    window.scrollTo({
                        top: 0,
                        behavior: 'smooth'
                    });
                }
            }
        });

        // Function to handle scroll behavior for filter button
        function handleFilterScroll() {
            if (!stickyFilterButton || !buttonContainer) return;
            
            const buttonRect = buttonContainer.getBoundingClientRect();
            const isButtonVisible = buttonRect.bottom > 0 && buttonRect.top < window.innerHeight;
            
            // Only show sticky button on mobile devices
            const isMobile = window.innerWidth <= 768;
            
            if (!isButtonVisible && isMobile) {
                // Original button is scrolled out of view on mobile - show sticky button
                stickyFilterButton.classList.add('visible');
            } else {
                // Original button is visible or we're on desktop - hide sticky button
                stickyFilterButton.classList.remove('visible');
            }
        }

        // Add scroll event listener with throttling for better performance
        let filterTicking = false;
        window.addEventListener('scroll', function() {
            if (!filterTicking) {
                requestAnimationFrame(function() {
                    handleFilterScroll();
                    filterTicking = false;
                });
                filterTicking = true;
            }
        });

        // Add resize event listener
        window.addEventListener('resize', handleFilterScroll);

        // Check initial state
        handleFilterScroll();

        // Optional: Hide sticky button when mobile nav is open
        if (tabContentMobile) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.target === tabContentMobile && mutation.attributeName === 'style') {
                        const isNavOpen = tabContentMobile.style.display === 'block';
                        if (isNavOpen && stickyFilterButton) {
                            stickyFilterButton.classList.remove('visible');
                        } else {
                            handleFilterScroll(); // Re-evaluate when nav closes
                            closeSlideAnimation(); // Close slide animation when nav closes
                        }
                    }
                });
            });

            // Start observing the mobile nav for style changes
            observer.observe(tabContentMobile, { 
                attributes: true, 
                attributeFilter: ['style'] 
            });
        }

        // Expose filter button API
        window.StickyFilter = {
            refresh: handleFilterScroll,
            openSlide: triggerSlideAnimation,
            closeSlide: closeSlideAnimation
        };
    }
})();


// ============================
// STICKY BUTTONS FUNCTIONALITY
// ============================

(function() {
    'use strict';
    
    const CONFIG = {
        animation: { duration: 900, translateY: 74, easing: 'ease' }
    };

    // Get elements
    const elements = {
        searchbarIcons: document.querySelectorAll('.searchbar-icon'),
        searchbarContainer: document.getElementById('searchbar-container'),
        closeSearchbar: document.getElementById('close-searchbar'),
        searchInput: document.getElementById('opensearch-input'),
        stickyFilterButton: document.getElementById('sticky-filter-button'),
        originalFilterButton: document.querySelector('.filter-button-trigger')
    };

    // Create sticky search button if it doesn't exist
    let stickySearchButton = document.getElementById('sticky-search-button');
    if (!stickySearchButton) {
        stickySearchButton = document.createElement('button');
        stickySearchButton.id = 'sticky-search-button';
        stickySearchButton.className = 'search-button';
        stickySearchButton.setAttribute('aria-label', 'Open search');
        stickySearchButton.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 19 19" fill="none">
                <path d="M7.50837 14.3092C11.115 14.3092 14.0387 11.3855 14.0387 7.77887C14.0387 4.17227 11.115 1.24854 7.50837 1.24854C3.90176 1.24854 0.978027 4.17227 0.978027 7.77887C0.978027 11.3855 3.90176 14.3092 7.50837 14.3092Z" stroke="black" stroke-linecap="round" stroke-linejoin="round"></path>
                <path d="M12.1143 12.375L19.7257 19.9958" stroke="black" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
        `;
        document.body.appendChild(stickySearchButton);
    }

    // Animation functions
    const animateSearchbar = {
        open() {
            if (!elements.searchbarContainer) return;
            
            // Make container visible immediately (before animation)
            elements.searchbarContainer.style.display = 'flex';
            elements.searchbarContainer.style.opacity = '0';
            elements.searchbarContainer.style.transform = 'translateY(-20px) scale(0)';
            
            // Force reflow to ensure CSS changes are applied
            void elements.searchbarContainer.offsetHeight;
            
            // Start animation
            elements.searchbarContainer.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
            elements.searchbarContainer.style.opacity = '1';
            elements.searchbarContainer.style.transform = 'translateY(0) scale(1)';
            elements.searchbarContainer.classList.add('active');

            // Focus input - moved outside setTimeout for better reliability
            if (elements.searchInput) {
                elements.searchInput.focus();
            }
        },
        close() {
            if (!elements.searchbarContainer) return;
            
            // Add transition and transform with scale
            elements.searchbarContainer.style.transition = 'opacity 0.2s ease, transform 0.4s ease';
            elements.searchbarContainer.style.transform = 'translateY(-20px) scale(0)'; 
            elements.searchbarContainer.style.opacity = '0';
            
            setTimeout(() => {
                elements.searchbarContainer.classList.remove('active');
                elements.searchbarContainer.style.display = 'none';
            }, CONFIG.animation.duration);
        }
    };

    // Search actions
    const searchActions = {
        toggle() {
            const isActive = elements.searchbarContainer.classList.contains('active');
            isActive ? this.close() : this.open();
        },

        open() {
            animateSearchbar.open();
            stickySearchButton.classList.add('active');
            elements.searchbarIcons.forEach(icon => {
                icon.classList.add('active');
            });
        },

        close() {
            animateSearchbar.close();
            stickySearchButton.classList.remove('active');
            elements.searchbarIcons.forEach(icon => {
                icon.classList.remove('active');
            });
        }
    };

    // Button visibility management
    const updateButtonVisibility = () => {
        // Check if we're on browse page - hide sticky search button if not
        const isOnBrowsePage = window.location.pathname === '/browse' || window.location.pathname.startsWith('/browse/');
        const isMobile = window.innerWidth <= 768;
        
        // Handle original filter button (tablet and mobile only)
        if (elements.originalFilterButton) {
            if (isOnBrowsePage && isMobile) {
                elements.originalFilterButton.style.display = 'flex';
            } else {
                elements.originalFilterButton.style.display = 'none';
            }
        }
        
        // Hide both sticky buttons on desktop
        if (!isMobile) {
            stickySearchButton.classList.remove('visible');
            if (elements.stickyFilterButton) elements.stickyFilterButton.classList.remove('visible');
            return;
        }

        // Mobile behavior - check if original filter button is out of view
        const filterButton = document.getElementById('filter-button');
        let shouldShowBothButtons = false;
        
        if (filterButton) {
            const buttonRect = filterButton.getBoundingClientRect();
            const isFilterButtonOutOfView = buttonRect.bottom < 0 || buttonRect.top > window.innerHeight;
            shouldShowBothButtons = isFilterButtonOutOfView;
        }
        
        // Sticky filter button - show when original is out of view
        if (elements.stickyFilterButton) {
            elements.stickyFilterButton.classList.toggle('visible', shouldShowBothButtons);
        }
        
        // Sticky search button - show at the same time as filter button (only on browse page)
        if (isOnBrowsePage) {
            stickySearchButton.classList.toggle('visible', shouldShowBothButtons);
        } else {
            stickySearchButton.classList.remove('visible');
        }
    };
    
    // Event handlers
    const setupEventListeners = () => {
        // Search button click
        stickySearchButton.addEventListener('click', (e) => {
            e.preventDefault();
            searchActions.open();
        });

        // Original search icon click
        elements.searchbarIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                searchActions.toggle();
            });
        });

        // Close searchbar
        if (elements.closeSearchbar) {
            elements.closeSearchbar.addEventListener('click', (e) => {
                e.preventDefault();
                searchActions.close();
            });
        }

        // Search form submission
        const searchForm = document.getElementById('search-form');

        if (searchForm) {
            searchForm.addEventListener('submit', function (event) {

                event.preventDefault();
                window.scrollTo({ top: 0, behavior: 'smooth' });
                if (searchInput) searchInput.blur();

                const searchQuery = searchInput ? searchInput.value.trim() : '';
                
                const sortBy = document.getElementById('dropdown-sortby')?.value || 'newlyAdded';
                
                // Get current filter states from the UI
                const categoryIds = getCategoryIds();
                
                // Get current size filters from selected size buttons
                const currentSizes = {};
                const selectedSizeButtons = document.querySelectorAll('.button-size.selected');
                
                selectedSizeButtons.forEach((button) => {
                    const category = button.getAttribute('data-category').replace(/\s+/g, '_');
                    const value = button.value;
                    
                    if (!currentSizes[category]) {
                        currentSizes[category] = [];
                    }
                    if (!currentSizes[category].includes(value)) {
                        currentSizes[category].push(value);
                    }
                });

                // Get current color filters from selected color buttons
                const currentColors = [];
                const selectedColorSwatches = document.querySelectorAll('.button-color .color-swatch.selected');
                
                selectedColorSwatches.forEach((swatch) => {
                    const colorButton = swatch.closest('.button-color');
                    if (colorButton && !currentColors.includes(colorButton.value)) {
                        currentColors.push(colorButton.value);
                    }
                });

                // Get current price filters from input fields
                const minPrice = document.getElementById('min-price')?.value || '';
                const maxPrice = document.getElementById('max-price')?.value || '';

                // Handle curated filter logic
                let finalSearchQuery = searchQuery;
                let currentCuratedFilter = null;
                
                // Check if there's an active curated filter (access from window/global scope)
                if (typeof window.activeCuratedFilter !== 'undefined' && window.activeCuratedFilter) {
                    currentCuratedFilter = window.activeCuratedFilter;
                    
                    // Get curated filter terms
                    let curatedTerms = '';
                    if (typeof window.curatedFilterQuery !== 'undefined' && window.curatedFilterQuery) {
                        curatedTerms = window.curatedFilterQuery;
                    } else if (typeof window.CURATED_FILTERS !== 'undefined' && window.CURATED_FILTERS[currentCuratedFilter]) {
                        // Fallback: build curated terms from config
                        const config = window.CURATED_FILTERS[currentCuratedFilter];
                        const allTerms = [];
                        if (config.keywords) allTerms.push(...config.keywords);
                        if (config.materials) allTerms.push(...config.materials);
                        if (config.brands) allTerms.push(...config.brands);
                        curatedTerms = allTerms.join(' ');
                    }
                    
                    // Combine user search with curated terms
                    if (searchQuery && curatedTerms) {
                        finalSearchQuery = `${searchQuery} ${curatedTerms}`;
                    } else if (curatedTerms) {
                        finalSearchQuery = curatedTerms;
                    }
                }

                // CHECK FOR REDIRECT FIRST - before any async operations
                if (window.location.pathname !== '/browse/') {
                    
                    // Build complete URL with all current parameters
                    const finalUrlParams = new URLSearchParams();
                    
                    // Add the combined search query
                    if (finalSearchQuery) finalUrlParams.set('query', finalSearchQuery);
                    
                    // Add user_query parameter to preserve original user input
                    if (searchQuery) finalUrlParams.set('user_query', searchQuery);
                    
                    // Add curated filter parameter
                    if (currentCuratedFilter) finalUrlParams.set('curated_filter', currentCuratedFilter);
                    
                    // Add sorting
                    finalUrlParams.set('sort_by', sortBy);
                    finalUrlParams.set('page', '1');
                    
                    // Add category filters
                    categoryIds.forEach(id => finalUrlParams.append('categoryId', id));
                    
                    // Add size parameters
                    for (const [category, values] of Object.entries(currentSizes)) {
                        if (values.length > 0) {
                            finalUrlParams.append('size_category', category);
                            finalUrlParams.append('size_value', values.join(','));
                        }
                    }
                    
                    // Add color filters
                    currentColors.forEach(color => finalUrlParams.append('color', color));
                    
                    // Add price filters
                    if (minPrice) finalUrlParams.set('min_price', minPrice);
                    if (maxPrice) finalUrlParams.set('max_price', maxPrice);

                    const redirectUrl = `/browse/?${finalUrlParams.toString()}`;
                    
                    // Navigate with complete URL
                    window.location.href = redirectUrl;
                    return; // Exit early to prevent further execution
                }

                // ONLY EXECUTE THE REST IF WE'RE ALREADY ON /browse/ PAGE

                const noResultsMessage = document.getElementById('no-results-message');
                const resultsMessage = document.getElementById('results-message')?.querySelector('p');
                const resetLink = document.querySelector('.reset-searchbar-link');

                // Update URL with search query first
                const urlParams = new URLSearchParams(window.location.search);
                
                if (finalSearchQuery) {
                    urlParams.set('query', finalSearchQuery);
                } else {
                    urlParams.delete('query');
                }
                
                // Add user_query parameter to preserve original user input
                if (searchQuery) {
                    urlParams.set('user_query', searchQuery);
                } else {
                    urlParams.delete('user_query');
                }
                
                // Add curated filter parameter
                if (currentCuratedFilter) {
                    urlParams.set('curated_filter', currentCuratedFilter);
                } else {
                    urlParams.delete('curated_filter');
                }
                
                history.pushState({}, '', `${window.location.pathname}?${urlParams.toString()}`);

                // Check if loadItems function exists
                if (typeof loadItems !== 'function') {
                    console.error('❌ loadItems function not found!');
                    return;
                }

                // Pass curated filter parameter to loadItems
                loadItems(finalSearchQuery, 1, sortBy, categoryIds, currentSizes, currentColors, minPrice, maxPrice, currentCuratedFilter)
                    .then(response => {
                        const items = response.results;
                        const hasActiveFilters = categoryIds.length > 0 || 
                                            Object.keys(currentSizes).length > 0 || 
                                            currentColors.length > 0 || 
                                            minPrice || maxPrice;

                        if (noResultsMessage) {
                            noResultsMessage.style.display = (!items.length && hasActiveFilters) ? 'block' : 'none';
                        }

                        // Show only user's search term in results message
                        if (searchQuery.length > 0 && resultsMessage) {
                            resultsMessage.innerHTML = items.length > 0 ? 
                                `Results for "${searchQuery}" <br><a href="#" id="clear-search-link">Clear Search</a>` : 
                                `No results for "${searchQuery}" <br><a href="#" id="clear-search-link">Clear Search</a>`;
                            resultsMessage.style.display = 'block';
                            if (resetLink) resetLink.style.display = 'block';
                        } else if (resultsMessage) {
                            resultsMessage.style.display = 'none';
                            if (resetLink) resetLink.style.display = 'none';
                        }

                        // Check if updateURLParams function exists
                        if (typeof updateURLParams !== 'function') {
                            return;
                        }

                        // Pass curated filter parameter to updateURLParams
                        updateURLParams(finalSearchQuery, 1, sortBy, categoryIds, currentSizes, currentColors, minPrice, maxPrice, currentCuratedFilter);
                        
                    })
                    .catch(error => {
                        console.error('❌ Error loading items:', error);
                        if (resultsMessage) {
                            resultsMessage.textContent = `Error loading results for "${searchQuery}"`;
                            resultsMessage.style.display = 'block';
                            if (resetLink) resetLink.style.display = 'block';
                        }
                    });
            });
        }

        // Scroll/resize events with throttling
        let ticking = false;
        const handleScrollResize = () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    updateButtonVisibility();
                    ticking = false;
                });
                ticking = true;
            }
        };
        
        window.addEventListener('scroll', handleScrollResize);
        window.addEventListener('resize', handleScrollResize);
    };

    // Initialize
    const init = () => {
        setupEventListeners();
        updateButtonVisibility();
        
        // Initial check in case we're already scrolled
        setTimeout(updateButtonVisibility, 100);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    window.StickySearch = {
        toggle: searchActions.toggle,
        close: searchActions.close,
        refresh: updateButtonVisibility
    };
})();


// ============================
// PERSISTENT SEARCH INPUT SYNC
// ============================

function syncPersistentSearchInput() {
    const persistentSearchInput = document.getElementById('persistent-opensearch-input');
    const persistentResetButton = document.getElementById('persistent-reset-search');
    
    if (!persistentSearchInput) return;
    
    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const existingQuery = urlParams.get('query');
    const userQuery = urlParams.get('user_query');
    
    // Determine what to show in the persistent input
    // Priority: user_query > query (if no curated filter)
    let valueToShow = '';
    
    if (userQuery && userQuery.trim().length > 0) {
        valueToShow = userQuery;
    } else if (existingQuery && existingQuery.trim().length > 0 && !urlParams.get('curated_filter')) {
        valueToShow = existingQuery;
    }
    
    // Set the value
    persistentSearchInput.value = valueToShow;
    
    // Show/hide reset button
    if (persistentResetButton) {
        persistentResetButton.style.display = valueToShow.length > 0 ? 'block' : 'none';
    }
}

// Handle persistent search input changes
function handlePersistentSearchInput() {
    const persistentSearchInput = document.getElementById('persistent-opensearch-input');
    const persistentResetButton = document.getElementById('persistent-reset-search');
    
    if (!persistentSearchInput) return;
    
    // Sync with main search input
    const mainSearchInput = document.getElementById('opensearch-input');
    
    // Input event handler
    persistentSearchInput.addEventListener('input', function() {
        const value = this.value.trim();
        
        // Show/hide reset button
        if (persistentResetButton) {
            persistentResetButton.style.display = value.length > 0 ? 'block' : 'none';
        }
        
        // Sync with main search input if it exists
        if (mainSearchInput) {
            mainSearchInput.value = this.value;
            // Trigger input event on main search to update its UI
            mainSearchInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    });
    
    // Reset button handler
    if (persistentResetButton) {
        persistentResetButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Use the smart reset function
            smartResetSearch();
            
            // Also clear persistent input
            persistentSearchInput.value = '';
            this.style.display = 'none';
        });
    }
}

// Handle persistent search form submission
function handlePersistentSearchForm() {
    const persistentSearchForm = document.getElementById('persistent-search-form');
    const mainSearchForm = document.getElementById('search-form');
    
    if (!persistentSearchForm) return;
    
    persistentSearchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // If main search form exists, trigger its submit
        if (mainSearchForm) {
            // Copy value to main input first
            const persistentInput = document.getElementById('persistent-opensearch-input');
            const mainInput = document.getElementById('opensearch-input');
            
            if (persistentInput && mainInput) {
                mainInput.value = persistentInput.value;
            }
            
            // Trigger main form submit
            mainSearchForm.dispatchEvent(new Event('submit', { cancelable: true }));
        } else {
            // Fallback: handle submission directly
            const searchQuery = document.getElementById('persistent-opensearch-input')?.value.trim() || '';
            
            // Redirect to browse page with query
            const urlParams = new URLSearchParams();
            if (searchQuery) {
                urlParams.set('query', searchQuery);
                urlParams.set('user_query', searchQuery);
            }
            
            window.location.href = `/browse/?${urlParams.toString()}`;
        }
    });
}

// Initialize persistent search functionality
function initPersistentSearch() {
    syncPersistentSearchInput();
    handlePersistentSearchInput();
    handlePersistentSearchForm();
    
    // Also sync whenever the main input changes
    const mainSearchInput = document.getElementById('opensearch-input');
    if (mainSearchInput) {
        mainSearchInput.addEventListener('input', function() {
            const persistentInput = document.getElementById('persistent-opensearch-input');
            if (persistentInput) {
                persistentInput.value = this.value;
                
                // Update persistent reset button
                const persistentResetButton = document.getElementById('persistent-reset-search');
                if (persistentResetButton) {
                    persistentResetButton.style.display = this.value.trim().length > 0 ? 'block' : 'none';
                }
            }
        });
    }
}

// Add to the existing initialization
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPersistentSearch);
} else {
    initPersistentSearch();
}

// Also update smartResetSearch to handle persistent input
const originalSmartResetSearch = smartResetSearch;
smartResetSearch = function() {
    // Call original function
    originalSmartResetSearch();
    
    // Also clear persistent input
    const persistentInput = document.getElementById('persistent-opensearch-input');
    const persistentResetButton = document.getElementById('persistent-reset-search');
    
    if (persistentInput) {
        persistentInput.value = '';
    }
    if (persistentResetButton) {
        persistentResetButton.style.display = 'none';
    }
};