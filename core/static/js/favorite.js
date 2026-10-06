// ============================
// favorite.js 
// ============================


// Function to get a cookie by name
const getCookie = (name) => {
    const cookieValue = document.cookie.split('; ').find(row => row.startsWith(`${name}=`));
    return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : null;
};

// Function to fetch the authentication status
const checkAuth = () => fetch('/api/check-auth/', { method: 'GET', credentials: 'include' });

// Function to update local storage and button state
// Function to update local storage and button state
const updateFavoriteState = (itemId, isFavorited) => {
    let favoritedItemIds = JSON.parse(localStorage.getItem('favoritedItemIds') || '[]');
    
    if (isFavorited) {
        if (!favoritedItemIds.includes(itemId)) {
            favoritedItemIds.push(itemId);
        }
    } else {
        favoritedItemIds = favoritedItemIds.filter(id => id !== itemId);
    }
    
    localStorage.setItem('favoritedItemIds', JSON.stringify(favoritedItemIds));
    
    // Update ALL buttons with the same item ID (both overlay and modal)
    const allButtonsForItem = document.querySelectorAll(`[data-item-id="${itemId}"]`);
    allButtonsForItem.forEach(button => {
        updateFavoriteButton(button, isFavorited);
    });
};

// Function to handle the favorite button click
const handleFavoriteButtonClick = async (button) => {
    const itemId = button.dataset.itemId;
    const isFavorited = !button.classList.contains('favorited');
    
    console.log(`Button clicked for item ID: ${itemId}, isFavorited: ${isFavorited}`);

    // Update the button state visually and in local storage
    updateFavoriteButton(button, isFavorited);
    updateFavoriteState(itemId, isFavorited);

    try {
        const response = await checkAuth();
        
        if (response.status === 401) {
            console.log('User is not authenticated. Redirecting to login.');
            const currentUrl = window.location.href; // Capture full URL with filters
            localStorage.setItem('pending_favorite', JSON.stringify({ item_id: itemId, is_favorited: isFavorited }));
            localStorage.setItem('redirect_after_login', currentUrl);
            window.location.href = `/accounts/login/`;
        } else {
            console.log('User is authenticated. Processing favorite...');
            await processFavorite(itemId, isFavorited);
        }
    } catch (error) {
        console.error('Error during authentication check:', error);
    }
};

// Function to process the favorite action
const processFavorite = async (itemId, isFavorited) => {
    try {
        const method = isFavorited ? 'POST' : 'DELETE'; // Use POST to add favorite, DELETE to remove it
        console.log(`Sending ${method} request for item ID: ${itemId}`);

        // Create the request body with the required parameters
        const requestBody = {
            item_id: itemId,
            is_favorited: isFavorited,
            action: isFavorited ? 'add' : 'remove', // Adding the action parameter
            favorited_at: new Date().toISOString() // Add the current date and time in ISO format
        };

        console.log('Request Body:', JSON.stringify(requestBody)); // Log the request body

        const response = await fetch('/api/favorite/', {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(requestBody), // Use the requestBody variable here
            credentials: 'include',
        });

        console.log('Favorite action response:', response);

        if (response.type === 'opaqueredirect') {
            window.location.href = response.url;
        } else if (!response.ok) {
            const text = await response.text();
            console.error('Error response text:', text);
            throw new Error('Something went wrong');
        } else {
            const responseData = await response.json();
            console.log('Favorite action successful:', responseData);
            
        }
    } catch (error) {
        console.error('Error in processFavorite function:', error);
    }
};


// Function to initialize favorite buttons
function initFavorites() {
    // Get favorited item IDs from localStorage (must match updateFavoriteState)
    const favoritedItemIds = JSON.parse(localStorage.getItem('favoritedItemIds') || '[]');

    // Apply favorited state to all favorite buttons on the page
    favoritedItemIds.forEach(itemId => {
        const favoriteButtons = document.querySelectorAll(`[data-item-id="${itemId}"]`);
        
        favoriteButtons.forEach(favoriteButton => {
            // Only add the "favorited" state if it isn't already applied
            if (favoriteButton && !favoriteButton.classList.contains('favorited')) {
                favoriteButton.classList.add('favorited');
                // Update the button's visual state
                updateFavoriteButton(favoriteButton, true);
            }
        });
    });
}

// Function to update the button text and class
const updateFavoriteButton = (button, isFavorited) => {
    button.classList.toggle('favorited', isFavorited);

    const saved = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 20.4001L10.6725 19.1916C5.95753 14.9161 2.84473 12.0962 2.84473 8.63552C2.84473 5.81568 5.06031 3.6001 7.88015 3.6001C9.47317 3.6001 11.0021 4.34168 12 5.51356C12.998 4.34168 14.5269 3.6001 16.1199 3.6001C18.9398 3.6001 21.1554 5.81568 21.1554 8.63552C21.1554 12.0962 18.0425 14.9161 13.3276 19.2008L12 20.4001Z" fill="#48110C"/>
        </svg>
    `;

    const save = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M16.1201 4.1001C18.6636 4.10019 20.6551 6.09175 20.6553 8.63525C20.6553 10.2014 19.9552 11.6615 18.6221 13.2925C17.2834 14.9302 15.3594 16.6785 12.9922 18.8296L12.001 19.7251L11.0088 18.8218V18.8208L9.31836 17.2817C7.7155 15.8082 6.382 14.519 5.37793 13.2915C4.04495 11.6618 3.34473 10.2014 3.34473 8.63525C3.34487 6.09178 5.3364 4.10024 7.87988 4.1001C9.32138 4.1001 10.713 4.77349 11.6191 5.8374L12 6.28467L12.3809 5.8374C13.287 4.77347 14.6786 4.1001 16.1201 4.1001Z" stroke="#48110C"/>
        </svg>
    `;

    // Update button's inner HTML with SVG and conditionally include text
    button.innerHTML = `${isFavorited ? saved : ''} ${isFavorited ? '' : save }`;
};

// Function to load pending favorites after redirecting
const loadPendingFavorite = async () => {
    const pendingFavorite = localStorage.getItem('pending_favorite');
    const redirectUrl = localStorage.getItem('redirect_after_login');
    if (pendingFavorite) {
        const { item_id, is_favorited } = JSON.parse(pendingFavorite);
        const response = await checkAuth();
        if (response.status === 200) {
            await processFavorite(item_id, is_favorited);
            localStorage.removeItem('pending_favorite');
            localStorage.removeItem('redirect_after_login');
            if (redirectUrl) {
                window.location.href = redirectUrl; // Redirect directly to the stored URL
            }
        } else {
            console.log('User is not authenticated yet');
        }
    }
};
// Function to create the favorite button element
export const createFavoriteButton = (item, isFavorited) => {
    const button = document.createElement('button');
    button.className = 'overlay-button button-light';
    button.dataset.itemId = item.item_id;
    updateFavoriteButton(button, isFavorited);
    button.onclick = () => handleFavoriteButtonClick(button);
    return button;
};

// Initialize favorites when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initFavorites();
    loadPendingFavorite();
});

// Ensure createFavoriteButton is available globally
window.createFavoriteButton = createFavoriteButton;

// Make sure this runs after the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    const overlayButtons = document.querySelectorAll('.overlay-button');
    
    overlayButtons.forEach(button => {
        button.addEventListener('click', (event) => {
            event.preventDefault(); // Prevent default behavior
            handleFavoriteButtonClick(button);
        });
    });
});
