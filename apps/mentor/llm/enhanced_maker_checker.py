"""
Enhanced Maker/Checker LLM orchestration for the AI Mentor system.

This module implements a dual-LLM pattern where:
- Maker LLM generates content (plans, patches, explanations)
- Checker LLM validates, improves, and ensures quality

This approach significantly improves output quality and reduces errors.
"""

import json
import time
from dataclasses import dataclass
from enum import Enum

from apps.mentor.llm.base import BaseLLMProvider
from apps.mentor.analyzers.impact_analyzer import ImpactResult


class MakerCheckerRole(Enum):
    """Roles in the maker/checker pattern."""
    MAKER = "maker"
    CHECKER = "checker"


class ValidationResult(Enum):
    """Results of checker validation."""
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


@dataclass
class MakerCheckerResult:
    """Result of maker/checker process."""
    final_content: Any
    maker_iterations: int
    checker_feedback: List[str]
    validation_result: ValidationResult
    confidence_score: float
    total_tokens_used: int
    total_time_seconds: float
    maker_reasoning: str
    checker_reasoning: str


@dataclass
class MakerPromptContext:
    """Context for maker LLM prompts."""
    task_type: str  # 'plan', 'patch', 'explain'
    request: str
    constraints: Dict[str, Any]
    impact_analysis: Optional[ImpactResult] = None
    existing_content: Optional[str] = None
    iteration: int = 1


@dataclass
class CheckerPromptContext:
    """Context for checker LLM prompts."""
    task_type: str
    original_request: str
    maker_output: Any
    validation_criteria: List[str]
    impact_analysis: Optional[ImpactResult] = None
    iteration: int = 1


class EnhancedMakerChecker:
    """Enhanced Maker/Checker LLM orchestration system."""

    def __init__(self, maker_provider: BaseLLMProvider, checker_provider: Optional[BaseLLMProvider] = None):
        """
        Initialize with LLM providers.

        Args:
            maker_provider: LLM provider for content generation
            checker_provider: LLM provider for validation (defaults to same as maker)
        """
        self.maker_provider = maker_provider
        self.checker_provider = checker_provider or maker_provider
        self.max_iterations = 3
        self.confidence_threshold = 0.8

    def generate_plan(self, request: str, scope: Optional[List[str]] = None,
                     impact_analysis: Optional[ImpactResult] = None) -> MakerCheckerResult:
        """Generate a plan using maker/checker pattern."""

        maker_context = MakerPromptContext(
            task_type='plan',
            request=request,
            constraints={'scope': scope},
            impact_analysis=impact_analysis
        )

        checker_context = CheckerPromptContext(
            task_type='plan',
            original_request=request,
            maker_output=None,  # Will be filled after maker runs
            validation_criteria=[
                'Plan steps are logical and sequential',
                'All major components are addressed',
                'Risk assessment is appropriate',
                'Testing strategy is comprehensive',
                'Dependencies are properly identified'
            ],
            impact_analysis=impact_analysis
        )

        return self._run_maker_checker_loop(maker_context, checker_context)

    def generate_patch(self, request: str, target_files: List[str],
                      impact_analysis: Optional[ImpactResult] = None) -> MakerCheckerResult:
        """Generate patches using maker/checker pattern."""

        maker_context = MakerPromptContext(
            task_type='patch',
            request=request,
            constraints={'target_files': target_files},
            impact_analysis=impact_analysis
        )

        checker_context = CheckerPromptContext(
            task_type='patch',
            original_request=request,
            maker_output=None,
            validation_criteria=[
                'Code changes are syntactically correct',
                'Changes address the requested functionality',
                'No security vulnerabilities introduced',
                'Code follows project conventions',
                'Changes are minimal and focused'
            ],
            impact_analysis=impact_analysis
        )

        return self._run_maker_checker_loop(maker_context, checker_context)

    def generate_explanation(self, target: str, target_type: str,
                           context_depth: int = 2) -> MakerCheckerResult:
        """Generate explanations using maker/checker pattern."""

        maker_context = MakerPromptContext(
            task_type='explain',
            request=f"Explain {target_type}: {target}",
            constraints={'target_type': target_type, 'context_depth': context_depth}
        )

        checker_context = CheckerPromptContext(
            task_type='explain',
            original_request=f"Explain {target_type}: {target}",
            maker_output=None,
            validation_criteria=[
                'Explanation is accurate and complete',
                'Technical details are correct',
                'Examples are relevant and helpful',
                'Explanation is well-structured',
                'No misleading information'
            ]
        )

        return self._run_maker_checker_loop(maker_context, checker_context)

    def _run_maker_checker_loop(self, maker_context: MakerPromptContext,
                               checker_context: CheckerPromptContext) -> MakerCheckerResult:
        """Run the maker/checker iteration loop."""
        start_time = time.time()
        total_tokens = 0
        iterations = 0
        checker_feedback = []

        current_content = None
        final_validation = ValidationResult.NEEDS_REVISION

        for iteration in range(1, self.max_iterations + 1):
            iterations += 1
            maker_context.iteration = iteration
            checker_context.iteration = iteration

            # Update maker context with previous feedback
            if checker_feedback:
                maker_context.existing_content = current_content
                maker_context.constraints['checker_feedback'] = checker_feedback[-1]

            # Maker phase: Generate/revise content
            maker_result = self._run_maker(maker_context)
            current_content = maker_result['content']
            total_tokens += maker_result.get('tokens_used', 0)

            # Checker phase: Validate content
            checker_context.maker_output = current_content
            checker_result = self._run_checker(checker_context)
            total_tokens += checker_result.get('tokens_used', 0)

            validation = checker_result['validation_result']
            feedback = checker_result['feedback']
            confidence = checker_result['confidence_score']

            checker_feedback.append(feedback)

            # Check if we should continue iterations
            if validation == ValidationResult.APPROVED:
                final_validation = ValidationResult.APPROVED
                break
            elif validation == ValidationResult.REJECTED:
                final_validation = ValidationResult.REJECTED
                break
            elif confidence >= self.confidence_threshold:
                final_validation = ValidationResult.APPROVED
                break

        total_time = time.time() - start_time

        return MakerCheckerResult(
            final_content=current_content,
            maker_iterations=iterations,
            checker_feedback=checker_feedback,
            validation_result=final_validation,
            confidence_score=checker_result.get('confidence_score', 0.0),
            total_tokens_used=total_tokens,
            total_time_seconds=total_time,
            maker_reasoning=maker_result.get('reasoning', ''),
            checker_reasoning=checker_result.get('reasoning', '')
        )

    def _run_maker(self, context: MakerPromptContext) -> Dict[str, Any]:
        """Run the maker LLM to generate content."""
        prompt = self._build_maker_prompt(context)

        try:
            response = self.maker_provider.generate(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.7,  # Slightly higher for creativity
                role=MakerCheckerRole.MAKER.value
            )

            return {
                'content': response['content'],
                'reasoning': response.get('reasoning', ''),
                'tokens_used': response.get('tokens_used', 0)
            }

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            print(f"Maker LLM error: {e}")
            return {
                'content': f"Error in maker phase: {str(e)}",
                'reasoning': '',
                'tokens_used': 0
            }

    def _run_checker(self, context: CheckerPromptContext) -> Dict[str, Any]:
        """Run the checker LLM to validate content."""
        prompt = self._build_checker_prompt(context)

        try:
            response = self.checker_provider.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.2,  # Lower temperature for more consistent validation
                role=MakerCheckerRole.CHECKER.value
            )

            # Parse checker response
            validation_result, confidence, feedback, reasoning = self._parse_checker_response(response['content'])

            return {
                'validation_result': validation_result,
                'confidence_score': confidence,
                'feedback': feedback,
                'reasoning': reasoning,
                'tokens_used': response.get('tokens_used', 0)
            }

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
            print(f"Checker LLM error: {e}")
            return {
                'validation_result': ValidationResult.NEEDS_REVISION,
                'confidence_score': 0.0,
                'feedback': f"Checker error: {str(e)}",
                'reasoning': '',
                'tokens_used': 0
            }

    def _build_maker_prompt(self, context: MakerPromptContext) -> str:
        """Build the prompt for the maker LLM."""
        base_prompt = f"""
You are an expert AI Mentor Maker responsible for generating high-quality {context.task_type} content.

TASK: {context.request}

CONSTRAINTS:
{json.dumps(context.constraints, indent=2)}
"""

        if context.impact_analysis:
            base_prompt += f"""
IMPACT ANALYSIS:
- Affected files: {len(context.impact_analysis.affected_files)}
- Affected symbols: {len(context.impact_analysis.affected_symbols)}
- Breaking changes: {len(context.impact_analysis.breaking_changes)}
- Severity: {context.impact_analysis.severity.value}
- Confidence: {context.impact_analysis.confidence:.2f}

Breaking changes details:
{json.dumps(context.impact_analysis.breaking_changes, indent=2)}
"""

        if context.existing_content and context.iteration > 1:
            base_prompt += f"""
PREVIOUS ATTEMPT (Iteration {context.iteration - 1}):
{context.existing_content}

CHECKER FEEDBACK:
{context.constraints.get('checker_feedback', 'No feedback')}

Please revise your output based on the checker feedback above.
"""

        # Task-specific instructions
        if context.task_type == 'plan':
            base_prompt += """
Generate a detailed implementation plan with:
1. Sequential steps with clear dependencies
2. Risk assessment for each step
3. Time estimates
4. Required tests and validations
5. Rollback considerations

Focus on leveraging the impact analysis to make the plan code-aware and specific.
"""
        elif context.task_type == 'patch':
            base_prompt += """
Generate specific code patches with:
1. Exact file locations and line numbers
2. Original and modified code blocks
3. Clear descriptions of changes
4. Dependency considerations
5. Risk assessments

Ensure patches are minimal, focused, and address the request precisely.
"""
        elif context.task_type == 'explain':
            base_prompt += """
Generate a comprehensive explanation with:
1. Clear overview of the component/concept
2. Technical details and implementation
3. Usage examples
4. Related components and dependencies
5. Common patterns and best practices

Make the explanation accessible but technically accurate.
"""

        base_prompt += """
OUTPUT FORMAT: Return your response as valid JSON with the following structure:
{
  "content": "Your main output here",
  "reasoning": "Brief explanation of your approach and decisions",
  "confidence": 0.85,
  "metadata": {
    "key_assumptions": [],
    "areas_of_uncertainty": [],
    "recommendations": []
  }
}
"""

        return base_prompt

    def _build_checker_prompt(self, context: CheckerPromptContext) -> str:
        """Build the prompt for the checker LLM."""
        base_prompt = f"""
You are an expert AI Mentor Checker responsible for validating and improving {context.task_type} content.

ORIGINAL REQUEST: {context.original_request}

MAKER OUTPUT TO VALIDATE:
{json.dumps(context.maker_output, indent=2) if isinstance(context.maker_output, dict) else str(context.maker_output)}

VALIDATION CRITERIA:
{chr(10).join(f"- {criteria}" for criteria in context.validation_criteria)}
"""

        if context.impact_analysis:
            base_prompt += f"""
IMPACT ANALYSIS CONTEXT:
- This change affects {len(context.impact_analysis.affected_files)} files
- Breaking changes: {len(context.impact_analysis.breaking_changes)}
- Severity: {context.impact_analysis.severity.value}
- Test coverage gaps: {len(context.impact_analysis.test_coverage_gaps)}

Ensure the maker's output properly accounts for these impacts.
"""

        base_prompt += f"""
ITERATION: {context.iteration}

Your job is to:
1. Validate the maker's output against the criteria
2. Check for technical accuracy and completeness
3. Identify any missing elements or errors
4. Provide specific, actionable feedback for improvement
5. Assign a confidence score (0.0-1.0)

VALIDATION GUIDELINES:
- Be thorough but constructive
- Focus on technical accuracy and completeness
- Consider security and performance implications
- Ensure alignment with the original request
- Validate that impact analysis insights are properly incorporated

OUTPUT FORMAT: Return your response as valid JSON:
{{
  "validation_result": "approved|needs_revision|rejected",
  "confidence_score": 0.85,
  "feedback": "Specific feedback for the maker",
  "reasoning": "Your validation reasoning",
  "suggested_improvements": [
    "Specific improvement 1",
    "Specific improvement 2"
  ],
  "technical_concerns": [
    "Concern 1 if any",
    "Concern 2 if any"
  ],
  "approval_conditions": [
    "Condition 1 for approval",
    "Condition 2 for approval"
  ]
}}
"""

        return base_prompt

    def _parse_checker_response(self, response_content: str) -> Tuple[ValidationResult, float, str, str]:
        """Parse checker LLM response."""
        try:
            response_json = json.loads(response_content)

            validation_str = response_json.get('validation_result', 'needs_revision').lower()
            validation_result = ValidationResult(validation_str)

            confidence = float(response_json.get('confidence_score', 0.0))
            feedback = response_json.get('feedback', 'No feedback provided')
            reasoning = response_json.get('reasoning', 'No reasoning provided')

            # Enhance feedback with specific suggestions
            if response_json.get('suggested_improvements'):
                feedback += "\n\nSuggested improvements:\n"
                for improvement in response_json['suggested_improvements']:
                    feedback += f"• {improvement}\n"

            if response_json.get('technical_concerns'):
                feedback += "\nTechnical concerns:\n"
                for concern in response_json['technical_concerns']:
                    feedback += f"⚠ {concern}\n"

            return validation_result, confidence, feedback, reasoning

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Error parsing checker response: {e}")
            # Fallback parsing
            if 'approved' in response_content.lower():
                return ValidationResult.APPROVED, 0.7, response_content, "Fallback parsing"
            elif 'rejected' in response_content.lower():
                return ValidationResult.REJECTED, 0.3, response_content, "Fallback parsing"
            else:
                return ValidationResult.NEEDS_REVISION, 0.5, response_content, "Fallback parsing"


class SpecializedMakerChecker:
    """Specialized maker/checker implementations for specific tasks."""

    def __init__(self, base_maker_checker: EnhancedMakerChecker):
        self.base = base_maker_checker

    def generate_security_patch(self, vulnerability_description: str, file_path: str,
                              impact_analysis: Optional[ImpactResult] = None) -> MakerCheckerResult:
        """Generate security patches with specialized validation."""

        maker_context = MakerPromptContext(
            task_type='security_patch',
            request=f"Fix security vulnerability: {vulnerability_description} in {file_path}",
            constraints={
                'security_focus': True,
                'file_path': file_path,
                'no_functionality_changes': True
            },
            impact_analysis=impact_analysis
        )

        checker_context = CheckerPromptContext(
            task_type='security_patch',
            original_request=vulnerability_description,
            maker_output=None,
            validation_criteria=[
                'Vulnerability is properly addressed',
                'No new security vulnerabilities introduced',
                'Minimal code changes',
                'Backward compatibility maintained',
                'Input validation is comprehensive',
                'No hardcoded secrets or credentials'
            ],
            impact_analysis=impact_analysis
        )

        return self.base._run_maker_checker_loop(maker_context, checker_context)

    def generate_performance_optimization(self, performance_issue: str, target_files: List[str],
                                        impact_analysis: Optional[ImpactResult] = None) -> MakerCheckerResult:
        """Generate performance optimizations with specialized validation."""

        maker_context = MakerPromptContext(
            task_type='performance_patch',
            request=f"Optimize performance issue: {performance_issue}",
            constraints={
                'performance_focus': True,
                'target_files': target_files,
                'maintain_functionality': True
            },
            impact_analysis=impact_analysis
        )

        checker_context = CheckerPromptContext(
            task_type='performance_patch',
            original_request=performance_issue,
            maker_output=None,
            validation_criteria=[
                'Performance improvement is measurable',
                'No functionality regression',
                'Database query optimization is correct',
                'Caching strategy is appropriate',
                'Memory usage is considered',
                'Changes are maintainable'
            ],
            impact_analysis=impact_analysis
        )

        return self.base._run_maker_checker_loop(maker_context, checker_context)

    def refactor_code(self, refactor_request: str, target_area: str,
                     impact_analysis: Optional[ImpactResult] = None) -> MakerCheckerResult:
        """Generate refactoring changes with specialized validation."""

        maker_context = MakerPromptContext(
            task_type='refactor',
            request=f"Refactor: {refactor_request} in {target_area}",
            constraints={
                'refactor_focus': True,
                'target_area': target_area,
                'preserve_api': True
            },
            impact_analysis=impact_analysis
        )

        checker_context = CheckerPromptContext(
            task_type='refactor',
            original_request=refactor_request,
            maker_output=None,
            validation_criteria=[
                'Code structure is improved',
                'API contracts are maintained',
                'Tests still pass',
                'Code is more maintainable',
                'Design patterns are properly applied',
                'No breaking changes for consumers'
            ],
            impact_analysis=impact_analysis
        )

        return self.base._run_maker_checker_loop(maker_context, checker_context)


class MakerCheckerMetrics:
    """Metrics collection for maker/checker operations."""

    def __init__(self):
        self.metrics = []

    def record_operation(self, result: MakerCheckerResult, task_type: str):
        """Record metrics for a maker/checker operation."""
        metric = {
            'timestamp': time.time(),
            'task_type': task_type,
            'iterations': result.maker_iterations,
            'validation_result': result.validation_result.value,
            'confidence_score': result.confidence_score,
            'tokens_used': result.total_tokens_used,
            'time_seconds': result.total_time_seconds,
            'feedback_count': len(result.checker_feedback)
        }
        self.metrics.append(metric)

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of maker/checker operations."""
        if not self.metrics:
            return {'message': 'No operations recorded'}

        total_ops = len(self.metrics)
        approved_ops = len([m for m in self.metrics if m['validation_result'] == 'approved'])
        avg_iterations = sum(m['iterations'] for m in self.metrics) / total_ops
        avg_confidence = sum(m['confidence_score'] for m in self.metrics) / total_ops
        avg_time = sum(m['time_seconds'] for m in self.metrics) / total_ops
        total_tokens = sum(m['tokens_used'] for m in self.metrics)

        return {
            'total_operations': total_ops,
            'approval_rate': approved_ops / total_ops if total_ops > 0 else 0,
            'average_iterations': round(avg_iterations, 2),
            'average_confidence': round(avg_confidence, 3),
            'average_time_seconds': round(avg_time, 2),
            'total_tokens_used': total_tokens,
            'cost_estimate_usd': total_tokens * 0.0001  # Rough estimate
        }


# Global metrics instance
_maker_checker_metrics = MakerCheckerMetrics()

def get_maker_checker_metrics() -> MakerCheckerMetrics:
    """Get the global maker/checker metrics instance."""
    return _maker_checker_metrics