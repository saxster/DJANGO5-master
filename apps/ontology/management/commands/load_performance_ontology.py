"""
Management command to load performance optimization patterns into the ontology.

Usage:
    python manage.py load_performance_ontology
    python manage.py load_performance_ontology --stats
"""

from django.core.management.base import BaseCommand
from apps.ontology.registrations.performance_optimization_patterns import (
    register_performance_optimization_patterns,
    get_performance_summary
)
from apps.ontology.registry import OntologyRegistry


class Command(BaseCommand):
    help = "Load performance optimization patterns into the ontology registry"

    def add_arguments(self, parser):
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show statistics after loading'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing ontology before loading'
        )

    def handle(self, *args, **options):
        self.stdout.write("Loading performance optimization patterns...")
        
        if options['clear']:
            self.stdout.write("Clearing existing ontology...")
            OntologyRegistry.clear()
        
        # Load patterns
        count = register_performance_optimization_patterns()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Successfully registered {count} performance patterns"
            )
        )
        
        if options['stats']:
            self.stdout.write("\n" + "="*60)
            self.stdout.write("Performance Ontology Statistics")
            self.stdout.write("="*60 + "\n")
            
            summary = get_performance_summary()
            self.stdout.write(f"Database Concepts: {summary['database_concepts']}")
            self.stdout.write(f"Testing Concepts: {summary['testing_concepts']}")
            self.stdout.write(f"Monitoring Tools: {summary['monitoring_tools']}")
            self.stdout.write(f"Total Registered: {summary['total_registered']}")
            
            self.stdout.write("\n" + "-"*60)
            
            # Show all registered domains
            stats = OntologyRegistry.get_statistics()
            self.stdout.write("\nAll Domains:")
            for domain, count in stats['by_domain'].items():
                self.stdout.write(f"  • {domain}: {count} components")
            
            self.stdout.write("\n" + "-"*60)
            
            # Show sample concepts
            self.stdout.write("\nSample Concepts:")
            n1_concept = OntologyRegistry.get("concepts.n_plus_one_query_problem")
            if n1_concept:
                self.stdout.write(f"\n  📌 {n1_concept['qualified_name']}")
                self.stdout.write(f"     {n1_concept['purpose'][:100]}...")
                self.stdout.write(f"     Tags: {', '.join(n1_concept['tags'])}")
            
            select_related = OntologyRegistry.get("concepts.select_related")
            if select_related:
                self.stdout.write(f"\n  📌 {select_related['qualified_name']}")
                self.stdout.write(f"     {select_related['purpose'][:100]}...")
                self.stdout.write(f"     Tags: {', '.join(select_related['tags'])}")
            
            self.stdout.write("\n" + "="*60 + "\n")
