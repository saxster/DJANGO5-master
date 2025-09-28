"""
Advanced recommendation engine for intelligent navigation and content suggestions
"""
import numpy as np
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.models.heatmap import HeatmapSession, ClickHeatmap, ScrollHeatmap
    UserBehaviorProfile, NavigationRecommendation, ContentRecommendation,
    UserSimilarity, RecommendationFeedback
)
from apps.ab_testing.models import Experiment, Assignment, Conversion

User = get_user_model()
logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Main recommendation engine orchestrator"""
    
    def __init__(self):
        self.collaborative_filter = CollaborativeFilteringEngine()
        self.content_filter = ContentBasedEngine()
        self.navigation_analyzer = NavigationAnalyzer()
        self.behavior_analyzer = BehaviorAnalyzer()
    
    def generate_user_recommendations(self, user: User, limit: int = 10) -> List[ContentRecommendation]:
        """Generate personalized recommendations for a user"""
        try:
            # Get or create user behavior profile
            profile, created = UserBehaviorProfile.objects.get_or_create(user=user)
            if created:
                self.behavior_analyzer.build_user_profile(user)
                profile.refresh_from_db()
            
            # Generate recommendations from different engines
            collaborative_recs = self.collaborative_filter.get_recommendations(user, limit//2)
            content_recs = self.content_filter.get_recommendations(user, limit//2)
            
            # Combine and rank recommendations
            all_recommendations = collaborative_recs + content_recs
            ranked_recommendations = self._rank_recommendations(all_recommendations, user)
            
            return ranked_recommendations[:limit]
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error generating user recommendations: {str(e)}")
            return []
    
    def generate_navigation_recommendations(self, page_url: str = None) -> List[NavigationRecommendation]:
        """Generate navigation improvement recommendations"""
        try:
            return self.navigation_analyzer.analyze_navigation_patterns(page_url)
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error generating navigation recommendations: {str(e)}")
            return []
    
    def update_user_behavior(self, user: User, session_data: Dict):
        """Update user behavior based on new session data"""
        try:
            profile, created = UserBehaviorProfile.objects.get_or_create(user=user)
            profile.update_profile(session_data)
            
            # Recalculate similarity if needed
            if created or self._should_recalculate_similarity(profile):
                self.collaborative_filter.calculate_user_similarities(user)
                
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error updating user behavior: {str(e)}")
    
    def _rank_recommendations(self, recommendations: List[ContentRecommendation], user: User) -> List[ContentRecommendation]:
        """Rank recommendations by relevance and user context"""
        if not recommendations:
            return []
        
        # Get user context
        profile = UserBehaviorProfile.objects.filter(user=user).first()
        if not profile:
            return recommendations
        
        # Apply context-based scoring
        for rec in recommendations:
            base_score = rec.relevance_score
            
            # Boost based on user's preferred content types
            if rec.content_type in profile.preferred_content_types:
                rec.relevance_score *= 1.2
            
            # Penalize if shown too recently or too often
            if rec.shown_count > 5:
                rec.relevance_score *= 0.8
            
            if rec.dismissed_count > 0:
                rec.relevance_score *= (1.0 - (rec.dismissed_count * 0.2))
            
            # Boost based on time of day and user activity patterns
            rec.relevance_score = min(1.0, max(0.0, rec.relevance_score))
        
        return sorted(recommendations, key=lambda x: x.relevance_score, reverse=True)
    
    def _should_recalculate_similarity(self, profile: UserBehaviorProfile) -> bool:
        """Check if user similarity should be recalculated"""
        last_similarity_calc = UserSimilarity.objects.filter(
            Q(user1=profile.user) | Q(user2=profile.user)
        ).order_by('-calculated_at').first()
        
        if not last_similarity_calc:
            return True
        
        # Recalculate if it's been more than 7 days
        return timezone.now() - last_similarity_calc.calculated_at > timedelta(days=7)


class CollaborativeFilteringEngine:
    """Collaborative filtering recommendation engine"""
    
    def get_recommendations(self, user: User, limit: int = 5) -> List[ContentRecommendation]:
        """Get recommendations based on similar users"""
        try:
            # Find similar users
            similar_users = self._get_similar_users(user, limit=10)
            if not similar_users:
                return []
            
            # Get content liked by similar users
            recommended_content = self._get_content_from_similar_users(user, similar_users)
            
            # Create recommendation objects
            recommendations = []
            for content_data in recommended_content[:limit]:
                rec = ContentRecommendation(
                    user=user,
                    content_type=content_data['type'],
                    content_title=content_data['title'],
                    content_url=content_data['url'],
                    content_description=content_data.get('description', ''),
                    reason=f"Users with similar behavior also liked this {content_data['type']}",
                    relevance_score=content_data['score'],
                    recommendation_algorithm='collaborative_filtering'
                )
                recommendations.append(rec)
            
            return recommendations
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error in collaborative filtering: {str(e)}")
            return []
    
    def _get_similar_users(self, user: User, limit: int = 10) -> List[Tuple[User, float]]:
        """Get users similar to the given user"""
        similarities = UserSimilarity.objects.filter(
            Q(user1=user) | Q(user2=user)
        ).order_by('-similarity_score')[:limit]
        
        similar_users = []
        for sim in similarities:
            other_user = sim.user2 if sim.user1 == user else sim.user1
            similar_users.append((other_user, sim.similarity_score))
        
        return similar_users
    
    def _get_content_from_similar_users(self, user: User, similar_users: List[Tuple[User, float]]) -> List[Dict]:
        """Get content recommendations based on similar users' behavior"""
        content_scores = defaultdict(float)
        content_info = {}
        
        for similar_user, similarity_score in similar_users:
            # Get pages visited by similar user
            profile = UserBehaviorProfile.objects.filter(user=similar_user).first()
            if not profile or not profile.preferred_pages:
                continue
            
            for page_url, visit_count in profile.preferred_pages.items():
                # Skip if current user already visits this page frequently
                user_profile = UserBehaviorProfile.objects.filter(user=user).first()
                if user_profile and page_url in user_profile.preferred_pages:
                    if user_profile.preferred_pages[page_url] >= visit_count:
                        continue
                
                # Calculate recommendation score
                score = similarity_score * (visit_count / 10.0)  # normalize visit count
                content_scores[page_url] += score
                
                if page_url not in content_info:
                    content_info[page_url] = {
                        'type': 'page',
                        'title': self._get_page_title(page_url),
                        'url': page_url,
                        'description': f"Popular page among similar users"
                    }
        
        # Convert to list and sort by score
        recommendations = []
        for page_url, score in content_scores.items():
            content_data = content_info[page_url]
            content_data['score'] = min(1.0, score)  # Cap at 1.0
            recommendations.append(content_data)
        
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)
    
    def _get_page_title(self, page_url: str) -> str:
        """Get a friendly title for a page URL"""
        # Simple title extraction from URL
        if page_url == '/':
            return 'Home'
        
        # Remove leading/trailing slashes and split
        clean_url = page_url.strip('/')
        parts = clean_url.split('/')
        
        # Use the last part as title, capitalize and replace underscores
        if parts:
            title = parts[-1].replace('_', ' ').replace('-', ' ').title()
            return title if title else 'Page'
        
        return 'Page'
    
    def calculate_user_similarities(self, user: User = None):
        """Calculate user similarities using behavior profiles"""
        try:
            # Get all users with behavior profiles
            profiles = UserBehaviorProfile.objects.select_related('user').all()
            
            if user:
                # Calculate similarities for specific user
                user_profile = UserBehaviorProfile.objects.filter(user=user).first()
                if not user_profile:
                    return
                
                for other_profile in profiles:
                    if other_profile.user == user:
                        continue
                    
                    similarity = self._calculate_cosine_similarity(user_profile, other_profile)
                    
                    # Store similarity (ensure user1 < user2 for consistency)
                    user1, user2 = (user, other_profile.user) if user.id < other_profile.user.id else (other_profile.user, user)
                    
                    UserSimilarity.objects.update_or_create(
                        user1=user1,
                        user2=user2,
                        defaults={
                            'similarity_score': similarity,
                            'calculation_method': 'cosine_similarity',
                            'features_used': ['behavior_vector', 'page_preferences']
                        }
                    )
            else:
                # Calculate all pairwise similarities
                for i, profile1 in enumerate(profiles):
                    for profile2 in profiles[i+1:]:
                        similarity = self._calculate_cosine_similarity(profile1, profile2)
                        
                        UserSimilarity.objects.update_or_create(
                            user1=profile1.user,
                            user2=profile2.user,
                            defaults={
                                'similarity_score': similarity,
                                'calculation_method': 'cosine_similarity',
                                'features_used': ['behavior_vector', 'page_preferences']
                            }
                        )
        
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error calculating user similarities: {str(e)}")
    
    def _calculate_cosine_similarity(self, profile1: UserBehaviorProfile, profile2: UserBehaviorProfile) -> float:
        """Calculate cosine similarity between two user profiles"""
        try:
            # Ensure both profiles have similarity vectors
            if not profile1.similarity_vector:
                profile1.calculate_similarity_vector()
            if not profile2.similarity_vector:
                profile2.calculate_similarity_vector()
            
            vec1 = np.array(profile1.similarity_vector)
            vec2 = np.array(profile2.similarity_vector)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm_product = np.linalg.norm(vec1) * np.linalg.norm(vec2)
            
            if norm_product == 0:
                return 0.0
            
            similarity = dot_product / norm_product
            return float(np.clip(similarity, -1.0, 1.0))
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0


class ContentBasedEngine:
    """Content-based recommendation engine"""
    
    def get_recommendations(self, user: User, limit: int = 5) -> List[ContentRecommendation]:
        """Get recommendations based on user's content preferences"""
        try:
            profile = UserBehaviorProfile.objects.filter(user=user).first()
            if not profile:
                return []
            
            # Analyze user's content patterns
            content_features = self._extract_content_features(user)
            
            # Find similar content
            similar_content = self._find_similar_content(content_features, limit)
            
            # Create recommendation objects
            recommendations = []
            for content_data in similar_content:
                rec = ContentRecommendation(
                    user=user,
                    content_type=content_data['type'],
                    content_title=content_data['title'],
                    content_url=content_data['url'],
                    content_description=content_data.get('description', ''),
                    reason=f"Based on your interest in {', '.join(content_data.get('features', []))}",
                    relevance_score=content_data['score'],
                    recommendation_algorithm='content_based'
                )
                recommendations.append(rec)
            
            return recommendations
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error in content-based filtering: {str(e)}")
            return []
    
    def _extract_content_features(self, user: User) -> Dict[str, float]:
        """Extract content features from user's behavior"""
        profile = UserBehaviorProfile.objects.filter(user=user).first()
        if not profile:
            return {}
        
        features = {}
        
        # Extract features from preferred pages
        for page_url, visit_count in profile.preferred_pages.items():
            # Extract features from URL structure
            url_parts = page_url.strip('/').split('/')
            for part in url_parts:
                if part and len(part) > 2:  # Skip very short parts
                    clean_part = part.replace('_', ' ').replace('-', ' ')
                    features[clean_part] = features.get(clean_part, 0) + visit_count
        
        # Normalize feature scores
        if features:
            max_score = max(features.values())
            features = {k: v/max_score for k, v in features.items()}
        
        return features
    
    def _find_similar_content(self, user_features: Dict[str, float], limit: int) -> List[Dict]:
        """Find content similar to user's preferences"""
        # This is a simplified implementation
        # In a real system, you would have a content database with features
        
        recommendations = []
        
        # Example recommendations based on common features
        if 'reports' in user_features or 'report' in user_features:
            recommendations.append({
                'type': 'report',
                'title': 'Advanced Analytics Dashboard',
                'url': '/reports/advanced-analytics',
                'score': user_features.get('reports', user_features.get('report', 0.5)),
                'features': ['reports', 'analytics'],
                'description': 'Comprehensive analytics with advanced visualizations'
            })
        
        if 'dashboard' in user_features:
            recommendations.append({
                'type': 'dashboard',
                'title': 'Executive Summary Dashboard',
                'url': '/dashboard/executive',
                'score': user_features.get('dashboard', 0.5),
                'features': ['dashboard', 'executive'],
                'description': 'High-level overview for executives'
            })
        
        if 'admin' in user_features:
            recommendations.append({
                'type': 'tool',
                'title': 'System Administration Tools',
                'url': '/admin/tools',
                'score': user_features.get('admin', 0.5),
                'features': ['admin', 'tools'],
                'description': 'Advanced administration utilities'
            })
        
        return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:limit]


class NavigationAnalyzer:
    """Analyze navigation patterns and generate improvement recommendations"""
    
    def analyze_navigation_patterns(self, page_url: str = None) -> List[NavigationRecommendation]:
        """Analyze navigation patterns and generate recommendations"""
        try:
            recommendations = []
            
            # Analyze heatmap data for navigation issues
            if page_url:
                recommendations.extend(self._analyze_page_navigation(page_url))
            else:
                recommendations.extend(self._analyze_global_navigation())
            
            # Analyze A/B test results for navigation insights
            recommendations.extend(self._analyze_ab_test_results())
            
            return recommendations
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing navigation patterns: {str(e)}")
            return []
    
    def _analyze_page_navigation(self, page_url: str) -> List[NavigationRecommendation]:
        """Analyze navigation patterns for a specific page"""
        recommendations = []
        
        # Get heatmap data for the page
        sessions = HeatmapSession.objects.filter(page_url=page_url)
        if not sessions.exists():
            return recommendations
        
        # Analyze click patterns
        click_data = self._analyze_click_patterns(sessions)
        if click_data['dead_zones']:
            rec = NavigationRecommendation(
                recommendation_type='layout_improvement',
                title=f'Improve layout for {page_url}',
                description='Users are not clicking on important elements',
                target_page=page_url,
                suggested_action='Redesign layout to make important elements more prominent',
                expected_impact='Increase user engagement by 15-25%',
                confidence_score=0.8,
                supporting_data=click_data,
                priority='medium'
            )
            recommendations.append(rec)
        
        # Analyze scroll patterns
        scroll_data = self._analyze_scroll_patterns(sessions)
        if scroll_data['low_scroll_depth']:
            rec = NavigationRecommendation(
                recommendation_type='content_personalization',
                title=f'Improve content engagement on {page_url}',
                description='Users are not scrolling down to see important content',
                target_page=page_url,
                suggested_action='Move important content above the fold or improve content hierarchy',
                expected_impact='Increase content consumption by 20-30%',
                confidence_score=0.7,
                supporting_data=scroll_data,
                priority='medium'
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _analyze_global_navigation(self) -> List[NavigationRecommendation]:
        """Analyze global navigation patterns"""
        recommendations = []
        
        # Find pages with high bounce rates
        high_bounce_pages = self._find_high_bounce_pages()
        for page_data in high_bounce_pages:
            rec = NavigationRecommendation(
                recommendation_type='page_suggestion',
                title=f'Improve retention on {page_data["page_url"]}',
                description=f'Page has high bounce rate of {page_data["bounce_rate"]:.1%}',
                target_page=page_data['page_url'],
                suggested_action='Add related links, improve content quality, or simplify navigation',
                expected_impact='Reduce bounce rate by 10-20%',
                confidence_score=0.6,
                supporting_data=page_data,
                priority='medium'
            )
            recommendations.append(rec)
        
        # Find common exit points
        exit_patterns = self._analyze_exit_patterns()
        if exit_patterns:
            rec = NavigationRecommendation(
                recommendation_type='menu_optimization',
                title='Optimize navigation menu based on exit patterns',
                description='Users frequently exit from specific navigation points',
                suggested_action='Restructure menu to reduce friction at common exit points',
                expected_impact='Improve user flow and reduce exit rate by 15%',
                confidence_score=0.7,
                supporting_data=exit_patterns,
                priority='high'
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _analyze_click_patterns(self, sessions) -> Dict:
        """Analyze click patterns for sessions"""
        total_clicks = 0
        element_clicks = Counter()
        dead_zones = []
        
        for session in sessions:
            clicks = ClickHeatmap.objects.filter(session=session)
            total_clicks += clicks.count()
            
            for click in clicks:
                element_key = f"{click.element_tag}_{click.element_class}_{click.element_id}"
                element_clicks[element_key] += 1
        
        # Identify potential dead zones (areas with very few clicks)
        if total_clicks > 0:
            avg_clicks_per_element = total_clicks / max(1, len(element_clicks))
            for element, click_count in element_clicks.items():
                if click_count < avg_clicks_per_element * 0.1:  # Less than 10% of average
                    dead_zones.append(element)
        
        return {
            'total_clicks': total_clicks,
            'element_distribution': dict(element_clicks.most_common(10)),
            'dead_zones': dead_zones[:5],  # Top 5 dead zones
            'avg_clicks_per_session': total_clicks / sessions.count() if sessions.count() > 0 else 0
        }
    
    def _analyze_scroll_patterns(self, sessions) -> Dict:
        """Analyze scroll patterns for sessions"""
        total_scrolls = 0
        avg_scroll_depth = 0
        low_scroll_sessions = 0
        
        for session in sessions:
            scrolls = ScrollHeatmap.objects.filter(session=session)
            total_scrolls += scrolls.count()
            
            if scrolls.exists():
                max_depth = scrolls.aggregate(max_depth=models.Max('scroll_depth'))['max_depth'] or 0
                avg_scroll_depth += max_depth
                
                if max_depth < 0.3:  # Less than 30% scroll depth
                    low_scroll_sessions += 1
            else:
                low_scroll_sessions += 1
        
        session_count = sessions.count()
        return {
            'total_scrolls': total_scrolls,
            'avg_scroll_depth': avg_scroll_depth / session_count if session_count > 0 else 0,
            'low_scroll_percentage': low_scroll_sessions / session_count if session_count > 0 else 0,
            'low_scroll_depth': low_scroll_sessions / session_count > 0.6 if session_count > 0 else False
        }
    
    def _find_high_bounce_pages(self) -> List[Dict]:
        """Find pages with high bounce rates"""
        
        # Calculate bounce rate for each page
        page_stats = []
        
        # Get pages with session data
        pages = HeatmapSession.objects.values('page_url').annotate(
            session_count=Count('id'),
            short_sessions=Count('id', filter=Q(duration_seconds__lt=30))
        ).filter(session_count__gte=10)  # Only pages with enough data
        
        for page in pages:
            bounce_rate = page['short_sessions'] / page['session_count']
            if bounce_rate > 0.7:  # More than 70% bounce rate
                page_stats.append({
                    'page_url': page['page_url'],
                    'bounce_rate': bounce_rate,
                    'session_count': page['session_count'],
                    'short_sessions': page['short_sessions']
                })
        
        return sorted(page_stats, key=lambda x: x['bounce_rate'], reverse=True)[:5]
    
    def _analyze_exit_patterns(self) -> Dict:
        """Analyze common exit patterns"""
        # This would analyze user paths and find common exit points
        # Simplified implementation
        
        exit_pages = HeatmapSession.objects.values('page_url').annotate(
            exit_count=Count('id', filter=Q(is_active=False))
        ).order_by('-exit_count')[:10]
        
        return {
            'top_exit_pages': list(exit_pages),
            'analysis_date': timezone.now().isoformat()
        }
    
    def _analyze_ab_test_results(self) -> List[NavigationRecommendation]:
        """Generate recommendations based on A/B test results"""
        recommendations = []
        
        # Find completed experiments with clear winners
        completed_experiments = Experiment.objects.filter(
            status='completed',
            end_date__isnull=False
        )
        
        for experiment in completed_experiments:
            # Analyze experiment results
            variants = experiment.variants.all()
            if len(variants) < 2:
                continue
            
            # Find the best performing variant
            best_variant = None
            best_conversion_rate = 0
            
            for variant in variants:
                assignments = Assignment.objects.filter(variant=variant).count()
                conversions = Conversion.objects.filter(
                    assignment__variant=variant,
                    goal_type=experiment.primary_metric
                ).count()
                
                conversion_rate = conversions / assignments if assignments > 0 else 0
                
                if conversion_rate > best_conversion_rate:
                    best_conversion_rate = conversion_rate
                    best_variant = variant
            
            # Create recommendation if there's a clear winner
            if best_variant and best_conversion_rate > 0.1:  # At least 10% conversion rate
                rec = NavigationRecommendation(
                    recommendation_type='layout_improvement',
                    title=f'Implement winning variant from {experiment.name}',
                    description=f'Variant "{best_variant.name}" showed {best_conversion_rate:.1%} conversion rate',
                    suggested_action=f'Roll out variant "{best_variant.name}" to all users',
                    expected_impact=f'Increase conversions by {(best_conversion_rate * 100):.1f}%',
                    confidence_score=0.9,
                    supporting_data={
                        'experiment_id': experiment.id,
                        'winning_variant': best_variant.name,
                        'conversion_rate': best_conversion_rate
                    },
                    priority='high'
                )
                recommendations.append(rec)
        
        return recommendations


class BehaviorAnalyzer:
    """Analyze and build user behavior profiles"""
    
    def build_user_profile(self, user: User):
        """Build comprehensive behavior profile for user"""
        try:
            profile, created = UserBehaviorProfile.objects.get_or_create(user=user)
            
            # Analyze heatmap sessions
            sessions = HeatmapSession.objects.filter(user=user)
            if sessions.exists():
                self._analyze_session_patterns(profile, sessions)
                self._analyze_navigation_patterns(profile, sessions)
                self._analyze_interaction_patterns(profile, sessions)
            
            # Analyze A/B test participation
            assignments = Assignment.objects.filter(user=user)
            if assignments.exists():
                self._analyze_experiment_participation(profile, assignments)
            
            # Calculate behavioral characteristics
            self._calculate_behavior_metrics(profile)
            
            profile.save()
            
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error building user profile: {str(e)}")
    
    def _analyze_session_patterns(self, profile: UserBehaviorProfile, sessions):
        """Analyze user session patterns"""
        # Calculate average session duration
        durations = [s.duration_seconds for s in sessions if s.duration_seconds]
        if durations:
            profile.session_duration_avg = sum(durations) / len(durations)
        
        # Analyze page preferences
        page_visits = Counter()
        for session in sessions:
            page_visits[session.page_url] += 1
        
        profile.preferred_pages = dict(page_visits.most_common(20))
        
        # Analyze device preferences
        device_counts = Counter(session.device_type for session in sessions)
        if device_counts:
            profile.preferred_device_type = device_counts.most_common(1)[0][0]
    
    def _analyze_navigation_patterns(self, profile: UserBehaviorProfile, sessions):
        """Analyze user navigation patterns"""
        # Track common navigation paths
        paths = []
        sorted_sessions = sessions.order_by('start_time')
        
        current_path = []
        for session in sorted_sessions:
            # If there's a gap of more than 1 hour, start a new path
            if current_path and session.start_time:
                last_session = sorted_sessions.filter(
                    start_time__lt=session.start_time
                ).last()
                if last_session and session.start_time - last_session.start_time > timedelta(hours=1):
                    if len(current_path) > 1:
                        paths.append(current_path)
                    current_path = []
            
            current_path.append(session.page_url)
        
        if len(current_path) > 1:
            paths.append(current_path)
        
        # Store most common paths
        path_counter = Counter(tuple(path) for path in paths if len(path) > 1)
        profile.common_paths = [list(path) for path, count in path_counter.most_common(5)]
    
    def _analyze_interaction_patterns(self, profile: UserBehaviorProfile, sessions):
        """Analyze user interaction patterns"""
        click_patterns = {}
        interaction_freq = defaultdict(int)
        
        for session in sessions:
            # Analyze clicks
            clicks = ClickHeatmap.objects.filter(session=session)
            for click in clicks:
                element_key = f"{click.element_tag}#{click.element_id}.{click.element_class}"
                if element_key not in click_patterns:
                    click_patterns[element_key] = 0
                click_patterns[element_key] += 1
                interaction_freq[click.element_tag] += 1
        
        profile.click_patterns = dict(Counter(click_patterns).most_common(20))
        profile.interaction_frequency = dict(interaction_freq)
    
    def _analyze_experiment_participation(self, profile: UserBehaviorProfile, assignments):
        """Analyze user's A/B test participation"""
        # Calculate feature adoption rate based on experiment participation
        experiments_with_conversion = assignments.filter(
            conversions__isnull=False
        ).distinct().count()
        
        total_experiments = assignments.values('experiment').distinct().count()
        
        if total_experiments > 0:
            profile.feature_adoption_rate = experiments_with_conversion / total_experiments
    
    def _calculate_behavior_metrics(self, profile: UserBehaviorProfile):
        """Calculate behavioral characteristic scores"""
        # Calculate exploration tendency based on page diversity
        unique_pages = len(profile.preferred_pages)
        total_visits = sum(profile.preferred_pages.values()) if profile.preferred_pages else 0
        
        if total_visits > 0:
            # Higher ratio of unique pages to total visits = more exploratory
            profile.exploration_tendency = min(1.0, unique_pages / (total_visits * 0.1))
        
        # Calculate task completion rate (simplified)
        # This would ideally be based on actual task completion data
        if profile.session_duration_avg > 300:  # Sessions longer than 5 minutes
            profile.task_completion_rate = min(1.0, profile.session_duration_avg / 1800)  # Normalize to 30 minutes
        
        # Update similarity vector
        profile.calculate_similarity_vector()