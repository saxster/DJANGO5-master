"""
Django signals for face recognition and AI integration
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from django.db import models

from apps.attendance.models import PeopleEventlog
from apps.peoples.models import People
from apps.face_recognition.models import FaceEmbedding, FaceVerificationLog, FaceQualityMetrics
from apps.face_recognition.integrations import process_attendance_async

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PeopleEventlog)
def handle_attendance_created(sender, instance, created, **kwargs):
    """Handle new attendance record creation with AI processing"""
    if created and instance.facerecognitionin:
        try:
            logger.info(f"New face recognition attendance created: {instance.id}")
            
            # Schedule asynchronous AI processing
            # This will run anomaly detection, fraud analysis, and behavioral updates
            if hasattr(instance, 'imagein') and instance.imagein:
                image_path = instance.imagein.path if hasattr(instance.imagein, 'path') else None
                process_attendance_async.delay(instance.id, image_path)
            else:
                process_attendance_async.delay(instance.id)
                
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error scheduling AI processing for attendance {instance.id}: {str(e)}")


@receiver(post_save, sender=People)
def handle_user_updated(sender, instance, created, **kwargs):
    """Handle user profile updates that might affect face recognition"""
    try:
        if not created:
            # Clear face recognition cache for this user
            cache_key = f"user_embeddings_{instance.id}"
            cache.delete(cache_key)
            
            logger.info(f"Face recognition cache cleared for user {instance.id}")
            
    except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
        logger.error(f"Error handling user update for {instance.id}: {str(e)}")


@receiver(post_save, sender=FaceEmbedding)
def handle_face_embedding_updated(sender, instance, created, **kwargs):
    """Handle face embedding creation/updates with race condition protection"""
    from django.db import transaction, IntegrityError

    try:
        if created:
            logger.info(f"New face embedding created for user {instance.user_id}")

            # Set as primary using row-level locking to prevent TOCTOU
            with transaction.atomic():
                # Lock all embeddings for this user's model type
                user_embeddings = FaceEmbedding.objects.select_for_update().filter(
                    user=instance.user,
                    extraction_model__model_type=instance.extraction_model.model_type
                ).order_by('id')

                primary_exists = user_embeddings.filter(
                    is_primary=True
                ).exclude(id=instance.id).exists()

                if not primary_exists:
                    # Set this as primary
                    try:
                        FaceEmbedding.objects.filter(pk=instance.pk).update(is_primary=True)
                        instance.is_primary = True
                        logger.info(f"Set embedding {instance.id} as primary for user {instance.user_id}")
                    except IntegrityError:
                        # Another transaction won the race - acceptable
                        logger.info(f"Another embedding became primary for user {instance.user_id}")

        # Clear user's face recognition cache
        cache_key = f"user_embeddings_{instance.user_id}"
        cache.delete(cache_key)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
        logger.error(f"Error handling face embedding update: {str(e)}", exc_info=True)


@receiver(post_delete, sender=FaceEmbedding)
def handle_face_embedding_deleted(sender, instance, **kwargs):
    """Handle face embedding deletion"""
    try:
        logger.info(f"Face embedding deleted for user {instance.user_id}")
        
        # Clear user's face recognition cache
        cache_key = f"user_embeddings_{instance.user_id}"
        cache.delete(cache_key)
        
        # If this was a primary embedding, set another one as primary
        if instance.is_primary:
            next_embedding = FaceEmbedding.objects.filter(
                user=instance.user,
                is_validated=True
            ).first()
            
            if next_embedding:
                next_embedding.is_primary = True
                next_embedding.save(update_fields=['is_primary'])
                
    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling face embedding deletion: {str(e)}")


@receiver(post_save, sender=FaceVerificationLog)
def handle_verification_logged(sender, instance, created, **kwargs):
    """Handle face verification log creation with atomic counter updates"""
    from django.db import transaction
    from django.db.models import F

    if not created:
        return

    try:
        logger.info(f"Face verification logged: {instance.id}")

        # Update model statistics atomically
        if instance.verification_model:
            with transaction.atomic():
                update_dict = {
                    'verification_count': F('verification_count') + 1,
                    'last_used': timezone.now()
                }

                if instance.result == 'SUCCESS':
                    update_dict['successful_verifications'] = F('successful_verifications') + 1

                # Single atomic update query
                from apps.face_recognition.models import FaceRecognitionModel
                FaceRecognitionModel.objects.filter(
                    pk=instance.verification_model.pk
                ).update(**update_dict)

                logger.debug(f"Updated model {instance.verification_model.pk} statistics")

        # Update matched embedding statistics atomically
        if instance.matched_embedding:
            with transaction.atomic():
                update_dict = {
                    'verification_count': F('verification_count') + 1,
                    'last_used': timezone.now()
                }

                if instance.result == 'SUCCESS':
                    update_dict['successful_matches'] = F('successful_matches') + 1

                # Single atomic update query
                FaceEmbedding.objects.filter(
                    pk=instance.matched_embedding.pk
                ).update(**update_dict)

                logger.debug(f"Updated embedding {instance.matched_embedding.pk} statistics")

        # Clear cache
        if instance.user_id:
            cache_key = f"user_verification_stats_{instance.user_id}"
            cache.delete(cache_key)

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling verification log: {str(e)}", exc_info=True)


@receiver(pre_save, sender=FaceQualityMetrics)
def handle_quality_metrics_save(sender, instance, **kwargs):
    """Handle face quality metrics before saving"""
    try:
        # Ensure overall quality is calculated correctly
        if not instance.overall_quality or instance.overall_quality == 0:
            # Calculate overall quality if not set
            instance.overall_quality = (
                instance.sharpness_score * 0.3 +
                instance.brightness_score * 0.25 +
                instance.contrast_score * 0.25 +
                instance.face_size_score * 0.2
            )
        
        # Generate improvement suggestions based on quality issues
        suggestions = []
        if 'LOW_SHARPNESS' in instance.quality_issues:
            suggestions.append("Ensure camera is in focus and stable")
        if 'POOR_LIGHTING' in instance.quality_issues:
            suggestions.append("Improve lighting conditions")
        if 'LOW_CONTRAST' in instance.quality_issues:
            suggestions.append("Adjust image contrast and exposure")
        if 'SMALL_FACE_SIZE' in instance.quality_issues:
            suggestions.append("Move closer to camera or use higher resolution")
            
        instance.improvement_suggestions = suggestions
        
    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling quality metrics save: {str(e)}")


# Cache management signals
@receiver([post_save, post_delete], sender=FaceEmbedding)
def clear_face_recognition_cache(sender, instance, **kwargs):
    """Clear face recognition related caches"""
    try:
        # Clear user-specific caches
        user_cache_keys = [
            f"user_embeddings_{instance.user_id}",
            f"user_verification_stats_{instance.user_id}",
            f"user_face_models_{instance.user_id}"
        ]
        
        for cache_key in user_cache_keys:
            cache.delete(cache_key)
        
        # Clear model-specific caches
        if hasattr(instance, 'extraction_model') and instance.extraction_model:
            model_cache_key = f"model_embeddings_{instance.extraction_model.id}"
            cache.delete(model_cache_key)
            
    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error clearing face recognition cache: {str(e)}")


# Performance monitoring signals
@receiver(post_save, sender=FaceVerificationLog)
def monitor_performance(sender, instance, created, **kwargs):
    """Monitor face recognition performance"""
    if created:
        try:
            # Track processing time statistics
            processing_time = instance.processing_time_ms
            if processing_time and processing_time > 5000:  # More than 5 seconds
                logger.warning(
                    f"Slow face verification detected: {processing_time}ms for verification {instance.id}"
                )
            
            # Track fraud detection rates
            if instance.fraud_risk_score and instance.fraud_risk_score > 0.8:
                logger.warning(
                    f"High fraud risk detected: {instance.fraud_risk_score:.2%} for user {instance.user_id}"
                )
            
            # Track spoof detection
            if instance.spoof_detected:
                logger.warning(f"Spoof detected for user {instance.user_id} in verification {instance.id}")
                
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error monitoring performance: {str(e)}")


# Model health monitoring
@receiver(post_save, sender=FaceVerificationLog)
def monitor_model_health(sender, instance, created, **kwargs):
    """Monitor model health and performance"""
    if created and instance.verification_model:
        try:
            model = instance.verification_model
            
            # Check if model success rate is declining
            recent_logs = FaceVerificationLog.objects.filter(
                verification_model=model,
                verification_timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            )
            
            if recent_logs.count() >= 10:  # Only check if we have enough data
                success_rate = recent_logs.filter(result='SUCCESS').count() / recent_logs.count()
                
                if success_rate < 0.7:  # Less than 70% success rate
                    logger.warning(
                        f"Model {model.name} has low success rate: {success_rate:.2%} in last 24 hours"
                    )
                    
                    # Update model status if consistently poor
                    if success_rate < 0.5:
                        logger.error(f"Model {model.name} performance critically low, consider deactivation")
                        
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error monitoring model health: {str(e)}")


# Data consistency signals
@receiver(post_save, sender=FaceEmbedding)
def ensure_data_consistency(sender, instance, created, **kwargs):
    """Ensure data consistency for face embeddings with locking"""
    from django.db import transaction

    if not created:
        return

    try:
        # Ensure only one primary embedding per user per model type
        if instance.is_primary:
            with transaction.atomic():
                # Lock and update other primary embeddings
                other_primary = FaceEmbedding.objects.select_for_update().filter(
                    user=instance.user,
                    extraction_model__model_type=instance.extraction_model.model_type,
                    is_primary=True
                ).exclude(id=instance.id)

                if other_primary.exists():
                    count = other_primary.update(is_primary=False)
                    logger.info(f"Demoted {count} primary embeddings for user {instance.user_id}")

        # Validate embedding vector dimensions
        if len(instance.embedding_vector) != 512:
            logger.warning(
                f"Embedding vector has unexpected dimensions: {len(instance.embedding_vector)} for embedding {instance.id}"
            )

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error ensuring data consistency: {str(e)}", exc_info=True)