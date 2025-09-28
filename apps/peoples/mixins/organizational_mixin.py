"""
Organizational query helper mixin for PeopleOrganizational model.

This mixin provides query optimization helpers and organizational
relationship methods to keep the PeopleOrganizational model under
the 150-line limit (Rule #7).
"""


class OrganizationalQueryMixin:
    """
    Mixin providing organizational query helpers and relationship methods.

    This mixin adds query optimization helpers and convenience methods
    for working with organizational relationships while keeping the
    main model file focused and concise.

    Methods:
        get_team_members: Get all people reporting to this user
        get_department_colleagues: Get colleagues in the same department
        get_location_colleagues: Get colleagues at the same location
        is_in_same_business_unit: Check if in same business unit as another user
        get_reporting_chain: Get the full reporting chain up to top
    """

    def get_team_members(self):
        """
        Get all people who report directly to this user.

        Returns:
            QuerySet: People who have this user as their reportto

        Example:
            team = manager.get_team_members()
            for member in team:
                print(f"{member.peoplename} reports to {manager.peoplename}")
        """
        if not hasattr(self, 'organizat

ional'):
            return self.__class__.objects.none()

        from ..models.user_model import People
        return People.objects.filter(
            organizational__reportto=self
        ).select_related(
            'organizational__department',
            'organizational__designation'
        )

    def get_department_colleagues(self):
        """
        Get all colleagues in the same department.

        Returns:
            QuerySet: People in the same department (excluding self)

        Example:
            colleagues = user.get_department_colleagues()
        """
        if not hasattr(self, 'organizational') or not self.organizational:
            return self.__class__.objects.none()

        if not self.organizational.department:
            return self.__class__.objects.none()

        from ..models.user_model import People
        return People.objects.filter(
            organizational__department=self.organizational.department
        ).exclude(id=self.id).select_related(
            'organizational__designation',
            'organizational__location'
        )

    def get_location_colleagues(self):
        """
        Get all colleagues at the same location.

        Returns:
            QuerySet: People at the same location (excluding self)

        Example:
            local_team = user.get_location_colleagues()
        """
        if not hasattr(self, 'organizational') or not self.organizational:
            return self.__class__.objects.none()

        if not self.organizational.location:
            return self.__class__.objects.none()

        from ..models.user_model import People
        return People.objects.filter(
            organizational__location=self.organizational.location
        ).exclude(id=self.id).select_related(
            'organizational__department',
            'organizational__designation'
        )

    def is_in_same_business_unit(self, other_user):
        """
        Check if this user is in the same business unit as another user.

        Args:
            other_user: Another People instance to compare with

        Returns:
            bool: True if in same business unit, False otherwise

        Example:
            if user1.is_in_same_business_unit(user2):
                # They can collaborate on shared resources
        """
        if not hasattr(self, 'organizational') or not self.organizational:
            return False

        if not hasattr(other_user, 'organizational') or not other_user.organizational:
            return False

        return (
            self.organizational.bu_id == other_user.organizational.bu_id
            and self.organizational.bu_id is not None
        )

    def get_reporting_chain(self):
        """
        Get the full reporting chain from this user up to the top.

        Returns:
            list: List of People instances representing the reporting chain

        Example:
            chain = employee.get_reporting_chain()
            # [employee, supervisor, manager, director, ...]
        """
        chain = [self]
        current = self

        # Prevent infinite loops with a max depth
        max_depth = 10
        depth = 0

        while depth < max_depth:
            if not hasattr(current, 'organizational') or not current.organizational:
                break

            if not current.organizational.reportto:
                break

            next_manager = current.organizational.reportto
            if next_manager in chain:
                # Circular reference detected, stop
                break

            chain.append(next_manager)
            current = next_manager
            depth += 1

        return chain

    def get_organizational_summary(self):
        """
        Get a summary dictionary of organizational information.

        Returns:
            dict: Organizational information summary

        Example:
            summary = user.get_organizational_summary()
            # {
            #     'department': 'Engineering',
            #     'designation': 'Senior Developer',
            #     'location': 'Building A',
            #     'business_unit': 'Tech Solutions',
            #     'reports_to': 'John Manager',
            #     'team_size': 5
            # }
        """
        if not hasattr(self, 'organizational') or not self.organizational:
            return {}

        org = self.organizational
        summary = {
            'department': org.department.tname if org.department else None,
            'designation': org.designation.tname if org.designation else None,
            'location': org.location.locationname if org.location else None,
            'business_unit': org.bu.buname if org.bu else None,
            'reports_to': org.reportto.peoplename if org.reportto else None,
            'team_size': self.get_team_members().count() if hasattr(self, 'get_team_members') else 0,
        }

        return summary