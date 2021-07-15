import datetime

from flask_wtf import FlaskForm
from wtforms import SelectField, SelectMultipleField, StringField, \
    TimeField, TextAreaField, SubmitField
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired

from . import models

class GenerateSiteDowntimeForm(FlaskForm):
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

    start_date = DateField("Start Date/Time (UTC)", [InputRequired()])
    start_time = TimeField("&nbsp;", [InputRequired()])
    end_date = DateField("End Date/Time (UTC)", [InputRequired()])
    end_time = TimeField("&nbsp;", [InputRequired()])

    facility = SelectField("Facility", choices=[], default="")
    change_facility = SubmitField()
    site = SelectField("Site", choices=[], default="")
    change_site = SubmitField()
    resource_group = SelectField("Resource Group", choices=[], default="")
    change_resource_group = SubmitField()

    generate = SubmitField()

    yamloutput = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "15"})

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
        if self.start_date.data > self.end_date.data:
            self.end_date.errors.append("End date/time must be after start date/time")
            return False
        elif self.start_date.data == self.end_date.data:
            if self.start_time.data >= self.end_time.data:
                self.end_time.errors.append("End date/time must be after start date/time")
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
        return datetime.datetime.combine(self.start_date.data, self.start_time.data)

    def get_end_datetime(self):
        return datetime.datetime.combine(self.end_date.data, self.end_time.data)

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

    start_date = DateField("Start Date/Time (UTC)", [InputRequired()])
    start_time = TimeField("&nbsp;", [InputRequired()])
    end_date = DateField("End Date/Time (UTC)", [InputRequired()])
    end_time = TimeField("&nbsp;", [InputRequired()])
    services = SelectMultipleField("Known OSG Services (select one or more)", [InputRequired()], choices=[])

    facility = SelectField("Facility", choices=[])
    change_facility = SubmitField()
    resource = SelectField("Resource", choices=[])
    change_resource = SubmitField()

    generate = SubmitField()

    yamloutput = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "15"})

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
        if self.start_date.data > self.end_date.data:
            self.end_date.errors.append("End date/time must be after start date/time")
            return False
        elif self.start_date.data == self.end_date.data:
            if self.start_time.data >= self.end_time.data:
                self.end_time.errors.append("End date/time must be after start date/time")
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
        return datetime.datetime.combine(self.start_date.data, self.start_time.data)

    def get_end_datetime(self):
        return datetime.datetime.combine(self.end_date.data, self.end_time.data)

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
