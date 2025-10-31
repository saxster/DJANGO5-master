"""
Test Synthesizer Service
AI-powered generation of test code from anomaly patterns and coverage gaps
"""

import logging
import re
from typing import Dict, List, Optional, Any

from apps.ai_testing.models import TestCoverageGap
logger = logging.getLogger(__name__)


class TestSynthesizer:
    """
    Generates test code automatically from anomaly patterns and coverage gaps
    """

    def __init__(self):
        self.kotlin_templates = KotlinTestTemplates()
        self.swift_templates = SwiftTestTemplates()

    def generate_test_for_gap(self, coverage_gap: TestCoverageGap, framework: str = None) -> Optional[str]:
        """
        Generate test code for a specific coverage gap

        Args:
            coverage_gap: TestCoverageGap instance
            framework: Target test framework (paparazzi, macrobenchmark, etc.)

        Returns:
            Generated test code as string
        """
        if not framework:
            framework = coverage_gap.recommended_framework or self._recommend_framework(coverage_gap)

        logger.info(f"Generating {framework} test for gap: {coverage_gap.title}")

        try:
            if framework in ['paparazzi', 'espresso', 'junit', 'robolectric', 'macrobenchmark']:
                return self._generate_kotlin_test(coverage_gap, framework)
            elif framework in ['ui_testing', 'xctest']:
                return self._generate_swift_test(coverage_gap, framework)
            else:
                logger.warning(f"Unsupported framework: {framework}")
                return None

        except (ValueError, TypeError) as e:
            logger.error(f"Error generating test for gap {coverage_gap.id}: {str(e)}")
            return None

    def _recommend_framework(self, coverage_gap: TestCoverageGap) -> str:
        """Recommend appropriate test framework based on coverage gap type"""
        recommendations = {
            'visual': 'paparazzi',
            'performance': 'macrobenchmark',
            'functional': 'espresso',
            'integration': 'espresso',
            'edge_case': 'junit',
            'error_handling': 'junit',
            'user_flow': 'espresso',
            'api_contract': 'junit',
            'device_specific': 'robolectric',
            'network_condition': 'robolectric'
        }
        return recommendations.get(coverage_gap.coverage_type, 'junit')

    def _generate_kotlin_test(self, coverage_gap: TestCoverageGap, framework: str) -> str:
        """Generate Kotlin test code for Android"""
        if framework == 'paparazzi':
            return self.kotlin_templates.generate_paparazzi_test(coverage_gap)
        elif framework == 'macrobenchmark':
            return self.kotlin_templates.generate_macrobenchmark_test(coverage_gap)
        elif framework == 'espresso':
            return self.kotlin_templates.generate_espresso_test(coverage_gap)
        elif framework == 'junit':
            return self.kotlin_templates.generate_junit_test(coverage_gap)
        elif framework == 'robolectric':
            return self.kotlin_templates.generate_robolectric_test(coverage_gap)
        else:
            return self.kotlin_templates.generate_generic_test(coverage_gap)

    def _generate_swift_test(self, coverage_gap: TestCoverageGap, framework: str) -> str:
        """Generate Swift test code for iOS"""
        if framework == 'ui_testing':
            return self.swift_templates.generate_ui_test(coverage_gap)
        elif framework == 'xctest':
            return self.swift_templates.generate_xctest(coverage_gap)
        else:
            return self.swift_templates.generate_generic_test(coverage_gap)

    def suggest_tests_for_gap(self, coverage_gap: TestCoverageGap) -> List[Dict[str, Any]]:
        """Generate multiple test suggestions for a coverage gap"""
        suggestions = []

        # Get anomaly context
        anomaly = coverage_gap.anomaly_signature

        # Generate different types of tests based on coverage type
        test_types = self._get_recommended_test_types(coverage_gap)

        for test_type, framework in test_types:
            test_code = self.generate_test_for_gap(coverage_gap, framework)
            if test_code:
                suggestions.append({
                    'test_type': test_type,
                    'framework': framework,
                    'confidence': self._calculate_suggestion_confidence(coverage_gap, test_type),
                    'estimated_implementation_time': self._estimate_implementation_time(test_type),
                    'test_code': test_code,
                    'file_path': self._suggest_file_path(coverage_gap, framework),
                    'description': self._generate_test_description(coverage_gap, test_type)
                })

        return sorted(suggestions, key=lambda x: x['confidence'], reverse=True)

    def _get_recommended_test_types(self, coverage_gap: TestCoverageGap) -> List[tuple]:
        """Get recommended test types and frameworks for a coverage gap"""
        coverage_type = coverage_gap.coverage_type

        recommendations = {
            'visual': [
                ('visual_regression', 'paparazzi'),
                ('ui_functional', 'espresso')
            ],
            'performance': [
                ('performance_benchmark', 'macrobenchmark'),
                ('memory_test', 'junit')
            ],
            'functional': [
                ('unit_test', 'junit'),
                ('integration_test', 'espresso')
            ],
            'integration': [
                ('integration_test', 'espresso'),
                ('api_test', 'junit')
            ],
            'edge_case': [
                ('edge_case_test', 'junit'),
                ('error_scenario_test', 'junit')
            ],
            'error_handling': [
                ('error_handling_test', 'junit'),
                ('exception_test', 'robolectric')
            ],
            'user_flow': [
                ('user_flow_test', 'espresso'),
                ('end_to_end_test', 'espresso')
            ],
            'api_contract': [
                ('api_contract_test', 'junit'),
                ('schema_validation_test', 'junit')
            ],
            'device_specific': [
                ('device_test', 'robolectric'),
                ('compatibility_test', 'junit')
            ],
            'network_condition': [
                ('network_test', 'robolectric'),
                ('connectivity_test', 'junit')
            ]
        }

        return recommendations.get(coverage_type, [('generic_test', 'junit')])

    def _calculate_suggestion_confidence(self, coverage_gap: TestCoverageGap, test_type: str) -> float:
        """Calculate confidence score for test suggestion"""
        base_confidence = coverage_gap.confidence_score

        # Adjust based on test type appropriateness
        type_appropriateness = {
            'visual_regression': 0.9 if coverage_gap.coverage_type == 'visual' else 0.5,
            'performance_benchmark': 0.9 if coverage_gap.coverage_type == 'performance' else 0.4,
            'unit_test': 0.8,  # Generally appropriate
            'integration_test': 0.7,
            'edge_case_test': 0.9 if coverage_gap.coverage_type == 'edge_case' else 0.6,
            'error_handling_test': 0.9 if coverage_gap.coverage_type == 'error_handling' else 0.5,
            'user_flow_test': 0.8 if coverage_gap.coverage_type == 'user_flow' else 0.6,
        }

        appropriateness = type_appropriateness.get(test_type, 0.6)

        # Consider anomaly recurrence (more recurrent = higher confidence)
        if hasattr(coverage_gap, 'anomaly_signature') and coverage_gap.anomaly_signature:
            recurrence_factor = min(coverage_gap.anomaly_signature.occurrence_count / 10.0, 1.0)
        else:
            recurrence_factor = 0.5

        final_confidence = (base_confidence * 0.5) + (appropriateness * 0.3) + (recurrence_factor * 0.2)
        return min(final_confidence, 1.0)

    def _estimate_implementation_time(self, test_type: str) -> int:
        """Estimate implementation time in hours"""
        time_estimates = {
            'visual_regression': 2,
            'performance_benchmark': 4,
            'unit_test': 1,
            'integration_test': 3,
            'edge_case_test': 2,
            'error_handling_test': 2,
            'user_flow_test': 6,
            'api_contract_test': 3,
            'device_test': 4,
            'network_test': 3
        }
        return time_estimates.get(test_type, 2)

    def _suggest_file_path(self, coverage_gap: TestCoverageGap, framework: str) -> str:
        """Suggest file path for the test"""
        # Extract component name from affected endpoints
        endpoints = coverage_gap.affected_endpoints
        if endpoints:
            endpoint = endpoints[0]
            # Extract meaningful component name from endpoint
            component = self._extract_component_name(endpoint)
        else:
            component = 'Unknown'

        # Sanitize component name for file path
        component = re.sub(r'[^a-zA-Z0-9]', '', component).capitalize()

        framework_paths = {
            'paparazzi': f'app/src/test/java/com/intelliwiz/tests/visual/{component}VisualTest.kt',
            'macrobenchmark': f'macrobenchmark/src/main/java/com/intelliwiz/benchmark/{component}BenchmarkTest.kt',
            'espresso': f'app/src/androidTest/java/com/intelliwiz/ui/{component}UiTest.kt',
            'junit': f'app/src/test/java/com/intelliwiz/tests/{component}Test.kt',
            'robolectric': f'app/src/test/java/com/intelliwiz/tests/{component}RobolectricTest.kt',
            'ui_testing': f'IntelliwizUITests/{component}UITests.swift',
            'xctest': f'IntelliwizTests/{component}Tests.swift'
        }

        return framework_paths.get(framework, f'tests/{component}Test.kt')

    def _extract_component_name(self, endpoint: str) -> str:
        """Extract meaningful component name from endpoint"""
        # Remove common prefixes and clean up
        endpoint = endpoint.replace('/api/', '')

        # Split by / and take meaningful parts
        parts = [part for part in endpoint.split('/') if part and not part.isdigit()]

        if parts:
            # Use the first meaningful part
            component = parts[0]
            # Convert to PascalCase
            return ''.join(word.capitalize() for word in re.split(r'[_-]', component))

        return 'Component'

    def _generate_test_description(self, coverage_gap: TestCoverageGap, test_type: str) -> str:
        """Generate human-readable description for test"""
        descriptions = {
            'visual_regression': f"Visual regression test to catch UI changes in {coverage_gap.title}",
            'performance_benchmark': f"Performance benchmark test to monitor {coverage_gap.title}",
            'unit_test': f"Unit test to cover edge cases in {coverage_gap.title}",
            'integration_test': f"Integration test to verify {coverage_gap.title}",
            'edge_case_test': f"Edge case test for {coverage_gap.title}",
            'error_handling_test': f"Error handling test for {coverage_gap.title}",
            'user_flow_test': f"End-to-end user flow test covering {coverage_gap.title}",
            'api_contract_test': f"API contract test to validate {coverage_gap.title}",
            'device_test': f"Device-specific test for {coverage_gap.title}",
            'network_test': f"Network condition test for {coverage_gap.title}"
        }
        return descriptions.get(test_type, f"Test for {coverage_gap.title}")


class KotlinTestTemplates:
    """Templates for generating Kotlin test code"""

    def generate_paparazzi_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import app.cash.paparazzi.DeviceConfig.Companion.PIXEL_5
import app.cash.paparazzi.Paparazzi
import com.intelliwiz.ui.theme.IntelliwizTheme
import org.junit.Rule
import org.junit.Test

/**
 * Visual regression tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}VisualTest {{

    @get:Rule
    val paparazzi = Paparazzi(
        deviceConfig = PIXEL_5,
        theme = "Theme.Intelliwiz",
        maxPercentDifference = 0.1
    )

    @Test
    fun `{component_name.lower()}_default_state`() {{
        paparazzi.snapshot {{
            IntelliwizTheme {{
                // TODO: Add your component here
                // {component_name}Component(
                //     state = Default{component_name}State()
                // )
            }}
        }}
    }}

    @Test
    fun `{component_name.lower()}_error_state`() {{
        paparazzi.snapshot {{
            IntelliwizTheme {{
                // TODO: Test error state that caused anomalies
                // {component_name}Component(
                //     state = Error{component_name}State(
                //         error = "Network timeout"
                //     )
                // )
            }}
        }}
    }}

    @Test
    fun `{component_name.lower()}_loading_state`() {{
        paparazzi.snapshot {{
            IntelliwizTheme {{
                // TODO: Test loading state
                // {component_name}Component(
                //     state = Loading{component_name}State()
                // )
            }}
        }}
    }}
}}
""".strip()

    def generate_macrobenchmark_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import androidx.benchmark.macro.CompilationMode
import androidx.benchmark.macro.FrameTimingMetric
import androidx.benchmark.macro.MacrobenchmarkScope
import androidx.benchmark.macro.StartupMode
import androidx.benchmark.macro.StartupTimingMetric
import androidx.benchmark.macro.junit4.MacrobenchmarkRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.By
import androidx.test.uiautomator.Until
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Performance benchmark tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
@RunWith(AndroidJUnit4::class)
class {component_name}BenchmarkTest {{

    @get:Rule
    val benchmarkRule = MacrobenchmarkRule()

    @Test
    fun {component_name.lower()}_startup_performance() {{
        benchmarkRule.measureRepeated(
            packageName = "com.intelliwiz",
            metrics = listOf(StartupTimingMetric()),
            compilationMode = CompilationMode.DEFAULT,
            iterations = 5,
            startupMode = StartupMode.COLD
        ) {{
            pressHome()
            startActivityAndWait()

            // Navigate to {component_name}
            // TODO: Add navigation steps to reach component
            device.wait(Until.hasObject(By.text("{component_name}")), 5000)
        }}
    }}

    @Test
    fun {component_name.lower()}_scroll_performance() {{
        benchmarkRule.measureRepeated(
            packageName = "com.intelliwiz",
            metrics = listOf(FrameTimingMetric()),
            compilationMode = CompilationMode.DEFAULT,
            iterations = 5,
            startupMode = StartupMode.WARM
        ) {{
            startActivityAndWait()
            navigate{component_name}()

            // TODO: Implement scrolling interaction that was problematic
            repeat(5) {{
                device.swipe(500, 1000, 500, 200, 10)
                device.waitForIdle(1000)
            }}
        }}
    }}

    private fun MacrobenchmarkScope.navigate{component_name}() {{
        // TODO: Add navigation logic to reach {component_name}
        device.wait(Until.hasObject(By.text("{component_name}")), 5000)
        device.findObject(By.text("{component_name}")).click()
    }}
}}
""".strip()

    def generate_espresso_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.*
import androidx.test.espresso.assertion.ViewAssertions.*
import androidx.test.espresso.matcher.ViewMatchers.*
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.LargeTest
import org.hamcrest.Matchers.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * UI tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
@RunWith(AndroidJUnit4::class)
@LargeTest
class {component_name}UiTest {{

    @get:Rule
    val activityRule = ActivityScenarioRule(MainActivity::class.java)

    @Test
    fun {component_name.lower()}_displays_correctly() {{
        // Navigate to {component_name}
        // TODO: Add navigation steps

        // Verify component is displayed
        onView(withText("{component_name}"))
            .check(matches(isDisplayed()))
    }}

    @Test
    fun {component_name.lower()}_handles_error_gracefully() {{
        // TODO: Trigger error condition that caused anomalies
        // This test addresses the anomaly pattern found in analysis

        // Verify error is handled properly
        onView(withText("Error"))
            .check(matches(isDisplayed()))
    }}

    @Test
    fun {component_name.lower()}_user_flow_complete() {{
        // TODO: Test complete user flow through {component_name}
        // This addresses gaps in end-to-end testing

        // Step 1: Navigate to component
        // Step 2: Perform main action
        // Step 3: Verify result

        onView(withText("Success"))
            .check(matches(isDisplayed()))
    }}
}}
""".strip()

    def generate_junit_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import junit.framework.TestCase.assertEquals
import junit.framework.TestCase.assertNotNull
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever

/**
 * Unit tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}Test {{

    @Mock
    private lateinit var mock{component_name}Repository: {component_name}Repository

    private lateinit var {component_name.lower()}: {component_name}

    @Before
    fun setup() {{
        MockitoAnnotations.openMocks(this)
        {component_name.lower()} = {component_name}(mock{component_name}Repository)
    }}

    @Test
    fun `{component_name.lower()}_handles_valid_input`() {{
        // Arrange
        val validInput = createValidInput()
        val expectedResult = createExpectedResult()
        whenever(mock{component_name}Repository.process(validInput)).thenReturn(expectedResult)

        // Act
        val result = {component_name.lower()}.process(validInput)

        // Assert
        assertEquals(expectedResult, result)
    }}

    @Test
    fun `{component_name.lower()}_handles_invalid_input`() {{
        // Arrange - Test edge case that caused anomalies
        val invalidInput = createInvalidInput()

        // Act & Assert
        try {{
            {component_name.lower()}.process(invalidInput)
            fail("Expected exception was not thrown")
        }} catch (e: IllegalArgumentException) {{
            // Expected exception
            assertNotNull(e.message)
        }}
    }}

    @Test
    fun `{component_name.lower()}_handles_network_error`() {{
        // Arrange - Test network error scenario from anomaly analysis
        val input = createValidInput()
        whenever(mock{component_name}Repository.process(input))
            .thenThrow(NetworkException("Connection timeout"))

        // Act
        val result = {component_name.lower()}.processWithErrorHandling(input)

        // Assert
        assertEquals(ErrorResult.NETWORK_ERROR, result)
    }}

    private fun createValidInput(): {component_name}Input {{
        // TODO: Create valid input for testing
        return {component_name}Input()
    }}

    private fun createInvalidInput(): {component_name}Input {{
        // TODO: Create invalid input that triggers edge cases
        return {component_name}Input()
    }}

    private fun createExpectedResult(): {component_name}Result {{
        // TODO: Create expected result for valid input
        return {component_name}Result()
    }}
}}
""".strip()

    def generate_robolectric_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

/**
 * Robolectric tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [30])
class {component_name}RobolectricTest {{

    private lateinit var context: Context
    private lateinit var {component_name.lower()}: {component_name}

    @Before
    fun setup() {{
        context = ApplicationProvider.getApplicationContext()
        {component_name.lower()} = {component_name}(context)
    }}

    @Test
    fun `{component_name.lower()}_handles_different_device_configs`() {{
        // Test device-specific scenarios that caused anomalies
        val configs = listOf(
            DeviceConfig.PHONE,
            DeviceConfig.TABLET,
            DeviceConfig.FOLDABLE
        )

        configs.forEach {{ config ->
            // TODO: Test component behavior with different device configurations
            val result = {component_name.lower()}.adaptToDevice(config)
            assertNotNull(result)
        }}
    }}

    @Test
    fun `{component_name.lower()}_handles_network_conditions`() {{
        // Test various network conditions that were problematic
        val networkStates = listOf(
            NetworkState.CONNECTED,
            NetworkState.DISCONNECTED,
            NetworkState.SLOW
        )

        networkStates.forEach {{ state ->
            // TODO: Simulate network state and test behavior
            val result = {component_name.lower()}.handleNetworkState(state)
            // Verify appropriate handling
        }}
    }}
}}
""".strip()

    def generate_generic_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import org.junit.Test
import org.junit.Assert.*

/**
 * Generic tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}Test {{

    @Test
    fun `test_{component_name.lower()}_basic_functionality`() {{
        // TODO: Implement basic functionality test
        // This test was generated based on anomaly analysis

        val component = {component_name}()
        val result = component.performBasicOperation()

        assertNotNull(result)
    }}

    @Test
    fun `test_{component_name.lower()}_error_scenarios`() {{
        // TODO: Test error scenarios identified in anomaly analysis
        // Focus on cases that caused production issues

        val component = {component_name}()

        // Test null input handling
        assertThrows(IllegalArgumentException::class.java) {{
            component.performBasicOperation(null)
        }}
    }}
}}
""".strip()

    def _extract_component_name(self, coverage_gap: TestCoverageGap) -> str:
        """Extract component name from coverage gap for test generation"""
        if coverage_gap.affected_endpoints:
            endpoint = coverage_gap.affected_endpoints[0]
            # Extract meaningful component name from endpoint
            endpoint = endpoint.replace('/api/', '')
            parts = [part for part in endpoint.split('/') if part and not part.isdigit()]
            if parts:
                component = parts[0]
                return ''.join(word.capitalize() for word in re.split(r'[_-]', component))

        # Fallback to generic name based on coverage type
        return coverage_gap.coverage_type.replace('_', ' ').title().replace(' ', '')


class SwiftTestTemplates:
    """Templates for generating Swift test code for iOS"""

    def generate_ui_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import XCTest

/**
 * UI tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}UITests: XCTestCase {{

    var app: XCUIApplication!

    override func setUpWithError() throws {{
        continueAfterFailure = false
        app = XCUIApplication()
        app.launch()
    }}

    func test{component_name}DisplaysCorrectly() throws {{
        // Navigate to {component_name}
        // TODO: Add navigation steps

        let {component_name.lower()}Element = app.staticTexts["{component_name}"]
        XCTAssertTrue({component_name.lower()}Element.exists)
    }}

    func test{component_name}HandlesErrorGracefully() throws {{
        // TODO: Trigger error condition that caused anomalies
        // This test addresses the anomaly pattern found in analysis

        let errorAlert = app.alerts["Error"]
        XCTAssertTrue(errorAlert.exists)
    }}

    func test{component_name}UserFlowComplete() throws {{
        // TODO: Test complete user flow through {component_name}
        // This addresses gaps in end-to-end testing

        // Step 1: Navigate to component
        // Step 2: Perform main action
        // Step 3: Verify result

        let successLabel = app.staticTexts["Success"]
        XCTAssertTrue(successLabel.exists)
    }}
}}
""".strip()

    def generate_xctest(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import XCTest
@testable import IntelliwizApp

/**
 * Unit tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}Tests: XCTestCase {{

    var {component_name.lower()}: {component_name}!
    var mock{component_name}Repository: Mock{component_name}Repository!

    override func setUpWithError() throws {{
        super.setUp()
        mock{component_name}Repository = Mock{component_name}Repository()
        {component_name.lower()} = {component_name}(repository: mock{component_name}Repository)
    }}

    override func tearDownWithError() throws {{
        {component_name.lower()} = nil
        mock{component_name}Repository = nil
        super.tearDown()
    }}

    func test{component_name}HandlesValidInput() throws {{
        // Arrange
        let validInput = createValidInput()
        let expectedResult = createExpectedResult()
        mock{component_name}Repository.processResult = expectedResult

        // Act
        let result = {component_name.lower()}.process(validInput)

        // Assert
        XCTAssertEqual(result, expectedResult)
    }}

    func test{component_name}HandlesInvalidInput() throws {{
        // Arrange - Test edge case that caused anomalies
        let invalidInput = createInvalidInput()

        // Act & Assert
        XCTAssertThrowsError(try {component_name.lower()}.process(invalidInput)) {{ error in
            XCTAssertTrue(error is ValidationError)
        }}
    }}

    func test{component_name}HandlesNetworkError() throws {{
        // Arrange - Test network error scenario from anomaly analysis
        let input = createValidInput()
        mock{component_name}Repository.shouldThrowError = true

        // Act
        let result = {component_name.lower()}.processWithErrorHandling(input)

        // Assert
        XCTAssertEqual(result, .networkError)
    }}

    // MARK: - Helper Methods

    private func createValidInput() -> {component_name}Input {{
        // TODO: Create valid input for testing
        return {component_name}Input()
    }}

    private func createInvalidInput() -> {component_name}Input {{
        // TODO: Create invalid input that triggers edge cases
        return {component_name}Input()
    }}

    private func createExpectedResult() -> {component_name}Result {{
        // TODO: Create expected result for valid input
        return {component_name}Result()
    }}
}}
""".strip()

    def generate_generic_test(self, coverage_gap: TestCoverageGap) -> str:
        component_name = self._extract_component_name(coverage_gap)

        return f"""
import XCTest
@testable import IntelliwizApp

/**
 * Generic tests for {component_name}
 * Generated to address coverage gap: {coverage_gap.title}
 *
 * Confidence: {coverage_gap.confidence_score:.2f}
 * Priority: {coverage_gap.priority}
 */
class {component_name}Tests: XCTestCase {{

    func test{component_name}BasicFunctionality() throws {{
        // TODO: Implement basic functionality test
        // This test was generated based on anomaly analysis

        let component = {component_name}()
        let result = component.performBasicOperation()

        XCTAssertNotNil(result)
    }}

    func test{component_name}ErrorScenarios() throws {{
        // TODO: Test error scenarios identified in anomaly analysis
        // Focus on cases that caused production issues

        let component = {component_name}()

        // Test nil input handling
        XCTAssertThrowsError(try component.performBasicOperation(nil))
    }}
}}
""".strip()

    def _extract_component_name(self, coverage_gap: TestCoverageGap) -> str:
        """Extract component name from coverage gap for Swift test generation"""
        if coverage_gap.affected_endpoints:
            endpoint = coverage_gap.affected_endpoints[0]
            endpoint = endpoint.replace('/api/', '')
            parts = [part for part in endpoint.split('/') if part and not part.isdigit()]
            if parts:
                component = parts[0]
                return ''.join(word.capitalize() for word in re.split(r'[_-]', component))

        return coverage_gap.coverage_type.replace('_', ' ').title().replace(' ', '')
