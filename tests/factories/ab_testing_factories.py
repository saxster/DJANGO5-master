"""
Factory classes for A/B testing feature testing
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
import random
import uuid
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta

from apps.ab_testing.models import (
    Experiment, Variant, Assignment, Conversion, 
    ExperimentResult, NavigationExperiment
)

fake = Faker()
User = get_user_model()


class ExperimentFactory(DjangoModelFactory):
    """Factory for creating A/B test experiments"""
    class Meta:
        model = Experiment
    
    name = factory.Sequence(lambda n: f"experiment_{n}_{fake.slug()}")
    description = factory.Faker('paragraph', nb_sentences=3)
    hypothesis = factory.Faker('paragraph', nb_sentences=2)
    experiment_type = factory.Faker('random_element', 
                                   elements=['navigation', 'layout', 'feature', 'content', 'workflow'])
    status = factory.Faker('random_element', 
                          elements=['draft', 'running', 'paused', 'completed', 'archived'])
    target_url_pattern = factory.Faker('uri_path')
    target_percentage = factory.Faker('pyfloat', min_value=10, max_value=100, right_digits=1)
    start_date = factory.Faker('date_time_this_month', tzinfo=timezone.get_current_timezone())
    end_date = factory.LazyAttribute(
        lambda obj: obj.start_date + timedelta(days=random.randint(7, 30))
    )
    primary_metric = factory.Faker('random_element', 
                                  elements=['conversion_rate', 'click_through_rate', 
                                          'time_on_page', 'bounce_rate'])
    minimum_sample_size = factory.Faker('random_int', min=100, max=10000)
    confidence_level = 0.95
    is_active = True
    allow_multiple_exposures = False
    
    @factory.lazy_attribute
    def secondary_metrics(self):
        """Generate secondary metrics list"""
        metrics = ['page_views', 'session_duration', 'engagement_rate', 'revenue_per_user']
        return random.sample(metrics, k=random.randint(1, 3))
    
    @factory.lazy_attribute
    def target_user_groups(self):
        """Generate target user groups"""
        if random.random() > 0.5:
            groups = ['premium', 'basic', 'trial', 'enterprise']
            return random.sample(groups, k=random.randint(1, 2))
        return None


class VariantFactory(DjangoModelFactory):
    """Factory for creating experiment variants"""
    class Meta:
        model = Variant
    
    experiment = factory.SubFactory(ExperimentFactory)
    name = factory.Faker('word')
    description = factory.Faker('paragraph', nb_sentences=2)
    is_control = False
    weight = factory.Faker('pyfloat', min_value=10, max_value=50, right_digits=1)
    
    @factory.lazy_attribute
    def configuration(self):
        """Generate variant configuration"""
        return {
            'color_scheme': fake.color_name(),
            'button_text': fake.word(),
            'layout_version': random.randint(1, 5),
            'feature_enabled': fake.boolean()
        }
    
    @factory.lazy_attribute
    def navigation_config(self):
        """Generate navigation configuration"""
        return {
            'menu_style': random.choice(['horizontal', 'vertical', 'hamburger']),
            'menu_position': random.choice(['top', 'left', 'right']),
            'submenu_behavior': random.choice(['hover', 'click', 'accordion']),
            'items': [
                {'label': fake.word(), 'url': fake.uri_path(), 'order': i}
                for i in range(5)
            ]
        }
    
    @factory.lazy_attribute
    def layout_config(self):
        """Generate layout configuration"""
        return {
            'grid_columns': random.choice([2, 3, 4]),
            'sidebar_position': random.choice(['left', 'right', 'none']),
            'header_style': random.choice(['minimal', 'full', 'sticky']),
            'footer_visible': fake.boolean()
        }
    
    @factory.lazy_attribute
    def feature_flags(self):
        """Generate feature flags"""
        return {
            'new_dashboard': fake.boolean(),
            'advanced_search': fake.boolean(),
            'quick_actions': fake.boolean(),
            'ai_suggestions': fake.boolean()
        }


class AssignmentFactory(DjangoModelFactory):
    """Factory for creating user assignments to variants"""
    class Meta:
        model = Assignment
    
    experiment = factory.SubFactory(ExperimentFactory)
    variant = factory.SubFactory(VariantFactory, experiment=factory.SelfAttribute('..experiment'))
    user = factory.SubFactory('tests.factories.heatmap_factories.UserFactory')
    session_id = factory.LazyFunction(lambda: str(uuid.uuid4())[:64])
    assignment_reason = factory.Faker('random_element', 
                                    elements=['random', 'forced', 'cookie', 'user_based'])
    ip_address = factory.Faker('ipv4')
    user_agent = factory.Faker('user_agent')
    referrer = factory.Faker('uri')
    first_exposure = factory.Faker('date_time_this_week', tzinfo=timezone.get_current_timezone())
    last_exposure = factory.LazyAttribute(lambda obj: obj.first_exposure)
    exposure_count = factory.Faker('random_int', min=1, max=20)


class ConversionFactory(DjangoModelFactory):
    """Factory for creating conversion events"""
    class Meta:
        model = Conversion
    
    assignment = factory.SubFactory(AssignmentFactory)
    goal_type = factory.LazyAttribute(lambda obj: obj.assignment.experiment.primary_metric)
    goal_value = factory.Faker('pyfloat', min_value=0, max_value=1000, right_digits=2)
    converted_at = factory.Faker('date_time_this_week', tzinfo=timezone.get_current_timezone())
    conversion_url = factory.Faker('uri_path')
    
    @factory.lazy_attribute
    def time_to_conversion(self):
        """Calculate time to conversion"""
        if self.assignment and self.converted_at:
            delta = self.converted_at - self.assignment.first_exposure
            return delta.total_seconds()
        return random.uniform(60, 3600)
    
    @factory.lazy_attribute
    def conversion_metadata(self):
        """Generate conversion metadata"""
        return {
            'source': random.choice(['direct', 'search', 'social', 'email']),
            'device': random.choice(['desktop', 'mobile', 'tablet']),
            'browser': fake.chrome(),
            'revenue': random.uniform(10, 500) if self.goal_type == 'purchase' else None
        }


class ExperimentResultFactory(DjangoModelFactory):
    """Factory for creating experiment results"""
    class Meta:
        model = ExperimentResult
    
    experiment = factory.SubFactory(ExperimentFactory)
    total_participants = factory.Faker('random_int', min=100, max=10000)
    overall_conversion_rate = factory.Faker('pyfloat', min_value=0.01, max_value=0.5, right_digits=4)
    p_value = factory.Faker('pyfloat', min_value=0.001, max_value=0.2, right_digits=4)
    statistical_power = factory.Faker('pyfloat', min_value=0.7, max_value=0.99, right_digits=2)
    winner_variant = None
    lift_percentage = factory.Faker('pyfloat', min_value=-20, max_value=50, right_digits=2)
    recommendation = factory.Faker('paragraph', nb_sentences=2)
    
    @factory.lazy_attribute
    def variant_participants(self):
        """Generate participant counts per variant"""
        return {
            'control': random.randint(50, 5000),
            'variant_a': random.randint(50, 5000),
            'variant_b': random.randint(50, 5000)
        }
    
    @factory.lazy_attribute
    def variant_conversion_rates(self):
        """Generate conversion rates per variant"""
        return {
            'control': random.uniform(0.01, 0.3),
            'variant_a': random.uniform(0.01, 0.35),
            'variant_b': random.uniform(0.01, 0.32)
        }
    
    @factory.lazy_attribute
    def confidence_interval(self):
        """Generate confidence intervals"""
        return {
            'control': [0.08, 0.12],
            'variant_a': [0.09, 0.14],
            'variant_b': [0.07, 0.11]
        }
    
    @factory.lazy_attribute
    def secondary_metrics_results(self):
        """Generate secondary metrics results"""
        return {
            'page_views': {
                'control': random.uniform(2, 5),
                'variant_a': random.uniform(2.5, 5.5),
                'variant_b': random.uniform(2, 4.5)
            },
            'session_duration': {
                'control': random.uniform(60, 300),
                'variant_a': random.uniform(70, 320),
                'variant_b': random.uniform(65, 290)
            }
        }


class NavigationExperimentFactory(DjangoModelFactory):
    """Factory for creating navigation-specific experiments"""
    class Meta:
        model = NavigationExperiment
    
    experiment = factory.SubFactory(ExperimentFactory, experiment_type='navigation')
    test_menu_structure = factory.Faker('boolean', chance_of_getting_true=60)
    test_menu_labels = factory.Faker('boolean', chance_of_getting_true=50)
    test_menu_order = factory.Faker('boolean', chance_of_getting_true=40)
    test_breadcrumbs = factory.Faker('boolean', chance_of_getting_true=30)
    test_sidebar = factory.Faker('boolean', chance_of_getting_true=40)
    track_click_through_rate = True
    track_time_to_action = True
    track_bounce_rate = factory.Faker('boolean', chance_of_getting_true=70)
    track_navigation_depth = factory.Faker('boolean', chance_of_getting_true=60)


def create_complete_experiment(name=None, num_variants=2, participants_per_variant=100):
    """
    Create a complete experiment with variants and sample data
    
    Args:
        name: Experiment name (optional)
        num_variants: Number of variants to create (including control)
        participants_per_variant: Number of participants per variant
    
    Returns:
        Experiment object with associated data
    """
    experiment = ExperimentFactory(
        name=name or f"Complete Experiment {fake.slug()}",
        status='running',
        is_active=True
    )
    
    # Create control variant
    control = VariantFactory(
        experiment=experiment,
        name='Control',
        is_control=True,
        weight=50.0
    )
    
    # Create test variants
    variants = [control]
    remaining_weight = 50.0
    for i in range(1, num_variants):
        variant_weight = remaining_weight / (num_variants - i)
        variant = VariantFactory(
            experiment=experiment,
            name=f'Variant {chr(65 + i - 1)}',  # A, B, C...
            is_control=False,
            weight=variant_weight
        )
        variants.append(variant)
        remaining_weight -= variant_weight
    
    # Create assignments and conversions
    for variant in variants:
        for _ in range(participants_per_variant):
            assignment = AssignmentFactory(
                experiment=experiment,
                variant=variant
            )
            
            # Create conversion with probability based on variant
            conversion_probability = 0.1 if variant.is_control else random.uniform(0.08, 0.15)
            if random.random() < conversion_probability:
                ConversionFactory(
                    assignment=assignment,
                    goal_type=experiment.primary_metric
                )
    
    # Create experiment result
    result = ExperimentResultFactory(experiment=experiment)
    
    return experiment


def create_navigation_experiment_with_data():
    """
    Create a navigation-specific experiment with complete data
    
    Returns:
        NavigationExperiment object with associated experiment data
    """
    experiment = create_complete_experiment(
        name=f"Navigation Test {fake.slug()}",
        num_variants=3,
        participants_per_variant=200
    )
    
    # Create navigation-specific configuration
    nav_experiment = NavigationExperimentFactory(experiment=experiment)
    
    # Update variants with navigation-specific configs
    for variant in experiment.variants.all():
        if not variant.is_control:
            variant.navigation_config = {
                'menu_style': random.choice(['horizontal', 'vertical']),
                'menu_items': [
                    {'label': fake.word().title(), 'url': fake.uri_path()}
                    for _ in range(random.randint(4, 8))
                ],
                'show_icons': fake.boolean(),
                'mega_menu': fake.boolean()
            }
            variant.save()
    
    return nav_experiment