"""
Tests for Maker/Checker dual-LLM pattern implementation.
"""

import json
from unittest.mock import patch, MagicMock
from django.test import TestCase

    MakerCheckerOrchestrator, ConsensusResult, MakerCheckerResult,
    maker_checker_generate, quick_maker_response
)


class TestMakerCheckerOrchestrator(TestCase):
    """Test MakerCheckerOrchestrator class."""

    def setUp(self):
        self.orchestrator = MakerCheckerOrchestrator()

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_successful_accept_consensus(self, mock_llm_manager):
        """Test successful execution with ACCEPT consensus."""
        # Mock maker response
        maker_response = LLMResponse(
            content="This is a good solution",
            tokens_used=50,
            confidence_score=0.8,
            provider="mock",
            role=LLMRole.MAKER
        )

        # Mock checker response (accepts)
        checker_response = LLMResponse(
            content=json.dumps({
                "decision": "ACCEPT",
                "reasoning": "The solution looks good",
                "improvements": [],
                "final_response": None
            }),
            tokens_used=30,
            confidence_score=0.9,
            provider="mock",
            role=LLMRole.CHECKER
        )

        mock_llm_manager.generate.side_effect = [maker_response, checker_response]

        result = self.orchestrator.execute(
            "Generate a simple function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.ACCEPT)
        self.assertEqual(result.final_response, "This is a good solution")
        self.assertEqual(result.iterations, 1)
        self.assertEqual(result.total_tokens, 80)
        self.assertGreater(result.confidence_score, 0.8)

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_successful_improve_consensus(self, mock_llm_manager):
        """Test successful execution with IMPROVE consensus."""
        # Mock maker response
        maker_response = LLMResponse(
            content="Basic solution",
            tokens_used=50,
            confidence_score=0.7,
            provider="mock",
            role=LLMRole.MAKER
        )

        # Mock checker response (improves)
        improved_solution = "Enhanced solution with better error handling"
        checker_response = LLMResponse(
            content=json.dumps({
                "decision": "IMPROVE",
                "reasoning": "Could add error handling",
                "improvements": ["Add error handling", "Improve documentation"],
                "final_response": improved_solution
            }),
            tokens_used=40,
            confidence_score=0.85,
            provider="mock",
            role=LLMRole.CHECKER
        )

        mock_llm_manager.generate.side_effect = [maker_response, checker_response]

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.IMPROVE)
        self.assertEqual(result.final_response, improved_solution)
        self.assertEqual(len(result.improvements_made), 2)
        self.assertIn("Add error handling", result.improvements_made)

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_reject_then_accept_consensus(self, mock_llm_manager):
        """Test rejection followed by acceptance in next iteration."""
        # First iteration - reject
        maker_response1 = LLMResponse(
            content="Poor solution",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response1 = LLMResponse(
            content=json.dumps({
                "decision": "REJECT",
                "reasoning": "Solution has major flaws",
                "improvements": [],
                "final_response": None
            }),
            tokens_used=30,
            provider="mock",
            role=LLMRole.CHECKER
        )

        # Second iteration - accept
        maker_response2 = LLMResponse(
            content="Improved solution addressing feedback",
            tokens_used=60,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response2 = LLMResponse(
            content=json.dumps({
                "decision": "ACCEPT",
                "reasoning": "Much better now",
                "improvements": [],
                "final_response": None
            }),
            tokens_used=25,
            provider="mock",
            role=LLMRole.CHECKER
        )

        mock_llm_manager.generate.side_effect = [
            maker_response1, checker_response1,
            maker_response2, checker_response2
        ]

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.ACCEPT)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.total_tokens, 165)  # Sum of all tokens
        self.assertEqual(len(result.improvements_made), 1)

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_max_iterations_reached(self, mock_llm_manager):
        """Test behavior when max iterations is reached."""
        # Always reject to force max iterations
        maker_response = LLMResponse(
            content="Solution attempt",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response = LLMResponse(
            content=json.dumps({
                "decision": "REJECT",
                "reasoning": "Still has issues",
                "improvements": [],
                "final_response": None
            }),
            tokens_used=30,
            provider="mock",
            role=LLMRole.CHECKER
        )

        mock_llm_manager.generate.side_effect = [
            maker_response, checker_response
        ] * 5  # More than max_iterations

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch",
            max_iterations=3
        )

        self.assertEqual(result.consensus, ConsensusResult.RETRY)
        self.assertEqual(result.iterations, 3)
        self.assertEqual(result.confidence_score, 0.6)
        self.assertTrue(result.metadata.get('timeout'))

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_maker_error_handling(self, mock_llm_manager):
        """Test error handling when Maker fails."""
        maker_response = LLMResponse(
            content="",
            tokens_used=0,
            provider="mock",
            role=LLMRole.MAKER,
            error="Maker failed to generate response"
        )

        mock_llm_manager.generate.return_value = maker_response

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.ERROR)
        self.assertIn("Maker failed", result.final_response)
        self.assertEqual(result.iterations, 1)

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_checker_error_handling(self, mock_llm_manager):
        """Test error handling when Checker fails."""
        maker_response = LLMResponse(
            content="Good solution",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response = LLMResponse(
            content="",
            tokens_used=0,
            provider="mock",
            role=LLMRole.CHECKER,
            error="Checker failed to validate"
        )

        mock_llm_manager.generate.side_effect = [maker_response, checker_response]

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.ERROR)
        self.assertIn("Checker failed", result.final_response)

    @patch('apps.mentor.llm.maker_checker.llm_manager')
    def test_heuristic_consensus_fallback(self, mock_llm_manager):
        """Test fallback to heuristic consensus when JSON parsing fails."""
        maker_response = LLMResponse(
            content="Some solution",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        # Invalid JSON response from checker
        checker_response = LLMResponse(
            content="This looks good and I approve it.",
            tokens_used=20,
            provider="mock",
            role=LLMRole.CHECKER
        )

        mock_llm_manager.generate.side_effect = [maker_response, checker_response]

        result = self.orchestrator.execute(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(result.consensus, ConsensusResult.ACCEPT)
        self.assertEqual(result.final_response, "Some solution")

    def test_create_maker_request(self):
        """Test maker request creation."""
        request = self.orchestrator._create_maker_request(
            "Generate a function",
            {"language": "python"},
            "patch"
        )

        self.assertEqual(request.role, LLMRole.MAKER)
        self.assertEqual(request.prompt, "Generate a function")
        self.assertEqual(request.context, {"language": "python"})
        self.assertIn("code generator", request.system_message)

    def test_create_checker_request(self):
        """Test checker request creation."""
        request = self.orchestrator._create_checker_request(
            "Generate a function",
            {"language": "python"},
            "Some code solution",
            "patch"
        )

        self.assertEqual(request.role, LLMRole.CHECKER)
        self.assertIn("Generate a function", request.prompt)
        self.assertIn("Some code solution", request.prompt)
        self.assertIn("code reviewer", request.system_message)
        self.assertEqual(request.temperature, 0.1)

    def test_determine_consensus_accept(self):
        """Test consensus determination for ACCEPT decision."""
        maker_response = LLMResponse(
            content="Good solution",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response = LLMResponse(
            content=json.dumps({
                "decision": "ACCEPT",
                "reasoning": "Looks good",
                "improvements": [],
                "final_response": None
            }),
            tokens_used=30,
            provider="mock",
            role=LLMRole.CHECKER
        )

        consensus, final_response, improvements = self.orchestrator._determine_consensus(
            maker_response, checker_response, "patch"
        )

        self.assertEqual(consensus, ConsensusResult.ACCEPT)
        self.assertEqual(final_response, "Good solution")
        self.assertEqual(improvements, [])

    def test_determine_consensus_improve(self):
        """Test consensus determination for IMPROVE decision."""
        maker_response = LLMResponse(
            content="Basic solution",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        improved_solution = "Enhanced solution"
        checker_response = LLMResponse(
            content=json.dumps({
                "decision": "IMPROVE",
                "reasoning": "Could be better",
                "improvements": ["Add documentation"],
                "final_response": improved_solution
            }),
            tokens_used=40,
            provider="mock",
            role=LLMRole.CHECKER
        )

        consensus, final_response, improvements = self.orchestrator._determine_consensus(
            maker_response, checker_response, "patch"
        )

        self.assertEqual(consensus, ConsensusResult.IMPROVE)
        self.assertEqual(final_response, improved_solution)
        self.assertEqual(improvements, ["Add documentation"])

    def test_calculate_final_confidence(self):
        """Test final confidence calculation."""
        maker_response = LLMResponse(
            content="Solution", tokens_used=50, provider="mock",
            role=LLMRole.MAKER, confidence_score=0.8
        )

        checker_response = LLMResponse(
            content="Validation", tokens_used=30, provider="mock",
            role=LLMRole.CHECKER, confidence_score=0.9
        )

        # Test ACCEPT consensus
        confidence = self.orchestrator._calculate_final_confidence(
            maker_response, checker_response, ConsensusResult.ACCEPT
        )
        self.assertGreater(confidence, 0.8)
        self.assertLessEqual(confidence, 0.95)

        # Test IMPROVE consensus
        confidence = self.orchestrator._calculate_final_confidence(
            maker_response, checker_response, ConsensusResult.IMPROVE
        )
        self.assertGreater(confidence, 0.7)
        self.assertLessEqual(confidence, 0.9)


class TestConvenienceFunctions(TestCase):
    """Test convenience functions."""

    @patch('apps.mentor.llm.maker_checker.MakerCheckerOrchestrator')
    def test_maker_checker_generate(self, mock_orchestrator_class):
        """Test maker_checker_generate convenience function."""
        mock_orchestrator = MagicMock()
        mock_result = MakerCheckerResult(
            final_response="Test response",
            maker_response=None,
            checker_response=None,
            consensus=ConsensusResult.ACCEPT,
            iterations=1,
            total_tokens=100,
            confidence_score=0.9,
            improvements_made=[],
            metadata={}
        )
        mock_orchestrator.execute.return_value = mock_result
        mock_orchestrator_class.return_value = mock_orchestrator

        result = maker_checker_generate(
            "Test prompt",
            {"context": "test"},
            "general"
        )

        self.assertEqual(result, mock_result)
        mock_orchestrator.execute.assert_called_once_with(
            "Test prompt",
            {"context": "test"},
            "general"
        )

    @patch('apps.mentor.llm.maker_checker.MakerCheckerOrchestrator')
    def test_quick_maker_response(self, mock_orchestrator_class):
        """Test quick_maker_response convenience function."""
        mock_orchestrator = MagicMock()
        mock_result = MakerCheckerResult(
            final_response="Quick response",
            maker_response=None,
            checker_response=None,
            consensus=ConsensusResult.ACCEPT,
            iterations=1,
            total_tokens=50,
            confidence_score=0.8,
            improvements_made=[],
            metadata={}
        )
        mock_orchestrator.execute.return_value = mock_result
        mock_orchestrator_class.return_value = mock_orchestrator

        response = quick_maker_response("Test prompt", {"key": "value"}, "patch")

        self.assertEqual(response, "Quick response")
        mock_orchestrator.execute.assert_called_once_with(
            "Test prompt",
            {"key": "value"},
            "patch"
        )


class TestMakerCheckerResult(TestCase):
    """Test MakerCheckerResult dataclass."""

    def test_result_initialization(self):
        """Test result initialization."""
        maker_response = LLMResponse(
            content="Maker content",
            tokens_used=50,
            provider="mock",
            role=LLMRole.MAKER
        )

        checker_response = LLMResponse(
            content="Checker content",
            tokens_used=30,
            provider="mock",
            role=LLMRole.CHECKER
        )

        result = MakerCheckerResult(
            final_response="Final content",
            maker_response=maker_response,
            checker_response=checker_response,
            consensus=ConsensusResult.ACCEPT,
            iterations=2,
            total_tokens=80,
            confidence_score=0.85,
            improvements_made=["Improvement 1"],
            metadata={"key": "value"}
        )

        self.assertEqual(result.final_response, "Final content")
        self.assertEqual(result.maker_response, maker_response)
        self.assertEqual(result.checker_response, checker_response)
        self.assertEqual(result.consensus, ConsensusResult.ACCEPT)
        self.assertEqual(result.iterations, 2)
        self.assertEqual(result.total_tokens, 80)
        self.assertEqual(result.confidence_score, 0.85)
        self.assertEqual(result.improvements_made, ["Improvement 1"])
        self.assertEqual(result.metadata, {"key": "value"})

    def test_result_metadata_default(self):
        """Test result metadata default initialization."""
        result = MakerCheckerResult(
            final_response="Test",
            maker_response=None,
            checker_response=None,
            consensus=ConsensusResult.ACCEPT,
            iterations=1,
            total_tokens=10,
            confidence_score=0.5,
            improvements_made=[],
            metadata=None
        )

        self.assertEqual(result.metadata, {})