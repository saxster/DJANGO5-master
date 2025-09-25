# Question Conditional Logic Documentation

## Overview
This feature enables conditional display of questions based on answers to previous questions. Questions can be shown or hidden dynamically based on user responses.

## Key Implementation Detail: Using `question_id` Instead of `question_seqno`

### Why `question_id`?
- **Global Uniqueness**: Each QuestionSetBelonging record has a unique ID across the entire database
- **No Conflicts**: Multiple questionsets can have questions with seqno=1, but IDs are always unique
- **Mobile Storage**: Mobile apps can safely store multiple questionsets without ID conflicts
- **Database Integrity**: Foreign key relationships work better with IDs

### Data Structure

The `display_conditions` field in QuestionSetBelonging stores:

```json
{
    "depends_on": {
        "question_id": 2,  // ID of the parent QuestionSetBelonging record
        "operator": "EQUALS",
        "values": ["Yes"]
    },
    "show_if": true,
    "cascade_hide": false,
    "group": "labour_work"
}
```

## API Endpoints

### 1. Get Questions with Logic
```
GET /api/questionset/?action=get_questions_with_logic&qset_id=2
```

Response:
```json
{
    "questions": [
        {
            "pk": 2,  // QuestionSetBelonging ID (use this for answers)
            "question_id": 101,  // Question template ID
            "seqno": 1,  // Display order
            "quesname": "Any Labour Work Going on?",
            "display_conditions": {}
        },
        {
            "pk": 3,
            "question_id": 102,
            "seqno": 2,
            "quesname": "Type of work",
            "display_conditions": {
                "depends_on": {
                    "question_id": 2,  // Depends on QuestionSetBelonging ID 2
                    "operator": "EQUALS",
                    "values": ["Yes"]
                }
            }
        }
    ],
    "dependency_map": {
        "2": [  // Parent question ID 2 controls:
            {
                "question_id": 3,
                "question_seqno": 2,
                "operator": "EQUALS",
                "values": ["Yes"]
            }
        ]
    }
}
```

### 2. Legacy Endpoint (Still Works)
```
GET /api/questionset/?action=get_questions_of_qset&qset_id=2
```
- Returns questions with `display_conditions` field included
- Backwards compatible with existing mobile apps

## Mobile Implementation

### Key Points for Mobile Developers

1. **Use `pk` field as the question identifier** when storing answers
2. **Use `pk` field as the key** in dependency evaluations
3. **The `question_id` in display_conditions** refers to the parent's `pk`
4. **The `seqno` field** is only for display ordering

### Example Answer Storage
```javascript
// Correct - use pk
answers = {
    2: "Yes",    // Answer to question with pk=2
    3: "Electrical",  // Answer to question with pk=3
    4: "John Doe"    // Answer to question with pk=4
}

// Incorrect - don't use seqno
answers = {
    1: "Yes",    // This would conflict across questionsets!
    2: "Electrical"
}
```

### Evaluation Logic
```javascript
function shouldShowQuestion(question, answers) {
    if (!question.display_conditions?.depends_on) {
        return true;  // No condition, always show
    }
    
    const parentId = question.display_conditions.depends_on.question_id;
    const parentAnswer = answers[parentId];  // Use the parent's pk
    
    // Evaluate condition...
}
```

## Setting Up Conditions

### Via Management Command
```bash
python manage.py setup_question_conditions 2 --setup-labour-example
```

### Programmatically
```python
from apps.activity.utils_conditions import QuestionConditionManager
from apps.activity.models.question_model import QuestionSetBelonging

# Get parent question
parent = QuestionSetBelonging.objects.filter(qset_id=2, seqno=1).first()

# Set condition on dependent question
dependent = QuestionSetBelonging.objects.filter(qset_id=2, seqno=2).first()
dependent.display_conditions = QuestionConditionManager.create_condition(
    depends_on_id=parent.pk,  # Use the parent's ID
    operator="EQUALS",
    values=["Yes"],
    show_if=True
)
dependent.save()
```

## Operators Supported

- `EQUALS`: Exact match
- `NOT_EQUALS`: Not equal to
- `CONTAINS`: Contains substring
- `IN`: Value in list
- `GREATER_THAN`: Numeric comparison
- `LESS_THAN`: Numeric comparison
- `IS_EMPTY`: Field is empty
- `IS_NOT_EMPTY`: Field has value

## Example Use Case

**Scenario**: Security checklist where follow-up questions only appear based on initial answers

1. **Q1** (ID: 2): "Any Labour Work Going on?" → Options: Yes/No
2. **Q2** (ID: 3): "Type of work" → Shows only if Q1 = "Yes"
3. **Q3** (ID: 4): "Name of vendors" → Shows only if Q1 = "Yes"
4. **Q4** (ID: 5): "Number of labours" → Shows only if Q1 = "Yes"
5. **Q5** (ID: 6): "Any suspicious activity?" → Always visible
6. **Q6** (ID: 7): "Any damage seen?" → Always visible

When user answers "No" to Q1, only questions 1, 5, and 6 are visible.
When user changes answer to "Yes", questions 2, 3, and 4 become visible.

## Migration from `question_seqno` to `question_id`

If you have existing data using the old format with `question_seqno`, run:
```bash
python migrate_question_conditions.py
```

This will update all existing conditions to use `question_id` instead of `question_seqno`.

## Benefits

1. **Better UX**: Users only see relevant questions
2. **Data Quality**: Prevents collection of irrelevant data
3. **Efficiency**: Shorter forms when conditions are not met
4. **Flexibility**: Complex branching logic support
5. **Scalability**: Works across multiple questionsets without conflicts