import datetime

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, \
    TimeField, HiddenField, TextAreaField, SubmitField
from wtforms.widgets.html5 import TimeInput
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired

from . import models, widgets


class GenerateDowntimeForm(FlaskForm):
    scheduled = SelectField("Scheduled (registered at least 48 hours in advance)",
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
    start_time = TimeField("&nbsp;", [InputRequired()]
                           #, widget=TimeInput()
                           )
    end_date = DateField("End Date/Time (UTC)", [InputRequired()])
    end_time = TimeField("&nbsp;", [InputRequired()]
                         #, widget=TimeInput()
                         )
    services = SelectMultipleField("Services (select one or more)", [InputRequired()], choices=[])

    facility = HiddenField()
    resource = SelectField("Resource", choices=[])
    change_resource = SubmitField("&nbsp;", render_kw={"value": "Change Resource"})

    yamloutput = TextAreaField(None, render_kw={"readonly": True,
                                                "style": "font-family:monospace; font-size:small;",
                                                "rows": "15"})

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
