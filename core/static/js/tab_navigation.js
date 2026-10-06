// ============================
// tab_navigation.js 
// ============================

// Ensure the heights of desktop hover menus are synced 
// Function to sync heights of hover menu #Category and #Category2, #Size and #Size2
function syncCategoryHeights() {
    const categoryDiv = document.getElementById('Category');
    const category2Div = document.getElementById('Category2');
    const sizeDiv = document.getElementById('Size');
    const size2Div = document.getElementById('Size2');

    // Sync heights for #Category and #Category2
    if (categoryDiv && category2Div) {
        // Temporarily make #Category visible to calculate its height
        const originalDisplay = categoryDiv.style.display;
        categoryDiv.style.display = 'block';

        // Get the height of #Category
        const categoryHeight = categoryDiv.offsetHeight;

        // Restore the original display value of #Category
        categoryDiv.style.display = originalDisplay;

        // Get the current height of #Category2
        const category2Height = category2Div.offsetHeight;

        // Set the min-height of #Category2 to the larger of the two heights
        category2Div.style.minHeight = `${Math.max(categoryHeight, category2Height)}px`;

    }

    // Sync heights for #Size and #Size2
    if (sizeDiv && size2Div) {
        // Temporarily make #Size visible to calculate its height
        const originalDisplay = sizeDiv.style.display;
        sizeDiv.style.display = 'block';

        // Get the height of #Size
        const sizeHeight = sizeDiv.offsetHeight;

        // Restore the original display value of #Size
        sizeDiv.style.display = originalDisplay;

        // Get the current height of #Size2
        const size2Height = size2Div.offsetHeight;

        // Set the min-height of #Size2 to the larger of the two heights
        size2Div.style.minHeight = `${Math.max(sizeHeight, size2Height)}px`;


    }
}

// Function to smoothly scroll to top
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

document.addEventListener('DOMContentLoaded', function () {
    // Ensure the heights of desktop hover menus are synced when the page loads
    syncCategoryHeights();


    // Initialize tab navigation
    const navigationPlaceholders = document.getElementsByClassName('tab-navigation');
    for (let placeholder of navigationPlaceholders) {
        const tabLinks = placeholder.getElementsByClassName('tablink-nav');
        Array.from(tabLinks).forEach(tabLink => {
            tabLink.addEventListener('click', () => handleTabClick(tabLink, tabLinks));
        });

        // Add click event to the 'more' filter button
        document.getElementById('filter-button').addEventListener('click', () => {
            const mobileNav = document.getElementById('tabcontent-mobile-nav');
            if (mobileNav) {
                mobileNav.style.display = 'block';
            }
            const categoryTabLink = Array.from(tabLinks).find(link => link.getAttribute('data-tab') === 'Category');
            if (categoryTabLink) {
                handleTabClick(categoryTabLink, tabLinks);
            }
        });

        // Initialize category logic
        const categoryDiv = document.getElementById('Category');
        const category2Div = document.getElementById('Category2');
        const topLevelCategories = document.getElementsByClassName('top_level_category');
        Array.from(topLevelCategories).forEach(category => {
            category.addEventListener('click', () => {
                const clickedCategory = category.getAttribute('data-top-category');
                toggleCategoryLayers(clickedCategory, categoryDiv, category2Div);
            });
        });

        
        // Add click event listener to the back button
        const backButton = document.querySelector('.back-button');
        if (backButton) {
            backButton.addEventListener('click', () => {
                if (categoryDiv) categoryDiv.style.display = 'block';
                if (category2Div) category2Div.style.display = 'none';
            });
        }
    }

    // Initialize size navigation
    const sizePlaceholders = document.getElementsByClassName('tab-navigation');
    for (let placeholder of sizePlaceholders) {
        const sizeLinks = placeholder.getElementsByClassName('size_type');
        Array.from(sizeLinks).forEach(sizeLink => {
            sizeLink.addEventListener('click', () => handleSizeClick(sizeLink, sizeLinks));
        });

        const sizeDiv = document.getElementById('Size');
        const size2Div = document.getElementById('Size2');
        const sizeTypes = document.getElementsByClassName('size_type');
        Array.from(sizeTypes).forEach(sizeType => {
            sizeType.addEventListener('click', () => {
                const clickedSizeType = sizeType.getAttribute('data-category');
                toggleSizeLayers(clickedSizeType, sizeDiv, size2Div);
            });
        });

        const backButtonSize = document.querySelector('.back-button-size');
        if (backButtonSize) {
            backButtonSize.addEventListener('click', () => {
                if (sizeDiv) sizeDiv.style.display = 'block';
                if (size2Div) size2Div.style.display = 'none';
            });
        }
    }

    // Initialize hover logic
    initializeHoverLogic();

});

// Helper function to toggle category layers
function toggleCategoryLayers(clickedCategory, categoryDiv, category2Div) {
    if (categoryDiv) categoryDiv.style.display = 'none';
    if (category2Div) category2Div.style.display = 'block';

    // Hide all buttons AND subgroup labels
    const allButtons = category2Div.querySelectorAll('.dropdown-category, .dropdown-top-category, .subgroup-label');
    allButtons.forEach(button => button.style.display = 'none');

    // Show relevant buttons AND subgroup labels for the clicked category
    const relevantButtons = category2Div.querySelectorAll(
        `.dropdown-category[data-top-category="${clickedCategory}"], 
         .dropdown-top-category[data-top-category="${clickedCategory}"],
         .subgroup-label[data-top-category="${clickedCategory}"]`
    );
    relevantButtons.forEach(button => button.style.display = 'block');

    const secondLayerCategoryName = category2Div.querySelector('.top_level_category');
    if (secondLayerCategoryName) {
        secondLayerCategoryName.textContent = clickedCategory;
        secondLayerCategoryName.setAttribute('data-top-category', clickedCategory);
    }
}
// Helper function to toggle size layers
function toggleSizeLayers(clickedSizeType, sizeDiv, size2Div) {
    if (sizeDiv) sizeDiv.style.display = 'none';
    if (size2Div) size2Div.style.display = 'block';

    const allButtons = size2Div.querySelectorAll('.category-container');
    allButtons.forEach(button => button.style.display = 'none');

    const relevantButtons = size2Div.querySelectorAll(`.category-container[data-category="${clickedSizeType}"]`);
    relevantButtons.forEach(button => button.style.display = 'block');

    const secondLayerSizeType = size2Div.querySelector('.size_type');
    if (secondLayerSizeType) {
        secondLayerSizeType.textContent = clickedSizeType;
    }
}

// Handle tab click event
function handleTabClick(tabLink, tabLinks) {

    Array.from(tabLinks).forEach(link => link.classList.remove('active'));
    tabLink.classList.add('active');

    const allTabContents = document.querySelectorAll('.tabcontent');
    allTabContents.forEach(tabContent => tabContent.style.display = 'none');

    const activeTabName = tabLink.getAttribute('data-tab');
    const activeTabContent = document.getElementById(activeTabName);
    if (activeTabContent) activeTabContent.style.display = 'block';

    const mobileNavText = document.querySelector('#tabcontent-mobile-nav #tabName');
    if (mobileNavText) mobileNavText.textContent = activeTabName;
}
// Toggle visibility of tab content
function toggleTabContent(pageName = null, isVisible = true) {
    const tabcontentElements = document.getElementsByClassName('tabcontent');
    Array.from(tabcontentElements).forEach(tabContent => tabContent.style.display = 'none');

    if (pageName) {
        const tabcontent = document.getElementById(pageName);
        if (tabcontent) tabcontent.style.display = isVisible ? 'block' : 'none';
    }

    const mobileNav = document.getElementById('tabcontent-mobile-nav');
    if (mobileNav) mobileNav.style.display = isVisible ? 'block' : 'none';
}

// Initialize hover logic
function initializeHoverLogic() {
    const tablinks = document.getElementsByClassName('tablink');
    Array.from(tablinks).forEach(tablink => {
        tablink.addEventListener('mouseenter', () => {
            if (isDesktop()) {
                const pageName = tablink.getAttribute('data-tab');
                closeAllTabContentExcept(pageName);
                toggleTabContent(pageName, true);
            }
        });

        tablink.addEventListener('mouseleave', () => {
            if (isDesktop()) {
                const pageName = tablink.getAttribute('data-tab');
                toggleTabContent(pageName, false);
            }
        });

        tablink.addEventListener('click', () => {
            if (!isDesktop()) {
                const pageName = tablink.getAttribute('data-tab');
                if (pageName) { // Only proceed if data-tab attribute exists
                    toggleTabContent(pageName, !isVisible(pageName));
                }
            }
        });
        
    });

    const tabcontents = document.getElementsByClassName('tabcontent');
    Array.from(tabcontents).forEach(tabcontent => {
        tabcontent.addEventListener('mouseenter', () => {
            if (isDesktop()) {
                const pageName = tabcontent.id;
                closeAllTabContentExcept(pageName);
                toggleTabContent(pageName, true);
            }
        });

        // Close tabcontent when the mouse leaves any tabcontent
        tabcontent.addEventListener('mouseleave', () => {
            if (isDesktop()) {
                const pageName = tabcontent.id;
                toggleTabContent(pageName, false); // Close the current tabcontent
            }
        });
    });
}

// Helper function to check if tabcontent is visible
function isVisible(pageName) {
    if (!pageName) return false; // Add null check
    const tabcontent = document.getElementById(pageName);
    if (!tabcontent) return false; // Add element existence check
    return tabcontent.style.display === 'block';
}

// Helper function to check if the device is a desktop
function isDesktop() {
    return window.innerWidth > 768;
}

// Close all tab content except the specified one
function closeAllTabContentExcept(pageName) {
    Array.from(document.getElementsByClassName('tabcontent')).forEach(content => {
        if (content.id !== pageName) content.style.display = 'none';
    });
}

// Close all tab content
function closeAllTabContent() {
    Array.from(document.getElementsByClassName('tabcontent')).forEach(tabContent => {
        tabContent.style.display = 'none';
    });

    const mobileNav = document.getElementById('tabcontent-mobile-nav');
    if (mobileNav) mobileNav.style.display = 'none';
}




// Event listeners for close buttons
document.querySelectorAll('.close-button').forEach(button => {
    button.addEventListener('click', () => {
        toggleTabContent(null, false);
    });
});

