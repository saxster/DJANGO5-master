"""
Tests for mentor_plan management command.
"""

from django.core.management import call_command
from io import StringIO

from apps.mentor.management.commands.mentor_plan import PlanGenerator, ChangePlan, ChangeStep


class TestMentorPlanCommand(TestCase):
    """Test mentor_plan management command."""

    def setUp(self):
        self.out = StringIO()
        self.err = StringIO()

    def test_command_requires_request(self):
        """Test that command requires --request argument."""
        with self.assertRaises(SystemExit):
            call_command('mentor_plan', stdout=self.out, stderr=self.err)

    def test_command_basic_execution(self):
        """Test basic command execution."""
        call_command(
            'mentor_plan',
            '--request', 'Add user authentication',
            '--format', 'summary',
            stdout=self.out,
            stderr=self.err
        )

        output = self.out.getvalue()
        self.assertIn('Generated plan', output)
        self.assertIn('steps', output)

    def test_command_with_scope(self):
        """Test command execution with scope limitation."""
        call_command(
            'mentor_plan',
            '--request', 'Add validation',
            '--scope', 'apps/users/', 'apps/auth/',
            '--format', 'json',
            stdout=self.out,
            stderr=self.err
        )

        output = self.out.getvalue()
        self.assertIn('Generated plan', output)


class TestPlanGenerator(TestCase):
    """Test PlanGenerator class."""

    def setUp(self):
        self.generator = PlanGenerator()

    def test_analyze_request_intent_feature(self):
        """Test intent analysis for feature requests."""
        request = "Add user role management system"
        intent = self.generator._analyze_request_intent(request)

        self.assertEqual(intent['type'], 'feature')
        self.assertIn('complexity', intent)
        self.assertIsInstance(intent['entities'], list)

    def test_analyze_request_intent_bugfix(self):
        """Test intent analysis for bug fixes."""
        request = "Fix the login error in authentication"
        intent = self.generator._analyze_request_intent(request)

        self.assertEqual(intent['type'], 'bugfix')

    def test_analyze_request_intent_security(self):
        """Test intent analysis for security fixes."""
        request = "Fix SQL injection vulnerability in queries"
        intent = self.generator._analyze_request_intent(request)

        self.assertEqual(intent['type'], 'security')

    def test_extract_entities(self):
        """Test entity extraction from requests."""
        request = "Update User model and Profile view to add validation"
        entities = self.generator._extract_entities(request)

        self.assertIn('model:User', entities)
        self.assertIn('view:Profile', entities)

    def test_estimate_complexity_simple(self):
        """Test complexity estimation for simple changes."""
        complexity = self.generator._estimate_complexity("Fix typo in comments", [])
        self.assertIn(complexity, ['simple', 'medium'])

    def test_estimate_complexity_complex(self):
        """Test complexity estimation for complex changes."""
        entities = ['model:User', 'view:Profile', 'api:Auth', 'model:Permission']
        complexity = self.generator._estimate_complexity(
            "Refactor authentication system", entities
        )
        self.assertEqual(complexity, 'complex')

    def test_identify_affected_areas(self):
        """Test identification of affected code areas."""
        request = "Update activity models for better performance"
        areas = self.generator._identify_affected_areas(request, None)

        self.assertIn('apps/activity/', areas)

    def test_plan_feature_addition(self):
        """Test plan generation for feature addition."""
        plan = ChangePlan("Add user notifications")
        intent = {'type': 'feature', 'entities': ['model:Notification'], 'complexity': 'medium'}
        areas = ['apps/users/']

        self.generator._plan_feature_addition(plan, intent, areas)

        self.assertGreater(len(plan.steps), 0)
        self.assertTrue(any(step.step_type == 'design' for step in plan.steps))
        self.assertTrue(plan.migration_needed)

    def test_plan_bug_fix(self):
        """Test plan generation for bug fixes."""
        plan = ChangePlan("Fix login redirect issue")
        intent = {'type': 'bugfix', 'entities': [], 'complexity': 'simple'}
        areas = ['apps/auth/']

        self.generator._plan_bug_fix(plan, intent, areas)

        self.assertGreater(len(plan.steps), 0)
        self.assertTrue(any(step.step_type == 'investigate' for step in plan.steps))
        self.assertTrue(any(step.step_type == 'create' for step in plan.steps))  # regression test

    def test_plan_security_fix(self):
        """Test plan generation for security fixes."""
        plan = ChangePlan("Fix XSS vulnerability in forms")
        intent = {'type': 'security', 'entities': [], 'complexity': 'medium'}
        areas = ['apps/forms/']

        self.generator._plan_security_fix(plan, intent, areas)

        self.assertGreater(len(plan.steps), 0)
        self.assertTrue(any(step.step_type == 'audit' for step in plan.steps))
        self.assertTrue(any(step.risk_level == 'critical' for step in plan.steps))
        self.assertIn('Security review by security team', plan.prerequisites)

    def test_add_testing_steps(self):
        """Test addition of testing steps to plan."""
        plan = ChangePlan("Test request")
        plan.impacted_files = {'apps/users/models.py', 'apps/users/views.py'}

        self.generator._add_testing_steps(plan)

        test_steps = [step for step in plan.steps if step.step_type == 'test']
        self.assertGreater(len(test_steps), 0)
        self.assertGreater(len(plan.required_tests), 0)

    def test_add_safety_checks(self):
        """Test addition of safety checks to plan."""
        plan = ChangePlan("Test request")
        plan.migration_needed = True

        # Add a modify step
        plan.add_step(ChangeStep(
            step_id="modify_test",
            description="Test modification",
            step_type="modify",
            target_files=["test.py"],
            risk_level="medium"
        ))

        self.generator._add_safety_checks(plan)

        safety_steps = [step for step in plan.steps if step.step_type == 'validate']
        self.assertGreater(len(safety_steps), 0)

    def test_generate_rollback_plan(self):
        """Test rollback plan generation."""
        plan = ChangePlan("Test request")
        plan.migration_needed = True

        # Add some steps
        plan.add_step(ChangeStep(
            step_id="create_test",
            description="Create test file",
            step_type="create",
            target_files=["new_file.py"],
            risk_level="low"
        ))
        plan.add_step(ChangeStep(
            step_id="modify_test",
            description="Modify existing file",
            step_type="modify",
            target_files=["existing_file.py"],
            risk_level="medium"
        ))

        self.generator._generate_rollback_plan(plan)

        self.assertGreater(len(plan.rollback_plan), 0)
        self.assertIn('database rollback migration', ' '.join(plan.rollback_plan).lower())

    def test_generate_complete_plan(self):
        """Test complete plan generation."""
        plan = self.generator.generate_plan(
            "Add user role management with permissions",
            scope=['apps/users/']
        )

        # Verify plan structure
        self.assertIsInstance(plan, ChangePlan)
        self.assertEqual(plan.request, "Add user role management with permissions")
        self.assertGreater(len(plan.steps), 0)
        self.assertIn(plan.overall_risk, ['low', 'medium', 'high', 'critical'])
        self.assertGreater(plan.estimated_total_time, 0)

        # Verify steps have required fields
        for step in plan.steps:
            self.assertIsInstance(step, ChangeStep)
            self.assertIsNotNone(step.step_id)
            self.assertIsNotNone(step.description)
            self.assertIsNotNone(step.step_type)
            self.assertIsInstance(step.target_files, list)
            self.assertIn(step.risk_level, ['low', 'medium', 'high', 'critical'])


class TestChangePlan(TestCase):
    """Test ChangePlan class."""

    def test_plan_initialization(self):
        """Test plan initialization."""
        plan = ChangePlan("Test request")

        self.assertEqual(plan.request, "Test request")
        self.assertIsNotNone(plan.plan_id)
        self.assertIsInstance(plan.steps, list)
        self.assertIsInstance(plan.impacted_files, set)
        self.assertEqual(plan.overall_risk, 'low')
        self.assertEqual(plan.estimated_total_time, 0)

    def test_add_step(self):
        """Test adding steps to plan."""
        plan = ChangePlan("Test request")

        step = ChangeStep(
            step_id="test_step",
            description="Test step",
            step_type="modify",
            target_files=["test.py"],
            risk_level="medium",
            estimated_time=30
        )

        plan.add_step(step)

        self.assertEqual(len(plan.steps), 1)
        self.assertIn("test.py", plan.impacted_files)
        self.assertEqual(plan.overall_risk, 'medium')  # Should be updated
        self.assertEqual(plan.estimated_total_time, 30)

    def test_risk_level_escalation(self):
        """Test that overall risk escalates with higher-risk steps."""
        plan = ChangePlan("Test request")

        # Add low risk step
        plan.add_step(ChangeStep(
            step_id="low_step",
            description="Low risk step",
            step_type="modify",
            target_files=["test1.py"],
            risk_level="low"
        ))
        self.assertEqual(plan.overall_risk, 'low')

        # Add critical risk step
        plan.add_step(ChangeStep(
            step_id="critical_step",
            description="Critical risk step",
            step_type="modify",
            target_files=["test2.py"],
            risk_level="critical"
        ))
        self.assertEqual(plan.overall_risk, 'critical')

    def test_to_dict(self):
        """Test plan serialization to dictionary."""
        plan = ChangePlan("Test request")
        plan.add_step(ChangeStep(
            step_id="test_step",
            description="Test step",
            step_type="modify",
            target_files=["test.py"],
            risk_level="low"
        ))

        plan_dict = plan.to_dict()

        self.assertEqual(plan_dict['request'], "Test request")
        self.assertEqual(len(plan_dict['steps']), 1)
        self.assertEqual(plan_dict['steps'][0]['step_id'], "test_step")
        self.assertIn('created_at', plan_dict)


class TestChangeStep(TestCase):
    """Test ChangeStep class."""

    def test_step_initialization(self):
        """Test step initialization."""
        step = ChangeStep(
            step_id="test_step",
            description="Test step",
            step_type="modify",
            target_files=["test.py"],
            dependencies=["other_step"],
            risk_level="medium",
            estimated_time=45
        )

        self.assertEqual(step.step_id, "test_step")
        self.assertEqual(step.description, "Test step")
        self.assertEqual(step.step_type, "modify")
        self.assertEqual(step.target_files, ["test.py"])
        self.assertEqual(step.dependencies, ["other_step"])
        self.assertEqual(step.risk_level, "medium")
        self.assertEqual(step.estimated_time, 45)

    def test_step_defaults(self):
        """Test step default values."""
        step = ChangeStep(
            step_id="test_step",
            description="Test step",
            step_type="modify",
            target_files=["test.py"]
        )

        self.assertEqual(step.dependencies, [])
        self.assertEqual(step.risk_level, 'low')
        self.assertEqual(step.estimated_time, 15)

    def test_to_dict(self):
        """Test step serialization to dictionary."""
        step = ChangeStep(
            step_id="test_step",
            description="Test step",
            step_type="modify",
            target_files=["test.py"],
            risk_level="medium"
        )

        step_dict = step.to_dict()

        self.assertEqual(step_dict['step_id'], "test_step")
        self.assertEqual(step_dict['description'], "Test step")
        self.assertEqual(step_dict['step_type'], "modify")
        self.assertEqual(step_dict['target_files'], ["test.py"])
        self.assertEqual(step_dict['risk_level'], "medium")