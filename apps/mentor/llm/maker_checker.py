"""
Maker/Checker dual-LLM pattern implementation for enhanced reliability.

This module implements the dual-LLM pattern where:
- Maker LLM: Generates initial responses/solutions
- Checker LLM: Validates and improves Maker responses
- Consensus: Determines final output based on validation
"""

from dataclasses import dataclass
from enum import Enum
import json
import logging

from .base import (
    LLMManager, LLMRequest, LLMResponse, LLMRole,
    llm_manager
)

logger = logging.getLogger(__name__)


class ConsensusResult(Enum):
    """Possible outcomes of Maker/Checker consensus."""
    ACCEPT = "accept"           # Checker accepts Maker's response
    IMPROVE = "improve"         # Checker provides improvements
    REJECT = "reject"           # Checker rejects Maker's response
    RETRY = "retry"             # Requires another attempt
    ERROR = "error"             # System error occurred


@dataclass
class MakerCheckerResult:
    """Result of Maker/Checker process."""
    final_response: str
    maker_response: LLMResponse
    checker_response: LLMResponse
    consensus: ConsensusResult
    iterations: int
    total_tokens: int
    confidence_score: float
    improvements_made: List[str]
    metadata: Dict[str, Any]

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MakerCheckerOrchestrator:
    """Orchestrates the Maker/Checker dual-LLM pattern."""

    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm_manager = llm_manager or llm_manager
        self.max_iterations = 3
        self.consensus_threshold = 0.8

    def execute(
        self,
        prompt: str,
        context: Dict[str, Any],
        task_type: str = "general",
        max_iterations: Optional[int] = None
    ) -> MakerCheckerResult:
        """
        Execute Maker/Checker process for a given prompt.

        Args:
            prompt: The main prompt/request
            context: Additional context for the LLMs
            task_type: Type of task (plan, patch, explain, etc.)
            max_iterations: Maximum number of iterations

        Returns:
            MakerCheckerResult with final response and metadata
        """
        max_iter = max_iterations or self.max_iterations
        iterations = 0
        total_tokens = 0
        improvements_made = []

        maker_response = None
        checker_response = None

        while iterations < max_iter:
            iterations += 1

            # Step 1: Maker generates initial response
            maker_request = self._create_maker_request(prompt, context, task_type)
            maker_response = self.llm_manager.generate(maker_request)
            total_tokens += maker_response.tokens_used

            if maker_response.error:
                return self._create_error_result(
                    maker_response, None, iterations, total_tokens,
                    f"Maker failed: {maker_response.error}"
                )

            # Step 2: Checker validates Maker's response
            checker_request = self._create_checker_request(
                prompt, context, maker_response.content, task_type
            )
            checker_response = self.llm_manager.generate(checker_request)
            total_tokens += checker_response.tokens_used

            if checker_response.error:
                return self._create_error_result(
                    maker_response, checker_response, iterations, total_tokens,
                    f"Checker failed: {checker_response.error}"
                )

            # Step 3: Determine consensus
            consensus, final_response, improvements = self._determine_consensus(
                maker_response, checker_response, task_type
            )

            improvements_made.extend(improvements)

            if consensus in [ConsensusResult.ACCEPT, ConsensusResult.IMPROVE]:
                # Success case
                confidence = self._calculate_final_confidence(
                    maker_response, checker_response, consensus
                )

                return MakerCheckerResult(
                    final_response=final_response,
                    maker_response=maker_response,
                    checker_response=checker_response,
                    consensus=consensus,
                    iterations=iterations,
                    total_tokens=total_tokens,
                    confidence_score=confidence,
                    improvements_made=improvements_made,
                    metadata={
                        'task_type': task_type,
                        'maker_provider': maker_response.provider,
                        'checker_provider': checker_response.provider
                    }
                )

            elif consensus == ConsensusResult.REJECT:
                # Modify prompt for next iteration
                prompt = self._enhance_prompt_with_feedback(
                    prompt, checker_response.content
                )

            # Continue to next iteration for RETRY case

        # Max iterations reached
        return self._create_timeout_result(
            maker_response, checker_response, iterations, total_tokens
        )

    def _create_maker_request(
        self,
        prompt: str,
        context: Dict[str, Any],
        task_type: str
    ) -> LLMRequest:
        """Create a request for the Maker LLM."""
        system_messages = {
            "plan": """You are an expert software architect. Generate detailed, structured change plans.
                      Focus on breaking down complex requests into actionable steps with risk assessments.""",

            "patch": """You are an expert code generator. Create safe, high-quality code patches.
                       Always consider edge cases, error handling, and code style consistency.""",

            "explain": """You are an expert code analyst. Provide clear, comprehensive explanations.
                        Include context, relationships, and practical examples where relevant.""",

            "security": """You are a security expert. Identify and fix security vulnerabilities.
                          Prioritize safety and follow security best practices rigorously.""",

            "performance": """You are a performance optimization expert. Suggest improvements
                            that balance performance gains with code maintainability."""
        }

        system_message = system_messages.get(task_type,
                                           "You are a helpful AI coding assistant.")

        return LLMRequest(
            prompt=prompt,
            context=context,
            role=LLMRole.MAKER,
            system_message=system_message,
            max_tokens=2000,
            temperature=0.3
        )

    def _create_checker_request(
        self,
        original_prompt: str,
        context: Dict[str, Any],
        maker_response: str,
        task_type: str
    ) -> LLMRequest:
        """Create a request for the Checker LLM."""
        checker_prompt = f"""Review and validate the following response to ensure quality and correctness.

Original Request: {original_prompt}

Response to Review: {maker_response}

Please evaluate the response and provide one of the following:

1. ACCEPT: If the response is correct and complete
2. IMPROVE: If the response is mostly correct but could be enhanced (provide specific improvements)
3. REJECT: If the response has significant issues (explain why)

Provide your evaluation in the following JSON format:
{{
    "decision": "ACCEPT|IMPROVE|REJECT",
    "reasoning": "explanation of your decision",
    "improvements": ["list of specific improvements if applicable"],
    "final_response": "improved version if decision is IMPROVE, otherwise null"
}}"""

        system_messages = {
            "plan": "You are a senior architect reviewing change plans for completeness and safety.",
            "patch": "You are a code reviewer checking patches for correctness and security.",
            "explain": "You are a technical writer reviewing explanations for clarity and accuracy.",
            "security": "You are a security auditor validating security fixes for effectiveness.",
            "performance": "You are a performance expert reviewing optimizations for impact."
        }

        system_message = system_messages.get(task_type,
                                           "You are a thorough code reviewer.")

        return LLMRequest(
            prompt=checker_prompt,
            context=context,
            role=LLMRole.CHECKER,
            system_message=system_message,
            max_tokens=1500,
            temperature=0.1  # Lower temperature for more consistent evaluation
        )

    def _determine_consensus(
        self,
        maker_response: LLMResponse,
        checker_response: LLMResponse,
        task_type: str
    ) -> Tuple[ConsensusResult, str, List[str]]:
        """Determine consensus between Maker and Checker responses."""
        try:
            # Try to parse Checker's response as JSON
            checker_content = checker_response.content.strip()

            # Handle cases where JSON might be wrapped in markdown
            if checker_content.startswith('```json'):
                checker_content = checker_content.split('```json')[1].split('```')[0].strip()
            elif checker_content.startswith('```'):
                checker_content = checker_content.split('```')[1].split('```')[0].strip()

            checker_evaluation = json.loads(checker_content)

            decision = checker_evaluation.get('decision', '').upper()
            reasoning = checker_evaluation.get('reasoning', '')
            improvements = checker_evaluation.get('improvements', [])
            improved_response = checker_evaluation.get('final_response')

            if decision == 'ACCEPT':
                return (
                    ConsensusResult.ACCEPT,
                    maker_response.content,
                    []
                )
            elif decision == 'IMPROVE' and improved_response:
                return (
                    ConsensusResult.IMPROVE,
                    improved_response,
                    improvements
                )
            elif decision == 'REJECT':
                return (
                    ConsensusResult.REJECT,
                    maker_response.content,
                    [f"Rejection reason: {reasoning}"]
                )
            else:
                # Fallback to heuristic evaluation
                return self._heuristic_consensus(maker_response, checker_response)

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse checker response: {e}")
            # Fall back to heuristic evaluation
            return self._heuristic_consensus(maker_response, checker_response)

    def _heuristic_consensus(
        self,
        maker_response: LLMResponse,
        checker_response: LLMResponse
    ) -> Tuple[ConsensusResult, str, List[str]]:
        """Fallback heuristic consensus when structured parsing fails."""
        checker_content = checker_response.content.lower()

        if any(word in checker_content for word in ['accept', 'good', 'correct', 'approve']):
            return (ConsensusResult.ACCEPT, maker_response.content, [])
        elif any(word in checker_content for word in ['improve', 'enhance', 'better']):
            return (ConsensusResult.IMPROVE, checker_response.content, ['General improvements suggested'])
        elif any(word in checker_content for word in ['reject', 'wrong', 'incorrect', 'issues']):
            return (ConsensusResult.REJECT, maker_response.content, ['Issues found by checker'])
        else:
            # Default to accepting with low confidence
            return (ConsensusResult.ACCEPT, maker_response.content, [])

    def _calculate_final_confidence(
        self,
        maker_response: LLMResponse,
        checker_response: LLMResponse,
        consensus: ConsensusResult
    ) -> float:
        """Calculate final confidence score based on both responses."""
        base_confidence = (maker_response.confidence_score or 0.7)
        checker_confidence = (checker_response.confidence_score or 0.7)

        if consensus == ConsensusResult.ACCEPT:
            # Both LLMs agree, high confidence
            return min(0.95, (base_confidence + checker_confidence) / 2 + 0.1)
        elif consensus == ConsensusResult.IMPROVE:
            # Checker improved response, good confidence
            return min(0.9, (base_confidence + checker_confidence) / 2)
        else:
            # Consensus was difficult to reach, lower confidence
            return max(0.5, (base_confidence + checker_confidence) / 2 - 0.1)

    def _enhance_prompt_with_feedback(self, original_prompt: str, feedback: str) -> str:
        """Enhance prompt with feedback from previous iteration."""
        return f"""{original_prompt}

Previous attempt had issues. Please address the following feedback:
{feedback}

Please provide an improved response that addresses these concerns."""

    def _create_error_result(
        self,
        maker_response: Optional[LLMResponse],
        checker_response: Optional[LLMResponse],
        iterations: int,
        total_tokens: int,
        error_message: str
    ) -> MakerCheckerResult:
        """Create result for error cases."""
        return MakerCheckerResult(
            final_response=f"Error: {error_message}",
            maker_response=maker_response,
            checker_response=checker_response,
            consensus=ConsensusResult.ERROR,
            iterations=iterations,
            total_tokens=total_tokens,
            confidence_score=0.0,
            improvements_made=[],
            metadata={'error': error_message}
        )

    def _create_timeout_result(
        self,
        maker_response: Optional[LLMResponse],
        checker_response: Optional[LLMResponse],
        iterations: int,
        total_tokens: int
    ) -> MakerCheckerResult:
        """Create result when max iterations reached."""
        return MakerCheckerResult(
            final_response=maker_response.content if maker_response else "No response generated",
            maker_response=maker_response,
            checker_response=checker_response,
            consensus=ConsensusResult.RETRY,
            iterations=iterations,
            total_tokens=total_tokens,
            confidence_score=0.6,  # Medium confidence when consensus wasn't reached
            improvements_made=['Max iterations reached without full consensus'],
            metadata={'timeout': True}
        )


# Convenience functions
def maker_checker_generate(
    prompt: str,
    context: Dict[str, Any] = None,
    task_type: str = "general"
) -> MakerCheckerResult:
    """Generate response using Maker/Checker pattern."""
    orchestrator = MakerCheckerOrchestrator()
    return orchestrator.execute(prompt, context or {}, task_type)


def quick_maker_response(
    prompt: str,
    context: Dict[str, Any] = None,
    task_type: str = "general"
) -> str:
    """Get just the final response from Maker/Checker process."""
    result = maker_checker_generate(prompt, context, task_type)
    return result.final_response


# Global orchestrator instance
maker_checker = MakerCheckerOrchestrator()