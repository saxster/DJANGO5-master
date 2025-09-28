"""
mentor_spec management command for the AI Mentor system.

This command manages MentorSpec files - structured YAML/JSON documents
that define change requests with full requirements, constraints, and
acceptance criteria.
"""

import json
import yaml
from pathlib import Path

    MentorSpec, MentorSpecValidator, MentorSpecLoader, MentorSpecRepository,
    create_spec_template, IntentType, PriorityLevel, RiskTolerance
)


class Command(BaseCommand):
    help = 'Manage MentorSpec files for structured change requests'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')

        # Create spec
        create_parser = subparsers.add_parser('create', help='Create a new spec from template')
        create_parser.add_argument('spec_id', help='ID for the new spec')
        create_parser.add_argument('--title', help='Title for the spec')
        create_parser.add_argument('--intent', choices=[e.value for e in IntentType], default='feature')
        create_parser.add_argument('--priority', choices=[e.value for e in PriorityLevel], default='medium')
        create_parser.add_argument('--format', choices=['yaml', 'json'], default='yaml')

        # List specs
        list_parser = subparsers.add_parser('list', help='List all specs')
        list_parser.add_argument('--status', help='Filter by status')
        list_parser.add_argument('--intent', choices=[e.value for e in IntentType], help='Filter by intent')
        list_parser.add_argument('--format', choices=['table', 'json'], default='table')

        # Show spec
        show_parser = subparsers.add_parser('show', help='Show spec details')
        show_parser.add_argument('spec_id', help='ID of the spec to show')
        show_parser.add_argument('--format', choices=['yaml', 'json', 'summary'], default='summary')

        # Validate spec
        validate_parser = subparsers.add_parser('validate', help='Validate specs')
        validate_parser.add_argument('spec_id', nargs='?', help='Specific spec to validate (optional)')
        validate_parser.add_argument('--all', action='store_true', help='Validate all specs')

        # Update spec
        update_parser = subparsers.add_parser('update', help='Update spec status or fields')
        update_parser.add_argument('spec_id', help='ID of the spec to update')
        update_parser.add_argument('--status', help='New status')
        update_parser.add_argument('--priority', choices=[e.value for e in PriorityLevel])
        update_parser.add_argument('--owner', help='New owner')

        # Delete spec
        delete_parser = subparsers.add_parser('delete', help='Delete a spec')
        delete_parser.add_argument('spec_id', help='ID of the spec to delete')
        delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')

        # Import spec
        import_parser = subparsers.add_parser('import', help='Import spec from file')
        import_parser.add_argument('file_path', help='Path to spec file')
        import_parser.add_argument('--validate', action='store_true', help='Validate after import')

        # Export spec
        export_parser = subparsers.add_parser('export', help='Export spec to file')
        export_parser.add_argument('spec_id', help='ID of the spec to export')
        export_parser.add_argument('output_path', help='Output file path')
        export_parser.add_argument('--format', choices=['yaml', 'json'], default='yaml')

        # Lint all specs
        subparsers.add_parser('lint', help='Lint all specs for style and consistency')

    def handle(self, *args, **options):
        action = options.get('action')

        if not action:
            self.stdout.write(self.style.ERROR("No action specified. Use -h for help."))
            return

        try:
            method = getattr(self, f'handle_{action}')
            method(options)
        except AttributeError:
            self.stdout.write(self.style.ERROR(f"Unknown action: {action}"))
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise CommandError(f"Command failed: {e}")

    def handle_create(self, options):
        """Create a new spec from template."""
        spec_id = options['spec_id']
        repository = MentorSpecRepository()

        # Check if spec already exists
        if repository.load_spec(spec_id):
            self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' already exists"))
            return

        # Create spec from template or parameters
        if options.get('title'):
            # Create spec from command line parameters
            spec = MentorSpec(
                id=spec_id,
                title=options['title'],
                intent=IntentType(options['intent']),
                description=f"Description for {options['title']}",
                priority=PriorityLevel(options['priority'])
            )
            file_path = repository.save_spec(spec, format=options['format'])
        else:
            # Create from template
            template_content = create_spec_template(spec_id)
            spec_data = yaml.safe_load(template_content)
            spec = MentorSpecLoader.load_from_dict(spec_data)
            file_path = repository.save_spec(spec, format=options['format'])

        self.stdout.write(
            self.style.SUCCESS(f"✅ Created spec '{spec_id}' at {file_path}")
        )
        self.stdout.write(f"Edit the file to complete your specification.")

    def handle_list(self, options):
        """List all specs."""
        repository = MentorSpecRepository()
        spec_ids = repository.list_specs()

        if not spec_ids:
            self.stdout.write(self.style.WARNING("No specs found"))
            return

        # Load and filter specs
        specs = []
        for spec_id in spec_ids:
            spec = repository.load_spec(spec_id)
            if spec:
                # Apply filters
                if options.get('status') and spec.status != options['status']:
                    continue
                if options.get('intent') and spec.intent.value != options['intent']:
                    continue
                specs.append(spec)

        if not specs:
            self.stdout.write(self.style.WARNING("No specs match the filter criteria"))
            return

        # Output format
        if options['format'] == 'json':
            spec_data = [
                {
                    'id': spec.id,
                    'title': spec.title,
                    'intent': spec.intent.value,
                    'status': spec.status,
                    'priority': spec.priority.value,
                    'owner': spec.owner,
                    'created_at': spec.created_at
                }
                for spec in specs
            ]
            self.stdout.write(json.dumps(spec_data, indent=2))
        else:
            # Table format
            self.stdout.write("📋 MentorSpecs")
            self.stdout.write("=" * 80)
            self.stdout.write(f"{'ID':<25} {'Title':<30} {'Intent':<12} {'Status':<10} {'Priority':<8}")
            self.stdout.write("-" * 80)

            for spec in specs:
                title = spec.title[:28] + '..' if len(spec.title) > 30 else spec.title
                self.stdout.write(
                    f"{spec.id:<25} {title:<30} {spec.intent.value:<12} "
                    f"{spec.status:<10} {spec.priority.value:<8}"
                )

    def handle_show(self, options):
        """Show spec details."""
        spec_id = options['spec_id']
        repository = MentorSpecRepository()

        spec = repository.load_spec(spec_id)
        if not spec:
            self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' not found"))
            return

        if options['format'] == 'summary':
            self._show_spec_summary(spec)
        elif options['format'] == 'json':
            spec_dict = spec.__dict__.copy()
            # Convert enums to strings for JSON serialization
            spec_dict['intent'] = spec.intent.value
            spec_dict['priority'] = spec.priority.value
            spec_dict['risk_tolerance'] = spec.risk_tolerance.value
            self.stdout.write(json.dumps(spec_dict, indent=2, default=str))
        else:  # yaml
            spec_dict = spec.__dict__.copy()
            spec_dict['intent'] = spec.intent.value
            spec_dict['priority'] = spec.priority.value
            spec_dict['risk_tolerance'] = spec.risk_tolerance.value
            self.stdout.write(yaml.dump(spec_dict, default_flow_style=False, sort_keys=False))

    def handle_validate(self, options):
        """Validate specs."""
        repository = MentorSpecRepository()

        if options.get('all') or not options.get('spec_id'):
            # Validate all specs
            results = repository.validate_all_specs()
            total_specs = len(results)
            valid_specs = sum(1 for errors in results.values() if not errors)

            self.stdout.write(f"🔍 Validated {total_specs} specs")
            self.stdout.write(f"✅ {valid_specs} valid, ❌ {total_specs - valid_specs} with errors")
            self.stdout.write("")

            for spec_id, errors in results.items():
                if errors:
                    self.stdout.write(self.style.ERROR(f"❌ {spec_id}:"))
                    for error in errors:
                        self.stdout.write(f"   • {error}")
                    self.stdout.write("")
                else:
                    self.stdout.write(self.style.SUCCESS(f"✅ {spec_id}"))

        else:
            # Validate specific spec
            spec_id = options['spec_id']
            spec = repository.load_spec(spec_id)

            if not spec:
                self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' not found"))
                return

            errors = MentorSpecValidator.validate_spec(spec)

            if errors:
                self.stdout.write(self.style.ERROR(f"❌ Spec '{spec_id}' has {len(errors)} errors:"))
                for error in errors:
                    self.stdout.write(f"   • {error}")
            else:
                self.stdout.write(self.style.SUCCESS(f"✅ Spec '{spec_id}' is valid"))

    def handle_update(self, options):
        """Update spec fields."""
        spec_id = options['spec_id']
        repository = MentorSpecRepository()

        spec = repository.load_spec(spec_id)
        if not spec:
            self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' not found"))
            return

        # Apply updates
        updated_fields = []

        if options.get('status'):
            spec.status = options['status']
            updated_fields.append(f"status -> {options['status']}")

        if options.get('priority'):
            spec.priority = PriorityLevel(options['priority'])
            updated_fields.append(f"priority -> {options['priority']}")

        if options.get('owner'):
            spec.owner = options['owner']
            updated_fields.append(f"owner -> {options['owner']}")

        if not updated_fields:
            self.stdout.write(self.style.WARNING("No updates specified"))
            return

        # Save updated spec
        repository.save_spec(spec)

        self.stdout.write(
            self.style.SUCCESS(f"✅ Updated spec '{spec_id}':")
        )
        for field in updated_fields:
            self.stdout.write(f"   • {field}")

    def handle_delete(self, options):
        """Delete a spec."""
        spec_id = options['spec_id']
        repository = MentorSpecRepository()

        if not repository.load_spec(spec_id):
            self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' not found"))
            return

        if not options.get('force'):
            confirm = input(f"Delete spec '{spec_id}'? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write("Cancelled")
                return

        if repository.delete_spec(spec_id):
            self.stdout.write(self.style.SUCCESS(f"✅ Deleted spec '{spec_id}'"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to delete spec '{spec_id}'"))

    def handle_import(self, options):
        """Import spec from file."""
        file_path = Path(options['file_path'])
        repository = MentorSpecRepository()

        if not file_path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        try:
            spec = MentorSpecLoader.load_from_file(file_path)

            if options.get('validate'):
                errors = MentorSpecValidator.validate_spec(spec)
                if errors:
                    self.stdout.write(self.style.ERROR("Validation errors:"))
                    for error in errors:
                        self.stdout.write(f"   • {error}")
                    return

            repository.save_spec(spec)
            self.stdout.write(
                self.style.SUCCESS(f"✅ Imported spec '{spec.id}' from {file_path}")
            )

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            self.stdout.write(self.style.ERROR(f"Import failed: {e}"))

    def handle_export(self, options):
        """Export spec to file."""
        spec_id = options['spec_id']
        output_path = Path(options['output_path'])
        repository = MentorSpecRepository()

        spec = repository.load_spec(spec_id)
        if not spec:
            self.stdout.write(self.style.ERROR(f"Spec '{spec_id}' not found"))
            return

        # Save to specified location
        if options['format'] == 'json':
            spec_dict = spec.__dict__.copy()
            spec_dict['intent'] = spec.intent.value
            spec_dict['priority'] = spec.priority.value
            spec_dict['risk_tolerance'] = spec.risk_tolerance.value

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(spec_dict, f, indent=2, default=str, ensure_ascii=False)
        else:  # yaml
            spec_dict = spec.__dict__.copy()
            spec_dict['intent'] = spec.intent.value
            spec_dict['priority'] = spec.priority.value
            spec_dict['risk_tolerance'] = spec.risk_tolerance.value

            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(spec_dict, f, default_flow_style=False, sort_keys=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"✅ Exported spec '{spec_id}' to {output_path}")
        )

    def handle_lint(self, options):
        """Lint all specs for style and consistency."""
        repository = MentorSpecRepository()
        spec_ids = repository.list_specs()

        if not spec_ids:
            self.stdout.write(self.style.WARNING("No specs found to lint"))
            return

        issues = []

        for spec_id in spec_ids:
            spec = repository.load_spec(spec_id)
            if not spec:
                continue

            # Check various style issues
            spec_issues = self._lint_spec(spec)
            if spec_issues:
                issues.extend([(spec_id, issue) for issue in spec_issues])

        if issues:
            self.stdout.write(f"🔍 Found {len(issues)} style issues:")
            self.stdout.write("")

            for spec_id, issue in issues:
                self.stdout.write(f"• {spec_id}: {issue}")
        else:
            self.stdout.write(self.style.SUCCESS("✅ All specs pass linting checks"))

    def _show_spec_summary(self, spec: MentorSpec):
        """Show a formatted summary of a spec."""
        self.stdout.write("")
        self.stdout.write(f"📋 {spec.title}")
        self.stdout.write("=" * len(spec.title))
        self.stdout.write(f"ID: {spec.id}")
        self.stdout.write(f"Intent: {spec.intent.value}")
        self.stdout.write(f"Status: {spec.status}")
        self.stdout.write(f"Priority: {spec.priority.value}")
        self.stdout.write(f"Risk Tolerance: {spec.risk_tolerance.value}")
        self.stdout.write(f"Owner: {spec.owner or 'Not assigned'}")
        self.stdout.write("")

        self.stdout.write("Description:")
        self.stdout.write(f"  {spec.description}")
        self.stdout.write("")

        if spec.impacted_areas:
            self.stdout.write("Impacted Areas:")
            for area in spec.impacted_areas:
                self.stdout.write(f"  • {area}")
            self.stdout.write("")

        if spec.acceptance_criteria:
            self.stdout.write("Acceptance Criteria:")
            for i, criteria in enumerate(spec.acceptance_criteria, 1):
                self.stdout.write(f"  {i}. {criteria}")
            self.stdout.write("")

        if spec.security_constraints:
            self.stdout.write("Security Constraints:")
            for constraint in spec.security_constraints:
                self.stdout.write(f"  • {constraint.type}: {constraint.description}")
            self.stdout.write("")

        if spec.references:
            self.stdout.write("References:")
            for ref in spec.references:
                self.stdout.write(f"  • {ref}")

    def _lint_spec(self, spec: MentorSpec) -> List[str]:
        """Check a spec for style and consistency issues."""
        issues = []

        # Check title formatting
        if not spec.title[0].isupper():
            issues.append("Title should start with capital letter")

        if len(spec.title) > 80:
            issues.append("Title is too long (>80 characters)")

        # Check description
        if len(spec.description) < 50:
            issues.append("Description is too short (<50 characters)")

        # Check acceptance criteria
        if len(spec.acceptance_criteria) < 2:
            issues.append("Should have at least 2 acceptance criteria")

        # Check security specs have security constraints
        if spec.intent == IntentType.SECURITY and not spec.security_constraints:
            issues.append("Security specs should have security constraints")

        # Check performance specs have performance constraints
        if spec.intent == IntentType.PERFORMANCE and not spec.performance_constraints:
            issues.append("Performance specs should have performance constraints")

        return issues