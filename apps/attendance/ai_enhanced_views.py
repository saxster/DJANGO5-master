"""
AI-Enhanced Attendance Views for YOUTILITY5
Integrates cutting-edge biometric authentication and analytics
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.utils import IntegrityError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from apps.face_recognition.ai_enhanced_engine import AIEnhancedFaceRecognitionEngine, BiometricResult
from apps.attendance import models as atdm
from apps.attendance import forms as atf
from apps.behavioral_analytics.models import UserBehaviorProfile, BehavioralEvent, BehavioralAnalysis
from apps.peoples.models import People
from apps.core.utils import handle_Exception
from apps.peoples import utils as putils

logger = logging.getLogger(__name__)


class AIEnhancedAttendanceView(LoginRequiredMixin, View):
    """AI-Enhanced attendance management with advanced biometric authentication"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ai_engine = AIEnhancedFaceRecognitionEngine()
        
    params = {
        "form_class": atf.AttendanceForm,
        "template_form": "attendance/partials/partial_ai_attendance_form.html",
        "template_list": "attendance/ai_attendance.html",
        "related": ["people", "bu", "verifiedby", "peventtype", "shift"],
        "model": atdm.PeopleEventlog,
        "form_initials": {},
        "fields": [
            "id", "people__peoplename", "people__peoplecode", "verifiedby__peoplename",
            "peventtype__taname", "peventtype__tacode", "bu__buname", "datefor",
            "uuid", "people__id", "punchintime", "punchouttime",
            "facerecognitionin", "facerecognitionout", "shift__shiftname",
            "ctzoffset", "peventlogextras", "sL", "eL", "people__location__locname",
            "people__mobno", "bu__siteincharge__peoplename", "bu__siteincharge__mobno",
            "bu__siteincharge__email", "shift__starttime", "shift__endtime",
            # AI-enhanced fields
            "ai_verification_confidence", "fraud_risk_score", "biometric_modalities",
            "quality_metrics", "liveness_score"
        ],
    }

    async def post(self, request, *args, **kwargs):
        """Enhanced attendance processing with AI biometric verification"""
        try:
            logger.info(f"AI-enhanced attendance request from user: {request.user.id}")
            
            # Parse request data
            attendance_data = json.loads(request.POST.get('formData', '{}'))
            biometric_data = json.loads(request.POST.get('biometricData', '{}'))
            
            # Validate required biometric data
            if not biometric_data.get('image_path'):
                return JsonResponse({
                    'error': 'Face image required for AI verification',
                    'code': 'MISSING_BIOMETRIC_DATA'
                }, status=400)
            
            # Create or update attendance record
            pk = request.POST.get('pk')
            if pk:
                attendance_record = atdm.PeopleEventlog.objects.get(id=int(pk))
                form = self.params["form_class"](attendance_data, instance=attendance_record)
                is_update = True
            else:
                form = self.params["form_class"](attendance_data)
                attendance_record = None
                is_update = False
            
            if not form.is_valid():
                return JsonResponse({
                    'error': 'Invalid attendance data',
                    'form_errors': form.errors
                }, status=400)
            
            # Save initial attendance record
            with transaction.atomic():
                attendance_record = form.save(commit=False)
                attendance_record.save()
                
                # Perform AI-enhanced biometric verification
                verification_result = await self._perform_ai_verification(
                    request, attendance_record, biometric_data
                )
                
                # Update attendance record with AI results
                await self._update_attendance_with_ai_results(
                    attendance_record, verification_result
                )
                
                # Log behavioral event
                await self._log_behavioral_event(
                    request, attendance_record, verification_result
                )
                
                # Update user behavior profile
                await self._update_behavior_profile(
                    request.user.id, attendance_record, verification_result
                )
                
                # Generate response
                response_data = self._generate_response(
                    attendance_record, verification_result, is_update
                )
                
                return JsonResponse(response_data, status=200)
                
        except Exception as e:
            logger.error(f"Error in AI-enhanced attendance: {str(e)}", exc_info=True)
            return handle_Exception(request)
    
    async def get(self, request, *args, **kwargs):
        """Enhanced attendance view with AI analytics"""
        try:
            action = request.GET.get('action')
            
            # AI Analytics Dashboard
            if action == 'ai_dashboard':
                dashboard_data = await self._generate_ai_dashboard_data(request)
                return JsonResponse(dashboard_data, status=200)
            
            # Real-time fraud alerts
            elif action == 'fraud_alerts':
                alerts_data = await self._get_fraud_alerts(request)
                return JsonResponse(alerts_data, status=200)
            
            # Biometric quality assessment
            elif action == 'quality_check':
                image_path = request.GET.get('image_path')
                if image_path:
                    quality_data = await self.ai_engine._ai_quality_assessment(image_path)
                    return JsonResponse(quality_data, status=200)
                return JsonResponse({'error': 'Image path required'}, status=400)
            
            # User behavior insights
            elif action == 'behavior_insights':
                user_id = request.GET.get('user_id', request.user.id)
                insights_data = await self._get_behavior_insights(user_id)
                return JsonResponse(insights_data, status=200)
            
            # Standard attendance list with AI enhancements
            elif action == 'list' or request.GET.get('search_term'):
                enhanced_list_data = await self._get_enhanced_attendance_list(request)
                return JsonResponse({'data': enhanced_list_data}, status=200)
            
            # Render main template
            elif request.GET.get("template"):
                return render(request, self.params["template_list"])
            
            # Default form view
            else:
                context = {
                    "ai_attendance_form": self.params["form_class"](),
                    "ai_config": self._get_ai_config(),
                    "user_profile": await self._get_user_ai_profile(request.user.id)
                }
                return render(request, self.params["template_form"], context)
                
        except Exception as e:
            logger.error(f"Error in GET request: {str(e)}", exc_info=True)
            return handle_Exception(request)
    
    async def _perform_ai_verification(
        self,
        request,
        attendance_record: atdm.PeopleEventlog,
        biometric_data: Dict
    ) -> BiometricResult:
        """Perform comprehensive AI biometric verification"""
        try:
            # Prepare additional biometric data
            additional_data = {}
            
            # Voice sample (if provided)
            if 'voice_sample' in biometric_data:
                additional_data['voice_sample'] = biometric_data['voice_sample']
            
            # Behavioral data from browser/device
            if 'behavioral_data' in biometric_data:
                additional_data['behavioral_data'] = biometric_data['behavioral_data']
            
            # Device and session info
            additional_data.update({
                'device_data': {
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'ip_address': request.META.get('REMOTE_ADDR', ''),
                    'device_type': self._detect_device_type(request),
                    'session_id': request.session.session_key
                },
                'temporal_data': {
                    'current_time': timezone.now().hour,
                    'request_timestamp': timezone.now()
                }
            })
            
            # Perform AI verification
            verification_result = await self.ai_engine.verify_biometric(
                user_id=request.user.id,
                image_path=biometric_data['image_path'],
                additional_data=additional_data,
                attendance_record_id=attendance_record.id
            )
            
            logger.info(f"AI verification completed for user {request.user.id}: "
                       f"verified={verification_result.verified}, "
                       f"confidence={verification_result.confidence}")
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Error in AI verification: {str(e)}")
            # Return failed result
            return BiometricResult(
                verified=False,
                confidence=0.0,
                modalities_used=[],
                processing_time_ms=0.0,
                fraud_risk_score=1.0,
                quality_score=0.0,
                liveness_score=0.0,
                recommendations=[f'Verification error: {str(e)}'],
                detailed_scores={'error': str(e)}
            )
    
    async def _update_attendance_with_ai_results(
        self,
        attendance_record: atdm.PeopleEventlog,
        verification_result: BiometricResult
    ):
        """Update attendance record with AI verification results"""
        try:
            # Update existing peventlogextras with AI data
            extras = attendance_record.peventlogextras or {}
            
            # AI verification metadata
            extras.update({
                'ai_enhanced': True,
                'ai_version': '2025.1',
                'verification_confidence': verification_result.confidence,
                'fraud_risk_score': verification_result.fraud_risk_score,
                'quality_score': verification_result.quality_score,
                'liveness_score': verification_result.liveness_score,
                'modalities_used': verification_result.modalities_used,
                'processing_time_ms': verification_result.processing_time_ms,
                'recommendations': verification_result.recommendations,
                'verified': verification_result.verified,
                'detailed_scores': verification_result.detailed_scores,
                'timestamp': timezone.now().isoformat()
            })
            
            # Update face recognition flags based on AI results
            if 'face_recognition' in verification_result.modalities_used:
                if attendance_record.punchintime and not attendance_record.punchouttime:
                    attendance_record.facerecognitionin = verification_result.verified
                else:
                    attendance_record.facerecognitionout = verification_result.verified
            
            attendance_record.peventlogextras = extras
            
            # Save updated record
            await asyncio.get_event_loop().run_in_executor(
                None, attendance_record.save
            )
            
            logger.info(f"Attendance record {attendance_record.id} updated with AI results")
            
        except Exception as e:
            logger.error(f"Error updating attendance with AI results: {str(e)}")
    
    async def _log_behavioral_event(
        self,
        request,
        attendance_record: atdm.PeopleEventlog,
        verification_result: BiometricResult
    ):
        """Log behavioral event for analytics"""
        try:
            # Determine event type
            if attendance_record.punchintime and not attendance_record.punchouttime:
                event_type = BehavioralEvent.EventType.ATTENDANCE_IN
            else:
                event_type = BehavioralEvent.EventType.ATTENDANCE_OUT
            
            # Create behavioral event
            event_data = {
                'verification_result': {
                    'verified': verification_result.verified,
                    'confidence': verification_result.confidence,
                    'fraud_risk_score': verification_result.fraud_risk_score,
                    'modalities_used': verification_result.modalities_used
                },
                'attendance_record_id': attendance_record.id,
                'location': getattr(request.user, 'location', {})
            }
            
            behavioral_event = await asyncio.get_event_loop().run_in_executor(
                None,
                BehavioralEvent.objects.create,
                {
                    'user': request.user,
                    'event_type': event_type,
                    'event_timestamp': timezone.now(),
                    'source_system': 'youtility_ai',
                    'session_id': request.session.session_key,
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                    'event_data': event_data,
                    'is_anomalous': verification_result.fraud_risk_score > 0.6,
                    'anomaly_score': verification_result.fraud_risk_score,
                    'risk_indicators': verification_result.recommendations if not verification_result.verified else []
                }
            )
            
            logger.info(f"Behavioral event logged: {behavioral_event.id}")
            
        except Exception as e:
            logger.error(f"Error logging behavioral event: {str(e)}")
    
    async def _update_behavior_profile(
        self,
        user_id: int,
        attendance_record: atdm.PeopleEventlog,
        verification_result: BiometricResult
    ):
        """Update user behavior profile with new data"""
        try:
            # Get or create user behavior profile
            profile, created = await asyncio.get_event_loop().run_in_executor(
                None,
                UserBehaviorProfile.objects.get_or_create,
                {'user_id': user_id},
                {
                    'attendance_regularity_score': 0.5,
                    'location_consistency_score': 0.5,
                    'fraud_risk_score': 0.0
                }
            )
            
            current_hour = timezone.now().hour
            
            # Update temporal patterns
            typical_hours = profile.typical_login_hours or []
            if current_hour not in typical_hours:
                typical_hours.append(current_hour)
                # Keep only last 30 unique hours to prevent infinite growth
                profile.typical_login_hours = list(set(typical_hours))[-30:]
            
            # Update fraud risk score (exponential moving average)
            alpha = 0.3  # Learning rate
            profile.fraud_risk_score = (
                alpha * verification_result.fraud_risk_score +
                (1 - alpha) * profile.fraud_risk_score
            )
            
            # Update attendance regularity (higher confidence = more regular)
            if verification_result.verified:
                profile.attendance_regularity_score = min(
                    1.0,
                    profile.attendance_regularity_score + 0.05
                )
            else:
                profile.attendance_regularity_score = max(
                    0.0,
                    profile.attendance_regularity_score - 0.1
                )
            
            # Update profile statistics
            profile.data_points_count += 1
            profile.profile_confidence = min(
                1.0,
                profile.data_points_count / 100.0  # Full confidence after 100 data points
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None, profile.save
            )
            
            logger.info(f"Behavior profile updated for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating behavior profile: {str(e)}")
    
    def _generate_response(
        self,
        attendance_record: atdm.PeopleEventlog,
        verification_result: BiometricResult,
        is_update: bool
    ) -> Dict[str, Any]:
        """Generate comprehensive response with AI insights"""
        
        # Base response
        response = {
            'success': True,
            'attendance_id': attendance_record.id,
            'message': 'Attendance recorded successfully' if not is_update else 'Attendance updated successfully',
            'type': attendance_record.peventtype.tacode if attendance_record.peventtype else 'UNKNOWN'
        }
        
        # AI verification results
        response['ai_verification'] = {
            'verified': verification_result.verified,
            'confidence': round(verification_result.confidence, 3),
            'quality_score': round(verification_result.quality_score, 3),
            'liveness_score': round(verification_result.liveness_score, 3),
            'fraud_risk_score': round(verification_result.fraud_risk_score, 3),
            'processing_time_ms': round(verification_result.processing_time_ms, 2),
            'modalities_used': verification_result.modalities_used,
            'recommendations': verification_result.recommendations[:3]  # Top 3 recommendations
        }
        
        # Security alerts
        if verification_result.fraud_risk_score > 0.6:
            response['security_alert'] = {
                'level': 'HIGH' if verification_result.fraud_risk_score > 0.8 else 'MEDIUM',
                'message': 'High fraud risk detected - additional verification may be required',
                'details': verification_result.recommendations
            }
        
        # Quality feedback for user
        if verification_result.quality_score < 0.5:
            response['quality_feedback'] = {
                'message': 'Image quality could be improved',
                'suggestions': [
                    rec for rec in verification_result.recommendations 
                    if any(word in rec.lower() for word in ['lighting', 'focus', 'closer', 'camera'])
                ]
            }
        
        return response
    
    async def _generate_ai_dashboard_data(self, request) -> Dict[str, Any]:
        """Generate AI analytics dashboard data"""
        try:
            from django.db.models import Avg, Count, Q
            from datetime import datetime, timedelta
            
            now = timezone.now()
            week_ago = now - timedelta(days=7)
            
            # Get AI verification statistics
            recent_verifications = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: atdm.PeopleEventlog.objects.filter(
                    createdon__gte=week_ago,
                    peventlogextras__has_key='ai_enhanced'
                ).aggregate(
                    total_verifications=Count('id'),
                    avg_confidence=Avg('peventlogextras__verification_confidence'),
                    high_risk_count=Count('id', filter=Q(peventlogextras__fraud_risk_score__gt=0.6)),
                    successful_verifications=Count('id', filter=Q(peventlogextras__verified=True))
                )
            )
            
            # Calculate success rate
            total = recent_verifications.get('total_verifications', 0)
            successful = recent_verifications.get('successful_verifications', 0)
            success_rate = (successful / total * 100) if total > 0 else 0
            
            # Get behavior analytics
            behavior_stats = await self._get_behavior_analytics(week_ago)
            
            # Get fraud detection stats
            fraud_stats = await self._get_fraud_detection_stats(week_ago)
            
            return {
                'period': f"Last 7 days ({week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})",
                'verification_stats': {
                    'total_verifications': total,
                    'success_rate': round(success_rate, 1),
                    'avg_confidence': round(recent_verifications.get('avg_confidence', 0) or 0, 3),
                    'high_risk_detections': recent_verifications.get('high_risk_count', 0)
                },
                'behavior_analytics': behavior_stats,
                'fraud_detection': fraud_stats,
                'system_performance': {
                    'avg_processing_time_ms': 850,  # Mock data - replace with actual
                    'model_accuracy': 0.989,
                    'liveness_detection_rate': 0.976
                },
                'recommendations': self._generate_system_recommendations(recent_verifications, behavior_stats)
            }
            
        except Exception as e:
            logger.error(f"Error generating AI dashboard data: {str(e)}")
            return {'error': str(e)}
    
    async def _get_behavior_analytics(self, since: datetime) -> Dict[str, Any]:
        """Get behavioral analytics data"""
        try:
            # Mock implementation - replace with actual analytics
            return {
                'total_behavioral_events': 1250,
                'anomalous_events': 45,
                'anomaly_rate': 3.6,
                'top_risk_factors': [
                    {'factor': 'UNUSUAL_LOGIN_TIME', 'count': 18},
                    {'factor': 'LOW_CONFIDENCE_ANOMALY', 'count': 12},
                    {'factor': 'LOCATION_INCONSISTENCY', 'count': 8}
                ],
                'behavioral_trends': {
                    'improving_users': 67,
                    'declining_users': 23,
                    'stable_users': 156
                }
            }
        except Exception as e:
            logger.error(f"Error getting behavior analytics: {str(e)}")
            return {'error': str(e)}
    
    async def _get_fraud_detection_stats(self, since: datetime) -> Dict[str, Any]:
        """Get fraud detection statistics"""
        try:
            # Mock implementation - replace with actual fraud stats
            return {
                'total_fraud_attempts': 12,
                'blocked_attempts': 11,
                'detection_rate': 91.7,
                'fraud_types': [
                    {'type': 'DEEPFAKE_DETECTED', 'count': 5},
                    {'type': '2D_IMAGE_DETECTED', 'count': 4},
                    {'type': 'LOW_LIVENESS_SCORE', 'count': 3}
                ],
                'false_positive_rate': 2.1
            }
        except Exception as e:
            logger.error(f"Error getting fraud detection stats: {str(e)}")
            return {'error': str(e)}
    
    def _generate_system_recommendations(
        self, 
        verification_stats: Dict, 
        behavior_stats: Dict
    ) -> List[str]:
        """Generate intelligent system recommendations"""
        recommendations = []
        
        success_rate = (
            verification_stats.get('successful_verifications', 0) /
            max(verification_stats.get('total_verifications', 1), 1) * 100
        )
        
        if success_rate < 85:
            recommendations.append("Consider adjusting verification thresholds to improve success rate")
        
        if verification_stats.get('high_risk_count', 0) > 10:
            recommendations.append("High number of fraud attempts detected - review security policies")
        
        avg_confidence = verification_stats.get('avg_confidence', 0) or 0
        if avg_confidence < 0.8:
            recommendations.append("Average confidence is low - consider user training or camera upgrades")
        
        if behavior_stats.get('anomaly_rate', 0) > 5:
            recommendations.append("High behavioral anomaly rate - investigate potential system issues")
        
        return recommendations[:5]  # Return top 5 recommendations
    
    async def _get_fraud_alerts(self, request) -> Dict[str, Any]:
        """Get real-time fraud alerts"""
        try:
            # Get recent high-risk verifications
            alerts = []
            
            # Mock implementation - replace with actual alert system
            high_risk_threshold = 0.7
            recent_high_risk = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(atdm.PeopleEventlog.objects.filter(
                    createdon__gte=timezone.now() - timedelta(hours=24),
                    peventlogextras__fraud_risk_score__gt=high_risk_threshold
                ).select_related('people')[:10])
            )
            
            for record in recent_high_risk:
                extras = record.peventlogextras or {}
                alerts.append({
                    'id': record.id,
                    'user_name': record.people.peoplename if record.people else 'Unknown',
                    'timestamp': record.createdon.isoformat(),
                    'fraud_risk_score': extras.get('fraud_risk_score', 0),
                    'risk_indicators': extras.get('recommendations', []),
                    'severity': 'CRITICAL' if extras.get('fraud_risk_score', 0) > 0.9 else 'HIGH'
                })
            
            return {
                'alerts': alerts,
                'alert_count': len(alerts),
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting fraud alerts: {str(e)}")
            return {'error': str(e)}
    
    async def _get_behavior_insights(self, user_id: int) -> Dict[str, Any]:
        """Get user behavior insights"""
        try:
            # Get user behavior profile
            try:
                profile = await asyncio.get_event_loop().run_in_executor(
                    None,
                    UserBehaviorProfile.objects.get,
                    user_id=user_id
                )
            except UserBehaviorProfile.DoesNotExist:
                return {
                    'message': 'No behavior profile found for user',
                    'recommendation': 'More attendance data needed to build behavioral profile'
                }
            
            # Get recent behavioral events
            recent_events = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(BehavioralEvent.objects.filter(
                    user_id=user_id,
                    event_timestamp__gte=timezone.now() - timedelta(days=30)
                ).order_by('-event_timestamp')[:20])
            )
            
            # Analyze patterns
            insights = {
                'profile_confidence': round(profile.profile_confidence, 3),
                'attendance_regularity': round(profile.attendance_regularity_score, 3),
                'fraud_risk_level': self._categorize_risk_level(profile.fraud_risk_score),
                'typical_hours': profile.typical_login_hours or [],
                'recent_activity': {
                    'total_events': len(recent_events),
                    'anomalous_events': sum(1 for e in recent_events if e.is_anomalous),
                    'avg_anomaly_score': sum(e.anomaly_score for e in recent_events) / len(recent_events) if recent_events else 0
                },
                'recommendations': self._generate_user_recommendations(profile, recent_events)
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting behavior insights: {str(e)}")
            return {'error': str(e)}
    
    def _categorize_risk_level(self, fraud_risk_score: float) -> str:
        """Categorize fraud risk level"""
        if fraud_risk_score >= 0.8:
            return 'CRITICAL'
        elif fraud_risk_score >= 0.6:
            return 'HIGH'
        elif fraud_risk_score >= 0.3:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _generate_user_recommendations(
        self, 
        profile: UserBehaviorProfile, 
        recent_events: List
    ) -> List[str]:
        """Generate personalized user recommendations"""
        recommendations = []
        
        if profile.attendance_regularity_score < 0.5:
            recommendations.append("Maintain consistent attendance patterns to improve verification accuracy")
        
        if profile.fraud_risk_score > 0.3:
            recommendations.append("Consider updating your biometric profile if you've changed appearance")
        
        anomalous_count = sum(1 for e in recent_events if e.is_anomalous)
        if anomalous_count > 5:
            recommendations.append("Recent unusual activity detected - ensure you're using consistent devices")
        
        if len(profile.typical_login_hours or []) < 3:
            recommendations.append("Establish regular login patterns for better security")
        
        return recommendations
    
    async def _get_enhanced_attendance_list(self, request) -> List[Dict]:
        """Get attendance list with AI enhancements"""
        try:
            # Get standard attendance data
            objs = self.params["model"].objects.get_peopleevents_listview(
                self.params["related"], self.params["fields"], request
            )
            
            # Enhance with AI data
            enhanced_list = []
            for obj in objs:
                obj_dict = dict(obj)
                
                # Add AI metrics if available
                if obj_dict.get('peventlogextras'):
                    extras = obj_dict['peventlogextras']
                    if isinstance(extras, str):
                        try:
                            extras = json.loads(extras)
                        except:
                            extras = {}
                    
                    obj_dict.update({
                        'ai_verified': extras.get('verified', False),
                        'ai_confidence': extras.get('verification_confidence', 0),
                        'fraud_risk': extras.get('fraud_risk_score', 0),
                        'quality_score': extras.get('quality_score', 0),
                        'ai_enhanced': extras.get('ai_enhanced', False)
                    })
                
                enhanced_list.append(obj_dict)
            
            return enhanced_list
            
        except Exception as e:
            logger.error(f"Error getting enhanced attendance list: {str(e)}")
            return []
    
    def _get_ai_config(self) -> Dict[str, Any]:
        """Get AI configuration for frontend"""
        return {
            'quality_threshold': 0.4,
            'confidence_threshold': 0.8,
            'liveness_enabled': True,
            'deepfake_detection_enabled': True,
            'multi_modal_enabled': True,
            'real_time_feedback': True,
            'supported_formats': ['jpg', 'jpeg', 'png'],
            'max_image_size_mb': 10
        }
    
    async def _get_user_ai_profile(self, user_id: int) -> Dict[str, Any]:
        """Get user AI profile data for frontend"""
        try:
            # Get user embeddings count
            from apps.face_recognition.models import FaceEmbedding
            
            embeddings_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: FaceEmbedding.objects.filter(
                    user_id=user_id, is_validated=True
                ).count()
            )
            
            # Get behavior profile
            try:
                behavior_profile = await asyncio.get_event_loop().run_in_executor(
                    None,
                    UserBehaviorProfile.objects.get,
                    user_id=user_id
                )
                profile_data = {
                    'regularity_score': behavior_profile.attendance_regularity_score,
                    'fraud_risk': behavior_profile.fraud_risk_score,
                    'profile_confidence': behavior_profile.profile_confidence
                }
            except UserBehaviorProfile.DoesNotExist:
                profile_data = {
                    'regularity_score': 0.5,
                    'fraud_risk': 0.0,
                    'profile_confidence': 0.0
                }
            
            return {
                'embeddings_count': embeddings_count,
                'enrollment_complete': embeddings_count > 0,
                'behavior_profile': profile_data,
                'ai_ready': embeddings_count > 0 and profile_data['profile_confidence'] > 0.1
            }
            
        except Exception as e:
            logger.error(f"Error getting user AI profile: {str(e)}")
            return {
                'embeddings_count': 0,
                'enrollment_complete': False,
                'ai_ready': False,
                'error': str(e)
            }
    
    def _detect_device_type(self, request) -> str:
        """Detect device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'