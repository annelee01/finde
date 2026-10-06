from django.apps import apps
from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """Create tables for unmanaged models (e.g. CoreEbayitem) in the test database.

    Those tables are created outside Django migrations in production, so tests
    build the core app's schema directly from the models instead.
    """

    def setup_test_environment(self, *args, **kwargs):
        self._unmanaged = [m for m in apps.get_models() if not m._meta.managed]
        for model in self._unmanaged:
            model._meta.managed = True
        super().setup_test_environment(*args, **kwargs)

    def teardown_test_environment(self, *args, **kwargs):
        super().teardown_test_environment(*args, **kwargs)
        for model in self._unmanaged:
            model._meta.managed = False
