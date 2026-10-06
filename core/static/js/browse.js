// ============================
// browse.js 
// ============================

// Only initialize if loaded directly (not as module)
if (!window.browseInitialized && !window.importedAsModule) {
    window.browseInitialized = true;
    document.addEventListener('DOMContentLoaded', initializePageState);
}

window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
});
window.updateButtonStates = updateButtonStates;

// Export the specific functions needed by search_input.js
export { getURLParams, loadItems };


let favoritesCache = null;
let favoritesCacheTime = null;
const CACHE_DURATION = 5 * 60 * 1000; // Increase to 5 minutes
const STORAGE_KEY = 'favorites_backup';

const fetchFavoritedItemIds = async (forceRefresh = false) => {

    const now = Date.now();
    const isCacheValid = favoritesCache && favoritesCacheTime && 
                        (now - favoritesCacheTime) < CACHE_DURATION;
    
    // IMMEDIATE RETURN for cache hits
    if (!forceRefresh && isCacheValid) {
        return Promise.resolve(favoritesCache); // Return resolved promise immediately
    }
    
    // Try localStorage backup SYNCHRONOUSLY first
    if (!forceRefresh && !isCacheValid) {
        try {
            const backup = localStorage.getItem(STORAGE_KEY);
            if (backup) {
                const parsed = JSON.parse(backup);
                if (parsed.timestamp && (now - parsed.timestamp) < CACHE_DURATION * 2) {
                    favoritesCache = parsed.data;
                    favoritesCacheTime = parsed.timestamp;
                    return Promise.resolve(parsed.data); // Return immediately
                }
            }
        } catch (e) {
            console.warn('Failed to parse localStorage backup:', e);
        }
    }
    
    // Only fetch if absolutely necessary
    try {

        // Optimize fetch with keep-alive and compression hints
        const response = await fetch('/api/favorite-items/', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'max-age=300' // 5 minutes
            },
            // Add keep-alive for connection reuse
            keepalive: true
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: Failed to fetch favorited items`);
        }

        const favoritedData = await response.json();
        const favoritedItemIds = favoritedData.favoritedItemIds || [];
        
        // Cache immediately
        favoritesCache = favoritedItemIds;
        favoritesCacheTime = now;
        
        // Background localStorage save (don't block)
        setTimeout(() => {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify({
                    data: favoritedItemIds,
                    timestamp: now
                }));
            } catch (e) {
                console.warn('Failed to save to localStorage:', e);
            }
        }, 0);
        
        return favoritedItemIds;
    } catch (error) {
        console.error('Error fetching favorited items:', error);
        
        // Return stale cache or empty array
        return favoritesCache || [];
    }
};



function renderSize(item) {
    const sizeFields = ['us_shoe_size', 'size', 'hat_size', 'ring_size', 'waist_size', 'bra_size', 'bottoms_size'];
    
    for (const field of sizeFields) {
        const value = item[field];
        if (value && 
            value !== 'None' && 
            value.toString().trim() !== '') {
            
            const trimmedValue = value.toString().trim();
            
             // Special handling for shoe sizes - include width if available
            if (field === 'us_shoe_size' && item.shoe_size_width && 
                item.shoe_size_width !== 'None' && 
                item.shoe_size_width.toString().trim() !== '') {
                
                const widthCode = item.shoe_size_width.toString().trim();
                const widthLabel = shoeWidthLabels[widthCode] || widthCode; // Use label or fallback to original
                
                // Split by spaces to find multiple values for shoe size
                const parts = trimmedValue.split(/\s+/);
                
                if (parts.length > 1) {
                    // Multiple shoe sizes found - show as range with width
                    const first = parts[0];
                    const last = parts[parts.length - 1];
                    return `${first} to ${last} ${widthLabel}`;
                } else {
                    // Single shoe size with width
                    return `${trimmedValue} ${widthLabel}`;
                }
            }
            
            // Regular size handling (non-shoe sizes or shoes without width)
            // Split by spaces to find multiple values
            const parts = trimmedValue.split(/\s+/);
            
            if (parts.length > 1) {
                // Multiple values found - show as range
                const first = parts[0];
                const last = parts[parts.length - 1];
                return `${first} to ${last}`;
            } else {
                // Single value - return as is
                return trimmedValue;
            }
        }
    }
    
    return 'Unmarked Size';
}

// Create an intersection observer
// Track which rows have been revealed
const revealedRows = new Set();


// Get mapped category names by categoryId
function getCategoryNameById(categoryId) {
    if (!categoryId || !window.CATEGORY_NAMES) {
        return null;
    }
    
    const categoryIdStr = categoryId.toString();
    
    // Find the category in the category_names array
    const category = window.CATEGORY_NAMES.find(cat => cat.id === categoryIdStr);
    
    if (category && category.name) {
        let categoryName = category.name;
        
         // Specific replacements
        if (categoryName.toLowerCase() === 'suits & sets') {
            return 'Set';
        }

        // Words that should stay plural or unchanged
        const keepAsIs = [
            'boots', 'dress', 'earrings','eyeglasses', 'flats', 'glasses', 'heels', 
            'panties', 'pajamas', 'pants', 'loafers', 'jeans', 
            'shorts', 'shoes', 'sneakers', 'sunglasses', 'wedges'
        ];
        
        // Special cases for words ending in 'ses' that only need 's' removed
        const removeOnlyS = ['purses']; 
        
        // Remove trailing 'es' or 's' to make singular, except for special cases
        if (!keepAsIs.includes(categoryName.toLowerCase()) && categoryName.length > 2) {
            if (removeOnlyS.includes(categoryName.toLowerCase())) {
                // Just remove the 's' for these special cases
                categoryName = categoryName.slice(0, -1);
            } else if (categoryName.endsWith('es')) {
                // Remove 'es' ending (e.g., 'dresses' -> 'dress', 'watches' -> 'watch')
                categoryName = categoryName.slice(0, -2);
            } else if (categoryName.endsWith('s') && categoryName.length > 1) {
                // Remove 's' ending (e.g., 'shoes' -> 'shoe', 'bags' -> 'bag')
                categoryName = categoryName.slice(0, -1);
            }
        }

        return categoryName;
    }
    
    return null;
}


// Helper function to truncate text by words
function truncateByWords(text, maxLength) {
    if (text.length <= maxLength) return text;
    
    const words = text.split(' ');
    let truncated = '';
    
    for (let word of words) {
        if ((truncated + word).length > maxLength - 3) { // -3 for "..."
            break;
        }
        truncated += (truncated ? ' ' : '') + word;
    }
    
    return truncated + '...';
}


// Create an intersection observer for fade-in animations only
const fadeInObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            
            // Add loaded class for fade-in animation
            img.classList.add('loaded');
            
            // Stop observing this image once it's animated in
            fadeInObserver.unobserve(img);
        }
    });
}, {
    rootMargin: '50px', // Start animation slightly before entering viewport
    threshold: 0.1
});

// CLEANUP ON PAGE UNLOAD
window.addEventListener('beforeunload', () => {
    if (typeof fadeInObserver !== 'undefined') {
        fadeInObserver.disconnect();
    }
    // Clear any pending timers
    clearTimeout(priceTimeout);
});

// Shared function to create a single item element
function createItemElement(item, index, columnsPerRow, favoritedItemIds, options = {}) {
    const { 
        includePDPButton = true, 
        includeVisitButton = true, 
        observeImages = true 
    } = options;

    const itemContainer = document.createElement('div');
    itemContainer.classList.add('item-container');
    itemContainer.dataset.title = item.title;
    itemContainer.dataset.categoryId = item.categoryId;

    const anchor = document.createElement('a');
    anchor.style.position = 'relative';

    // Make image clickable for PDP
    anchor.addEventListener('click', (event) => {
        event.preventDefault();
        console.log('Opening PDP for:', item.title);
        openPDP(item);
    });

    const img = document.createElement('img');
    
    // ✨ ALWAYS SET SRC IMMEDIATELY - no lazy loading of src
    img.src = `https://finde-media.s3.amazonaws.com/${item.gallery_url}`;
    img.alt = item.title;
    img.classList.add('item-image');
    
    // Calculate and store row number (keep for compatibility)
    const row = Math.floor(index / columnsPerRow);
    img.dataset.row = row;

    // Handle animation based on options
    if (observeImages) {
        // For regular browse results: observe for fade-in animation
        // Image src loads immediately, but animation waits for viewport
        fadeInObserver.observe(img);
    } else {
        // For featured items or other cases: immediate animation
        img.classList.add('loaded');
    }

    // Create overlay with conditional buttons
    const overlay = document.createElement('div');
    overlay.className = 'overlay';

    // Visit button
    if (includeVisitButton) {
        const visitButton = document.createElement('button');
        visitButton.innerHTML = 'Visit';
        visitButton.className = 'overlay-button';
        visitButton.addEventListener('click', (event) => {
            event.stopPropagation();
            window.open(item.item_web_url, '_blank');
        });
        overlay.appendChild(visitButton);
    }

    // Favorite button
    const favoriteButton = createFavoriteButton(item, favoritedItemIds.includes(item.item_id));
    favoriteButton.addEventListener('click', (event) => {
        event.stopPropagation();
        event.preventDefault();
    });
    overlay.appendChild(favoriteButton);

    anchor.appendChild(img);
    anchor.appendChild(overlay);
    itemContainer.appendChild(anchor);

    // Item brand and details
    const itemBrand = document.createElement('span');
    itemBrand.target = "_blank";
    itemBrand.className = 'overflow-hidden item-brand';

    const brand = item.brand ? item.brand : 'Vintage';
    const sizeText = renderSize(item);
    const categoryId = item.categoryId;
    const categoryName = getCategoryNameById(categoryId);
    const maxTextLength = 29;

    // Build the display text
    if (sizeText) {
        if (categoryName) {
            const brandCategoryText = truncateByWords(`${brand} ${categoryName}`, maxTextLength);
            itemBrand.innerHTML = `<p class="caption1-semibold mt-3">${sizeText}</p><p class="caption1-regular">${brandCategoryText}</p>`;
        } else {
            const brandText = truncateByWords(brand, maxTextLength);
            itemBrand.innerHTML = `<p class="caption1-semibold mt-3">${sizeText}</p><p class="caption1-regular">${brandText}</p>`;
        }
    } else {
        if (categoryName) {
            const brandCategoryText = truncateByWords(`${brand} ${categoryName}`, maxTextLength);
            itemBrand.innerHTML = `<p class="caption1-semibold mt-3">None</p><p class="caption1-regular">${brandCategoryText}</p>`;
        } else {
            const brandText = truncateByWords(brand, maxTextLength);
            itemBrand.innerHTML = `<p class="caption1-semibold mt-3">None</p><p class="caption1-regular">${brandText}</p>`;
        }
    }

    const itemPrice = document.createElement('p');
    itemPrice.className = 'item-price caption1-regular';
    const formattedPrice = parseFloat(item.price) || 0;
    itemPrice.textContent = `$${formattedPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    itemContainer.appendChild(itemBrand);
    itemContainer.appendChild(itemPrice);

    return itemContainer;
}


function renderFeaturedItems(featuredItems, favoritedItemIds) {
    const featuredContainer = document.getElementById('featured-results');
    if (!featuredContainer) return;
    
    featuredContainer.innerHTML = '';
    
    if (!featuredItems || featuredItems.length === 0) {
        document.getElementById('featured-section').style.display = 'none';
        return;
    }
    
    document.getElementById('featured-section').style.display = 'block';
    
    const getColumnsPerRow = () => {
        const width = window.innerWidth;
        if (width >= 1024) return 6;
        else if (width >= 768) return 4;
        else return 2;
    };
    
    const columnsPerRow = getColumnsPerRow();
    
    featuredItems.forEach(function(item, index) {
        const itemElement = createItemElement(item, index, columnsPerRow, favoritedItemIds, {
            includePDPButton: true,
            includeVisitButton: true,
            observeImages: false // Featured items don't need image observer
        });
        
        featuredContainer.appendChild(itemElement);
    });
}


function renderItems(items, favoritedItemIds) {
    // Clear any existing observer
    if (typeof fadeInObserver !== 'undefined') {
        fadeInObserver.disconnect();
    }
    
    const resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';
    
    if (items.length === 0) {
        resultsContainer.innerHTML = '<p>No results found.<br>Try fewer filters.</p>';
        return;
    }
    
    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();
    
    const getColumnsPerRow = () => {
        const width = window.innerWidth;
        if (width >= 1024) return 6;
        else if (width >= 768) return 4;
        else return 2;
    };
    
    const columnsPerRow = getColumnsPerRow();
    
    // Batch DOM operations
    items.forEach(function(item, index) {
        const itemElement = createItemElement(item, index, columnsPerRow, favoritedItemIds, {
            includePDPButton: true,
            includeVisitButton: true,
            observeImages: true // This now means "observe for animation" not "lazy load src"
        });
        
        fragment.appendChild(itemElement);
    });
    
    // Single DOM update
    resultsContainer.appendChild(fragment);
}



// Measurements display for pdp
function formatDetailedMeasurements(item) {
    const measurements = [
        { key: 'us_shoe_size', label: 'US Shoe Size', value: item.us_shoe_size },
        { key: 'shoe_size_width', label: 'Shoe Width', value: item.shoe_size_width },
        { key: 'hat_size', label: 'Hat Size', value: item.hat_size },
        { key: 'chest_size', label: 'Chest', value: item.chest_size },
        { key: 'bra_size', label: 'Bra Size', value: item.bra_size },
        { key: 'waist_size', label: 'Waist', value: item.waist_size },
        { key: 'hip_size', label: 'Hip', value: item.hip_size },
        { key: 'waist_to_hem', label: 'Waist to Hem', value: item.waist_to_hem },
        { key: 'inseam', label: 'Inseam', value: item.inseam },
        { key: 'shoulder_to_shoulder', label: 'Shoulder to Shoulder', value: item.shoulder_to_shoulder },
        { key: 'shoulder_to_hem', label: 'Shoulder to Hem', value: item.shoulder_to_hem },
        { key: 'women_size', label: 'Women\'s Size', value: item.women_size },
        { key: 'bottoms_size', label: 'Bottoms Size', value: item.bottoms_size },
        { key: 'ring_size', label: 'Ring Size', value: item.ring_size },
        { key: 'necklace_length', label: 'Necklace Length', value: item.necklace_length },
        { key: 'item_length', label: 'Item Length', value: item.item_length },
        { key: 'material', label: 'Material', value: item.material }
    ];

    // Filter out empty/null measurements
    const validMeasurements = measurements.filter(m => 
        m.value && 
        m.value !== 'None' && 
        m.value.toString().trim() !== ''
    );

    return validMeasurements;
}

// PDP display
function openPDP(item) {

    // Store current URL with filters for restoration later
    const originalUrl = window.location.href;
    
    // Check if we're already on a PDP URL to avoid duplication
    const currentPath = window.location.pathname;
    const isAlreadyOnPDP = currentPath.startsWith('/browse/') && currentPath !== '/browse/';
    
    // Only update URL if we're not already on a PDP URL
    if (!isAlreadyOnPDP) {
        // Save the current filtered URL to sessionStorage
        const currentParams = new URLSearchParams(window.location.search);
        if (currentParams.toString()) {
            sessionStorage.setItem('pdp_filtered_url', window.location.href);
            console.log('💾 Saved filtered URL:', window.location.href);
        }
        
        // Create clean slug from gallery_url
        let cleanUrl = item.gallery_url.replace(/\.[^/.]+$/, ""); // Remove file extension
        cleanUrl = cleanUrl.replace(/^webp_images\//, ""); // Remove webp_images/ prefix
        
        // Create clean PDP URL with NO parameters
        const pdpUrl = `/browse/${cleanUrl}`;
        
        // Store the PDP URL for later restoration
        sessionStorage.setItem('pdp_url', pdpUrl);
        
        // Store the original URL in the history state for restoration
        history.pushState({ 
            pdp: true, 
            item: item, 
            originalUrl: originalUrl 
        }, item.title, pdpUrl);
    }

    // Store item in sessionStorage for refresh handling
    sessionStorage.setItem('current_pdp_item', JSON.stringify(item));

    // Populate modal content
    document.getElementById('pdp-image').src = `https://finde-media.s3.amazonaws.com/${item.gallery_url}`;
    document.getElementById('pdp-image').alt = item.title;
    
    const formattedPrice = parseFloat(item.price) || 0;
    document.getElementById('pdp-price').textContent = `$${formattedPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    
    const sizeText = renderSize(item);
    document.getElementById('pdp-size').textContent = `${sizeText || 'One Size'}`;
    
    if (item.measurements) {
        document.getElementById('pdp-measurements').textContent = item.measurements;
        document.getElementById('pdp-measurements').style.display = 'block';
    } else {
        document.getElementById('pdp-measurements').style.display = 'none';
    }

    // Handle detailed measurements
    const detailedMeasurementsContainer = document.getElementById('pdp-detailed-measurements');
    const measurementsGrid = document.getElementById('measurements-grid');
    const validMeasurements = formatDetailedMeasurements(item);

    if (validMeasurements.length > 0) {
        measurementsGrid.innerHTML = '';
        
        validMeasurements.forEach(measurement => {
            const measurementItem = document.createElement('div');
            measurementItem.className = 'measurement-item';
            
            // Add inches symbol for certain measurements
            const needsInches = ['chest_size', 'waist_size', 'hip_size', 'waist_to_hem', 'inseam', 'shoulder_to_shoulder', 'shoulder_to_hem', 'hat_size', 'necklace_length', 'item_length'];
            const value = needsInches.includes(measurement.key) ? `${measurement.value}` : measurement.value;
            
            measurementItem.innerHTML = `
                <span class="measurement-label">${measurement.label}</span>
                <span class="measurement-value">${value}</span>
            `;
            
            measurementsGrid.appendChild(measurementItem);
        });
        
        detailedMeasurementsContainer.style.display = 'block';
    } else {
        detailedMeasurementsContainer.style.display = 'none';
    }

    
    const brand = item.brand || 'Vintage';
    const categoryName = getCategoryNameById(item.categoryId);
    const brandCategory = categoryName ? `${brand} ${categoryName}` : brand;
    document.getElementById('pdp-brand-category').innerHTML = `<a href="${item.item_web_url}" target="_blank">${brandCategory}</a>`;
    
    document.getElementById('pdp-description').textContent = item.description || item.title;
    
    const ctaButton = document.getElementById('pdp-cta');
    if (item.available === false) {
        ctaButton.textContent = 'Sold Out';
        ctaButton.className = 'button-dark pdp-sold-out';
        ctaButton.disabled = true;
        ctaButton.onclick = null;
    } else {
        ctaButton.textContent = 'View on eBay';
        ctaButton.className = 'button-dark';
        ctaButton.disabled = false;
        ctaButton.onclick = () => window.open(item.item_web_url, '_blank');
    }

    // Add favorite button to PDP
    const pdpFavoriteContainer = document.getElementById('pdp-favorite-container');
    if (pdpFavoriteContainer) {
        // Clear any existing favorite button
        pdpFavoriteContainer.innerHTML = '';
        
        // Get current favorited items to check if this item is already favorited
        const favoritedItemIds = JSON.parse(localStorage.getItem('favoritedItemIds') || '[]');

        const isFavorited = favoritedItemIds.includes(item.item_id);
        
        // Create the favorite button
        const favoriteButton = createFavoriteButton(item, isFavorited);
        favoriteButton.classList.add('pdp-favorite-button'); // Add specific class for PDP styling
        
        // Add click event (same as overlay button)
        favoriteButton.addEventListener('click', (event) => {
            event.stopPropagation();
            event.preventDefault();
        });
        
        pdpFavoriteContainer.appendChild(favoriteButton);
    }

    // Pinterest button
    const pdpPinterestContainer = document.getElementById('pdp-pinterest-container');
    if (pdpPinterestContainer) {
        // Clear any existing Pinterest button
        pdpPinterestContainer.innerHTML = '';
        
        // Create custom button element
        const pinterestButton = document.createElement('button');
        pinterestButton.className = 'button-light';
        
        // Add custom SVG and text
        pinterestButton.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="#48110C">
                <path d="M12 0C5.373 0 0 5.373 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.994 3.995-.283 1.194.599 2.169 1.777 2.169 2.133 0 3.772-2.249 3.772-5.495 0-2.873-2.064-4.882-5.012-4.882-3.414 0-5.418 2.561-5.418 5.207 0 1.031.397 2.138.893 2.738a.36.36 0 01.083.345l-.333 1.36c-.053.22-.174.267-.402.161-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z"/>
            </svg>
        `;
        
        // Add click handler
        pinterestButton.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const description = item.description || item.title;
            const pinterestUrl = `https://www.pinterest.com/pin/create/button/?url=${encodeURIComponent(window.location.href)}&media=${encodeURIComponent(`https://finde-media.s3.amazonaws.com/${item.gallery_url}`)}&description=${encodeURIComponent(`${item.brand || 'Vintage'} - ${item.title} - $${parseFloat(item.price).toFixed(2)} - ${description}`)}`;
            
            window.open(pinterestUrl, 'pinterest-share', 'width=750,height=650,toolbar=0,menubar=0,location=0,status=0,scrollbars=1,resizable=1');
        });
        
        pdpPinterestContainer.appendChild(pinterestButton);
        
        // Don't call PinUtils.build() - we're using our custom button
    }

    // Copy Link button
    const copyLinkButton = document.createElement('button');
    copyLinkButton.className = 'button-light';
    copyLinkButton.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
        </svg>
    `;

    // Add click handler
    copyLinkButton.addEventListener('click', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        try {
            await navigator.clipboard.writeText(window.location.href);
            
            // Visual feedback - temporarily change button text
            const originalHTML = copyLinkButton.innerHTML;
            copyLinkButton.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            `;
            copyLinkButton.style.color = '#4CAF50';
            
            // Reset after 2 seconds
            setTimeout(() => {
                copyLinkButton.innerHTML = originalHTML;
                copyLinkButton.style.color = '';
            }, 2000);
            
        } catch (err) {
            console.error('Failed to copy:', err);
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = window.location.href;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
        }
    });

    // copy link button
    const buttonsContainer = pdpPinterestContainer.parentElement;
     const dynamicButtons = buttonsContainer.querySelectorAll('.button-light:not(#pdp-favorite-container > *, #pdp-pinterest-container > *)');
    dynamicButtons.forEach(button => button.remove());
    buttonsContainer.appendChild(copyLinkButton);

        
    // Show modal
    document.getElementById('pdp-modal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closePDP() {
    document.getElementById('pdp-modal').classList.remove('active');
    document.body.style.overflow = '';
    
    // Try to restore from sessionStorage first
    const savedFilteredUrl = sessionStorage.getItem('pdp_filtered_url');
    
    if (savedFilteredUrl) {
        console.log('🔄 Restoring saved filtered URL:', savedFilteredUrl);
        const urlObj = new URL(savedFilteredUrl);
        const restoreUrl = urlObj.pathname + urlObj.search;
        history.replaceState({}, '', restoreUrl);
        
        // Clean up
        sessionStorage.removeItem('pdp_filtered_url');
        sessionStorage.removeItem('pdp_url');
    } else {
        // Fallback to existing logic
        const currentState = history.state;
        if (currentState && currentState.originalUrl) {
            console.log('Restoring original URL:', currentState.originalUrl);
            const originalUrlObj = new URL(currentState.originalUrl);
            const restoreUrl = originalUrlObj.pathname + originalUrlObj.search;
            history.replaceState({}, '', restoreUrl);
        } else {
            const urlParams = new URLSearchParams(window.location.search);
            const cleanBrowseUrl = `/browse/?${urlParams.toString()}`;
            history.replaceState({}, '', cleanBrowseUrl);
        }
    }
}

// Add PDP event listeners once when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Only add these listeners once
    const pdpClose = document.getElementById('pdp-close');
    const pdpModal = document.getElementById('pdp-modal');
    
    if (pdpClose && !pdpClose.hasAttribute('data-listener-added')) {
        pdpClose.addEventListener('click', closePDP);
        pdpClose.setAttribute('data-listener-added', 'true');
    }

    // Mobile pdp back button listener
    const pdpBackMobile = document.getElementById('pdp-back-mobile');
    if (pdpBackMobile && !pdpBackMobile.hasAttribute('data-listener-added')) {
        pdpBackMobile.addEventListener('click', closePDP);
        pdpBackMobile.setAttribute('data-listener-added', 'true');
    }
    
    if (pdpModal && !pdpModal.hasAttribute('data-listener-added')) {
        pdpModal.addEventListener('click', (e) => {
            if (e.target === pdpModal) {
                closePDP();
            }
        });
        pdpModal.setAttribute('data-listener-added', 'true');
    }
    
    // Handle browser back/forward - only add once
    window.addEventListener('popstate', (e) => {
        if (e.state && e.state.pdp) {
            if (!document.getElementById('pdp-modal').classList.contains('active')) {
                openPDP(e.state.item);
            }
        } else {
            if (document.getElementById('pdp-modal').classList.contains('active')) {
                document.getElementById('pdp-modal').classList.remove('active');
                document.body.style.overflow = '';
                
                // If there's an original URL to restore, do it
                const originalUrl = sessionStorage.getItem('pdp_original_url');
                if (originalUrl) {
                    const originalUrlObj = new URL(originalUrl);
                    const restoreUrl = originalUrlObj.pathname + originalUrlObj.search;
                    history.replaceState({}, '', restoreUrl);
                    sessionStorage.removeItem('pdp_original_url');
                }
            }
        }
    });
});




let lastUrlParamsString = '';
let cachedUrlParams = null;

// initial load items 
function getURLParams() {
    const currentUrl = window.location.search;
    
    // Use cache if URL hasn't changed
    if (currentUrl === lastUrlParamsString && cachedUrlParams) {
        return { ...cachedUrlParams }; // Return copy to prevent mutations
    }
    
    lastUrlParamsString = currentUrl;
    
    const urlParams = new URLSearchParams(currentUrl);
    cachedUrlParams = {
        query: urlParams.get('query') || null,
        page: urlParams.get('page') || '1',
        sortBy: urlParams.get('sort_by') || 'newlyAdded',
        categoryIds: urlParams.getAll('categoryId').filter(id => id),
        sizes: {},
        colors: urlParams.getAll('color').filter(color => color),
        minPrice: urlParams.get('min_price') || '',
        maxPrice: urlParams.get('max_price') || '',
        curatedFilter: urlParams.get('curated_filter') || null
    };

    // Handle size_category and size_value parameters
    const sizeCategories = urlParams.getAll('size_category');
    const sizeValues = urlParams.getAll('size_value');

    sizeCategories.forEach((category, index) => {
        if (!cachedUrlParams.sizes[category]) {
            cachedUrlParams.sizes[category] = [];
        }
        const values = sizeValues[index].split(',');
        cachedUrlParams.sizes[category].push(...values);
    });

    return { ...cachedUrlParams };
}



function updateURLParams(query, page, sortBy, categoryIds, sizes, colors, minPrice = '', maxPrice = '', curatedFilter = null) {
    if (!sizes || typeof sizes !== 'object') {
        console.error("Invalid sizes object passed to updateURLParams:", sizes);
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);

    // Set or remove parameters based on their values
    if (query) {
        urlParams.set('query', query);
    } else {
        urlParams.delete('query');
    }
    urlParams.set('page', page);
    urlParams.set('sort_by', sortBy);

    // Remove all existing 'categoryId' parameters
    urlParams.delete('categoryId');
    // If there are category IDs left, append them to the URL
    categoryIds.forEach(id => urlParams.append('categoryId', id));

    // Clear previous size parameters
    for (const key of [...urlParams.keys()]) {
        if (key.startsWith("size_category") || key.startsWith("size_value")) {
            urlParams.delete(key);
        }
    }

    // Add new size parameters as comma-separated values
    for (const [category, values] of Object.entries(sizes)) {
        if (values.length > 0) { // Only add non-empty size categories
            urlParams.append('size_category', category);
            urlParams.append('size_value', values.join(',')); // Join sizes with commas
        }
    }

    // Remove existing colors
    urlParams.delete('color');
    // Add colors
    colors.forEach(color => urlParams.append('color', color));

    // Update price filters
    if (minPrice) {
        urlParams.set('min_price', minPrice);
    } else {
        urlParams.delete('min_price');
    }

    if (maxPrice) {
        urlParams.set('max_price', maxPrice);
    } else {
        urlParams.delete('max_price');
    }

    // Handle curated filter parameter
    if (curatedFilter) {
        urlParams.set('curated_filter', curatedFilter);
    } else {
        urlParams.delete('curated_filter');
    }

    // ignore empty shoe size filters
    if (!sizes.us_shoe_size || sizes.us_shoe_size.length === 0) {
        delete sizes.us_shoe_size; // Ensure backend doesn't receive an empty filter
    }

    // Update the URL with the modified parameters
    history.pushState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
}

let pendingRequest = null;

function loadItems(query, page = 1, sortBy = 'newlyAdded', categoryIds = [], sizes = {}, colors = [], minPrice = '', maxPrice = '', curatedFilter = null) {
    
    // Create request signature for deduplication
    const requestSignature = JSON.stringify({
        query, page, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter
    });
    
    // Return pending request if identical request is already in flight
    if (pendingRequest && pendingRequest.signature === requestSignature) {
        console.log('🚀 Deduplicating identical request');
        return pendingRequest.promise;
    }
    
    // Build request data
    const sizeParams = {
        'size_category': [], 
        'size_value': []
    };

    for (const [category, values] of Object.entries(sizes)) {
        sizeParams['size_category'].push(category);  
        sizeParams['size_value'].push(values.join(",")); 
    }

    const requestData = { 
        query: query,
        page: page,
        sort_by: sortBy,
        categoryId: categoryIds.join(','),
        color: colors.join(','),
        min_price: minPrice,
        max_price: maxPrice,
        ...sizeParams,
    };

    if (curatedFilter) {
        requestData.curated_filter = curatedFilter;
    }

    
    const promise = Promise.all([
        fetchFavoritedItemIds(), // This now returns immediately if cached
        $.ajax({
            type: 'GET',
            url: opensearchUrl,
            data: requestData,
            cache: true, // Enable browser caching
        })
    ]).then(([favoritedItemIds, response]) => {
        
        // Clear pending request
        pendingRequest = null;
        
        if (!response || !response.results || !Array.isArray(response.results)) {
            console.error("Invalid response from loadItems:", response);
            return { results: [] };
        }
        
        const filteredResults = response.results;
        const featuredItems = response.featured_items || [];

        // OPTIMIZED: Preload only first 6 images immediately
        preloadCriticalImages(filteredResults, 6);

        // OPTIMIZED: Use requestAnimationFrame for smooth rendering
        requestAnimationFrame(() => {
           
            renderFeaturedItems(featuredItems, favoritedItemIds);
            renderItems(filteredResults, favoritedItemIds);
            renderPagination(response.current_page, response.total_pages, query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter);
        
        });
        
        return { ...response, results: filteredResults };
    })
    .catch(error => {
        pendingRequest = null;
        console.error('Error loading items:', error);
        $('#results').append('<p>An error occurred while loading items.</p>');
        throw error;
    });

    // Store pending request
    pendingRequest = { signature: requestSignature, promise };
    
    return promise;
}


async function initializePageState() {
    const currentPath = window.location.pathname;
    const isPDPUrl = currentPath.startsWith('/browse/') && currentPath !== '/browse/';
    
    // Check if we're on a PDP URL after refresh and have saved data
    const savedFilteredUrl = sessionStorage.getItem('pdp_filtered_url');
    const savedPdpUrl = sessionStorage.getItem('pdp_url');
    
    // Check if we're on a PDP URL and need to clear stale data
    if (isPDPUrl) {
        const storedPdpUrl = sessionStorage.getItem('pdp_url');
        const currentUrl = window.location.pathname;
        const referrer = document.referrer;
        const currentHost = window.location.host;
        
        // Clear sessionStorage if:
        // 1. We navigated to a different PDP URL
        // 2. We came from a page outside of /browse/
        const isDifferentPDP = storedPdpUrl && storedPdpUrl !== currentUrl;
        const isFromOutsideBrowse = referrer && !referrer.includes(currentHost + '/browse/');
        
        if (isDifferentPDP || isFromOutsideBrowse) {    
            sessionStorage.removeItem('current_pdp_item');
            sessionStorage.removeItem('pdp_url');
            sessionStorage.removeItem('pdp_filtered_url');
        }
    }
    
    if (isPDPUrl && savedFilteredUrl && savedPdpUrl) {
        
        // Temporarily switch to the filtered URL to load correct data
        const urlObj = new URL(savedFilteredUrl);
        const tempUrl = urlObj.pathname + urlObj.search;
        
        // Replace URL temporarily to get correct params
        history.replaceState({}, '', tempUrl);
        
        // Set a flag to know we need to switch back to PDP URL after loading
        sessionStorage.setItem('pdp_needs_url_restore', 'true');
    }
    
     // Now get URL params (either from current URL or temporarily restored filtered URL)
    const { query, page, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter } = getURLParams();

    // **HANDLE CURATED FILTER ON PAGE REFRESH**
    let cleanUserQuery = query; // This will be the user's actual search input
    
    if (curatedFilter && CURATED_FILTERS[curatedFilter]) {
        // Restore curated filter state
        activeCuratedFilter = curatedFilter;
        
        // Find and activate the curated filter button
        const curatedButton = document.querySelector(`[data-filter="${curatedFilter}"]`);
        if (curatedButton) {
            curatedButton.classList.add('active');
        }
        
        // Try to get original user query from URL first
        const urlParams = new URLSearchParams(window.location.search);
        const storedUserQuery = urlParams.get('user_query');
        
        if (storedUserQuery) {
            // Use the stored clean user query
            cleanUserQuery = storedUserQuery;

        } else {
            // Fallback: try to extract from combined query
            const config = CURATED_FILTERS[curatedFilter];
            const allCuratedTerms = [];
            
            if (config.keywords) allCuratedTerms.push(...config.keywords);
            if (config.materials) allCuratedTerms.push(...config.materials);
            if (config.brands) allCuratedTerms.push(...config.brands);
            
            if (query && allCuratedTerms.length > 0) {
                let cleanQuery = query;
                
                // Sort terms by length (longest first) to avoid partial removals
                const sortedTerms = allCuratedTerms.sort((a, b) => b.length - a.length);
                
                sortedTerms.forEach(term => {
                    // Handle URL encoding and special characters better
                    const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const regex = new RegExp(`\\b${escapedTerm}\\b`, 'gi');
                    cleanQuery = cleanQuery.replace(regex, '');
                    
                    // Also try with URL encoding
                    const encodedTerm = encodeURIComponent(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                    const encodedRegex = new RegExp(`\\b${encodedTerm}\\b`, 'gi');
                    cleanQuery = cleanQuery.replace(encodedRegex, '');
                });
                
                cleanUserQuery = cleanQuery.replace(/\s+/g, ' ').trim();
            }
        }
        
        // Store curated query terms for filter logic
        const config = CURATED_FILTERS[curatedFilter];
        const allCuratedTerms = [];
        if (config.keywords) allCuratedTerms.push(...config.keywords);
        if (config.materials) allCuratedTerms.push(...config.materials);
        if (config.brands) allCuratedTerms.push(...config.brands);
        curatedFilterQuery = allCuratedTerms.join(' ');

    } else {
        // No curated filter, ensure state is clean
        activeCuratedFilter = null;
        curatedFilterQuery = '';
        cleanUserQuery = query;
    }

    let pdpItemToOpen = null;
    
    if (isPDPUrl) {
        
        // First try to get item from sessionStorage (for refresh)
        const storedItem = sessionStorage.getItem('current_pdp_item');
        if (storedItem) {
            try {
                const parsedItem = JSON.parse(storedItem);
                // NEW: Verify the stored item matches the current URL
                const itemSlug = parsedItem.gallery_url
                    .replace(/\.[^/.]+$/, "") // Remove file extension
                    .replace(/^webp_images\//, ""); // Remove webp_images/ prefix
                
                const currentSlug = currentPath.replace('/browse/', '').replace(/\/$/, '');
                
                if (itemSlug === currentSlug) {
                    pdpItemToOpen = parsedItem;
                    console.log("Found matching item in sessionStorage:", pdpItemToOpen.title);
                } else {
                    console.log("Stored item doesn't match current URL, clearing...");
                    sessionStorage.removeItem('current_pdp_item');
                }
            } catch (error) {
                console.error('Error parsing stored PDP item:', error);
                sessionStorage.removeItem('current_pdp_item');
            }
        }
        
        // If not in sessionStorage, try server-side data
        if (!pdpItemToOpen) {
            const pdpItemData = document.getElementById('pdp-item-data');
            if (pdpItemData) {
                try {
                    let itemData;
                    const rawData = pdpItemData.textContent.trim();
                    
                    try {
                        itemData = JSON.parse(rawData);
                    } catch (jsonError) {
                        const jsonString = rawData
                            .replace(/'/g, '"')
                            .replace(/True/g, 'true')
                            .replace(/False/g, 'false')
                            .replace(/None/g, 'null');
                        
                        itemData = JSON.parse(jsonString);
                    }
                    
                    pdpItemToOpen = itemData;
                } catch (error) {
                    console.error('Error parsing PDP item data:', error);
                }
            }
        }
        
        const pdpNotFound = document.querySelector('[data-pdp-not-found]');
        if (pdpNotFound) {
            if (savedFilteredUrl) {
                const urlObj = new URL(savedFilteredUrl);
                window.location.href = urlObj.pathname + urlObj.search;
            } else {
                window.location.href = '/browse/';
            }
            return;
        }
    }

    // Extract selected widths from the sizes object
    const selectedWidths = sizes.shoe_size_width || [];

    // If no widths are selected, clear the local storage for disabled buttons
    if (selectedWidths.length === 0) {
        document.querySelectorAll(".button-size[data-category='us_shoe_size']").forEach(usSizeButton => {
            localStorage.removeItem(`disabled_${usSizeButton.value}`);
            usSizeButton.disabled = false; // Re-enable the button
        });
    }
    
    // Set form elements based on URL parameters
    document.getElementById('dropdown-sortby').value = sortBy;
    
    // **IMPORTANT: Set the search input to the CLEAN user query, not the full query with curated terms**
    document.getElementById('opensearch-input').value = cleanUserQuery || '';

    // Get the elements for displaying input search keyword messages
    const resultsMessage = document.getElementById('results-message')?.querySelector('p');
    const noResultsMessage = document.getElementById('no-results-message');

    // If there is a clean user query, update the results message
    if (cleanUserQuery) {
        if (resultsMessage) {
            resultsMessage.style.display = 'block';
        }
    } else {
        if (resultsMessage) {
            resultsMessage.textContent = '';
            resultsMessage.style.display = 'none';
        }
    }

    // **ALWAYS load items** - whether PDP or regular browse
    // Load items with the correct filters (use original query for search, but display clean query)
    try {
        const response = await loadItems(query, page, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter);
        const items = response.results;
        const hasActiveFilters = categoryIds.length > 0 || Object.keys(sizes).length > 0 || colors.length > 0 || minPrice || maxPrice;

        if (noResultsMessage) {
            noResultsMessage.style.display = (!items.length && hasActiveFilters) ? 'block' : 'none';
        }

        if (cleanUserQuery && resultsMessage) {
            // Get both regular results and featured items
            const totalResults = items.length + (response.featured_items ? response.featured_items.length : 0);
            
            if (totalResults > 0) {
                resultsMessage.innerHTML = `Results for "${cleanUserQuery}" <br><a href="#" id="clear-search-link">Clear Search</a>`;
            } else {
                resultsMessage.innerHTML = `No search results for "${cleanUserQuery}" <br><a href="#" id="clear-search-link">Clear Search</a>`;
            }
            resultsMessage.style.display = 'block';
        }

        // After loading items, check if we need to restore PDP URL
        if (sessionStorage.getItem('pdp_needs_url_restore') === 'true') {
            const pdpUrlToRestore = sessionStorage.getItem('pdp_url');
            if (pdpUrlToRestore) {
                console.log('Restoring PDP URL after loading:', pdpUrlToRestore);
                history.replaceState({}, '', pdpUrlToRestore);
                sessionStorage.removeItem('pdp_needs_url_restore');
            }
        }

        // Open PDP after items are loaded
        if (pdpItemToOpen) {
            setTimeout(() => {
                openPDP(pdpItemToOpen);
            }, 100);
        } else if (isPDPUrl) {
            const urlSlug = currentPath.replace('/browse/', '').replace(/\/$/, '');
            console.log("Falling back to client-side search for:", urlSlug);
            handlePDPFromUrl(urlSlug);
        }

    } catch (error) {
        console.error('Error loading items:', error);
        if (resultsMessage) {
            resultsMessage.textContent = 'Error loading results';
            resultsMessage.style.display = 'block';
        }
    }
    
    document.getElementById('reset-search').style.display = cleanUserQuery ? 'block' : 'none';

    // Render initial tags
    renderTags('selected-category-filters', categoryIds, 'category');
    // Convert sizes object to an array of tags
    const sizeTags = Object.entries(sizes).flatMap(([category, values]) =>
        values.map(value => ({ category, value }))
    );
    renderTags('selected-size-filters', sizeTags, 'size');
    renderTags('selected-color-filters', colors, 'color');
    const priceTags = [];
    if (minPrice) priceTags.push(`Min: $${minPrice}`);
    if (maxPrice) priceTags.push(`Max: $${maxPrice}`);
    renderTags('selected-price-filters', priceTags, 'price');

    // **Persist selected filter buttons**
    
    // Apply selected class to size buttons
    document.querySelectorAll(".button-size").forEach(button => {
        const sizeCategory = button.getAttribute("data-category").replace(/\s+/g, "_");
        const sizeValue = button.value;

        if (sizes[sizeCategory]?.includes(sizeValue)) {
            button.classList.add("selected");
        } else {
            button.classList.remove("selected");
        }

        // Apply disabled state from localStorage
        if (localStorage.getItem(`disabled_${sizeValue}`)) {
            button.disabled = true;
        }
    });

    // Ensure US shoe size buttons are correctly marked as selected
    const usShoeSizes = sizes.us_shoe_size || [];
    document.querySelectorAll('.button-size[data-category="us_shoe_size"]').forEach(button => {
        if (usShoeSizes.includes(button.value)) {
            button.classList.add("selected");
        } else {
            button.classList.remove("selected");
        }

        // Apply disabled state from localStorage
        if (localStorage.getItem(`disabled_${button.value}`)) {
            button.disabled = true;
        }
    });
    
    // Color filters
    document.querySelectorAll(".button-color").forEach(button => {
        if (colors.includes(button.value)) {
            button.classList.add("selected");
            const colorSwatch = button.querySelector(".color-swatch");
            if (colorSwatch) {
                colorSwatch.classList.add("selected");
            }
        }
    });

    // Category filters
    document.querySelectorAll(".dropdown-category").forEach(button => {
        if (categoryIds.includes(button.value)) {
            button.classList.add("selected");
        }
    });

    // **Persist selected state for dropdown-top-category buttons**
    document.querySelectorAll(".dropdown-top-category").forEach(topButton => {
        const categoryIdsForTopCategory = topButton.getAttribute("data-category-ids").split(",").filter(id => id);

        // Check if all category IDs for this top category are selected
        const allSelected = categoryIdsForTopCategory.every(id => categoryIds.includes(id));

        // Set the selected state of the top category button
        if (allSelected) {
            topButton.classList.add("selected");
        } else {
            topButton.classList.remove("selected");
        }
    });

    // Persistent Blue Dot Logic after page refresh
    updateBlueDot("Category", categoryIds.length > 0);
    updateBlueDot("Size", Object.values(sizes).some(v => v.length > 0));
    updateBlueDot("Color", colors.length > 0);
    updateBlueDot("Price", minPrice || maxPrice);

    // Persist blue dots for top_level_category links
    document.querySelectorAll(".top-level-link").forEach(topCategoryLink => {
        const topCategory = topCategoryLink.getAttribute("data-top-category");

        // Check if any dropdown-category within this top_category is selected
        const hasSelectedSubCategory = document.querySelectorAll(
            `.dropdown-category[data-top-category="${topCategory}"].selected`
        ).length > 0;

        // Add or remove the blue-dot class based on selection
        if (hasSelectedSubCategory) {
            topCategoryLink.classList.add("blue-dot");
        } else {
            topCategoryLink.classList.remove("blue-dot");
        }
    });

    // Update blue dots for size_type links
    updateSizeTypeBlueDot(sizes);

    // Price filters
    document.getElementById('min-price').value = minPrice || '';
    document.getElementById('max-price').value = maxPrice || '';
    
    window.pageInitialized = true;
}

// Initialize page state on load
document.addEventListener('DOMContentLoaded', initializePageState);


// Optimized helper function to handle PDP from URL**
function handlePDPFromUrl(urlSlug) {
    let attemptCount = 0;
    const maxAttempts = 5; // Reduced significantly
    
    function findAndOpenPDP() {
        attemptCount++;
        console.log(`PDP search attempt ${attemptCount}, looking for: ${urlSlug}`);
        
        const itemElements = document.querySelectorAll('.item-container');
        
        if (itemElements.length > 0) {
            // Remove any numeric suffix and convert to lowercase for comparison
            const baseSlug = urlSlug.replace(/_\d+$/, '').toLowerCase();
            
            // OPTIMIZED: Try exact match first with early exit
            for (let element of itemElements) {
                const itemTitle = element.dataset.title;
                if (itemTitle) {
                    const titleSlug = itemTitle.toLowerCase()
                        .replace(/[^a-z0-9\s-]/g, '')
                        .replace(/\s+/g, '_')
                        .replace(/_+/g, '_');
                    
                    if (titleSlug === baseSlug) {
                        const anchor = element.querySelector('a');
                        if (anchor) {
                            console.log("✅ Found exact matching PDP item:", itemTitle);
                            anchor.click();
                            return true;
                        }
                    }
                }
            }
            
            // Only do partial matching if exact match fails and we have few items
            if (itemElements.length < 500) { // Only for reasonable dataset sizes
                const searchTerms = baseSlug.split('_').filter(term => term.length > 3);
                
                for (let element of itemElements) {
                    const itemTitle = element.dataset.title;
                    if (itemTitle) {
                        const titleSlug = itemTitle.toLowerCase()
                            .replace(/[^a-z0-9\s-]/g, '')
                            .replace(/\s+/g, '_')
                            .replace(/_+/g, '_');
                        
                        const matchCount = searchTerms.filter(term => titleSlug.includes(term)).length;
                        if (matchCount >= Math.min(3, searchTerms.length * 0.7)) {
                            const anchor = element.querySelector('a');
                            if (anchor) {
                                console.log(`⚡ Found partial matching PDP item (${matchCount}/${searchTerms.length} terms):`, itemTitle);
                                anchor.click();
                                return true;
                            }
                        }
                    }
                }
            }
        }
        
        // Retry with shorter intervals for smaller datasets
        if (attemptCount < maxAttempts) {
            setTimeout(findAndOpenPDP, 200);
        } else {
            console.log("❌ PDP item not found. Consider using server-side lookup for better performance.");
        }
        
        return false;
    }
    
    // Start immediately
    setTimeout(findAndOpenPDP, 100);
}

// Blue Dot logic for filter buttons
function updateBlueDot(tabType, isActive) {
    const tablinkNav = document.querySelector(`.tablink-nav[data-tab="${tabType}"]`);
    const tablink = document.querySelector(`.tablink[data-tab="${tabType}"]`);
    
    // Mapping for filter button IDs
    const filterButtonIds = {
        "Category": "filter-button-category",
        "Color": "filter-button-color", 
        "Price": "filter-button-price"
    };
    
    const filterButton = document.getElementById(filterButtonIds[tabType]);

    if (isActive) {
        tablinkNav?.classList.add("blue-dot");
        tablink?.classList.add("blue-dot");
        filterButton?.classList.add("blue-dot");
    } else {
        tablinkNav?.classList.remove("blue-dot");
        tablink?.classList.remove("blue-dot");
        filterButton?.classList.remove("blue-dot");
    }
    
    // Update main Filter button - show blue dot if ANY filter is active
    updateMainFilterButton();
}

// Handle the main mobile Filter button
function updateMainFilterButton() {
    const mainFilterButton = document.getElementById("filter-button");
    const { categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();
    
    const hasAnyFilters = categoryIds.length > 0 || 
                         Object.values(sizes).some(v => v.length > 0) || 
                         colors.length > 0 || 
                         minPrice || 
                         maxPrice; 
    
    if (hasAnyFilters) {
        mainFilterButton?.classList.add("blue-dot");
    } else {
        mainFilterButton?.classList.remove("blue-dot");
    }
}

// Class Mappings for blue-dot to be applied to size_type menu links
const sizeTypeMapping = {
    size: "clothing-size",
    bottoms_size: "clothing-size",
    bra_size: "clothing-size",
    hat_size: "clothing-size",
    chest_size: "body-measurements",
    waist_size: "body-measurements",
    hip_size: "body-measurements",
    inseam: "body-measurements",
    shoulder_to_shoulder: "body-measurements",
    waist_to_hem: "body-measurements",
    shoulder_to_hem: "body-measurements",
    us_shoe_size: "shoe-size",
    shoe_size_width: "shoe-size",
    ring_size: "jewelry-size",
    necklace_length: "jewelry-size",
    item_length: "jewelry-size",
};


// Blue Dot logic for size_type links
function updateSizeTypeBlueDot(updatedSizes) {
    const sizeTypeLinks = document.querySelectorAll(".size_type");

    // Reset all blue dots
    sizeTypeLinks.forEach(link => link.classList.remove("blue-dot"));

    // Iterate through the updatedSizes object
    for (const [category, values] of Object.entries(updatedSizes)) {
        if (values.length > 0) {
            // Get the corresponding size_type class from the mapping
            const sizeTypeClass = sizeTypeMapping[category];
            if (sizeTypeClass) {
                // Add the blue dot to the matching size_type link
                const sizeTypeLink = document.querySelector(`.size_type.${sizeTypeClass}`);
                if (sizeTypeLink) {
                    sizeTypeLink.classList.add("blue-dot");
                }
            }
        }
    }
}



// ============================
// Tags
// ============================

// Mapping for shoe width values
const shoeWidthLabels = {
    "XXS": "Super Narrow",
    "XS": "Extra Narrow",
    "S": "Narrow",
    "W": "Wide",
    "XW": "Extra Wide",
    "XXW": "Triple Wide",
};

// Converts tags from decimal to fraction for display purposes. Using JS for tags (for dynamic page loading), and using a separate fraction django filter for the size buttons
function decimalToFraction(decimalValue) {
    // Handle cases where the value is not a number
    if (isNaN(decimalValue)) {
        return decimalValue; // Return the original value if it's not a number
    }

    // Convert the value to a float
    const value = parseFloat(decimalValue);
    const integerPart = Math.floor(value);
    const fractionalPart = value - integerPart;

    // Common fractional conversions
    if (Math.abs(fractionalPart - 0.5) < 0.01) {
        return `${integerPart} 1/2`;
    } else if (Math.abs(fractionalPart - 0.25) < 0.01) {
        return `${integerPart} 1/4`;
    } else if (Math.abs(fractionalPart - 0.375) < 0.01) {
        return `${integerPart} 3/8`;
    } else if (Math.abs(fractionalPart - 0.75) < 0.01) {
        return `${integerPart} 3/4`;
    } else if (Math.abs(fractionalPart - 0.33) < 0.01) {
        return `${integerPart} 1/3`;
    } else if (Math.abs(fractionalPart - 0.66) < 0.01) {
        return `${integerPart} 2/3`;
    } else if (Math.abs(fractionalPart - 0.625) < 0.01) {
        return `${integerPart} 5/8`;
    } else if (Math.abs(fractionalPart - 0.875) < 0.01) {
        return `${integerPart} 7/8`;
    } else {
        // If no common fraction matches, return the original value
        return decimalValue;
    }
}

let lastTagStates = {};

function renderTags(containerId, tags, type) {
    const container = document.getElementById(containerId);
    
    // Create a simple hash of current tags for comparison
    const tagHash = JSON.stringify({ containerId, tags, type });
    
    // Skip rendering if tags haven't changed
    if (lastTagStates[containerId] === tagHash) {
        return;
    }
    
    lastTagStates[containerId] = tagHash;
    
    container.innerHTML = ''; // Clear previous tags

    // Mapping of technical category names to user-friendly display names
    const sizeCategoryDisplayNames = {
        size: "Clothing", 
        bottoms_size: "Shorts & Pants", 
        chest_size: "Bust", 
        bra_size: "Bra",
        hip_size: "Hip",    
        waist_size: "Waist", 
        inseam: "Inseam",
        waist_to_hem: "Waist to Hem",
        shoulder_to_shoulder: "Shoulder to Shoulder",
        shoulder_to_hem: "Shoulder to Hem",
        us_shoe_size: "Shoe (US)", 
        shoe_size_width: "Shoe Width",
        hat_size: "Hat Size",
        ring_size: "Ring", 
        necklace_length: "Necklace Length", 
        item_length: "Jewelry", 
    };

    // Use DocumentFragment for batch operations
    const fragment = document.createDocumentFragment();

    tags.forEach(tag => {
        const tagElement = document.createElement('div');
        tagElement.className = 'tag';

        // Set data-type and data-value based on the type of tag
        if (type === 'category') {
            tagElement.dataset.type = 'category';
            tagElement.dataset.value = tag;
        } else {
            tagElement.dataset.type = tag.category || type;
            tagElement.dataset.value = tag.value || tag;
        }

        const tagText = document.createElement('span');

        if (type === 'category') {
            const categoryButton = document.querySelector(`.dropdown-category[value="${tag}"]`);
            if (categoryButton) {
                tagText.textContent = categoryButton.textContent.trim();
            } else {
                tagText.textContent = tag;
            }
        } else if (type === 'size') {
            const displayName = sizeCategoryDisplayNames[tag.category] || tag.category;
            let displayValue = tag.value;
            
            if (tag.category === 'shoe_size_width') {
                displayValue = shoeWidthLabels[tag.value] || tag.value;
            } else {
                const cleanedValue = tag.value.replace(/"/g, '');
                displayValue = (tag.category === 'size' || tag.category === 'us_shoe_size') 
                    ? cleanedValue 
                    : decimalToFraction(cleanedValue);

                const containsNumbers = /\d/.test(cleanedValue);
                const shouldAddInches = !['size', 'bra_size', 'bottoms_size', 'us_shoe_size', 'ring_size'].includes(tag.category) && containsNumbers;
                displayValue = `${displayValue}${shouldAddInches ? '"' : ''}`;
            }

            if (displayName.trim() === "") {
                tagText.innerHTML = `${displayValue}`;
            } else {
                tagText.innerHTML = `${displayName}: ${displayValue}`;
            }
        } else if (type === 'color') {
            const colorButton = document.querySelector(`.dropdown-category[value="${tag}"]`);
            if (colorButton) {
                tagText.textContent = colorButton.textContent.trim();
            } else {
                tagText.textContent = tag;
            }
        } else if (type === 'price') {
            tagText.textContent = tag;
        } else {
            tagText.textContent = `${tag.category}: ${tag.value}`;
        }

        tagElement.appendChild(tagText);

        const closeButton = document.createElement('span');
        closeButton.className = 'close-button';
        closeButton.textContent = '×';
        closeButton.addEventListener('click', (event) => {
            event.stopPropagation();
            removeTag(type, tag.value || tag, tag.category);
        });

        tagElement.appendChild(closeButton);
        fragment.appendChild(tagElement);
    });

    // Single DOM update
    container.appendChild(fragment);
    container.style.display = 'block';
    
    // Handle section visibility after rendering tags
    updateAllSectionVisibility();
}

function preloadCriticalImages(items, count = 6) {
    const criticalImages = items.slice(0, count);
    
    // Use high priority for first 3 images
    criticalImages.forEach((item, index) => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = `https://finde-media.s3.amazonaws.com/${item.gallery_url}`;
        if (index < 3) {
            link.fetchPriority = 'high';
        }
        document.head.appendChild(link);
    });
}

// Simplified section visibility function with browser-compatible selectors
function updateAllSectionVisibility() {
    // Handle Categories section (first .filter-section)
    const categoryContainer = document.getElementById('selected-category-filters');
    const hasCategoryTags = categoryContainer && categoryContainer.children.length > 0;
    
    // Find category section by looking for the one that contains selected-category-filters
    const allFilterSections = document.querySelectorAll('.filter-section');
    let categorySection = null;
    let filtersSection = null;
    
    allFilterSections.forEach(section => {
        if (section.querySelector('#selected-category-filters')) {
            categorySection = section;
        } else if (section.querySelector('.stacked-tags')) {
            filtersSection = section;
        }
    });
    
    // Show/hide category section
    if (categorySection) {
        hasCategoryTags ? categorySection.classList.add('show') : categorySection.classList.remove('show');
    }

    // Handle Filters section
    const sizeContainer = document.getElementById('selected-size-filters');
    const colorContainer = document.getElementById('selected-color-filters');
    const priceContainer = document.getElementById('selected-price-filters');
    
    const hasSizeTags = sizeContainer && sizeContainer.children.length > 0;
    const hasColorTags = colorContainer && colorContainer.children.length > 0;
    const hasPriceTags = priceContainer && priceContainer.children.length > 0;
    
    const hasAnyFilterTags = hasSizeTags || hasColorTags || hasPriceTags;
    
    // Show/hide filters section
    if (filtersSection) {
        hasAnyFilterTags ? filtersSection.classList.add('show') : filtersSection.classList.remove('show');
    }
}

function removeTag(type, value, category) {

    const { query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();

    switch (type) {
        case 'category':
            const updatedCategoryIds = categoryIds.filter(id => id !== value);
            // PASS activeCuratedFilter to preserve curated filter logic
            loadItems(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
            updateURLParams(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
            renderTags('selected-category-filters', updatedCategoryIds, 'category');
            toggleFilterButtonOff(type, value); // Toggle off the category button
            // Update Blue Dot on Category Tab
            updateBlueDot("Category", updatedCategoryIds.length > 0);

            // Update blue dots for top_level_category links
            document.querySelectorAll('.top-level-link').forEach(topCategoryLink => {
                const topCategory = topCategoryLink.getAttribute("data-top-category");

                // Check if any dropdown-category within this top_category is selected
                const hasSelectedSubCategory = document.querySelectorAll(
                    `.dropdown-category[data-top-category="${topCategory}"].selected`
                ).length > 0;

                // Add or remove the blue-dot class based on selection
                if (hasSelectedSubCategory) {
                    topCategoryLink.classList.add("blue-dot");
                } else {
                    topCategoryLink.classList.remove("blue-dot");
                }
            });

            // Update the selected state of dropdown-top-category buttons
            document.querySelectorAll('.dropdown-top-category').forEach(topButton => {
                const categoryIds = topButton.getAttribute("data-category-ids").split(",").filter(id => id);
                const allSelected = categoryIds.every(id => updatedCategoryIds.includes(id));
                
                if (allSelected) {
                    topButton.classList.add("selected");
                } else {
                    topButton.classList.remove("selected");
                }
            });
            break;

        case 'size':
            const updatedSizes = { ...sizes };

            // Remove the size value from the category
            if (updatedSizes[category]) {
                updatedSizes[category] = updatedSizes[category].filter(size => size !== value);
                if (updatedSizes[category].length === 0) {
                    delete updatedSizes[category]; // Remove the category if no sizes are left
                }
            }

            // Rebuild the sizeTags array AFTER updating updatedSizes
            const sizeTags = Object.entries(updatedSizes).flatMap(([cat, values]) =>
                values.map(val => ({ category: cat, value: val }))
            );

            // Reload items and update URL - PASS activeCuratedFilter
            loadItems(query, 1, sortBy, categoryIds, updatedSizes, colors, minPrice, maxPrice, activeCuratedFilter);
            updateURLParams(query, 1, sortBy, categoryIds, updatedSizes, colors, minPrice, maxPrice, activeCuratedFilter);

            // Re-render the size tags
            renderTags('selected-size-filters', sizeTags, 'size');

            // Toggle off the corresponding size button
            toggleFilterButtonOff(type, value, category);

            // Update Blue Dot on Size tablink
            updateBlueDot("Size", Object.values(updatedSizes).some(values => values.length > 0));

            // Update blue dots for size_type links
            updateSizeTypeBlueDot(updatedSizes);

            // Re-enable previously disabled shoe size buttons
            updateButtonStates(updatedSizes.shoe_size_width || [], updatedSizes.us_shoe_size || []);
            break;

        case 'color':
            const updatedColors = colors.filter(color => color !== value);
            // PASS activeCuratedFilter to preserve curated filter logic
            loadItems(query, 1, sortBy, categoryIds, sizes, updatedColors, minPrice, maxPrice, activeCuratedFilter);
            updateURLParams(query, 1, sortBy, categoryIds, sizes, updatedColors, minPrice, maxPrice, activeCuratedFilter);
            renderTags('selected-color-filters', updatedColors, 'color');
            toggleFilterButtonOff(type, value); // Toggle off the color button
            // Update Blue Dot on Color Tab
            updateBlueDot("Color", updatedColors.length > 0);
            break;

        case 'price':
            
            // Clear any pending price tag timeouts using the global variables
            if (window.priceTagTimeout) {
                clearTimeout(window.priceTagTimeout);
            }
            if (window.priceTimeout) {
                clearTimeout(window.priceTimeout);
            }
            
            let updatedMinPrice = minPrice;
            let updatedMaxPrice = maxPrice;

            // Determine if the removed tag is for min or max price
            // The value comes in as "Min: $100" or "Max: $200"
            if (value.startsWith('Min:')) {
                document.getElementById('min-price').value = '';
                updatedMinPrice = '';
            } else if (value.startsWith('Max:')) {
                document.getElementById('max-price').value = '';
                updatedMaxPrice = '';
            }


            // Reload items and update URL with only the removed value cleared - PASS activeCuratedFilter
            loadItems(query, 1, sortBy, categoryIds, sizes, colors, updatedMinPrice, updatedMaxPrice, activeCuratedFilter);
            updateURLParams(query, 1, sortBy, categoryIds, sizes, colors, updatedMinPrice, updatedMaxPrice, activeCuratedFilter);

            // Rebuild price tags with only the remaining active values
            const updatedPriceTags = [];
            if (updatedMinPrice) updatedPriceTags.push(`Min: ${updatedMinPrice}`);
            if (updatedMaxPrice) updatedPriceTags.push(`Max: ${updatedMaxPrice}`);

            renderTags('selected-price-filters', updatedPriceTags, 'price');
            // Update Blue Dot on Price Tab 
            updateBlueDot("Price", updatedMinPrice || updatedMaxPrice);
            break;
    }
    
    // Update all section visibility at the end
    updateAllSectionVisibility();
}

// Toggle filter buttons off when deselecting tags
function toggleFilterButtonOff(type, value, updatedSizes = null) {
    let button;

    switch (type) {
        case 'category':
            button = document.querySelector(`.dropdown-category[value="${value}"]`);
            break;

        case 'size':
            const { sizes } = getURLParams();
            const currentSizes = updatedSizes || sizes;

            // Find the category that contains the size
            const sizeCategory = Object.keys(currentSizes).find(category => 
                currentSizes[category] && currentSizes[category].includes(value)
            );

            if (sizeCategory) {
                // Escape special characters in the value for the selector
                const escapedValue = value.replace(/"/g, '\\"'); // Escape double quotes
                // Deselect the size button for the specific category
                button = document.querySelector(`.button-size[value="${escapedValue}"][data-category="${sizeCategory}"]`);
                if (button) {
                    button.classList.remove("selected");
                }

                // Deselect the corresponding button for all relevant categories
                const categoriesToDeselect = ["bottoms_size", "us_shoe_size", "shoe_size_width", "chest_size", "inseam", "hat_size", "hip_size", "waist_to_hem", "bra_size", "shoulder_to_shoulder", "shoulder_to_hem", "ring_size", "necklace_length", "item_length", "women_size"];
                categoriesToDeselect.forEach(category => {
                    const categoryButton = document.querySelector(`.button-size[value="${escapedValue}"][data-category="${category}"]`);
                    if (categoryButton) {
                        categoryButton.classList.remove("selected");
                    }
                });
            } else {
                // Fallback: Try without category if data-category is causing issues
                const escapedValue = value.replace(/"/g, '\\"'); // Escape double quotes
                button = document.querySelector(`.button-size[value="${escapedValue}"]`);
                if (button) {
                    button.classList.remove("selected");
                }

                // Deselect the corresponding button for all relevant categories
                const categoriesToDeselect = ["bottoms_size", "us_shoe_size", "shoe_size_width", "chest_size", "inseam", "hat_size", "hip_size", "waist_to_hem", "bra_size", "shoulder_to_shoulder", "shoulder_to_hem", "ring_size", "necklace_length", "item_length", "women_size"];
                categoriesToDeselect.forEach(category => {
                    const categoryButton = document.querySelector(`.button-size[value="${escapedValue}"][data-category="${category}"]`);
                    if (categoryButton) {
                        categoryButton.classList.remove("selected");
                    }
                });
            }
            break;

        case 'color':
            button = document.querySelector(`.color-swatch[alt="${value}"]`);
            break;

        case 'price':
            // Clear the price input fields
            document.getElementById('min-price').value = '';
            document.getElementById('max-price').value = '';
            break;
    }

    if (button) {
        button.classList.remove("selected");
    } else {
        console.warn(`Button not found for ${type}: ${value}`);
    }
}


// ============================
// Toggle 'Selected' State Button behavior
// ============================
function updateButtonStates() {
    const { categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();

    // Update size buttons
    document.querySelectorAll(".button-size").forEach(button => {
        const sizeCategory = button.getAttribute("data-category").replace(/\s+/g, "_");
        const sizeValue = button.value;

        // Update selected state
        if (sizes[sizeCategory]?.includes(sizeValue)) {
            button.classList.add("selected");
        } else {
            button.classList.remove("selected");
        }

        // Ensure disabled state is respected
        if (sizeCategory === "us_shoe_size") {
            const selectedWidth = sizes.shoe_size_width?.[0]; // Get the selected width
            const buttonWidth = button.getAttribute("data-width");

            if (selectedWidth && !buttonWidth?.includes(selectedWidth)) {
                button.disabled = true; // Disable if width doesn't match
            } else {
                button.disabled = false; // Enable if width matches
            }
        }
    });

    // Update color buttons
    document.querySelectorAll(".button-color").forEach(button => {
        if (colors.includes(button.value)) {
            button.classList.add("selected");
            const colorSwatch = button.querySelector(".color-swatch");
            if (colorSwatch) {
                colorSwatch.classList.add("selected");
            }
        } else {
            button.classList.remove("selected");
            const colorSwatch = button.querySelector(".color-swatch");
            if (colorSwatch) {
                colorSwatch.classList.remove("selected");
            }
        }
    });

    // Update category buttons
    document.querySelectorAll(".dropdown-category").forEach(button => {
        if (categoryIds.includes(button.value)) {
            button.classList.add("selected");
        } else {
            button.classList.remove("selected");
        }
    });

    // Update top category buttons
    document.querySelectorAll(".dropdown-top-category").forEach(topButton => {
        const categoryIdsForTopCategory = topButton.getAttribute("data-category-ids").split(",").filter(id => id);
        const allSelected = categoryIdsForTopCategory.every(id => categoryIds.includes(id));
        if (allSelected) {
            topButton.classList.add("selected");
        } else {
            topButton.classList.remove("selected");
        }
    });

    // Update blue dots for each tablink
    updateBlueDot("Category", categoryIds.length > 0);
    updateBlueDot("Size", Object.values(sizes).some(values => values.length > 0));
    updateBlueDot("Color", colors.length > 0);
    updateBlueDot("Price", minPrice || maxPrice);

    // Update blue dots for top_level_category links
    document.querySelectorAll(".top-level-link").forEach(topCategoryLink => {
        const topCategory = topCategoryLink.getAttribute("data-top-category");
        const hasSelectedSubCategory = document.querySelectorAll(`.dropdown-category[data-top-category="${topCategory}"].selected`).length > 0;
        if (hasSelectedSubCategory) {
            topCategoryLink.classList.add("blue-dot");
        } else {
            topCategoryLink.classList.remove("blue-dot");
        }
    });
}

// ============================
// Filters ADD/REMOVE
// ============================
// Filter button logic (category, size, color, price, ect)




// size filters 
function handleSizeClick(event) {

    const button = event.target.closest(".button-size");

    if (!button) {
        console.error("No button found");
        return;
    }

    const sizeValue = button.value;
    const sizeCategory = button.getAttribute("data-category").replace(/\s+/g, "_");

    // Get current URL parameters
    const { query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();
    let updatedSizes = { ...sizes };

    // Toggle the size value in the URL parameters
    if (updatedSizes[sizeCategory]?.includes(sizeValue)) {
        updatedSizes[sizeCategory] = updatedSizes[sizeCategory].filter(value => value !== sizeValue);
        // Remove the category if it becomes empty
        if (updatedSizes[sizeCategory].length === 0) {
            delete updatedSizes[sizeCategory];
        }
    } else {
        updatedSizes[sizeCategory] = updatedSizes[sizeCategory] || [];
        updatedSizes[sizeCategory].push(sizeValue);
    }

    // Update URL parameters - PASS activeCuratedFilter
    updateURLParams(query, 1, sortBy, categoryIds, updatedSizes, colors, minPrice, maxPrice, activeCuratedFilter);

    // Toggle the 'selected' class on the button
    button.classList.toggle("selected", updatedSizes[sizeCategory]?.includes(sizeValue));

    // Disable/Enable buttons based on the selected width
    if (sizeCategory === "shoe_size_width") {
        const selectedWidth = sizeValue; // Use the value of the clicked button as the selected width

        document.querySelectorAll(".button-size[data-category='us_shoe_size']").forEach(usSizeButton => {
            const usSizeWidth = usSizeButton.getAttribute("data-width");

            if (usSizeWidth && usSizeWidth.includes(selectedWidth)) {
                usSizeButton.disabled = false; // Enable buttons with matching width
                localStorage.removeItem(`disabled_${usSizeButton.value}`); // Remove from localStorage if enabled
            } else {
                usSizeButton.disabled = true; // Disable buttons with non-matching width
                localStorage.setItem(`disabled_${usSizeButton.value}`, 'true'); // Save to localStorage if disabled
            }
            
        });

        // Update button states after modifying disabled state
        updateButtonStates();
    }

    // Render size tags
    const sizeTags = Object.entries(updatedSizes).flatMap(([category, values]) =>
        values.map(value => ({ category, value }))
    );
    renderTags('selected-size-filters', sizeTags, 'size');

    // Load items with the updated filters - PASS activeCuratedFilter
    loadItems(query, 1, sortBy, categoryIds, updatedSizes, colors, minPrice, maxPrice, activeCuratedFilter);

    // Update Blue Dot on Size tablink
    updateBlueDot("Size", Object.values(updatedSizes).some(values => values.length > 0));

    // Update blue dots for size_type links
    updateSizeTypeBlueDot(updatedSizes);
}


document.querySelectorAll(".button-size").forEach(button => {
    button.addEventListener("click", handleSizeClick);
});



















// color filters 
function handleColorClick(event) {
    const button = event.target.closest(".button-color");
    const colorValue = button.value;

    const { query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();
    let updatedColors = [...colors];

    // Toggle color selection
    if (updatedColors.includes(colorValue)) {
        updatedColors = updatedColors.filter(color => color !== colorValue);
    } else {
        updatedColors.push(colorValue);
    }

    // Update the color swatch border styling
    const colorSwatch = button.querySelector(".color-swatch");
    if (colorSwatch) {
        colorSwatch.classList.toggle("selected", updatedColors.includes(colorValue));
    }

    // Load items with updated color filter - PASS activeCuratedFilter
    loadItems(query, 1, sortBy, categoryIds, sizes, updatedColors, minPrice, maxPrice, activeCuratedFilter);
    updateURLParams(query, 1, sortBy, categoryIds, sizes, updatedColors, minPrice, maxPrice, activeCuratedFilter);

    // Update button states based on URL parameters
    updateButtonStates();

    // Render color tags
    renderTags('selected-color-filters', updatedColors, 'color');
}


// Attach event listener to color buttons
document.querySelectorAll(".button-color").forEach(button => {
    button.addEventListener("click", handleColorClick);
});


// price filters 
// Make these timeouts globally accessible
let priceTimeout;
let priceTagTimeout;

function handlePriceFilter() {
    clearTimeout(priceTimeout);
    clearTimeout(priceTagTimeout);

    priceTimeout = setTimeout(() => {
        const userMinPrice = document.getElementById('min-price').value;
        const userMaxPrice = document.getElementById('max-price').value;

        const { query, sortBy, categoryIds, sizes, colors } = getURLParams();

        // Load items and update the URL parameters - PASS activeCuratedFilter
        loadItems(query, 1, sortBy, categoryIds, sizes, colors, userMinPrice, userMaxPrice, activeCuratedFilter);
        updateURLParams(query, 1, sortBy, categoryIds, sizes, colors, userMinPrice, userMaxPrice, activeCuratedFilter);
    
        // Blue Dot Logic for Price Tab
        updateBlueDot("Price", userMinPrice || userMaxPrice);

    }, 500);

    // Separate timeout for rendering tags with a longer delay
    priceTagTimeout = setTimeout(() => {
        const userMinPrice = document.getElementById('min-price').value;
        const userMaxPrice = document.getElementById('max-price').value;

        // Render price tags after longer delay
        const priceTags = [];
        if (userMinPrice) priceTags.push(`Min: $${userMinPrice}`);
        if (userMaxPrice) priceTags.push(`Max: $${userMaxPrice}`);
        renderTags('selected-price-filters', priceTags, 'price');
        
    }, 2000); // 2 second delay for tags
}

// Attach event listeners to min and max price inputs
document.getElementById('min-price').addEventListener('input', handlePriceFilter);
document.getElementById('max-price').addEventListener('input', handlePriceFilter);

// On blur, immediately show tags
document.getElementById('min-price').addEventListener('blur', () => {
    clearTimeout(priceTagTimeout); // Clear the delayed tag timeout
    const userMinPrice = document.getElementById('min-price').value;
    const userMaxPrice = document.getElementById('max-price').value;
    
    if (userMinPrice || userMaxPrice) {
        const priceTags = [];
        if (userMinPrice) priceTags.push(`Min: $${userMinPrice}`);
        if (userMaxPrice) priceTags.push(`Max: $${userMaxPrice}`);
        renderTags('selected-price-filters', priceTags, 'price');
    }
});

document.getElementById('max-price').addEventListener('blur', () => {
    clearTimeout(priceTagTimeout); // Clear the delayed tag timeout
    const userMinPrice = document.getElementById('min-price').value;
    const userMaxPrice = document.getElementById('max-price').value;
    
    if (userMinPrice || userMaxPrice) {
        const priceTags = [];
        if (userMinPrice) priceTags.push(`Min: $${userMinPrice}`);
        if (userMaxPrice) priceTags.push(`Max: $${userMaxPrice}`);
        renderTags('selected-price-filters', priceTags, 'price');
    }
});

// Reset price filters logic
document.getElementById('reset-price-filter').addEventListener('click', function () {
    // Clear any pending timeouts
    clearTimeout(priceTimeout);
    clearTimeout(priceTagTimeout);
    
    // Clear the price input fields
    document.getElementById('min-price').value = '';
    document.getElementById('max-price').value = '';

    // Get existing URL parameters
    const { query, sortBy, categoryIds, sizes, colors } = getURLParams();

    // Reload items and update URL without min/max price
    loadItems(query, 1, sortBy, categoryIds, sizes, colors, '', '', activeCuratedFilter);
    updateURLParams(query, 1, sortBy, categoryIds, sizes, colors, '', '', activeCuratedFilter);

    // Clear the selected price tags from the UI
    renderTags('selected-price-filters', [], 'price');
    
    // Update blue dot
    updateBlueDot("Price", false);
});

// Make the timeout variables globally accessible for removeTag function
window.priceTimeout = priceTimeout;
window.priceTagTimeout = priceTagTimeout;


// category filters 
// Function to handle click on the **SUB** category button
function handleCategoryClick(categoryId, isActive) {
    const { sortBy, query, categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams();

    let updatedCategoryIds = [...categoryIds];

    if (isActive) {
        updatedCategoryIds = updatedCategoryIds.filter(id => id !== categoryId); // Remove category if active
    } else {
        updatedCategoryIds.push(categoryId); // Add category if not active
    }

    // Remove duplicates and update the selected categories
    updatedCategoryIds = [...new Set(updatedCategoryIds)];

    // PASS activeCuratedFilter
    loadItems(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
    updateURLParams(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter); 

    // Update button states based on URL parameters
    updateButtonStates();

    renderTags('selected-category-filters', updatedCategoryIds, 'category');
}


document.querySelectorAll('.dropdown-category').forEach(button => {
    button.addEventListener('click', function() {
        handleCategoryClick(this.value, this.classList.contains('selected'));
    });
});


// Function to handle click on the **TOP** category button
function handleTopCategoryClick(event) {
    const topCategoryButton = event.target.closest(".dropdown-top-category");
    const categoryIds = topCategoryButton.getAttribute("data-category-ids").split(",").filter(id => id);
    const isActive = topCategoryButton.classList.contains("selected");

    // Get the current URL parameters
    const { query, sortBy, sizes, colors, minPrice, maxPrice } = getURLParams();

    // Update categoryIds based on the new state
    let updatedCategoryIds = getURLParams().categoryIds.filter(id => !categoryIds.includes(id));

    if (!isActive) {
        updatedCategoryIds = [...new Set([...updatedCategoryIds, ...categoryIds])];
    }

    // Reload items with the updated category filters - PASS activeCuratedFilter
    loadItems(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
    updateURLParams(query, 1, sortBy, updatedCategoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);

    // Update button states based on URL parameters
    updateButtonStates();

    renderTags('selected-category-filters', updatedCategoryIds, 'category');
}


// Attach event listener to all top-level category buttons
document.querySelectorAll(".dropdown-top-category").forEach(button => {
    button.addEventListener("click", handleTopCategoryClick);
});


// sortBy dropdown
document.getElementById('dropdown-sortby').addEventListener('change', function () {
    const newSortBy = event.target.value;
    const { query, categoryIds, sizes, colors, minPrice, maxPrice } = getURLParams(); // Get all existing filters

    // Reload items with updated sorting, while keeping previous filters - PASS activeCuratedFilter
    loadItems(query, 1, newSortBy, categoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
    updateURLParams(query, 1, newSortBy, categoryIds, sizes, colors, minPrice, maxPrice, activeCuratedFilter);
});


// ============================
// Filters RESET
// ============================
// Reset filters that were previously applied/selected

// Helper function to remove selected class and reset elements
function resetSelectedClass(selector) {
    document.querySelectorAll(selector).forEach(button => {
        button.classList.remove('selected');
        // If the button has a color swatch, remove the selected class from it as well
        const colorSwatch = button.querySelector('.color-swatch');
        if (colorSwatch) {
            colorSwatch.classList.remove('selected');
        }
    });
}

// Helper function to clear tags in a container
function clearTags(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = ''; // Clear all tags
        container.style.display = 'none'; // Hide the container
    }
}

// Function to reset all filters
function resetAllFilters() {
    // Clear curated filter state first
    deactivateAllCuratedFilters();
    
    // 1. Clear tags in containers
    const tagContainers = [
        'selected-category-filters',
        'selected-size-filters',
        'selected-color-filters',
        'selected-price-filters'
    ];
    tagContainers.forEach(clearTags);

    // 2. Remove all selected classes from buttons
    resetSelectedClass('.dropdown-top-category.selected, .dropdown-category.selected');
    resetSelectedClass('.button-size.selected');
    resetSelectedClass('.button-color.selected');

    // 3. Reset price inputs
    document.getElementById('min-price').value = '';
    document.getElementById('max-price').value = '';

    // 4. Remove blue dots manually
    const tablinkNav = document.querySelectorAll('.tablink-nav');
    const tablink = document.querySelectorAll('.tablink');
    const filterButtons = document.querySelectorAll('#filter-button-category, #filter-button-color, #filter-button-price');
    const mainFilterButton = document.getElementById("filter-button");
    
    tablinkNav.forEach(el => el.classList.remove('blue-dot'));
    tablink.forEach(el => el.classList.remove('blue-dot'));
    filterButtons.forEach(el => el.classList.remove('blue-dot'));
    mainFilterButton?.classList.remove('blue-dot');

    // Remove blue dots from top_level_category links
    document.querySelectorAll('.top-level-link.blue-dot').forEach(topCategoryLink => {
        topCategoryLink.classList.remove('blue-dot');
    });

    // Update section visibility
    updateAllSectionVisibility();
    
    // Remove blue dots from size_type links
    updateSizeTypeBlueDot({});

    // 5. Re-enable all shoe size buttons
    document.querySelectorAll('.button-size[data-category="us_shoe_size"]').forEach(button => {
        button.disabled = false;
    });

    // 6. Clear shoe width data from localStorage
    Object.keys(localStorage).forEach(key => {
        if (key.startsWith('disabled_')) {
            localStorage.removeItem(key);
        }
    });

    // 7. Manually clear the URL first, then load items
    const searchInput = document.getElementById('opensearch-input');
    const currentUserQuery = searchInput ? searchInput.value.trim() : '';
    
    // Clear URL completely, keeping only the user's search query if it exists
    const newUrl = currentUserQuery ? `/browse/?query=${encodeURIComponent(currentUserQuery)}` : '/browse/';
    history.replaceState({}, '', newUrl);
    
    // Now load items and update URL with clean state
    loadItems(currentUserQuery, 1, 'newlyAdded', [], {}, [], '', '', null);
    updateURLParams(currentUserQuery, 1, 'newlyAdded', [], {}, [], '', '', null);
}

function resetPriceFilters() {
    // Clear the min and max price inputs
    document.getElementById('min-price').value = '';
    document.getElementById('max-price').value = '';

    // Reset URL params or reload the items
    const { query, sortBy, categoryIds, sizes, colors } = getURLParams();
    loadItems(query, 1, sortBy, categoryIds, sizes, colors, null, null); // Reload items with no price filters
    updateURLParams(query, 1, sortBy, categoryIds, sizes, colors, null, null); // Update URL params

    // Clear price tags from the UI
    renderTags('selected-price-filters', [], 'price');

    // Remove the blue dot from the Price tab
    updateBlueDot("Price", false);
}

// Add event listener to the reset price button
const resetPriceButton = document.getElementById("reset-price-filter");
resetPriceButton.addEventListener("click", resetPriceFilters);


// DESKTOP 'Reset All Filters' button functionality (only shows reset link when > 3 filter tags are selected)
function updateResetButtonVisibility() {
    // Get all elements with the class 'tag'
    const tags = document.querySelectorAll('.tag');
    
    // Count the number of visible tags
    let visibleTagCount = 0;
    tags.forEach(tag => {
        if (tag.offsetParent !== null) { // Check if the tag is visible
            visibleTagCount++;
        }
    });

    // Get the reset button
    const resetButton = document.querySelector('.reset-all-filters-button');

    // Show the button if more than 3 tags are visible, otherwise hide it
    if (visibleTagCount > 3) {
        resetButton.style.display = 'inline-block';
    } else {
        resetButton.style.display = 'none';
    }
}

// Call the function initially to set the correct state of the button
updateResetButtonVisibility();

// Optionally, you can set up a MutationObserver to watch for changes in the DOM
// and call the function whenever the DOM changes (e.g., tags are added/removed)
const observer = new MutationObserver(updateResetButtonVisibility);
observer.observe(document.body, { childList: true, subtree: true });

// Attach event listener to the Reset All Filters button (Desktop blue link)
document.querySelector('.reset-all-filters-button').addEventListener('click', resetAllFilters);
// Attach event listener to the Reset All Filters button (Mobile Button)
document.querySelector('.reset-all-filters-button-mobile-overlay-menu').addEventListener('click', resetAllFilters);


// ============================
// Pagination
// ============================
// Manage pagination behavior

function createPaginationControls(currentPage, totalPages, query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter = null) {
    const paginationContainer = document.getElementById('pagination');
    paginationContainer.innerHTML = '';

    const maxVisiblePages = 4; // Maximum number of visible page buttons
    const pageRange = Math.floor(maxVisiblePages / 2); // Range of pages to show around the current page

    const createButton = (text, page, isDisabled, isActive = false, isNav = false) => {
        const button = document.createElement(isDisabled ? 'span' : 'a');
        button.textContent = text;
        button.className = 'button-pagination';
        if (isDisabled) {
            button.classList.add('disabled'); 
            // Add 'no-border' class for disabled ellipsis buttons
            if (text === '...') {
                button.classList.add('no-border');
            }

        }
        if (isActive) {
            button.classList.add('selected');
        }
        if (!isDisabled && !isNav) {
            let href = `?page=${page}&query=${query}&sortBy=${sortBy}&categoryIds=${categoryIds}&sizes=${sizes}`;
            if (curatedFilter) {
                href += `&curated_filter=${curatedFilter}`;
            }
            button.href = href;
        }
        if (!isDisabled && isNav) {
            button.addEventListener('click', (event) => {
                if (event.target.classList.contains('button-pagination')) {
                    window.scrollTo({ top: 0, behavior: 'smooth' }); // Scroll to top only for pagination buttons
                }
                updateURLParams(query, page, sortBy, categoryIds, sizes, colors, minPrice, maxPrice);
                loadItems(query, page, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter);
            });
        }        
        return button;
    };

    // Previous button
    paginationContainer.appendChild(createButton('←', currentPage - 1, currentPage <= 1, false, true));

    if (totalPages <= maxVisiblePages) {
        // Simple case: show all pages
        for (let page = 1; page <= totalPages; page++) {
            const isActive = page === currentPage;
            const pageButton = createButton(page, page, false, isActive, true);
            paginationContainer.appendChild(pageButton);
        }
    } else {
        // Complex case: show subset with ellipsis
        let startPage = Math.max(1, currentPage - pageRange);
        let endPage = Math.min(totalPages, currentPage + pageRange);

        if (currentPage - pageRange <= 1) {
            endPage = Math.min(maxVisiblePages, totalPages);
        }

        if (currentPage + pageRange >= totalPages) {
            startPage = Math.max(1, totalPages - maxVisiblePages + 1);
        }

        // First page button (only if not already in range)
        if (startPage > 1) {
            paginationContainer.appendChild(createButton('1', 1, false, false, true));
            if (startPage > 2) {
                paginationContainer.appendChild(createButton('...', startPage - 1, true));
            }
        }

        // Page buttons
        for (let page = startPage; page <= endPage; page++) {
            const isActive = page === currentPage;
            const pageButton = createButton(page, page, false, isActive, true);
            paginationContainer.appendChild(pageButton);
        }

        // Last page button (only if not already in range)
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationContainer.appendChild(createButton('...', endPage + 1, true));
            }
            paginationContainer.appendChild(createButton(totalPages, totalPages, false, false, true));
        }
    }

    // Next button
    paginationContainer.appendChild(createButton('→', currentPage + 1, currentPage >= totalPages, false, true));
}

function renderPagination(currentPage, totalPages, query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter = null) {
    createPaginationControls(currentPage, totalPages, query, sortBy, categoryIds, sizes, colors, minPrice, maxPrice, curatedFilter);
}


// Restrict numbers only allowed in min/max price inputs
// Apply the restriction to the min and max price inputs
function restrictToNumbers(inputElement) {
    inputElement.addEventListener('input', function (event) {
        // Remove any non-numeric characters
        this.value = this.value.replace(/[^0-9]/g, '');
    });
}
// Apply the restriction to the min and max price inputs
const minPriceInput = document.getElementById('min-price');
const maxPriceInput = document.getElementById('max-price');

restrictToNumbers(minPriceInput);
restrictToNumbers(maxPriceInput);









// ============================
// CURATED FITLER LOGIC
// ============================

let activeCuratedFilter = null;
let curatedFilterQuery = ''; // Store the curated query separately

function initializeCuratedFilters() {
    
    // Find all curated filter buttons
    const curatedButtons = document.querySelectorAll('.curated-filter-btn');
    
    // Add click listeners to all curated filter buttons
    curatedButtons.forEach(button => {
        const filterName = button.getAttribute('data-filter');
        
        if (CURATED_FILTERS[filterName]) {
            button.addEventListener('click', function(event) {
                event.preventDefault();
                
                toggleCuratedFilter(filterName, this);
            });
            
        } else {
            console.warn('🔍 CURATED: No config found for filter:', filterName);
        }
    });
   
 
 
}

function toggleCuratedFilter(filterName, buttonElement) {

    if (activeCuratedFilter === filterName) {
        // Deactivate current filter
        activeCuratedFilter = null;
        curatedFilterQuery = '';
        buttonElement.classList.remove('active');
        clearCuratedFilter();
    } else {      
        // Don't call clearCuratedFilter() when switching between filters
        // Just deactivate button states and apply the new filter directly
        
        // Deactivate all button visual states
        deactivateAllCuratedFilters();
        
        // Set the new filter BEFORE calling applyCuratedFilter
        activeCuratedFilter = filterName;
        buttonElement.classList.add('active');
        
        // Apply the new filter directly without clearing first
        applyCuratedFilter(filterName);
    }
}



function applyCuratedFilter(filterName) {
    const config = CURATED_FILTERS[filterName];
    
    // Build curated terms
    const allSearchTerms = [];
    if (config.keywords && config.keywords.length > 0) {
        allSearchTerms.push(...config.keywords);
    }
    if (config.materials && config.materials.length > 0) {
        allSearchTerms.push(...config.materials);
    }
    if (config.brands && config.brands.length > 0) {
        allSearchTerms.push(...config.brands);
    }
    
    const uniqueTerms = [...new Set(allSearchTerms)];
    curatedFilterQuery = uniqueTerms.join(' ');
    
    // Update global variables immediately
    window.activeCuratedFilter = activeCuratedFilter;
    window.curatedFilterQuery = curatedFilterQuery;
    
    // Extract categories and colors 
    let curatedCategories = [];
    if (config.categories) {
        Object.values(config.categories).forEach(categoryList => {
            if (Array.isArray(categoryList)) {
                curatedCategories.push(...categoryList);
            }
        });
    }
     // Ensure curatedCategories is always an array and remove duplicates
    curatedCategories = [...new Set(curatedCategories)];

    let curatedColors = [];
    if (config.colors && config.colors.length > 0) {
        curatedColors.push(...config.colors.map(color => color.toLowerCase()));
    }
    // Ensure curatedColors is always an array and remove duplicates
    curatedColors = [...new Set(curatedColors)];
    
    // Get current user input WITHOUT modifying it
    const searchInput = document.getElementById('opensearch-input');
    const currentUserQuery = searchInput ? searchInput.value.trim() : '';
    
    if (window.pageInitialized) {
        
        // Get existing user filters
        const { sizes, minPrice, maxPrice } = getURLParams();
        const currentSortBy = document.getElementById('dropdown-sortby')?.value || 'newlyAdded';
        
        // Combine user query with curated query for search
        let finalQuery = '';
        if (currentUserQuery && curatedFilterQuery) {
            finalQuery = `${currentUserQuery} ${curatedFilterQuery}`;
        } else if (currentUserQuery) {
            finalQuery = currentUserQuery;
        } else if (curatedFilterQuery) {
            finalQuery = curatedFilterQuery;
        }
        
        // Load items with combined state
        loadItems(finalQuery, 1, currentSortBy, curatedCategories, sizes, curatedColors, minPrice, maxPrice, activeCuratedFilter);
        updateURLParams(finalQuery, 1, currentSortBy, curatedCategories, sizes, curatedColors, minPrice, maxPrice, activeCuratedFilter);
        
        // Add user_query parameter to URL to preserve original user input
        if (currentUserQuery) {
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.set('user_query', currentUserQuery);
            history.replaceState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
        }
        
        // Update UI
        renderTags('selected-category-filters', curatedCategories, 'category');
        renderTags('selected-color-filters', curatedColors, 'color');
        
        const sizeTags = Object.entries(sizes).flatMap(([category, values]) =>
            values.map(value => ({ category, value }))
        );
        renderTags('selected-size-filters', sizeTags, 'size');
        
        const priceTags = [];
        if (minPrice) priceTags.push(`Min: ${minPrice}`);
        if (maxPrice) priceTags.push(`Max: ${maxPrice}`);
        renderTags('selected-price-filters', priceTags, 'price');
        
        // Update button states and blue dots
        setTimeout(() => {
            updateButtonStates();
            updateBlueDot("Category", curatedCategories.length > 0);
            updateBlueDot("Size", Object.values(sizes).some(v => v.length > 0));
            updateBlueDot("Color", curatedColors.length > 0);
            updateBlueDot("Price", minPrice || maxPrice);
            updateAllSectionVisibility();
        }, 50);
    }
}


function clearCuratedFilter() {
    curatedFilterQuery = '';
    
    //  Update global variables immediately
    window.activeCuratedFilter = null;
    window.curatedFilterQuery = '';
    
    // DON'T touch the search input - let user keep their search
    const searchInput = document.getElementById('opensearch-input');
    const currentUserQuery = searchInput ? searchInput.value.trim() : '';
    
    // Fallback to basic reset with UI updates
    try {
        const isBrowsePage = window.location.pathname === '/browse/';
        
        if (isBrowsePage && typeof loadItems === 'function') {
            // Get current filter state but clear curated filters (categories, colors)
            let currentSizes = {};
            let minPrice = '';
            let maxPrice = '';
            
            if (typeof getURLParams === 'function') {
                const urlData = getURLParams();
                currentSizes = urlData.sizes || {};
                minPrice = urlData.minPrice || '';
                maxPrice = urlData.maxPrice || '';
            }
            
            const currentSortBy = document.getElementById('dropdown-sortby')?.value || 'newlyAdded';
            
            // Load with user's search but no curated categories/colors and NO curated filter
            loadItems(currentUserQuery, 1, currentSortBy, [], currentSizes, [], minPrice, maxPrice, null);
            
            if (typeof updateURLParams === 'function') {
                updateURLParams(currentUserQuery, 1, currentSortBy, [], currentSizes, [], minPrice, maxPrice, null);
            }
            
            // Clean up URL parameters
            const urlParams = new URLSearchParams(window.location.search);
            urlParams.delete('curated_filter');
            urlParams.delete('user_query');
            if (currentUserQuery) {
                urlParams.set('query', currentUserQuery);
            } else {
                urlParams.delete('query');
            }
            history.replaceState({}, '', `${window.location.pathname}?${urlParams.toString()}`);
            
            // Update tags to show cleared state
            if (typeof renderTags === 'function') {
                renderTags('selected-category-filters', [], 'category'); // Clear categories
                renderTags('selected-color-filters', [], 'color'); // Clear colors
                
                // Keep existing size and price tags
                const sizeTags = Object.entries(currentSizes).flatMap(([category, values]) =>
                    values.map(value => ({ category, value }))
                );
                renderTags('selected-size-filters', sizeTags, 'size');
                
                const priceTags = [];
                if (minPrice) priceTags.push(`Min: ${minPrice}`);
                if (maxPrice) priceTags.push(`Max: ${maxPrice}`);
                renderTags('selected-price-filters', priceTags, 'price');
            }
            
            // Update button states
            if (typeof updateButtonStates === 'function') {
                setTimeout(() => {
                    updateButtonStates();
                }, 50);
            }
            
            // Update blue dots
            if (typeof updateBlueDot === 'function') {
                updateBlueDot("Category", false); // No categories
                updateBlueDot("Size", Object.values(currentSizes).some(v => v.length > 0));
                updateBlueDot("Color", false); // No colors
                updateBlueDot("Price", minPrice || maxPrice);
            }
            
            // Update section visibility
            if (typeof updateAllSectionVisibility === 'function') {
                updateAllSectionVisibility();
            }
        }
        
    } catch (error) {
        console.error('🔍 CURATED: Error clearing curated filter:', error);
    }
    
}

function initializeGlobalCuratedVariables() {
    // Make curated filter variables globally accessible
    window.activeCuratedFilter = activeCuratedFilter || null;
    window.curatedFilterQuery = curatedFilterQuery || '';
    
    // Also expose the CURATED_FILTERS config if it exists
    if (typeof CURATED_FILTERS !== 'undefined') {
        window.CURATED_FILTERS = CURATED_FILTERS;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Add a small delay to ensure other scripts have loaded
    setTimeout(() => {
        initializeGlobalCuratedVariables();
    }, 100);
});

// Also call it immediately in case DOM is already loaded
if (document.readyState !== 'loading') {
    setTimeout(() => {
        initializeGlobalCuratedVariables();
    }, 100);
}



function deactivateAllCuratedFilters() {
    // Remove active class from all curated filter buttons
    const curatedButtons = document.querySelectorAll('.curated-filter-btn');
    curatedButtons.forEach(button => {
        button.classList.remove('active');
    });  
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        initializeCuratedFilters();
    }, 1500); // Wait for other scripts to load
});

const clearAllButton = document.querySelector('.clear-all-button');
if (clearAllButton) {
    clearAllButton.addEventListener('click', function(event) {
        event.preventDefault();
        resetAllFilters(); // This handles both regular and curated filter clearing perfectly
    });
}









// Make curated filter variables globally accessible
window.activeCuratedFilter = activeCuratedFilter;
window.curatedFilterQuery = curatedFilterQuery;
window.CURATED_FILTERS = CURATED_FILTERS;