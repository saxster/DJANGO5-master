"""
Factory classes for heatmap feature testing
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
import random
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.core.models.heatmap import (
    HeatmapSession, ClickHeatmap, ScrollHeatmap, 
    AttentionHeatmap, ElementInteraction, HeatmapAggregation
)

fake = Faker()
User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating test users"""
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True


class HeatmapSessionFactory(DjangoModelFactory):
    """Factory for creating heatmap sessions"""
    class Meta:
        model = HeatmapSession
    
    session_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    user = factory.SubFactory(UserFactory)
    page_url = factory.Faker('uri_path')
    page_title = factory.Faker('sentence', nb_words=4)
    viewport_width = factory.Faker('random_int', min=320, max=1920)
    viewport_height = factory.Faker('random_int', min=480, max=1080)
    screen_width = factory.Faker('random_int', min=1024, max=2560)
    screen_height = factory.Faker('random_int', min=768, max=1440)
    device_type = factory.Faker('random_element', elements=['desktop', 'tablet', 'mobile'])
    user_agent = factory.Faker('user_agent')
    ip_address = factory.Faker('ipv4')
    referrer = factory.Faker('uri')
    start_time = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())
    is_active = False
    
    @factory.post_generation
    def set_duration(obj, create, extracted, **kwargs):
        """Set session duration after creation"""
        if create and not obj.is_active:
            obj.end_time = obj.start_time + timezone.timedelta(
                seconds=random.randint(30, 600)
            )
            obj.duration_seconds = (obj.end_time - obj.start_time).total_seconds()
            obj.save()


class ClickHeatmapFactory(DjangoModelFactory):
    """Factory for creating click heatmap data"""
    class Meta:
        model = ClickHeatmap
    
    session = factory.SubFactory(HeatmapSessionFactory)
    x_position = factory.Faker('pyfloat', min_value=0, max_value=1, right_digits=4)
    y_position = factory.Faker('pyfloat', min_value=0, max_value=1, right_digits=4)
    absolute_x = factory.Faker('random_int', min=0, max=1920)
    absolute_y = factory.Faker('random_int', min=0, max=5000)
    element_type = factory.Faker('random_element', elements=['button', 'a', 'div', 'span', 'input'])
    element_id = factory.Faker('slug')
    element_class = factory.Faker('word')
    element_text = factory.Faker('sentence', nb_words=3)
    is_navigation = factory.Faker('boolean', chance_of_getting_true=30)
    time_since_load = factory.Faker('pyfloat', min_value=0.5, max_value=120, right_digits=2)
    click_type = factory.Faker('random_element', elements=['left', 'right', 'middle'])
    timestamp = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())


class ScrollHeatmapFactory(DjangoModelFactory):
    """Factory for creating scroll heatmap data"""
    class Meta:
        model = ScrollHeatmap
    
    session = factory.SubFactory(HeatmapSessionFactory)
    scroll_depth_pixels = factory.Faker('random_int', min=0, max=5000)
    scroll_depth_percentage = factory.Faker('pyfloat', min_value=0, max_value=100, right_digits=2)
    max_scroll_depth = factory.LazyAttribute(lambda obj: obj.scroll_depth_percentage)
    time_at_position = factory.Faker('pyfloat', min_value=0.1, max_value=30, right_digits=2)
    scroll_velocity = factory.Faker('pyfloat', min_value=0, max_value=1000, right_digits=2)
    timestamp = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())


class AttentionHeatmapFactory(DjangoModelFactory):
    """Factory for creating attention heatmap data"""
    class Meta:
        model = AttentionHeatmap
    
    session = factory.SubFactory(HeatmapSessionFactory)
    x_start = factory.Faker('pyfloat', min_value=0, max_value=0.8, right_digits=4)
    y_start = factory.Faker('pyfloat', min_value=0, max_value=0.8, right_digits=4)
    x_end = factory.LazyAttribute(lambda obj: min(obj.x_start + random.uniform(0.1, 0.3), 1.0))
    y_end = factory.LazyAttribute(lambda obj: min(obj.y_start + random.uniform(0.1, 0.3), 1.0))
    attention_duration = factory.Faker('pyfloat', min_value=0.5, max_value=60, right_digits=2)
    attention_score = factory.Faker('pyfloat', min_value=0, max_value=1, right_digits=3)
    content_type = factory.Faker('random_element', elements=['text', 'image', 'video', 'form', 'navigation'])
    has_interaction = factory.Faker('boolean', chance_of_getting_true=40)
    interaction_count = factory.Faker('random_int', min=0, max=10)
    timestamp = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())


class ElementInteractionFactory(DjangoModelFactory):
    """Factory for creating element interaction data"""
    class Meta:
        model = ElementInteraction
    
    session = factory.SubFactory(HeatmapSessionFactory)
    element_selector = factory.Faker('lexify', text='#????-????')
    element_type = factory.Faker('random_element', elements=['button', 'input', 'select', 'textarea', 'a'])
    element_id = factory.Faker('slug')
    element_class = factory.Faker('word')
    element_text = factory.Faker('sentence', nb_words=3)
    interaction_type = factory.Faker('random_element', 
                                    elements=['click', 'focus', 'blur', 'change', 'hover', 'submit'])
    duration = factory.Faker('pyfloat', min_value=0.1, max_value=30, right_digits=2)
    timestamp = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())


class HeatmapAggregationFactory(DjangoModelFactory):
    """Factory for creating heatmap aggregation data"""
    class Meta:
        model = HeatmapAggregation
    
    page_url = factory.Faker('uri_path')
    time_period = factory.Faker('random_element', elements=['hour', 'day', 'week', 'month'])
    period_start = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())
    period_end = factory.LazyAttribute(
        lambda obj: obj.period_start + timezone.timedelta(hours=1 if obj.time_period == 'hour' else 24)
    )
    device_type = factory.Faker('random_element', elements=['all', 'desktop', 'tablet', 'mobile'])
    session_count = factory.Faker('random_int', min=10, max=1000)
    total_clicks = factory.Faker('random_int', min=100, max=10000)
    total_scrolls = factory.Faker('random_int', min=50, max=5000)
    total_interactions = factory.Faker('random_int', min=50, max=5000)
    avg_session_duration = factory.Faker('pyfloat', min_value=30, max_value=600, right_digits=2)
    avg_scroll_depth = factory.Faker('pyfloat', min_value=20, max_value=100, right_digits=2)
    
    @factory.lazy_attribute
    def click_heatmap_data(self):
        """Generate sample click heatmap data"""
        return {
            'grid_size': 50,
            'matrix': [[random.random() for _ in range(50)] for _ in range(50)],
            'hotspots': [
                {'x': random.random(), 'y': random.random(), 'intensity': random.random()}
                for _ in range(10)
            ]
        }
    
    @factory.lazy_attribute
    def scroll_depth_distribution(self):
        """Generate sample scroll depth distribution"""
        return {
            str(i*10): random.randint(10, 100) for i in range(11)
        }
    
    @factory.lazy_attribute
    def interaction_summary(self):
        """Generate sample interaction summary"""
        return {
            'top_elements': [
                {
                    'selector': f'#element-{i}',
                    'count': random.randint(10, 100),
                    'avg_duration': random.uniform(0.5, 5.0)
                }
                for i in range(5)
            ],
            'interaction_types': {
                'click': random.randint(100, 500),
                'hover': random.randint(50, 200),
                'focus': random.randint(20, 100)
            }
        }


def create_complete_session_with_data(user=None, page_url='/test-page/', num_clicks=10, 
                                     num_scrolls=5, num_interactions=5):
    """
    Create a complete heatmap session with associated data
    
    Args:
        user: User object (optional)
        page_url: URL of the page
        num_clicks: Number of click events to create
        num_scrolls: Number of scroll events to create
        num_interactions: Number of interaction events to create
    
    Returns:
        HeatmapSession object with associated data
    """
    session = HeatmapSessionFactory(
        user=user,
        page_url=page_url,
        is_active=False
    )
    
    # Create click events
    for _ in range(num_clicks):
        ClickHeatmapFactory(session=session)
    
    # Create scroll events
    for _ in range(num_scrolls):
        ScrollHeatmapFactory(session=session)
    
    # Create interaction events
    for _ in range(num_interactions):
        ElementInteractionFactory(session=session)
    
    # Create some attention zones
    for _ in range(3):
        AttentionHeatmapFactory(session=session)
    
    # Update session data points count
    session.data_points_collected = num_clicks + num_scrolls + num_interactions + 3
    session.save()
    
    return session


def create_aggregation_for_page(page_url, num_sessions=100):
    """
    Create aggregation data for a specific page
    
    Args:
        page_url: URL of the page
        num_sessions: Number of sessions to aggregate
    
    Returns:
        HeatmapAggregation object
    """
    # Create sessions with data
    for _ in range(num_sessions):
        create_complete_session_with_data(page_url=page_url)
    
    # Create aggregation
    aggregation = HeatmapAggregationFactory(
        page_url=page_url,
        session_count=num_sessions
    )
    
    return aggregation