// ============================
// search_input.js 
// ============================



// Dynamic import handling for browse.js functions
if (typeof window.getURLParams === 'undefined' || 
    typeof window.loadItems === 'undefined') {
    
    // Use the hashed path from template instead of hardcoded path
    const browsePath = window.HASHED_BROWSE_PATH || './browse.js'; // Fallback for safety
    
    import(browsePath)
        .then(module => {
            window.getURLParams = module.getURLParams;
            window.loadItems = module.loadItems;
        })
        .catch(err => {
            
            // Fallback attempt with relative path
            if (browsePath !== './browse.js') {
                console.log('🔄 Trying fallback import...');
                import('./browse.js')
                    .then(module => {
                        window.getURLParams = module.getURLParams;
                        window.loadItems = module.loadItems;
                        console.log('✅ Fallback import successful');
                    })
                    .catch(fallbackErr => {
                        console.error('❌ Fallback import also failed:', fallbackErr);
                    });
            }
        });
}

document.body.setAttribute('data-page', window.location.pathname.includes('/browse') ? 'browse' : 'other');