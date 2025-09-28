"""
Comprehensive test suite for People model
Tests model creation, validation, encryption, relationships, and business logic
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.contrib.auth import authenticate
from datetime import date, timedelta


@pytest.mark.django_db
class TestPeopleModelCreation:
    """Test People model creation and basic functionality"""

    def test_create_basic_people(self):
        """Test creating a basic People instance"""
        people = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser001",
            email="test@example.com",
            mobno="1234567890",
            gender="M",
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2023, 1, 1)
        )

        assert people.id is not None
        assert people.peoplecode == "TEST001"
        assert people.peoplename == "Test User"
        assert people.loginid == "testuser001"
        assert people.uuid is not None

    def test_create_people_with_password(self):
        """Test creating People with password"""
        people = People.objects.create_user(
            loginid="testuser002",
            peoplecode="TEST002",
            peoplename="Test User 2",
            email="test2@example.com",
            dateofbirth=date(1990, 1, 1),
            password="SecurePass123!"
        )

        assert people.check_password("SecurePass123!")
        assert not people.check_password("WrongPassword")

    def test_people_string_representation(self):
        """Test the string representation of People model"""
        people = People.objects.create(
            peoplecode="TEST003",
            peoplename="John Doe",
            loginid="johndoe",
            email="john@example.com",
            dateofbirth=date(1990, 1, 1)
        )

        assert str(people) == "John Doe (TEST003)"

    def test_people_absolute_url(self):
        """Test get_absolute_wizard_url method"""
        people = People.objects.create(
            peoplecode="TEST004",
            peoplename="Test User",
            loginid="testuser004",
            email="test4@example.com",
            dateofbirth=date(1990, 1, 1)
        )

        expected_url = f"/people/wizard/update/{people.pk}/"
        assert people.get_absolute_wizard_url() == expected_url


@pytest.mark.django_db
class TestPeopleModelEncryption:
    """Test SecureString field encryption for email and mobile"""

    def test_email_encryption_on_save(self):
        """Test that email is encrypted when saved"""
        email = "sensitive@example.com"
        people = People.objects.create(
            peoplecode="TEST005",
            peoplename="Test User",
            loginid="testuser005",
            email=email,
            dateofbirth=date(1990, 1, 1)
        )

        # Refresh from database
        people.refresh_from_db()

        # Check that email can be retrieved correctly
        assert people.email == email

        # Check raw database value is different (encrypted)
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [people.id])
            raw_email = cursor.fetchone()[0]
            # Raw value should be encrypted (different from plain text)
            assert raw_email != email if raw_email else True

    def test_mobile_encryption_on_save(self):
        """Test that mobile number is encrypted when saved"""
        mobno = "9876543210"
        people = People.objects.create(
            peoplecode="TEST006",
            peoplename="Test User",
            loginid="testuser006",
            email="test@example.com",
            mobno=mobno,
            dateofbirth=date(1990, 1, 1)
        )

        # Refresh from database
        people.refresh_from_db()

        # Check that mobile can be retrieved correctly
        assert people.mobno == mobno


@pytest.mark.django_db
class TestPeopleModelConstraints:
    """Test database constraints and unique together constraints"""

    @pytest.fixture
    def setup_test_data(self, client_type_assist, bu_type_assist):
        """Setup test data for constraints testing"""
        # Create test client and bu
        client = Bt.objects.create(
            bucode="CLIENT001",
            buname="Test Client",
            butype=client_type_assist
        )
        bu = Bt.objects.create(
            bucode="BU001",
            buname="Test BU",
            butype=bu_type_assist,
            parent=client
        )
        return client, bu

    def test_unique_loginid_bu_constraint(self, setup_test_data):
        """Test unique constraint on loginid and bu"""
        client, bu = setup_test_data

        # Create first people
        People.objects.create(
            peoplecode="TEST007",
            peoplename="Test User 1",
            loginid="uniqueuser",
            email="test1@example.com",
            bu=bu,
            client=client,
            dateofbirth=date(1990, 1, 1)
        )

        # Try to create duplicate loginid with same bu
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                People.objects.create(
                    peoplecode="TEST008",
                    peoplename="Test User 2",
                    loginid="uniqueuser",  # Same loginid
                    email="test2@example.com",
                    bu=bu,  # Same bu
                    client=client,
                    dateofbirth=date(1990, 1, 1)
                )

    def test_unique_peoplecode_bu_constraint(self, setup_test_data):
        """Test unique constraint on peoplecode and bu"""
        client, bu = setup_test_data

        # Create first people
        People.objects.create(
            peoplecode="UNIQUE001",
            peoplename="Test User 1",
            loginid="user1",
            email="test1@example.com",
            bu=bu,
            client=client,
            dateofbirth=date(1990, 1, 1)
        )

        # Try to create duplicate peoplecode with same bu
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                People.objects.create(
                    peoplecode="UNIQUE001",  # Same peoplecode
                    peoplename="Test User 2",
                    loginid="user2",
                    email="test2@example.com",
                    bu=bu,  # Same bu
                    client=client,
                    dateofbirth=date(1990, 1, 1)
                )


@pytest.mark.django_db
class TestPeopleModelRelationships:
    """Test foreign key relationships"""

    @pytest.fixture
    def setup_relationships(self, department_type_assist, designation_type_assist):
        """Setup test data for relationship testing"""
        # Create TypeAssist instances
        department = TypeAssist.objects.create(
            tacode="DEPT001",
            taname="Engineering",
            tatype=department_type_assist
        )
        designation = TypeAssist.objects.create(
            tacode="DESIG001",
            taname="Senior Engineer",
            tatype=designation_type_assist
        )

        # Create Location
        location = Location.objects.create(
            locationcode="LOC001",
            locationname="Head Office"
        )

        # Create manager
        manager = People.objects.create(
            peoplecode="MGR001",
            peoplename="Manager User",
            loginid="manager",
            email="manager@example.com",
            dateofbirth=date(1985, 1, 1)
        )

        return department, designation, location, manager

    def test_people_with_relationships(self, setup_relationships):
        """Test creating People with all relationships"""
        department, designation, location, manager = setup_relationships

        people = People.objects.create(
            peoplecode="TEST009",
            peoplename="Test Employee",
            loginid="employee001",
            email="employee@example.com",
            department=department,
            designation=designation,
            location=location,
            reportto=manager,
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2023, 1, 1)
        )

        assert people.department.taname == "Engineering"
        assert people.designation.taname == "Senior Engineer"
        assert people.location.locationname == "Head Office"
        assert people.reportto.peoplename == "Manager User"

    def test_self_referential_reportto(self):
        """Test self-referential reportto relationship"""
        # Create CEO who reports to themselves
        ceo = People.objects.create(
            peoplecode="CEO001",
            peoplename="CEO User",
            loginid="ceo",
            email="ceo@example.com",
            dateofbirth=date(1970, 1, 1)
        )

        # CEO can report to themselves
        ceo.reportto = ceo
        ceo.save()

        assert ceo.reportto == ceo

    def test_cascade_restrict_on_delete(self, setup_relationships):
        """Test that RESTRICT prevents deletion of referenced objects"""
        department, designation, location, manager = setup_relationships

        people = People.objects.create(
            peoplecode="TEST010",
            peoplename="Test Employee",
            loginid="employee002",
            email="employee2@example.com",
            department=department,
            dateofbirth=date(1990, 1, 1)
        )

        # Try to delete department that is referenced
        with pytest.raises(Exception):  # Will raise ProtectedError
            department.delete()


@pytest.mark.django_db
class TestPeopleModelPermissions:
    """Test permission-related fields and methods"""

    def test_admin_and_staff_flags(self):
        """Test isadmin and is_staff flags"""
        admin_user = People.objects.create(
            peoplecode="ADMIN001",
            peoplename="Admin User",
            loginid="admin",
            email="admin@example.com",
            isadmin=True,
            is_staff=True,
            dateofbirth=date(1980, 1, 1)
        )

        regular_user = People.objects.create(
            peoplecode="REG001",
            peoplename="Regular User",
            loginid="regular",
            email="regular@example.com",
            isadmin=False,
            is_staff=False,
            dateofbirth=date(1990, 1, 1)
        )

        assert admin_user.isadmin is True
        assert admin_user.is_staff is True
        assert regular_user.isadmin is False
        assert regular_user.is_staff is False

    def test_superuser_creation(self):
        """Test creating a superuser"""
        superuser = People.objects.create_superuser(
            loginid="superuser",
            peoplecode="SUPER001",
            peoplename="Super User",
            email="super@example.com",
            dateofbirth=date(1980, 1, 1),
            password="SuperSecure123!"
        )

        assert superuser.is_superuser is True
        assert superuser.is_staff is True


@pytest.mark.django_db
class TestPeopleModelBusinessLogic:
    """Test business logic and save method behavior"""

    def test_save_sets_default_values(self):
        """Test that save method sets default None values"""
        people = People(
            peoplecode="TEST011",
            peoplename="Test User",
            loginid="testuser011",
            email="test@example.com",
            dateofbirth=date(1990, 1, 1)
        )

        # Initially these should be None
        assert people.department is None
        assert people.designation is None
        assert people.peopletype is None
        assert people.worktype is None
        assert people.reportto is None

        # Save should set defaults
        people.save()

        # After save, defaults should be set (get_none_typeassist() values)
        assert people.department is not None
        assert people.designation is not None
        assert people.peopletype is not None
        assert people.worktype is not None
        assert people.reportto is not None

    def test_people_extras_json_field(self):
        """Test people_extras JSON field functionality"""
        extras_data = {
            "andriodversion": "12.0",
            "appversion": "2.1.0",
            "mobilecapability": ["GPS", "Camera"],
            "loacationtracking": True,
            "debug": False,
            "secondaryemails": ["alt1@example.com", "alt2@example.com"],
            "currentaddress": "123 Test Street"
        }

        people = People.objects.create(
            peoplecode="TEST012",
            peoplename="Test User",
            loginid="testuser012",
            email="test@example.com",
            dateofbirth=date(1990, 1, 1),
            people_extras=extras_data
        )

        # Refresh from database
        people.refresh_from_db()

        assert people.people_extras["andriodversion"] == "12.0"
        assert people.people_extras["appversion"] == "2.1.0"
        assert "GPS" in people.people_extras["mobilecapability"]
        assert people.people_extras["loacationtracking"] is True

    def test_enable_disable_people(self):
        """Test enable/disable functionality"""
        people = People.objects.create(
            peoplecode="TEST013",
            peoplename="Test User",
            loginid="testuser013",
            email="test@example.com",
            dateofbirth=date(1990, 1, 1),
            enable=True
        )

        assert people.enable is True

        # Disable the user
        people.enable = False
        people.save()

        people.refresh_from_db()
        assert people.enable is False


@pytest.mark.django_db
class TestPeopleModelAuthentication:
    """Test authentication-related functionality"""

    def test_authenticate_valid_user(self):
        """Test authenticating a valid user"""
        password = "ValidPass123!"
        people = People.objects.create_user(
            loginid="authuser001",
            peoplecode="AUTH001",
            peoplename="Auth User",
            email="auth@example.com",
            dateofbirth=date(1990, 1, 1),
            password=password
        )

        # Mark as verified for authentication
        people.isverified = True
        people.save()

        # Test authentication
        authenticated = authenticate(username="authuser001", password=password)
        assert authenticated is not None
        assert authenticated.id == people.id

    def test_authenticate_invalid_password(self):
        """Test authentication with invalid password"""
        people = People.objects.create_user(
            loginid="authuser002",
            peoplecode="AUTH002",
            peoplename="Auth User 2",
            email="auth2@example.com",
            dateofbirth=date(1990, 1, 1),
            password="ValidPass123!"
        )

        authenticated = authenticate(username="authuser002", password="WrongPassword")
        assert authenticated is None

    def test_authenticate_non_existent_user(self):
        """Test authentication with non-existent user"""
        authenticated = authenticate(username="nonexistent", password="anypassword")
        assert authenticated is None


@pytest.mark.django_db
class TestPeopleModelValidation:
    """Test model validation and edge cases"""

    def test_gender_choices_validation(self):
        """Test that gender field only accepts valid choices"""
        people = People(
            peoplecode="TEST014",
            peoplename="Test User",
            loginid="testuser014",
            email="test@example.com",
            gender="X",  # Invalid choice
            dateofbirth=date(1990, 1, 1)
        )

        # This should raise validation error when full_clean is called
        with pytest.raises(ValidationError):
            people.full_clean()

    def test_valid_gender_choices(self):
        """Test valid gender choices"""
        for gender in ["M", "F", "O"]:
            people = People.objects.create(
                peoplecode=f"TEST{gender}",
                peoplename="Test User",
                loginid=f"user{gender}",
                email=f"test{gender}@example.com",
                gender=gender,
                dateofbirth=date(1990, 1, 1)
            )
            assert people.gender == gender

    def test_date_validations(self):
        """Test date field validations"""
        # Test future date of birth (should be invalid in real scenario)
        future_date = date.today() + timedelta(days=365)

        people = People(
            peoplecode="TEST015",
            peoplename="Test User",
            loginid="testuser015",
            email="test@example.com",
            dateofbirth=future_date,  # Future date
            dateofjoin=date.today()
        )

        # Save should work (no built-in validation) but business logic should handle
        people.save()
        assert people.dateofbirth == future_date

    def test_email_format(self):
        """Test email field with various formats"""
        valid_emails = [
            "user@example.com",
            "user.name@example.co.uk",
            "user+tag@example.com",
            "user_name@sub.example.com"
        ]

        for i, email in enumerate(valid_emails):
            people = People.objects.create(
                peoplecode=f"EMAIL{i:03d}",
                peoplename="Test User",
                loginid=f"emailuser{i:03d}",
                email=email,
                dateofbirth=date(1990, 1, 1)
            )
            assert people.email == email


@pytest.mark.django_db
class TestPeopleModelQuerysets:
    """Test custom manager and queryset methods"""

    def test_people_manager_create_user(self):
        """Test PeopleManager create_user method"""
        people = People.objects.create_user(
            loginid="managertest001",
            peoplecode="MGR001",
            peoplename="Manager Test",
            email="manager@example.com",
            dateofbirth=date(1990, 1, 1),
            password="TestPass123!"
        )

        assert people.loginid == "managertest001"
        assert people.check_password("TestPass123!")

    def test_filter_by_client_and_bu(self, client_bt, bu_bt):
        """Test filtering people by client and bu"""
        # Use the fixtures provided
        client1 = client_bt
        bu1 = bu_bt

        # Create a second client and BU for comparison
        from apps.onboarding.models import TypeAssist
        client_type = client1.butype
        bu_type = bu1.butype

        client2 = Bt.objects.create(bucode="CL002", buname="Client 2", butype=client_type)
        bu2 = Bt.objects.create(bucode="BU002", buname="BU 2", butype=bu_type, parent=client2)

        # Create people in different clients/bus
        People.objects.create(
            peoplecode="P001",
            peoplename="Person 1",
            loginid="person1",
            email="p1@example.com",
            client=client1,
            bu=bu1,
            dateofbirth=date(1990, 1, 1)
        )

        People.objects.create(
            peoplecode="P002",
            peoplename="Person 2",
            loginid="person2",
            email="p2@example.com",
            client=client2,
            bu=bu2,
            dateofbirth=date(1990, 1, 1)
        )

        # Test filtering
        client1_people = People.objects.filter(client=client1)
        assert client1_people.count() == 1
        assert client1_people.first().peoplecode == "P001"

        bu2_people = People.objects.filter(bu=bu2)
        assert bu2_people.count() == 1
        assert bu2_people.first().peoplecode == "P002"


@pytest.mark.django_db
class TestPeopleModelPerformance:
    """Test performance-related aspects"""

    def test_bulk_create_people(self):
        """Test bulk creation of People records"""
        people_list = []
        for i in range(100):
            people_list.append(People(
                peoplecode=f"BULK{i:04d}",
                peoplename=f"Bulk User {i}",
                loginid=f"bulkuser{i:04d}",
                email=f"bulk{i}@example.com",
                dateofbirth=date(1990, 1, 1)
            ))

        # Bulk create
        created = People.objects.bulk_create(people_list)

        assert len(created) == 100
        assert People.objects.filter(peoplecode__startswith="BULK").count() == 100

    def test_select_related_optimization(self, client_bt, bu_bt):
        """Test query optimization with select_related"""
        # Create test data
        from apps.onboarding.models import TypeAssist
        department_type = TypeAssist.objects.create(
            tacode="DEPT_TYPE",
            taname="Department Type"
        )

        department = TypeAssist.objects.create(
            tacode="DEPT002",
            taname="IT Department",
            tatype=department_type
        )

        for i in range(5):
            People.objects.create(
                peoplecode=f"OPT{i:03d}",
                peoplename=f"Optimized User {i}",
                loginid=f"optuser{i:03d}",
                email=f"opt{i}@example.com",
                client=client_bt,
                bu=bu_bt,
                dateofbirth=date(1990, 1, 1)
            )

        # Test that select_related works with client and bu relationships
        people_optimized = list(
            People.objects.filter(peoplecode__startswith="OPT").select_related("client", "bu")
        )

        # Verify the optimization works by accessing related objects
        for person in people_optimized:
            # Access related objects to ensure they're loaded
            client_name = person.client.buname if person.client else None
            bu_name = person.bu.buname if person.bu else None
            assert client_name is not None
            assert bu_name is not None

        # Verify we have the expected number of people
        assert len(people_optimized) == 5