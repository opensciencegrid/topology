from wtforms.widgets import html_params, HTMLString, TextInput
from wtforms.widgets.core import escape_html


class BootstrapTextInput(TextInput):
    """
    Render a basic ``<input>`` field with bootstrap classes attached to it.

    This is used as the basis for most of the other input fields.

    By default, the `_value()` method will be called upon the associated field
    to provide the ``value=`` HTML attribute.
    """
    html_params = staticmethod(html_params)

    def __init__(self, helptext=None):
        super().__init__("text")
        self.helptext = helptext

    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        kwargs.setdefault('type', self.input_type)
        if 'value' not in kwargs:
            kwargs['value'] = field._value()
        if 'required' not in kwargs and 'required' in getattr(field, 'flags', []):
            kwargs['required'] = True
        helpid = field.id + "Help"
        kwargs['aria-describedby'] = helpid
        return HTMLString('<input %s><small %s class="form-text text-muted">%s</small>' % (self.html_params(name=field.name, **kwargs),
                                                                                           self.html_params(id=helpid),
                                                                                           escape_html(self.helptext)))
