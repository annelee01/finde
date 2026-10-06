# core/storage.py
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

class StrictManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """
    A manifest static files storage that only creates hashed versions,
    no non-hashed fallbacks.
    """
    
    def post_process(self, paths, dry_run=False, **options):
        """
        Override to prevent creating non-hashed copies
        """
        # Run the normal post-processing to create hashed versions
        processed_files = super().post_process(paths, dry_run, **options)
        
        if not dry_run:
            # Remove non-hashed files after processing
            for original_name in paths:
                if original_name.endswith('.js') or original_name.endswith('.css'):
                    try:
                        # Delete the non-hashed version
                        self.delete(original_name)
                    except Exception:
                        pass  # File might not exist or be locked
        
        return processed_files