# core/migrations/0009_remove_templistingdata_user_tempimage_and_more.py

from django.db import migrations, models
import uuid

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_listingbatch_templistingdata'),
    ]

    operations = [
        # Comment out operations for non-existent tables
        # migrations.RemoveField(
        #     model_name='templistingdata',
        #     name='user',
        # ),
        
        # Only keep TempImage creation
        migrations.CreateModel(
            name='TempImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_key', models.CharField(db_index=True, max_length=100)),
                ('image', models.ImageField(upload_to='temp_images/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('batch_id', models.CharField(blank=True, max_length=100, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'ordering': ['uploaded_at'],
                'indexes': [
                    models.Index(fields=['session_key', 'batch_id'], name='core_tempim_session_dbde79_idx'), 
                    models.Index(fields=['expires_at'], name='core_tempim_expires_fc8beb_idx')
                ],
            },
        ),
        
        # Comment out deletions of non-existent tables
        # migrations.DeleteModel(
        #     name='ListingBatch',
        # ),
        # migrations.DeleteModel(
        #     name='TempListingData',
        # ),
    ]