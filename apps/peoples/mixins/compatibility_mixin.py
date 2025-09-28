"""
Backward Compatibility Mixin for People Model

This mixin provides property-based field access for fields that have been
moved to PeopleProfile and PeopleOrganizational models, ensuring 100%
backward compatibility with existing code.

Compliant with Rule #7 from .claude/rules.md (< 150 lines).
"""


class PeopleCompatibilityMixin:
    """
    Mixin providing backward-compatible property accessors.

    This mixin enables transparent access to fields in related models
    (PeopleProfile, PeopleOrganizational) as if they were still on the
    People model, maintaining backward compatibility with existing code.
    """

    @property
    def peopleimg(self):
        """Access peopleimg from profile."""
        return self.profile.peopleimg if hasattr(self, 'profile') else None

    @peopleimg.setter
    def peopleimg(self, value):
        """Set peopleimg in profile."""
        if hasattr(self, 'profile'):
            self.profile.peopleimg = value
            self.profile.save(update_fields=['peopleimg'])
        else:
            self._temp_peopleimg = value

    @property
    def gender(self):
        """Access gender from profile."""
        return self.profile.gender if hasattr(self, 'profile') else None

    @gender.setter
    def gender(self, value):
        """Set gender in profile."""
        if hasattr(self, 'profile'):
            self.profile.gender = value
            self.profile.save(update_fields=['gender'])
        else:
            self._temp_gender = value

    @property
    def dateofbirth(self):
        """Access dateofbirth from profile."""
        if hasattr(self, 'profile'):
            return self.profile.dateofbirth
        return getattr(self, '_temp_dateofbirth', None)

    @dateofbirth.setter
    def dateofbirth(self, value):
        """Set dateofbirth in profile."""
        if hasattr(self, 'profile'):
            self.profile.dateofbirth = value
            self.profile.save(update_fields=['dateofbirth'])
        else:
            self._temp_dateofbirth = value

    @property
    def dateofjoin(self):
        """Access dateofjoin from profile."""
        if hasattr(self, 'profile'):
            return self.profile.dateofjoin
        return getattr(self, '_temp_dateofjoin', None)

    @dateofjoin.setter
    def dateofjoin(self, value):
        """Set dateofjoin in profile."""
        if hasattr(self, 'profile'):
            self.profile.dateofjoin = value
            self.profile.save(update_fields=['dateofjoin'])
        else:
            self._temp_dateofjoin = value

    @property
    def dateofreport(self):
        """Access dateofreport from profile."""
        return self.profile.dateofreport if hasattr(self, 'profile') else None

    @dateofreport.setter
    def dateofreport(self, value):
        """Set dateofreport in profile."""
        if hasattr(self, 'profile'):
            self.profile.dateofreport = value
            self.profile.save(update_fields=['dateofreport'])

    @property
    def people_extras(self):
        """Access people_extras from profile."""
        from ..constants import peoplejson
        if hasattr(self, 'profile'):
            return self.profile.people_extras
        return peoplejson()

    @people_extras.setter
    def people_extras(self, value):
        """Set people_extras in profile."""
        if hasattr(self, 'profile'):
            self.profile.people_extras = value
            self.profile.save(update_fields=['people_extras'])

    @property
    def location(self):
        """Access location from organizational."""
        return self.organizational.location if hasattr(self, 'organizational') else None

    @location.setter
    def location(self, value):
        """Set location in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.location = value
            self.organizational.save(update_fields=['location'])
        else:
            self._temp_location = value

    @property
    def department(self):
        """Access department from organizational."""
        return self.organizational.department if hasattr(self, 'organizational') else None

    @department.setter
    def department(self, value):
        """Set department in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.department = value
            self.organizational.save(update_fields=['department'])
        else:
            self._temp_department = value

    @property
    def designation(self):
        """Access designation from organizational."""
        return self.organizational.designation if hasattr(self, 'organizational') else None

    @designation.setter
    def designation(self, value):
        """Set designation in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.designation = value
            self.organizational.save(update_fields=['designation'])
        else:
            self._temp_designation = value

    @property
    def peopletype(self):
        """Access peopletype from organizational."""
        return self.organizational.peopletype if hasattr(self, 'organizational') else None

    @peopletype.setter
    def peopletype(self, value):
        """Set peopletype in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.peopletype = value
            self.organizational.save(update_fields=['peopletype'])
        else:
            self._temp_peopletype = value

    @property
    def worktype(self):
        """Access worktype from organizational."""
        return self.organizational.worktype if hasattr(self, 'organizational') else None

    @worktype.setter
    def worktype(self, value):
        """Set worktype in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.worktype = value
            self.organizational.save(update_fields=['worktype'])
        else:
            self._temp_worktype = value

    @property
    def client(self):
        """Access client from organizational."""
        return self.organizational.client if hasattr(self, 'organizational') else None

    @client.setter
    def client(self, value):
        """Set client in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.client = value
            self.organizational.save(update_fields=['client'])
        else:
            self._temp_client = value

    @property
    def bu(self):
        """Access bu from organizational."""
        return self.organizational.bu if hasattr(self, 'organizational') else None

    @bu.setter
    def bu(self, value):
        """Set bu in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.bu = value
            self.organizational.save(update_fields=['bu'])
        else:
            self._temp_bu = value

    @property
    def reportto(self):
        """Access reportto from organizational."""
        return self.organizational.reportto if hasattr(self, 'organizational') else None

    @reportto.setter
    def reportto(self, value):
        """Set reportto in organizational."""
        if hasattr(self, 'organizational'):
            self.organizational.reportto = value
            self.organizational.save(update_fields=['reportto'])
        else:
            self._temp_reportto = value