from django.core.management import call_command
from django.apps import apps

from synapsesuggestor.tests.common import SynapseSuggestorTestCase


class CommandsTests(SynapseSuggestorTestCase):
    def assert_ss_db_population_state(self, should_exist):
        assertion = self.assertTrue if should_exist else self.assertFalse
        for ss_model in apps.get_app_config('synapsesuggestor').get_models():
            assertion(ss_model.objects.all().exists())

    def test_clear_ss_tables(self):
        self.assert_ss_db_population_state(True)
        call_command('clear_ss_tables', '-y')
        self.assert_ss_db_population_state(False)
