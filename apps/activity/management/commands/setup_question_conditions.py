from django.core.management.base import BaseCommand
from apps.activity.models.question_model import QuestionSetBelonging


class Command(BaseCommand):
    help = 'Set up conditional display logic for questions'

    def add_arguments(self, parser):
        parser.add_argument('qset_id', type=int, help='QuestionSet ID')
        parser.add_argument('--setup-labour-example', action='store_true',
                          help='Set up the labour work example conditions')

    def handle(self, *args, **options):
        qset_id = options['qset_id']
        
        if options['setup_labour_example']:
            self.setup_labour_example(qset_id)
        else:
            self.stdout.write("Use --setup-labour-example flag to set up conditions")

    def setup_labour_example(self, qset_id):
        """
        Setup example:
        Question 1: Any Labour Work Going on? (seqno=1)
        Question 2: Type of work (seqno=2) - Show only if Q1 = Yes
        Question 3: Name of vendors (seqno=3) - Show only if Q1 = Yes
        Question 4: Number of labours (seqno=4) - Show only if Q1 = Yes
        Question 5: Suspicious person? (seqno=5) - Always show
        Question 6: Any damage? (seqno=6) - Always show
        """
        
        try:
            # Get all questions in the questionset
            questions = QuestionSetBelonging.objects.filter(
                qset_id=qset_id
            ).order_by('seqno')
            
            if not questions.exists():
                self.stdout.write(self.style.ERROR(f"No questions found for qset_id={qset_id}"))
                return
            
            # Get the parent question (seqno=1)
            parent_question = questions.filter(seqno=1).first()
            if not parent_question:
                self.stdout.write(self.style.ERROR("Parent question (seqno=1) not found"))
                return
            
            parent_id = parent_question.pk
            
            # Update questions 2, 3, 4 to depend on question 1
            dependent_seqnos = [2, 3, 4]
            
            for q in questions:
                if q.seqno in dependent_seqnos:
                    # Set display condition using question_id
                    q.display_conditions = {
                        "depends_on": {
                            "question_id": parent_id,  # Use the actual ID of parent question
                            "operator": "EQUALS",
                            "values": ["Yes"]
                        },
                        "show_if": True,  # Show when condition is met
                        "cascade_hide": False,
                        "group": "labour_work"  # Group related questions
                    }
                    q.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Set condition for Question {q.seqno}: {q.question.quesname[:50]}..."
                        )
                    )
                elif q.seqno == 1:
                    # Clear any existing conditions on the parent question
                    q.display_conditions = {}
                    q.save()
                    self.stdout.write(
                        f"✓ Parent question {q.seqno}: {q.question.quesname[:50]}..."
                    )
                else:
                    # Questions 5 and 6 have no conditions
                    q.display_conditions = {}
                    q.save()
                    self.stdout.write(
                        f"✓ Independent question {q.seqno}: {q.question.quesname[:50]}..."
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Successfully configured conditional logic for QuestionSet {qset_id}"
                )
            )
            
            # Display the dependency structure
            self.stdout.write("\nDependency Structure:")
            self.stdout.write("Question 1 (Labour Work?)")
            self.stdout.write("  └─ If 'Yes' → Show:")
            self.stdout.write("      ├─ Question 2 (Type of work)")
            self.stdout.write("      ├─ Question 3 (Vendor names)")
            self.stdout.write("      └─ Question 4 (Number of labours)")
            self.stdout.write("Question 5 (Suspicious person?) - Always visible")
            self.stdout.write("Question 6 (Any damage?) - Always visible")
            
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            self.stdout.write(
                self.style.ERROR(f"Error setting up conditions: {str(e)}")
            )