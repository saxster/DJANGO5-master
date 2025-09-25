"""
Utility functions for managing question display conditions
"""
import json
from typing import Dict, List, Any, Optional


class QuestionConditionManager:
    """Helper class for managing question display conditions"""
    
    OPERATORS = {
        'EQUALS': 'equals',
        'NOT_EQUALS': 'not_equals',
        'CONTAINS': 'contains',
        'IN': 'in',
        'GREATER_THAN': 'greater_than',
        'LESS_THAN': 'less_than',
        'IS_EMPTY': 'is_empty',
        'IS_NOT_EMPTY': 'is_not_empty'
    }
    
    @staticmethod
    def create_condition(
        depends_on_id: int,
        operator: str,
        values: List[str],
        show_if: bool = True,
        cascade_hide: bool = False,
        group: Optional[str] = None
    ) -> Dict:
        """
        Create a display condition dictionary
        
        Args:
            depends_on_id: ID of the parent QuestionSetBelonging record
            operator: Comparison operator (EQUALS, NOT_EQUALS, etc.)
            values: List of values to compare against
            show_if: Show (True) or hide (False) when condition is met
            cascade_hide: Hide dependent questions if this is hidden
            group: Optional group identifier for related questions
        
        Returns:
            Dictionary with display condition structure
        """
        return {
            "depends_on": {
                "question_id": depends_on_id,
                "operator": operator,
                "values": values
            },
            "show_if": show_if,
            "cascade_hide": cascade_hide,
            "group": group
        }
    
    @staticmethod
    def create_multi_condition(conditions: List[Dict], logic: str = "AND") -> Dict:
        """
        Create complex conditions with multiple dependencies
        
        Args:
            conditions: List of condition dictionaries
            logic: AND or OR logic for combining conditions
        
        Returns:
            Dictionary with multiple conditions
        """
        return {
            "multi_depends": conditions,
            "logic": logic
        }
    
    @staticmethod
    def evaluate_condition(
        condition: Dict,
        answers: Dict[int, Any]
    ) -> bool:
        """
        Evaluate if a condition is met based on current answers
        
        Args:
            condition: Display condition dictionary
            answers: Dictionary of {question_id: answer_value}
        
        Returns:
            Boolean indicating if question should be displayed
        """
        if not condition or not condition.get("depends_on"):
            return True  # No condition, always show
        
        depends_on = condition["depends_on"]
        parent_id = depends_on.get("question_id")
        operator = depends_on.get("operator", "EQUALS")
        expected_values = depends_on.get("values", [])
        show_if = condition.get("show_if", True)
        
        # Get parent answer
        parent_answer = answers.get(parent_id)
        
        # Evaluate based on operator
        result = QuestionConditionManager._evaluate_operator(
            parent_answer, operator, expected_values
        )
        
        # Apply show_if logic
        return result if show_if else not result
    
    @staticmethod
    def _evaluate_operator(value: Any, operator: str, expected: List[Any]) -> bool:
        """Evaluate a single operator condition"""
        if operator == "EQUALS":
            return value in expected
        elif operator == "NOT_EQUALS":
            return value not in expected
        elif operator == "CONTAINS":
            if value is None:
                return False
            return any(exp in str(value) for exp in expected)
        elif operator == "IN":
            return value in expected
        elif operator == "GREATER_THAN":
            try:
                return float(value) > float(expected[0])
            except (ValueError, TypeError, IndexError):
                return False
        elif operator == "LESS_THAN":
            try:
                return float(value) < float(expected[0])
            except (ValueError, TypeError, IndexError):
                return False
        elif operator == "IS_EMPTY":
            return value is None or value == ""
        elif operator == "IS_NOT_EMPTY":
            return value is not None and value != ""
        else:
            return True
    
    @staticmethod
    def get_visible_questions(
        questions: List[Dict],
        answers: Dict[int, Any]
    ) -> List[Dict]:
        """
        Filter questions based on display conditions and current answers
        
        Args:
            questions: List of question dictionaries with display_conditions
            answers: Current answers {seqno: value}
        
        Returns:
            List of questions that should be visible
        """
        visible = []
        hidden_seqnos = set()
        
        for question in questions:
            seqno = question.get("seqno")
            
            # Check if parent question is hidden (cascade effect)
            if question.get("display_conditions", {}).get("cascade_hide"):
                parent_seqno = question["display_conditions"]["depends_on"].get("question_seqno")
                if parent_seqno in hidden_seqnos:
                    hidden_seqnos.add(seqno)
                    continue
            
            # Evaluate display condition
            if QuestionConditionManager.evaluate_condition(
                question.get("display_conditions", {}),
                answers
            ):
                visible.append(question)
            else:
                hidden_seqnos.add(seqno)
        
        return visible
    
    @staticmethod
    def validate_dependencies(questions: List[Dict]) -> List[str]:
        """
        Validate that question dependencies are properly configured
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        seqnos = {q["seqno"] for q in questions}
        
        for q in questions:
            if not q.get("display_conditions"):
                continue
            
            depends_on = q["display_conditions"].get("depends_on", {})
            parent_seqno = depends_on.get("question_seqno")
            
            if parent_seqno:
                # Check if parent exists
                if parent_seqno not in seqnos:
                    errors.append(
                        f"Question {q['seqno']} depends on non-existent question {parent_seqno}"
                    )
                
                # Check for circular dependencies
                if parent_seqno >= q["seqno"]:
                    errors.append(
                        f"Question {q['seqno']} depends on later question {parent_seqno}"
                    )
        
        return errors


# Helper functions for common patterns

def setup_yes_no_dependency(
    dependent_questions: List,
    parent_id: int,
    trigger_value: str = "Yes",
    group_name: Optional[str] = None
):
    """
    Set up common Yes/No dependency pattern
    
    Args:
        dependent_questions: List of QuestionSetBelonging objects to update
        parent_id: ID of the parent Yes/No QuestionSetBelonging record
        trigger_value: Value that triggers visibility (default "Yes")
        group_name: Optional group name for related questions
    """
    condition = QuestionConditionManager.create_condition(
        depends_on_id=parent_id,
        operator="EQUALS",
        values=[trigger_value],
        show_if=True,
        group=group_name
    )
    
    for q in dependent_questions:
        q.display_conditions = condition
        q.save()


def setup_numeric_range_dependency(
    dependent_question,
    parent_seqno: int,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None
):
    """
    Set up dependency based on numeric range
    
    Args:
        dependent_question: QuestionSetBelonging object to update
        parent_seqno: Sequence number of the parent numeric question
        min_value: Minimum value (show if parent > min)
        max_value: Maximum value (show if parent < max)
    """
    conditions = []
    
    if min_value is not None:
        conditions.append({
            "depends_on": {
                "question_seqno": parent_seqno,
                "operator": "GREATER_THAN",
                "values": [str(min_value)]
            }
        })
    
    if max_value is not None:
        conditions.append({
            "depends_on": {
                "question_seqno": parent_seqno,
                "operator": "LESS_THAN",
                "values": [str(max_value)]
            }
        })
    
    if len(conditions) == 1:
        dependent_question.display_conditions = conditions[0]
    elif len(conditions) == 2:
        dependent_question.display_conditions = {
            "multi_depends": conditions,
            "logic": "AND"
        }
    
    dependent_question.save()


def clear_conditions(questions):
    """Clear all display conditions from questions"""
    for q in questions:
        q.display_conditions = {}
        q.save()