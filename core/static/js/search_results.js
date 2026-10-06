// ============================
// search_results.js - Backend Search Results 
// ============================
// Save, Sort, Publish Backend Inventory of items

// Function to get CSRF token, pairs with javascript code at bottom of this code, save to database
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}



document.addEventListener('DOMContentLoaded', function() {
    // category dropdown & update button
    var updateButtons = document.querySelectorAll('.update-category-btn');
    updateButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            var form = button.closest('form');
            var itemId = form.querySelector('.item-id').value;
            var categoryId = form.querySelector('.item-category-dropdown').value;
            var color = form.querySelector('.item-color-dropdown').value; // Add this line
            var csrftoken = getCookie('csrftoken'); // Function to get CSRF token (see below)

            fetch('/update_category/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ 
                    itemId: itemId, 
                    categoryId: categoryId,
                    color: color
                })
            })
            .then(response => {
                if (response.ok) {
                    console.log('Item updated');
                    // Optionally, display success message
                    var message = form.querySelector('.update-message');
                    message.classList.remove('hidden');
                    setTimeout(function() {
                        message.classList.add('hidden');
                    }, 3000); // Hide message after 3 seconds
                } else {
                    console.error('Failed to update category');
                    // Optionally, display an error message to the user
                }
            })
            .catch(error => {
                console.error('Error updating category:', error);
                // Optionally, display an error message to the user
            });
        });
    });

    // Function to toggle the selection effect
    function toggleSelection(item) {
        item.classList.toggle('selected');
    }
    // Add an event listener to the document that listens for clicks on items with the "item-container" class
    document.querySelectorAll('.item-container').forEach(function (container) {
        container.addEventListener('click', function (event) {
            toggleSelection(container);
        });
    });

    // Function to toggle the 'selected' state on clicked items
    function toggleSelection(itemElement) {
        itemElement.classList.toggle('selected');
    }

    // Add an event listener to the document to handle clicks on specific child elements
    document.addEventListener('click', function (event) {
        // Find the closest parent element with one of the desired classes
        const targetElement = event.target.closest(
            '.published-item-container, .sold-item-container'
        );

        // If a matching element is found, toggle its selection
        if (targetElement) {
            toggleSelection(targetElement);
        }
    });



    // Begin pagination for first set of items
    let totalPages = 0; // Define totalPages at a higher scope

    // Function to update pagination controls
    const updatePaginationControls = () => {
        const paginationContainer = document.querySelector('.pagination');
        const paginatedList = document.getElementById('paginated-list');
        let currentPage = parseInt(paginatedList.getAttribute('data-current-page'));
        const listItems = paginatedList.querySelectorAll('.item-container');
        const paginationLimit = 21;
        const totalItems = listItems.length;
        const totalPages = Math.ceil(totalItems / paginationLimit);

        const maxVisiblePages = 7;
        const pageRange = Math.floor(maxVisiblePages / 2);

        const baseQueryString = new URLSearchParams(window.location.search);

        let pageLinks = '';

        if (totalPages <= maxVisiblePages) {
            for (let page = 1; page <= totalPages; page++) {
                pageLinks += page === currentPage
                    ? `<span class="button-pagination selected" data-page="${page}">${page}</span>`
                    : `<a href="?page=${page}&${baseQueryString}" class="button-pagination " data-page="${page}">${page}</a>`;
            }
        } else {
            if (currentPage > pageRange + 1) {
                pageLinks += `<a href="?page=1&${baseQueryString}" class="button-pagination " data-page="1">first</a>`;
            }

            let startPage = Math.max(1, currentPage - pageRange);
            let endPage = Math.min(totalPages, currentPage + pageRange);

            if (currentPage - pageRange <= 1) {
                endPage = Math.min(maxVisiblePages, totalPages);
            }

            if (currentPage + pageRange >= totalPages) {
                startPage = Math.max(1, totalPages - maxVisiblePages + 1);
            }

            for (let page = startPage; page <= endPage; page++) {
                pageLinks += page === currentPage
                    ? `<span class="button-pagination selected" data-page="${page}">${page}</span>`
                    : `<a href="?page=${page}&${baseQueryString}" class="button-pagination " data-page="${page}">${page}</a>`;
            }

            if (currentPage + pageRange < totalPages - 1) {
                pageLinks += `<a href="?page=${totalPages}&${baseQueryString}" class="button-pagination " data-page="${totalPages}">last</a>`;
            }
        }

        paginationContainer.innerHTML = `
            <span class="step-links" style="display:flex;"">
                ${currentPage > 1 ? `<a href="?page=${currentPage - 1}&${baseQueryString}" class="button-pagination " data-page="${currentPage - 1}" id="prev-link">&laquo;</a>` : '<span class="button-pagination  disabled">&laquo;</span>'}
                ${pageLinks}
                ${currentPage < totalPages ? `<a href="?page=${currentPage + 1}&${baseQueryString}" class="button-pagination " data-page="${currentPage + 1}" id="next-link">&raquo;</a>` : '<span class="button-pagination  disabled">&raquo;</span>'}
            </span>
        `;

        // Remove theselected class from all pagination links
        const paginationLinks = paginationContainer.querySelectorAll('.button-pagination');
        paginationLinks.forEach(link => {
            link.classList.remove('selected');
        });

        // Add theselected class to the current page link
        const selectedLink = paginationContainer.querySelector(`.button-pagination[data-page="${currentPage}"]`);
        if (selectedLink) {
           selectedLink.classList.add('selected');
        }

        // Attach event listeners to new pagination links
        paginationLinks.forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                const selectedPage = parseInt(this.getAttribute('data-page'));
                if (!isNaN(selectedPage)) {
                    handlePageChange(selectedPage);
                }
            });
        });
    };

    // Function to handle page change
    const handlePageChange = (newPage) => {
        const paginatedList = document.getElementById('paginated-list');
        paginatedList.setAttribute('data-current-page', newPage);
        updateUrlWithParams();
        fetchDataAndRender();
        updatePaginationControls(); // Ensure pagination controls are updated after page change
    };

    // Function to update the URL with pagination parameters
    const updateUrlWithParams = () => {
        const paginatedList = document.getElementById('paginated-list');
        const newPage = parseInt(paginatedList.getAttribute('data-current-page'));
        const params = new URLSearchParams(window.location.search);
        params.set('page', newPage);
        history.pushState(null, '', '?' + params.toString());
    };

    // Function to fetch data and render items based on the current page
    const fetchDataAndRender = () => {
        const paginatedList = document.getElementById('paginated-list');
        const currentPage = parseInt(paginatedList.getAttribute('data-current-page'));
        const paginationLimit = 21;
        const listItems = paginatedList.querySelectorAll('.item-container');
        
        const prevRange = (currentPage - 1) * paginationLimit;
        const currRange = currentPage * paginationLimit;

        listItems.forEach((item, index) => {
            item.classList.add('hidden');
            if (index >= prevRange && index < currRange) {
                item.classList.remove('hidden');
            }
        });
    };

    // Initial setup
    updatePaginationControls();
    fetchDataAndRender();


    // Function to handle the "Publish" and save to database on publish button click
    function publishItems() {
        const publishButton = document.getElementById('publish-button');
        
        // Change button to show loading spinner
        publishButton .innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Publishing...';

        const selectedReturnedItems = document.querySelectorAll('.item-container.selected');
        // Extract item IDs and titles from the selected items
        const itemsData = Array.from(selectedReturnedItems).map(item => ({
            itemId: item.getAttribute('data-itemid'),
            title: item.getAttribute('data-title'),
            price: item.getAttribute('data-price'),
            categories: item.getAttribute('data-categories'),
            itemAffiliateWebUrl: item.getAttribute('data-affiliatelink') 
        }));



        console.log("itemsData being sent to server:", itemsData); 

        fetch('/save-items/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(itemsData) // Sends data to views.py
        }).then(response => response.json())
        .then(data => {
            console.log("Response from server:", data);
            if (data.status === 'success') {
                console.log('Items saved');
                data.saved_item_ids.forEach(id => {
                    let item = document.querySelector(`[data-itemid="${id}"]`);
                    if (item) {
                        item.classList.add('saved');
                    }
                });
                // Reload the page after successful save
                window.location.reload();
            } else {
                console.log('Error saving items');
            }
        });
    }

    // Add event listener to the "Publish" button
    document.getElementById('publish-button').addEventListener('click', publishItems);




    // Function to get all selected items
    function getSelectedItems() {
        const selectedItems = document.querySelectorAll('.selected'); // Select all items with the 'selected' class
        let selectedIds = [];
        
        selectedItems.forEach(function(item) {
            selectedIds.push(item.dataset.itemid); // Assuming 'data-itemid' holds the item ID
        });
        
        return selectedIds;
    }

    // Function to delete selected items
    function deleteSelectedItems() {
        const removeButton = document.getElementById('remove-button');
        
        // Change button to show loading spinner
        removeButton .innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Removing...';


        const selectedIds = getSelectedItems(); // Get IDs of selected items
        
        if (selectedIds.length === 0) {
            alert('No items selected');
            return;
        }

        // Confirm deletion action with the user
        if (!confirm('Are you sure you want to delete the selected items?')) {
            return;
        }

        // Get CSRF token (Django-specific; adjust if you're using something else)
        const csrftoken = getCookie('csrftoken');

        // Send the delete request to the backend
        fetch('/delete-items/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken // CSRF token for security
            },
            body: JSON.stringify({ item_ids: selectedIds }) // Send selected item IDs to the backend
        })
        .then(response => response.json())
    .then(data => {
            if (data.status === 'success') {
                console.log('Items deleted');
                // Reload the page after successful deletion
                window.location.reload();
            } else {
                console.log('Error deleting items');
            }
        })
        .catch(error => {
            console.error('Error deleting items:', error);
        });
    }

    // Add event listener to the "Remove" button
    document.getElementById('remove-button').addEventListener('click', deleteSelectedItems);







    // Variable to store the scroll position
    let scrollPosition = 0;

    // Function to save the current scroll position
    function saveScrollPosition() {
        scrollPosition = window.scrollY;
    }

    // Function to restore the saved scroll position
    function restoreScrollPosition() {
        window.scrollTo(0, scrollPosition);
    }

    // Add event listener to pagination buttons
    document.querySelectorAll('.pagination-button').forEach(button => {
        button.addEventListener('click', () => {
            // Save scroll position before changing page
            saveScrollPosition();
        });
    });

    // Restore scroll position when the page is loaded
    window.addEventListener('load', () => {
        restoreScrollPosition();
    });






    // check item availability button functionality
    // Function to send AJAX request to update availability status
    function updateAvailability() {
        const button = document.getElementById('update-availability-button');
        // Add loading animation to the button
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Updating...';

        fetch('/update-availability/')
            .then(response => response.json())  // Parse the JSON response
            .then(data => {
                if (data.relisted_items) {
                    console.log('Relisted items:', data.relisted_items);  // Log the relisted items
                }
                if (data.message) {
                    console.log('Availability status updated successfully.');
                    showSuccessMessage();
                } else {
                    console.error('Failed to update availability status.');
                }
                // Reset the button text after processing
                button.innerHTML = 'Update Availability';
            })
            .catch(error => {
                console.error('Error:', error);
                // Reset the button text after processing
                button.innerHTML = 'Update Availability';
            });
    }

    // Function to display success message
    function showSuccessMessage() {
        // Create a success message element
        const successMessage = document.createElement('div');
        successMessage.textContent = 'Availability status updated successfully.';
        successMessage.classList.add('success-message');

        // Append the success message to the document body
        document.body.appendChild(successMessage);

        // Remove the success message after a certain time (e.g., 3 seconds)
        setTimeout(() => {
            successMessage.remove();
        }, 3000);
    }

    // Add click event listener to the button
    document.getElementById('update-availability-button').addEventListener('click', function () {
        updateAvailability();
    });






    // Fetch Ended Items & Items with past itemEndDate, Check Relisted, Check Availablity status ('Check Availability & Relist Items' button)

    function fetchEndedItems() {
        const relistButton = document.getElementById('get-ended-items');
        relistButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Fetching...';

        var xhr = new XMLHttpRequest();

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    // Refresh the page to display Django's success message
                    window.location.reload();
                } else {
                    // Handle error
                    alert("Error fetching ended items: " + xhr.statusText);
                }
                relistButton.innerHTML = 'Relist Items';
            }
        };

        xhr.open("GET", "/get-ended-items/", true);
        xhr.send();
    }

    document.getElementById("get-ended-items").addEventListener("click", function() {
        fetchEndedItems();
    });


    
    // Manually Relist items ('Manual Relist' button)

    function fetchEndedItemsManual() {
        const relistButtonManual = document.getElementById('manual-relist');
        relistButtonManual.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Relisting...';

        var xhr = new XMLHttpRequest();

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    // Refresh the page to display Django's success message
                    window.location.reload();
                } else {
                    // Handle error
                    alert("Error fetching ended items: " + xhr.statusText);
                }
                relistButtonManual.innerHTML = 'Manual Relist';
            }
        };

        xhr.open("GET", "/manual-relist/", true);
        xhr.send();
    }

    document.getElementById("manual-relist").addEventListener("click", function() {
        fetchEndedItemsManual();
    });


});
