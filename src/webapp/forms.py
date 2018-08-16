import datetime
from typing import List

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, \
    TimeField, HiddenField
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired

from webapp.common import gen_id


class GenerateDowntimeForm(FlaskForm):
    scheduled = BooleanField("Scheduled", None)  # default="checked" does not do anything
    severity = SelectField("Severity", [InputRequired()], choices=[
        ("Outage", "Outage (completely inaccessible)"),
        ("Severe", "Severe (most services down)"),
        ("Intermittent Outage", "Intermittent Outage (may be up for some of the time)"),
        ("No Significant Outage Expected", "No Significant Outage Expected (you shouldn't notice)")
    ])
    description = StringField("Description", [InputRequired()])
    start_date = DateField("Start Date", [InputRequired()])
    start_time = TimeField("Start Time", [InputRequired()])
    end_date = DateField("End Date", [InputRequired()])
    end_time = TimeField("End Time", [InputRequired()])
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

    def get_services_text(self):
        return "\n  - " + "\n  - ".join(self.services.data)

    def get_yaml(self) -> str:
        created_datetime = datetime.datetime.utcnow()
        dtid = gen_id(f"{created_datetime.timestamp()}{self.resource.data}")
        dtclass = "SCHEDULED" if self.scheduled.data else "UNSCHEDULED"
        services_text = self.get_services_text()

        return f"""\
- ID: {dtid}
  Description: {self.description.data}
  Class: {dtclass}
  Severity: {self.severity.data}
  StartTime: {self.get_start_datetime():%Y-%m-%d %H:%M} +0000
  EndTime: {self.get_end_datetime():%Y-%m-%d %H:%M} +0000
  CreatedTime: {created_datetime:%Y-%m-%d %H:%M} +0000
  ResourceName: {self.resource.data}
  Services: {services_text}
"""


class DowntimeResourceSelectForm(FlaskForm):
    facility = SelectField("Facility", [InputRequired()])
    resource = SelectField("Resource", [InputRequired()])

