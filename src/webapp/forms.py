import datetime

import yaml
from flask_wtf import FlaskForm
from wtforms import SelectField, SelectMultipleField, StringField, \
    TextAreaField, SubmitField
from wtforms.fields.html5 import TimeField, DateField
from wtforms.validators import InputRequired, ValidationError

from . import models

UTCOFFSET_CHOICES = [
    ('-840', '+14:00'),
    ('-825', '+13:45'),
    ('-810', '+13:30'),
    ('-795', '+13:15'),
    ('-780', '+13:00'),
    ('-765', '+12:45'),
    ('-750', '+12:30'),
    ('-735', '+12:15'),
    ('-720', '+12:00'),
    ('-705', '+11:45'),
    ('-690', '+11:30'),
    ('-675', '+11:15'),
    ('-660', '+11:00'),
    ('-645', '+10:45'),
    ('-630', '+10:30'),
    ('-615', '+10:15'),
    ('-600', '+10:00'),
    ('-585', '+9:45'),
    ('-570', '+9:30'),
    ('-555', '+9:15'),
    ('-540', '+9:00'),
    ('-525', '+8:45'),
    ('-510', '+8:30'),
    ('-495', '+8:15'),
    ('-480', '+8:00'),
    ('-465', '+7:45'),
    ('-450', '+7:30'),
    ('-435', '+7:15'),
    ('-420', '+7:00'),
    ('-405', '+6:45'),
    ('-390', '+6:30'),
    ('-375', '+6:15'),
    ('-360', '+6:00'),
    ('-345', '+5:45'),
    ('-330', '+5:30'),
    ('-315', '+5:15'),
    ('-300', '+5:00'),
    ('-285', '+4:45'),
    ('-270', '+4:30'),
    ('-255', '+4:15'),
    ('-240', '+4:00'),
    ('-225', '+3:45'),
    ('-210', '+3:30'),
    ('-195', '+3:15'),
    ('-180', '+3:00'),
    ('-165', '+2:45'),
    ('-150', '+2:30'),
    ('-135', '+2:15'),
    ('-120', '+2:00'),
    ('-105', '+1:45'),
    ('-90', '+1:30'),
    ('-75', '+1:15'),
    ('-60', '+1:00'),
    ('-45', '+0:45'),
    ('-30', '+0:30'),
    ('-15', '+0:15'),
    ('0', '-0:00'),
    ('15', '-0:15'),
    ('30', '-0:30'),
    ('45', '-0:45'),
    ('60', '-1:00'),
    ('75', '-1:15'),
    ('90', '-1:30'),
    ('105', '-1:45'),
    ('120', '-2:00'),
    ('135', '-2:15'),
    ('150', '-2:30'),
    ('165', '-2:45'),
    ('180', '-3:00'),
    ('195', '-3:15'),
    ('210', '-3:30'),
    ('225', '-3:45'),
    ('240', '-4:00'),
    ('255', '-4:15'),
    ('270', '-4:30'),
    ('285', '-4:45'),
    ('300', '-5:00'),
    ('315', '-5:15'),
    ('330', '-5:30'),
    ('345', '-5:45'),
    ('360', '-6:00'),
    ('375', '-6:15'),
    ('390', '-6:30'),
    ('405', '-6:45'),
    ('420', '-7:00'),
    ('435', '-7:15'),
    ('450', '-7:30'),
    ('465', '-7:45'),
    ('480', '-8:00'),
    ('495', '-8:15'),
    ('510', '-8:30'),
    ('525', '-8:45'),
    ('540', '-9:00'),
    ('555', '-9:15'),
    ('570', '-9:30'),
    ('585', '-9:45'),
    ('600', '-10:00'),
    ('615', '-10:15'),
    ('630', '-10:30'),
    ('645', '-10:45'),
    ('660', '-11:00'),
    ('675', '-11:15'),
    ('690', '-11:30'),
    ('705', '-11:45'),
    ('720', '-12:00')
]

class GenerateResourceGroupDowntimeForm(FlaskForm):
    scheduled = SelectField("Scheduled (registered at least 24 hours in advance)",
                            [InputRequired()], choices=[
        ("", "-- Select one --"),
        ("SCHEDULED", "Yes"),
        ("UNSCHEDULED", "No"),
    ])
    severity = SelectField("Severity (how much of the resource group is affected)", [InputRequired()], choices=[
        ("", "-- Select one --"),
        ("Outage", "Outage (completely inaccessible)"),
        ("Severe", "Severe (most services down)"),
        ("Intermittent Outage", "Intermittent Outage (may be up for some of the time)"),
        ("No Significant Outage Expected", "No Significant Outage Expected (you shouldn't notice)")
    ])
    description = StringField("Description (the reason and/or impact of the outage)", [InputRequired()])

    start_date = DateField("Local Start Date", validators=[InputRequired()])
    start_time = TimeField("Local Start Time", validators=[InputRequired()])
    end_date = DateField("Local End Date", validators=[InputRequired()])
    end_time = TimeField("Local End Time", validators=[InputRequired()])

    utc_offset = SelectField("UTC Offset", choices=UTCOFFSET_CHOICES)

    facility = SelectField("Facility", choices=[], default="")
    change_facility = SubmitField()
    site = SelectField("Site", choices=[], default="")
    change_site = SubmitField()
    resource_group = SelectField("Resource Group", choices=[], default="")
    change_resource_group = SubmitField()

    generate = SubmitField()

    yamloutput = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "10"})

    class Meta:
        csrf = False  # CSRF not needed because no data gets modified

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.infos = ""

    # https://stackoverflow.com/a/21815180
    def validate(self):
        self.infos = ""

        if not super().validate():
            return False
        if self.get_start_datetime() > self.get_end_datetime():
            self.end_date.errors.append("End date/time must be after start date/time")
            return False

        days_in_future = (self.get_start_datetime() - datetime.datetime.utcnow()).days
        if days_in_future < 1 and self.scheduled.data == "SCHEDULED":
            self.infos += "Note: Downtime registered less than one day in advance " \
                          "is considered unscheduled by WLCG policy."
        elif days_in_future >= 1 and self.scheduled.data == "UNSCHEDULED":
            self.infos += "Note: Downtime registered at least one day in advance " \
                          "is considered scheduled by WLCG policy."

        return True

    def get_start_datetime(self):
        return datetime.datetime.combine(
            self.start_date.data, self.start_time.data
        ) + datetime.timedelta(minutes=int(self.utc_offset.data))

    def get_end_datetime(self):
        return datetime.datetime.combine(
            self.end_date.data, self.end_time.data
        ) + datetime.timedelta(minutes=int(self.utc_offset.data))

    def get_yaml(self, resources, service_names_by_resource) -> str:

        created_datetime = datetime.datetime.utcnow()
        dtid = models._dtid(created_datetime)

        yaml = ""
        for index, resource in enumerate(resources):
            yaml += models.get_downtime_yaml(
                id=dtid+index,
                start_datetime=self.get_start_datetime(),
                end_datetime=self.get_end_datetime(),
                created_datetime=created_datetime,
                description=self.description.data,
                severity=self.severity.data,
                class_=self.scheduled.data,
                resource_name=resource,
                services=service_names_by_resource[resource],
            )

        return yaml


class GenerateDowntimeForm(FlaskForm):
    scheduled = SelectField("Scheduled (registered at least 24 hours in advance)",
                            [InputRequired()], choices=[
        ("", "-- Select one --"),
        ("SCHEDULED", "Yes"),
        ("UNSCHEDULED", "No"),
    ])
    severity = SelectField("Severity (how much of the resource is affected)", [InputRequired()], choices=[
        ("", "-- Select one --"),
        ("Outage", "Outage (completely inaccessible)"),
        ("Severe", "Severe (most services down)"),
        ("Intermittent Outage", "Intermittent Outage (may be up for some of the time)"),
        ("No Significant Outage Expected", "No Significant Outage Expected (you shouldn't notice)")
    ])
    description = StringField("Description (the reason and/or impact of the outage)", [InputRequired()])

    start_date = DateField("Local Start Date", validators=[InputRequired()])
    start_time = TimeField("Local Start Time", validators=[InputRequired()])
    end_date = DateField("Local End Date", validators=[InputRequired()])
    end_time = TimeField("Local End Time", validators=[InputRequired()])

    utc_offset = SelectField("UTC Offset", choices=UTCOFFSET_CHOICES)

    services = SelectMultipleField("Known OSG Services (select one or more)", [InputRequired()], choices=[])

    facility = SelectField("Facility", choices=[])
    change_facility = SubmitField()
    resource = SelectField("Resource", choices=[])
    change_resource = SubmitField()

    generate = SubmitField()

    yamloutput = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "10"})

    class Meta:
        csrf = False  # CSRF not needed because no data gets modified

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.infos = ""

    # https://stackoverflow.com/a/21815180
    def validate(self):
        self.infos = ""

        if not super().validate():
            return False
        if self.get_start_datetime() > self.get_end_datetime():
            self.end_date.errors.append("End date/time must be after start date/time")
            return False

        days_in_future = (self.get_start_datetime() - datetime.datetime.utcnow()).days
        if days_in_future < 1 and self.scheduled.data == "SCHEDULED":
            self.infos += "Note: Downtime registered less than one day in advance " \
                             "is considered unscheduled by WLCG policy."
        elif days_in_future >= 1 and self.scheduled.data == "UNSCHEDULED":
            self.infos += "Note: Downtime registered at least one day in advance " \
                             "is considered scheduled by WLCG policy."

        return True

    def get_start_datetime(self):
        return datetime.datetime.combine(
            self.start_date.data, self.start_time.data
        ) + datetime.timedelta(minutes=int(self.utc_offset.data))

    def get_end_datetime(self):
        return datetime.datetime.combine(
            self.end_date.data, self.end_time.data
        ) + datetime.timedelta(minutes=int(self.utc_offset.data))

    def get_yaml(self) -> str:

        created_datetime = datetime.datetime.utcnow()
        dtid = models._dtid(created_datetime)

        return models.get_downtime_yaml(
            id=dtid,
            start_datetime=self.get_start_datetime(),
            end_datetime=self.get_end_datetime(),
            created_datetime=created_datetime,
            description=self.description.data,
            severity=self.severity.data,
            class_=self.scheduled.data,
            resource_name=self.resource.data,
            services=self.services.data,
        )


class GenerateProjectForm(FlaskForm):
    project_name = StringField("Project Name", [InputRequired()])
    pi_first_name = StringField("PI First Name", [InputRequired()])
    pi_last_name = StringField("PI Last Name", [InputRequired()])
    pi_department_or_organization = StringField("PI Department or Organization", [InputRequired()])
    pi_institution = StringField("PI Institution", [InputRequired()])
    field_of_science = SelectField("Field of Science", [InputRequired()])

    description = TextAreaField(None, render_kw={
        "style": "font-family:monospace; font-size:small;",
        "rows": "5"
    })

    yaml_output = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "10"})

    auto_submit = SubmitField("Login to Github to Submit Automatically")
    manual_submit = SubmitField("Submit Manually")

    class Meta:
        csrf = True  # CSRF not needed because no data gets modified

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.project_name.data = kwargs.get("project_name", self.project_name.data)
        self.pi_first_name.data = kwargs.get("pi_first_name", self.pi_first_name.data)
        self.pi_last_name.data = kwargs.get("pi_last_name", self.pi_last_name.data)
        self.pi_department_or_organization.data = kwargs.get("pi_department_or_organization", self.pi_department_or_organization.data)
        self.pi_institution.data = kwargs.get("pi_institution", self.pi_institution.data)
        self.field_of_science.data = kwargs.get("field_of_science", self.field_of_science.data)
        self.description.data = kwargs.get("description", self.description.data)

        self.infos = ""

    def validate_project_name(form, field):
        if not set(field.data).isdisjoint(set('/<>:"\\|?* ')):
            intersection = set(field.data).intersection(set('/<>:\"\\|?* '))
            raise ValidationError(f"Must be valid filename, invalid chars: {','.join(intersection)}")

    def get_yaml(self) -> str:
        return yaml.dump({
            "Description": self.description.data,
            "FieldOfScience": self.field_of_science.data,
            "Department": self.pi_department_or_organization.data,
            "Organization": self.pi_institution.data,
            "PIName": f"{self.pi_first_name.data} {self.pi_last_name.data}"
        })

    def as_dict(self):
        return {
            "description": self.description.data,
            "field_of_science": self.field_of_science.data,
            "pi_department_or_organization": self.pi_department_or_organization.data,
            "pi_institution": self.pi_institution.data,
            "pi_first_name": self.pi_first_name.data,
            "pi_last_name": self.pi_last_name.data,
            "pi_name": f"{self.pi_first_name.data} {self.pi_last_name.data}",
            "project_name": self.project_name.data
        }

    def clear(self):
        self.project_name.data = ""
        self.pi_first_name.data = ""
        self.pi_last_name.data = ""
        self.pi_department_or_organization.data = ""
        self.pi_institution.data = ""
        self.field_of_science.data = ""
        self.description.data = ""