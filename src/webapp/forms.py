import datetime

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, \
    TimeField, HiddenField
from wtforms.widgets.html5 import TimeInput
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired

from . import models


class GenerateDowntimeForm(FlaskForm):
    scheduled = SelectField("Scheduled", [InputRequired()], choices=[
        ("SCHEDULED", "Yes"),
        ("UNSCHEDULED", "No"),
    ])
    severity = SelectField("Severity", [InputRequired()], choices=[
        ("Outage", "Outage (completely inaccessible)"),
        ("Severe", "Severe (most services down)"),
        ("Intermittent Outage", "Intermittent Outage (may be up for some of the time)"),
        ("No Significant Outage Expected", "No Significant Outage Expected (you shouldn't notice)")
    ])
    description = StringField("Description", [InputRequired()])
    start_date = DateField("Start Date", [InputRequired()])
    start_time = TimeField("Start Time", [InputRequired()], widget=TimeInput())
    end_date = DateField("End Date", [InputRequired()])
    end_time = TimeField("End Time", [InputRequired()], widget=TimeInput())
    services = SelectMultipleField("Services", [InputRequired()], choices=[])
    resource = HiddenField("Resource")

    class Meta:
        csrf = False  # CSRF not needed because no data gets modified

    # https://stackoverflow.com/a/21815180
    def validate(self):
        if not super().validate():
            return False
        if self.start_date.data > self.end_date.data:
            self.end_date.errors.append("End date/time must be after start date/time")
            return False
        elif self.start_date.data == self.end_date.data:
            if self.start_time.data >= self.end_time.data:
                self.end_time.errors.append("End date/time must be after start date/time")
                return False
        return True

    def get_start_datetime(self):
        return datetime.datetime.combine(self.start_date.data, self.start_time.data)

    def get_end_datetime(self):
        return datetime.datetime.combine(self.end_date.data, self.end_time.data)

    def get_yaml(self) -> str:
        return models.get_downtime_yaml(
            start_datetime=self.get_start_datetime(),
            end_datetime=self.get_end_datetime(),
            created_datetime=datetime.datetime.utcnow(),
            description=self.description.data,
            severity=self.severity.data,
            class_=self.scheduled.data,
            resource_name=self.resource.data,
            services=self.services.data,
        )


class DowntimeResourceSelectForm(FlaskForm):
    facility = SelectField("Facility", [InputRequired()])
    resource = SelectField("Resource", [InputRequired()])
