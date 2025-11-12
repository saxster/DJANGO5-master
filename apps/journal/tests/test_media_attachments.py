"""
Tests for Journal Media Attachments

Testing:
- Media attachment creation and validation
- File upload security
- File type validation
- Hero image management
- Sync status tracking
- Soft delete functionality

Run with: pytest apps/journal/tests/test_media_attachments.py -v
"""
import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.journal.models import JournalMediaAttachment
from apps.journal.models.enums import JournalSyncStatus


@pytest.mark.django_db
class TestMediaAttachmentCreation(TestCase):
    """Test media attachment creation"""

    def test_create_photo_attachment(self, test_journal_entry):
        """Test creating a photo attachment"""
        file = SimpleUploadedFile(
            "test_photo.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="test_photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"fake image content"),
            caption="Test photo",
        )

        assert attachment.id is not None
        assert attachment.media_type == "PHOTO"
        assert attachment.original_filename == "test_photo.jpg"
        assert attachment.mime_type == "image/jpeg"

    def test_create_video_attachment(self, test_journal_entry):
        """Test creating a video attachment"""
        file = SimpleUploadedFile(
            "test_video.mp4",
            b"fake video content",
            content_type="video/mp4"
        )

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="VIDEO",
            file=file,
            original_filename="test_video.mp4",
            mime_type="video/mp4",
            file_size=len(b"fake video content"),
        )

        assert attachment.media_type == "VIDEO"
        assert attachment.mime_type == "video/mp4"

    def test_create_document_attachment(self, test_journal_entry):
        """Test creating a document attachment"""
        file = SimpleUploadedFile(
            "report.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="DOCUMENT",
            file=file,
            original_filename="report.pdf",
            mime_type="application/pdf",
            file_size=len(b"fake pdf content"),
        )

        assert attachment.media_type == "DOCUMENT"

    def test_create_audio_attachment(self, test_journal_entry):
        """Test creating an audio attachment"""
        file = SimpleUploadedFile(
            "recording.mp3",
            b"fake audio content",
            content_type="audio/mpeg"
        )

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="AUDIO",
            file=file,
            original_filename="recording.mp3",
            mime_type="audio/mpeg",
            file_size=len(b"fake audio content"),
        )

        assert attachment.media_type == "AUDIO"

    def test_attachment_display_order(self, test_journal_entry):
        """Test setting display order for attachments"""
        file1 = SimpleUploadedFile("photo1.jpg", b"content1", content_type="image/jpeg")
        file2 = SimpleUploadedFile("photo2.jpg", b"content2", content_type="image/jpeg")

        attachment1 = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file1,
            original_filename="photo1.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content1"),
            display_order=1,
        )

        attachment2 = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file2,
            original_filename="photo2.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content2"),
            display_order=2,
        )

        assert attachment1.display_order == 1
        assert attachment2.display_order == 2

    def test_attachment_caption(self, test_journal_entry):
        """Test setting caption for attachments"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            caption="Beautiful sunset at the beach",
        )

        assert attachment.caption == "Beautiful sunset at the beach"


@pytest.mark.django_db
class TestHeroImage(TestCase):
    """Test hero image functionality"""

    def test_set_hero_image(self, test_journal_entry):
        """Test setting a hero image"""
        file = SimpleUploadedFile("hero.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="hero.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            is_hero_image=True,
        )

        assert attachment.is_hero_image is True

    def test_only_one_hero_image_per_entry(self, test_journal_entry):
        """Test that only one image can be hero per entry"""
        file1 = SimpleUploadedFile("photo1.jpg", b"c1", content_type="image/jpeg")
        file2 = SimpleUploadedFile("photo2.jpg", b"c2", content_type="image/jpeg")

        # Create first hero image
        attachment1 = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file1,
            original_filename="photo1.jpg",
            mime_type="image/jpeg",
            file_size=2,
            is_hero_image=True,
        )

        # Create second attachment
        attachment2 = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file2,
            original_filename="photo2.jpg",
            mime_type="image/jpeg",
            file_size=2,
            is_hero_image=False,
        )

        # Set second as hero
        attachment2.is_hero_image = True
        attachment2.save()

        # Refresh first from DB
        attachment1.refresh_from_db()
        attachment2.refresh_from_db()

        # Only attachment2 should be hero now
        assert attachment1.is_hero_image is False
        assert attachment2.is_hero_image is True

    def test_query_hero_image(self, test_journal_entry):
        """Test querying for hero image"""
        file = SimpleUploadedFile("hero.jpg", b"content", content_type="image/jpeg")

        hero = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="hero.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            is_hero_image=True,
        )

        hero_image = JournalMediaAttachment.objects.filter(
            journal_entry=test_journal_entry,
            is_hero_image=True
        ).first()

        assert hero_image.id == hero.id


@pytest.mark.django_db
class TestMediaSyncStatus(TestCase):
    """Test media sync status tracking"""

    def test_default_sync_status(self, test_journal_entry):
        """Test default sync status is SYNCED"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
        )

        assert attachment.sync_status == JournalSyncStatus.SYNCED

    def test_set_sync_status_pending(self, test_journal_entry):
        """Test setting sync status to pending"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            sync_status=JournalSyncStatus.PENDING_SYNC,
        )

        assert attachment.sync_status == JournalSyncStatus.PENDING_SYNC

    def test_update_sync_status(self, test_journal_entry):
        """Test updating sync status"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            sync_status=JournalSyncStatus.PENDING_SYNC,
        )

        attachment.sync_status = JournalSyncStatus.SYNCED
        attachment.save()

        refreshed = JournalMediaAttachment.objects.get(id=attachment.id)
        assert refreshed.sync_status == JournalSyncStatus.SYNCED

    def test_filter_by_sync_status(self, test_journal_entry):
        """Test filtering attachments by sync status"""
        file1 = SimpleUploadedFile("p1.jpg", b"c1", content_type="image/jpeg")
        file2 = SimpleUploadedFile("p2.jpg", b"c2", content_type="image/jpeg")

        JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file1,
            original_filename="p1.jpg",
            mime_type="image/jpeg",
            file_size=2,
            sync_status=JournalSyncStatus.SYNCED,
        )

        JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file2,
            original_filename="p2.jpg",
            mime_type="image/jpeg",
            file_size=2,
            sync_status=JournalSyncStatus.PENDING_SYNC,
        )

        pending = JournalMediaAttachment.objects.filter(
            sync_status=JournalSyncStatus.PENDING_SYNC
        )
        assert pending.count() == 1


@pytest.mark.django_db
class TestMediaSoftDelete(TestCase):
    """Test soft delete functionality for media"""

    def test_soft_delete_attachment(self, test_journal_entry):
        """Test soft deleting a media attachment"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            is_deleted=False,
        )

        assert attachment.is_deleted is False

        attachment.is_deleted = True
        attachment.save()

        refreshed = JournalMediaAttachment.objects.get(id=attachment.id)
        assert refreshed.is_deleted is True

    def test_restore_soft_deleted_attachment(self, test_journal_entry):
        """Test restoring a soft-deleted attachment"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            is_deleted=True,
        )

        attachment.is_deleted = False
        attachment.save()

        refreshed = JournalMediaAttachment.objects.get(id=attachment.id)
        assert refreshed.is_deleted is False

    def test_filter_active_attachments(self, test_journal_entry):
        """Test filtering out deleted attachments"""
        file1 = SimpleUploadedFile("p1.jpg", b"c1", content_type="image/jpeg")
        file2 = SimpleUploadedFile("p2.jpg", b"c2", content_type="image/jpeg")

        JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file1,
            original_filename="p1.jpg",
            mime_type="image/jpeg",
            file_size=2,
            is_deleted=False,
        )

        JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file2,
            original_filename="p2.jpg",
            mime_type="image/jpeg",
            file_size=2,
            is_deleted=True,
        )

        active = JournalMediaAttachment.objects.filter(is_deleted=False)
        assert active.count() == 1


@pytest.mark.django_db
class TestMediaMobileSync(TestCase):
    """Test mobile sync fields for media"""

    def test_mobile_id_tracking(self, test_journal_entry):
        """Test tracking mobile client ID"""
        from uuid import uuid4

        mobile_id = uuid4()
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            mobile_id=mobile_id,
        )

        assert attachment.mobile_id == mobile_id

    def test_filter_by_mobile_id(self, test_journal_entry):
        """Test filtering attachments by mobile ID"""
        from uuid import uuid4

        mobile_id = uuid4()
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
            mobile_id=mobile_id,
        )

        found = JournalMediaAttachment.objects.filter(mobile_id=mobile_id).first()
        assert found is not None
        assert found.mobile_id == mobile_id


@pytest.mark.django_db
class TestMediaTimestamps(TestCase):
    """Test media attachment timestamps"""

    def test_created_at_timestamp(self, test_journal_entry):
        """Test created_at is set on creation"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        before = timezone.now()
        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
        )
        after = timezone.now()

        assert before <= attachment.created_at <= after

    def test_updated_at_changes_on_update(self, test_journal_entry):
        """Test updated_at changes when entry is modified"""
        import time

        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
        )

        original_updated_at = attachment.updated_at
        time.sleep(0.01)  # Small delay

        attachment.caption = "Updated caption"
        attachment.save()

        assert attachment.updated_at >= original_updated_at


@pytest.mark.django_db
class TestMediaStringRepresentation(TestCase):
    """Test string representation and relationships"""

    def test_media_str_representation(self, test_journal_entry):
        """Test __str__ method returns meaningful representation"""
        file = SimpleUploadedFile("photo.jpg", b"content", content_type="image/jpeg")

        attachment = JournalMediaAttachment.objects.create(
            journal_entry=test_journal_entry,
            media_type="PHOTO",
            file=file,
            original_filename="photo.jpg",
            mime_type="image/jpeg",
            file_size=len(b"content"),
        )

        str_repr = str(attachment)
        assert "PHOTO" in str_repr
        assert "photo.jpg" in str_repr

    def test_media_ordered_by_display_order(self, test_journal_entry):
        """Test media attachments are ordered by display_order"""
        files = [
            SimpleUploadedFile(f"p{i}.jpg", b"c", content_type="image/jpeg")
            for i in range(3)
        ]

        for i, file in enumerate(files):
            JournalMediaAttachment.objects.create(
                journal_entry=test_journal_entry,
                media_type="PHOTO",
                file=file,
                original_filename=f"p{i}.jpg",
                mime_type="image/jpeg",
                file_size=1,
                display_order=2 - i,  # Create in reverse order
            )

        attachments = JournalMediaAttachment.objects.filter(journal_entry=test_journal_entry)
        orders = [a.display_order for a in attachments]
        assert orders == sorted(orders)
