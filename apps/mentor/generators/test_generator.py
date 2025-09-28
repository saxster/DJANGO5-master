"""
Test generator with factory patterns for comprehensive test creation.

This generator provides:
- Test scaffold creation: Class structure, fixtures
- Factory generation: Model factories with Faker
- Assertion generation: Expected vs actual
- Edge case generation: Boundary value analysis
- Mock generation: External service stubs
"""

from enum import Enum

try:
    import factory
except ImportError:
    FACTORY_BOY_AVAILABLE = False

try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False


class TestType(Enum):
    """Types of tests that can be generated."""
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    MODEL_TEST = "model_test"
    VIEW_TEST = "view_test"
    API_TEST = "api_test"
    FORM_TEST = "form_test"
    UTIL_TEST = "util_test"
    PERFORMANCE_TEST = "performance_test"


class TestComplexity(Enum):
    """Complexity levels for generated tests."""
    BASIC = "basic"
    COMPREHENSIVE = "comprehensive"
    EDGE_CASES = "edge_cases"
    FULL_COVERAGE = "full_coverage"


@dataclass
class TestCase:
    """Container for a single test case."""
    name: str
    description: str
    test_type: TestType
    code: str
    fixtures_needed: List[str]
    mocks_needed: List[str]
    assertions: List[str]
    setup_code: str = ""
    teardown_code: str = ""


@dataclass
class TestSuite:
    """Container for a complete test suite."""
    name: str
    file_path: str
    test_cases: List[TestCase]
    factories: List[str]
    imports: List[str]
    fixtures: List[str]
    base_class: str = "TestCase"


@dataclass
class ModelFactory:
    """Container for model factory definition."""
    model_name: str
    factory_name: str
    fields: Dict[str, str]
    traits: Dict[str, Dict[str, str]]
    subfactories: List[str]


class TestGenerator:
    """Intelligent test generator with factory patterns."""

    def __init__(self):
        self.fake = Faker() if FAKER_AVAILABLE else None
        self.generated_tests = []
        self.generated_factories = []

    def generate_model_tests(self, model_class, complexity: TestComplexity = TestComplexity.COMPREHENSIVE) -> TestSuite:
        """Generate comprehensive tests for a Django model."""
        test_cases = []

        # Basic model tests
        test_cases.extend(self._generate_basic_model_tests(model_class))

        # Field validation tests
        if complexity in [TestComplexity.COMPREHENSIVE, TestComplexity.FULL_COVERAGE]:
            test_cases.extend(self._generate_field_validation_tests(model_class))

        # Model method tests
        if complexity in [TestComplexity.COMPREHENSIVE, TestComplexity.FULL_COVERAGE]:
            test_cases.extend(self._generate_model_method_tests(model_class))

        # Edge case tests
        if complexity in [TestComplexity.EDGE_CASES, TestComplexity.FULL_COVERAGE]:
            test_cases.extend(self._generate_model_edge_case_tests(model_class))

        # Generate factory
        factory = self._generate_model_factory(model_class)
        if factory:
            self.generated_factories.append(factory)

        # Create test suite
        suite = TestSuite(
            name=f"Test{model_class.__name__}",
            file_path=f"tests/test_{model_class._meta.app_label}/test_{model_class.__name__.lower()}.py",
            test_cases=test_cases,
            factories=[factory.factory_name] if factory else [],
            imports=self._generate_model_test_imports(model_class),
            fixtures=[],
            base_class="TestCase"
        )

        return suite

    def generate_view_tests(self, view_class, complexity: TestComplexity = TestComplexity.COMPREHENSIVE) -> TestSuite:
        """Generate tests for Django views."""
        test_cases = []

        # Basic view tests
        test_cases.extend(self._generate_basic_view_tests(view_class))

        # Permission tests
        if complexity in [TestComplexity.COMPREHENSIVE, TestComplexity.FULL_COVERAGE]:
            test_cases.extend(self._generate_view_permission_tests(view_class))

        # Form handling tests
        if complexity in [TestComplexity.COMPREHENSIVE, TestComplexity.FULL_COVERAGE]:
            test_cases.extend(self._generate_view_form_tests(view_class))

        # Create test suite
        suite = TestSuite(
            name=f"Test{view_class.__name__}View",
            file_path=f"tests/test_views/test_{view_class.__name__.lower()}.py",
            test_cases=test_cases,
            factories=[],
            imports=self._generate_view_test_imports(view_class),
            fixtures=[],
            base_class="TestCase"
        )

        return suite

    def generate_api_tests(self, endpoint_info: Dict[str, Any]) -> TestSuite:
        """Generate API endpoint tests."""
        test_cases = []

        # Basic API tests
        test_cases.extend(self._generate_basic_api_tests(endpoint_info))

        # Authentication tests
        test_cases.extend(self._generate_api_auth_tests(endpoint_info))

        # Data validation tests
        test_cases.extend(self._generate_api_validation_tests(endpoint_info))

        suite = TestSuite(
            name=f"TestAPI{endpoint_info.get('name', 'Endpoint')}",
            file_path=f"tests/test_api/test_{endpoint_info.get('name', 'endpoint').lower()}.py",
            test_cases=test_cases,
            factories=[],
            imports=self._generate_api_test_imports(),
            fixtures=[],
            base_class="APITestCase"
        )

        return suite

    def generate_utility_tests(self, function_info: Dict[str, Any]) -> TestSuite:
        """Generate tests for utility functions."""
        test_cases = []

        # Basic function tests
        test_cases.extend(self._generate_basic_function_tests(function_info))

        # Edge case tests
        test_cases.extend(self._generate_function_edge_case_tests(function_info))

        suite = TestSuite(
            name=f"Test{function_info.get('name', 'Function')}",
            file_path=f"tests/test_utils/test_{function_info.get('name', 'function').lower()}.py",
            test_cases=test_cases,
            factories=[],
            imports=self._generate_utility_test_imports(),
            fixtures=[],
            base_class="TestCase"
        )

        return suite

    def _generate_basic_model_tests(self, model_class) -> List[TestCase]:
        """Generate basic model tests."""
        tests = []

        # Test model creation
        tests.append(TestCase(
            name="test_model_creation",
            description=f"Test {model_class.__name__} model creation",
            test_type=TestType.MODEL_TEST,
            code=f"""
    def test_model_creation(self):
        \"\"\"Test creating a {model_class.__name__} instance.\"\"\"
        instance = {model_class.__name__}Factory()
        self.assertTrue(isinstance(instance, {model_class.__name__}))
        self.assertTrue(instance.pk)
""",
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["isinstance check", "primary key check"]
        ))

        # Test string representation
        tests.append(TestCase(
            name="test_str_representation",
            description=f"Test {model_class.__name__} string representation",
            test_type=TestType.MODEL_TEST,
            code=f"""
    def test_str_representation(self):
        \"\"\"Test {model_class.__name__} string representation.\"\"\"
        instance = {model_class.__name__}Factory()
        str_repr = str(instance)
        self.assertIsInstance(str_repr, str)
        self.assertGreater(len(str_repr), 0)
""",
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["string type check", "non-empty string"]
        ))

        # Test model save
        tests.append(TestCase(
            name="test_model_save",
            description=f"Test {model_class.__name__} save functionality",
            test_type=TestType.MODEL_TEST,
            code=f"""
    def test_model_save(self):
        \"\"\"Test {model_class.__name__} save method.\"\"\"
        instance = {model_class.__name__}Factory.build()
        instance.save()
        self.assertTrue(instance.pk)

        # Test save idempotency
        old_pk = instance.pk
        instance.save()
        self.assertEqual(instance.pk, old_pk)
""",
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["save creates pk", "save is idempotent"]
        ))

        return tests

    def _generate_field_validation_tests(self, model_class) -> List[TestCase]:
        """Generate field validation tests."""
        tests = []

        for field in model_class._meta.get_fields():
            if hasattr(field, 'name') and not field.name.endswith('_ptr'):
                test = self._generate_field_test(model_class, field)
                if test:
                    tests.append(test)

        return tests

    def _generate_field_test(self, model_class, field) -> Optional[TestCase]:
        """Generate test for a specific field."""
        field_name = field.name
        field_type = field.__class__.__name__

        if field_type == 'CharField':
            return self._generate_char_field_test(model_class, field)
        elif field_type == 'IntegerField':
            return self._generate_integer_field_test(model_class, field)
        elif field_type == 'EmailField':
            return self._generate_email_field_test(model_class, field)
        elif field_type == 'ForeignKey':
            return self._generate_foreign_key_test(model_class, field)

        return None

    def _generate_char_field_test(self, model_class, field) -> TestCase:
        """Generate test for CharField."""
        max_length = getattr(field, 'max_length', None)

        test_code = f"""
    def test_{field.name}_validation(self):
        \"\"\"Test {field.name} field validation.\"\"\"
        instance = {model_class.__name__}Factory.build()

        # Test normal value
        instance.{field.name} = 'Valid text'
        instance.full_clean()  # Should not raise

"""

        if max_length:
            test_code += f"""
        # Test max length
        with self.assertRaises(ValidationError):
            instance.{field.name} = 'x' * {max_length + 1}
            instance.full_clean()
"""

        if not field.null:
            test_code += f"""
        # Test null constraint
        with self.assertRaises(ValidationError):
            instance.{field.name} = None
            instance.full_clean()
"""

        return TestCase(
            name=f"test_{field.name}_validation",
            description=f"Test {field.name} field validation",
            test_type=TestType.MODEL_TEST,
            code=test_code,
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["field validation"]
        )

    def _generate_integer_field_test(self, model_class, field) -> TestCase:
        """Generate test for IntegerField."""
        test_code = f"""
    def test_{field.name}_validation(self):
        \"\"\"Test {field.name} field validation.\"\"\"
        instance = {model_class.__name__}Factory.build()

        # Test valid integer
        instance.{field.name} = 42
        instance.full_clean()  # Should not raise

        # Test boundary values
        instance.{field.name} = 0
        instance.full_clean()

        instance.{field.name} = -1
        instance.full_clean()
"""

        return TestCase(
            name=f"test_{field.name}_validation",
            description=f"Test {field.name} field validation",
            test_type=TestType.MODEL_TEST,
            code=test_code,
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["integer validation", "boundary values"]
        )

    def _generate_email_field_test(self, model_class, field) -> TestCase:
        """Generate test for EmailField."""
        test_code = f"""
    def test_{field.name}_validation(self):
        \"\"\"Test {field.name} field validation.\"\"\"
        instance = {model_class.__name__}Factory.build()

        # Test valid email
        instance.{field.name} = 'test@example.com'
        instance.full_clean()  # Should not raise

        # Test invalid email
        with self.assertRaises(ValidationError):
            instance.{field.name} = 'invalid-email'
            instance.full_clean()
"""

        return TestCase(
            name=f"test_{field.name}_validation",
            description=f"Test {field.name} field validation",
            test_type=TestType.MODEL_TEST,
            code=test_code,
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["email validation"]
        )

    def _generate_foreign_key_test(self, model_class, field) -> TestCase:
        """Generate test for ForeignKey field."""
        related_model = field.related_model

        test_code = f"""
    def test_{field.name}_relationship(self):
        \"\"\"Test {field.name} foreign key relationship.\"\"\"
        related_instance = {related_model.__name__}Factory()
        instance = {model_class.__name__}Factory({field.name}=related_instance)

        # Test relationship
        self.assertEqual(instance.{field.name}, related_instance)
        self.assertIn(instance, related_instance.{field.remote_field.get_accessor_name()}.all())
"""

        return TestCase(
            name=f"test_{field.name}_relationship",
            description=f"Test {field.name} foreign key relationship",
            test_type=TestType.MODEL_TEST,
            code=test_code,
            fixtures_needed=[f"{model_class.__name__}Factory", f"{related_model.__name__}Factory"],
            mocks_needed=[],
            assertions=["foreign key relationship"]
        )

    def _generate_model_method_tests(self, model_class) -> List[TestCase]:
        """Generate tests for custom model methods."""
        tests = []

        # Get custom methods (exclude Django built-ins)
        custom_methods = []
        for method_name in dir(model_class):
            if (not method_name.startswith('_') and
                callable(getattr(model_class, method_name)) and
                method_name not in ['clean', 'save', 'delete', 'refresh_from_db']):
                custom_methods.append(method_name)

        for method_name in custom_methods:
            test = TestCase(
                name=f"test_{method_name}",
                description=f"Test {method_name} method",
                test_type=TestType.MODEL_TEST,
                code=f"""
    def test_{method_name}(self):
        \"\"\"Test {method_name} method.\"\"\"
        instance = {model_class.__name__}Factory()
        result = instance.{method_name}()

        # TODO: Add specific assertions based on method behavior
        self.assertIsNotNone(result)
""",
                fixtures_needed=[f"{model_class.__name__}Factory"],
                mocks_needed=[],
                assertions=["method execution", "result not None"]
            )
            tests.append(test)

        return tests

    def _generate_model_edge_case_tests(self, model_class) -> List[TestCase]:
        """Generate edge case tests for models."""
        tests = []

        # Test with minimal data
        tests.append(TestCase(
            name="test_minimal_instance",
            description="Test model with minimal required data",
            test_type=TestType.MODEL_TEST,
            code=f"""
    def test_minimal_instance(self):
        \"\"\"Test creating {model_class.__name__} with minimal data.\"\"\"
        # Create instance with only required fields
        required_fields = {{}}
        # TODO: Identify required fields and set minimal values

        instance = {model_class.__name__}(**required_fields)
        instance.full_clean()
        instance.save()

        self.assertTrue(instance.pk)
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["minimal instance creation"]
        ))

        # Test unique constraints
        tests.append(TestCase(
            name="test_unique_constraints",
            description="Test model unique constraints",
            test_type=TestType.MODEL_TEST,
            code=f"""
    def test_unique_constraints(self):
        \"\"\"Test {model_class.__name__} unique constraints.\"\"\"
        instance1 = {model_class.__name__}Factory()

        # TODO: Test specific unique constraints
        # This is a template - customize based on actual unique fields
        pass
""",
            fixtures_needed=[f"{model_class.__name__}Factory"],
            mocks_needed=[],
            assertions=["unique constraints"]
        ))

        return tests

    def _generate_basic_view_tests(self, view_class) -> List[TestCase]:
        """Generate basic view tests."""
        tests = []

        # Test GET request
        tests.append(TestCase(
            name="test_get_request",
            description=f"Test GET request to {view_class.__name__}",
            test_type=TestType.VIEW_TEST,
            code=f"""
    def test_get_request(self):
        \"\"\"Test GET request to {view_class.__name__}.\"\"\"
        url = reverse('view_name')  # TODO: Replace with actual URL name
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["status code 200"]
        ))

        # Test POST request (if applicable)
        tests.append(TestCase(
            name="test_post_request",
            description=f"Test POST request to {view_class.__name__}",
            test_type=TestType.VIEW_TEST,
            code=f"""
    def test_post_request(self):
        \"\"\"Test POST request to {view_class.__name__}.\"\"\"
        url = reverse('view_name')  # TODO: Replace with actual URL name
        data = {{
            # TODO: Add form data
        }}
        response = self.client.post(url, data)

        # TODO: Adjust expected status code based on view behavior
        self.assertIn(response.status_code, [200, 201, 302])
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["appropriate status code"]
        ))

        return tests

    def _generate_view_permission_tests(self, view_class) -> List[TestCase]:
        """Generate view permission tests."""
        tests = []

        # Test anonymous user
        tests.append(TestCase(
            name="test_anonymous_access",
            description="Test anonymous user access",
            test_type=TestType.VIEW_TEST,
            code=f"""
    def test_anonymous_access(self):
        \"\"\"Test anonymous user access to {view_class.__name__}.\"\"\"
        self.client.logout()
        url = reverse('view_name')  # TODO: Replace with actual URL name
        response = self.client.get(url)

        # TODO: Adjust expected behavior based on view requirements
        self.assertIn(response.status_code, [200, 302, 403])
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["anonymous access handling"]
        ))

        # Test authenticated user
        tests.append(TestCase(
            name="test_authenticated_access",
            description="Test authenticated user access",
            test_type=TestType.VIEW_TEST,
            code=f"""
    def test_authenticated_access(self):
        \"\"\"Test authenticated user access to {view_class.__name__}.\"\"\"
        user = UserFactory()
        self.client.force_login(user)

        url = reverse('view_name')  # TODO: Replace with actual URL name
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
""",
            fixtures_needed=["UserFactory"],
            mocks_needed=[],
            assertions=["authenticated access"]
        ))

        return tests

    def _generate_view_form_tests(self, view_class) -> List[TestCase]:
        """Generate view form handling tests."""
        tests = []

        # Test valid form submission
        tests.append(TestCase(
            name="test_valid_form_submission",
            description="Test valid form submission",
            test_type=TestType.VIEW_TEST,
            code=f"""
    def test_valid_form_submission(self):
        \"\"\"Test valid form submission to {view_class.__name__}.\"\"\"
        user = UserFactory()
        self.client.force_login(user)

        url = reverse('view_name')  # TODO: Replace with actual URL name
        valid_data = {{
            # TODO: Add valid form data
        }}
        response = self.client.post(url, valid_data)

        # TODO: Adjust assertions based on expected behavior
        self.assertIn(response.status_code, [200, 302])
""",
            fixtures_needed=["UserFactory"],
            mocks_needed=[],
            assertions=["valid form handling"]
        ))

        return tests

    def _generate_basic_api_tests(self, endpoint_info: Dict[str, Any]) -> List[TestCase]:
        """Generate basic API tests."""
        tests = []
        endpoint_name = endpoint_info.get('name', 'endpoint')

        # Test API GET
        tests.append(TestCase(
            name="test_api_get",
            description=f"Test GET request to {endpoint_name} API",
            test_type=TestType.API_TEST,
            code=f"""
    def test_api_get(self):
        \"\"\"Test GET request to {endpoint_name} API.\"\"\"
        url = '/api/{endpoint_name}/'  # TODO: Use actual API URL
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["status 200", "JSON content type"]
        ))

        return tests

    def _generate_api_auth_tests(self, endpoint_info: Dict[str, Any]) -> List[TestCase]:
        """Generate API authentication tests."""
        tests = []
        endpoint_name = endpoint_info.get('name', 'endpoint')

        tests.append(TestCase(
            name="test_api_authentication",
            description=f"Test {endpoint_name} API authentication",
            test_type=TestType.API_TEST,
            code=f"""
    def test_api_authentication(self):
        \"\"\"Test {endpoint_name} API authentication requirements.\"\"\"
        url = '/api/{endpoint_name}/'  # TODO: Use actual API URL

        # Test without authentication
        response = self.client.get(url)
        self.assertIn(response.status_code, [401, 403])

        # Test with authentication
        user = UserFactory()
        self.client.force_authenticate(user=user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
""",
            fixtures_needed=["UserFactory"],
            mocks_needed=[],
            assertions=["authentication required"]
        ))

        return tests

    def _generate_api_validation_tests(self, endpoint_info: Dict[str, Any]) -> List[TestCase]:
        """Generate API validation tests."""
        tests = []
        endpoint_name = endpoint_info.get('name', 'endpoint')

        tests.append(TestCase(
            name="test_api_validation",
            description=f"Test {endpoint_name} API data validation",
            test_type=TestType.API_TEST,
            code=f"""
    def test_api_validation(self):
        \"\"\"Test {endpoint_name} API data validation.\"\"\"
        user = UserFactory()
        self.client.force_authenticate(user=user)

        url = '/api/{endpoint_name}/'  # TODO: Use actual API URL

        # Test with invalid data
        invalid_data = {{
            # TODO: Add invalid data examples
        }}
        response = self.client.post(url, invalid_data, format='json')
        self.assertEqual(response.status_code, 400)

        # Test with valid data
        valid_data = {{
            # TODO: Add valid data examples
        }}
        response = self.client.post(url, valid_data, format='json')
        self.assertIn(response.status_code, [200, 201])
""",
            fixtures_needed=["UserFactory"],
            mocks_needed=[],
            assertions=["validation errors", "valid data accepted"]
        ))

        return tests

    def _generate_basic_function_tests(self, function_info: Dict[str, Any]) -> List[TestCase]:
        """Generate basic function tests."""
        tests = []
        function_name = function_info.get('name', 'function')

        tests.append(TestCase(
            name=f"test_{function_name}_basic",
            description=f"Test basic {function_name} functionality",
            test_type=TestType.UTIL_TEST,
            code=f"""
    def test_{function_name}_basic(self):
        \"\"\"Test basic {function_name} functionality.\"\"\"
        # TODO: Add test parameters based on function signature
        result = {function_name}()

        # TODO: Add appropriate assertions based on expected behavior
        self.assertIsNotNone(result)
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["function execution", "result not None"]
        ))

        return tests

    def _generate_function_edge_case_tests(self, function_info: Dict[str, Any]) -> List[TestCase]:
        """Generate edge case tests for functions."""
        tests = []
        function_name = function_info.get('name', 'function')

        # Test with None input
        tests.append(TestCase(
            name=f"test_{function_name}_with_none",
            description=f"Test {function_name} with None input",
            test_type=TestType.UTIL_TEST,
            code=f"""
    def test_{function_name}_with_none(self):
        \"\"\"Test {function_name} with None input.\"\"\"
        # TODO: Adjust based on whether function should handle None
        with self.assertRaises(TypeError):
            {function_name}(None)
""",
            fixtures_needed=[],
            mocks_needed=[],
            assertions=["None handling"]
        ))

        return tests

    def _generate_model_factory(self, model_class) -> Optional[ModelFactory]:
        """Generate a factory for the model."""
        if not FACTORY_BOY_AVAILABLE:
            return None

        fields = {}
        traits = {}
        subfactories = []

        # Generate field definitions
        for field in model_class._meta.get_fields():
            if hasattr(field, 'name') and not field.name.endswith('_ptr'):
                field_def = self._generate_factory_field(field)
                if field_def:
                    fields[field.name] = field_def

        factory_name = f"{model_class.__name__}Factory"

        return ModelFactory(
            model_name=model_class.__name__,
            factory_name=factory_name,
            fields=fields,
            traits=traits,
            subfactories=subfactories
        )

    def _generate_factory_field(self, field) -> Optional[str]:
        """Generate factory field definition."""
        field_type = field.__class__.__name__

        if field_type == 'CharField':
            max_length = getattr(field, 'max_length', 50)
            if field.name in ['name', 'title']:
                return f"factory.Faker('name')"
            elif field.name == 'email':
                return f"factory.Faker('email')"
            else:
                return f"factory.Faker('text', max_nb_chars={max_length})"

        elif field_type == 'IntegerField':
            return "factory.Faker('random_int', min=1, max=1000)"

        elif field_type == 'BooleanField':
            return "factory.Faker('boolean')"

        elif field_type == 'DateTimeField':
            return "factory.Faker('date_time')"

        elif field_type == 'DateField':
            return "factory.Faker('date')"

        elif field_type == 'EmailField':
            return "factory.Faker('email')"

        elif field_type == 'URLField':
            return "factory.Faker('url')"

        elif field_type == 'ForeignKey':
            related_model = field.related_model
            return f"factory.SubFactory({related_model.__name__}Factory)"

        return None

    def _generate_model_test_imports(self, model_class) -> List[str]:
        """Generate imports for model tests."""
        imports = [
            "from django.test import TestCase",
            "from django.core.exceptions import ValidationError",
            f"from {model_class._meta.app_label}.models import {model_class.__name__}",
        ]

        if FACTORY_BOY_AVAILABLE:
            imports.append("import factory")
            imports.append(f"from tests.factories import {model_class.__name__}Factory")

        return imports

    def _generate_view_test_imports(self, view_class) -> List[str]:
        """Generate imports for view tests."""
        return [
            "from django.test import TestCase, Client",
            "from django.urls import reverse",
            "from django.contrib.auth import get_user_model",
            "from tests.factories import UserFactory",
        ]

    def _generate_api_test_imports(self) -> List[str]:
        """Generate imports for API tests."""
        return [
            "from rest_framework.test import APITestCase",
            "from rest_framework import status",
            "from django.urls import reverse",
            "from tests.factories import UserFactory",
        ]

    def _generate_utility_test_imports(self) -> List[str]:
        """Generate imports for utility tests."""
        return [
            "from django.test import TestCase",
            "import unittest.mock as mock",
        ]

    def generate_test_file(self, test_suite: TestSuite) -> str:
        """Generate complete test file code."""
        imports_section = '\n'.join(test_suite.imports)

        # Generate test class
        test_methods = []
        for test_case in test_suite.test_cases:
            test_methods.append(test_case.code.strip())

        test_class_code = f"""

class {test_suite.name}({test_suite.base_class}):
    \"\"\"Test cases for {test_suite.name.replace('Test', '')}.\"\"\"

    def setUp(self):
        \"\"\"Set up test data.\"\"\"
        self.client = Client()
        # TODO: Add common setup code

    def tearDown(self):
        \"\"\"Clean up after tests.\"\"\"
        # TODO: Add cleanup code
        pass

{''.join(test_methods)}
"""

        # Combine all parts
        test_file_code = f'''"""
Tests for {test_suite.name.replace('Test', '')}.
Generated by Django AI Mentor System.
"""

{imports_section}
{test_class_code}
'''

        return test_file_code

    def generate_factory_file(self, factories: List[ModelFactory]) -> str:
        """Generate factory file code."""
        imports = [
            "import factory",
            "from factory import django",
            "from faker import Faker",
        ]

        if FAKER_AVAILABLE:
            imports.append("fake = Faker()")

        # Add model imports
        model_imports = set()
        for factory in factories:
            # Extract app from model (simplified)
            model_imports.add(f"# from app.models import {factory.model_name}")

        factory_classes = []
        for factory in factories:
            fields_code = []
            for field_name, field_def in factory.fields.items():
                fields_code.append(f"    {field_name} = {field_def}")

            factory_code = f"""
class {factory.factory_name}(django.DjangoModelFactory):
    \"\"\"Factory for {factory.model_name} model.\"\"\"

    class Meta:
        model = {factory.model_name}

{chr(10).join(fields_code) if fields_code else '    pass'}
"""
            factory_classes.append(factory_code)

        factory_file_code = f'''"""
Model factories for testing.
Generated by Django AI Mentor System.
"""

{chr(10).join(imports)}

{chr(10).join(model_imports)}

{chr(10).join(factory_classes)}
'''

        return factory_file_code