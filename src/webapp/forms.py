import datetime
from typing import List

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, \
    TimeField, HiddenField
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired

from webapp.common import gen_id
from webapp.topology import Downtime


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
        start_time_str = Downtime.fmttime_preferred(self.get_start_datetime())
        end_time_str = Downtime.fmttime_preferred(self.get_end_datetime())
        created_time_str = Downtime.fmttime_preferred(created_datetime)
        dtid = gen_id(f"{created_time_str}{self.resource.data}", digits=11)
        services_text = self.get_services_text()

        return f"""\
- ID: {dtid}
  Description: {self.description.data}
  Class: {self.scheduled.data}
  Severity: {self.severity.data}
  StartTime: {start_time_str}
  EndTime: {end_time_str}
  CreatedTime: {created_time_str}
  ResourceName: {self.resource.data}
  Services: {services_text}
"""

class DowntimeResourceSelectForm(FlaskForm):
    facility = SelectField("Facility", [InputRequired()])
    resource = SelectField("Resource", [InputRequired()])
