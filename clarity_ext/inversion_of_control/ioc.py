class InversionOfControl(object):
    def __init__(self):
        self._app = None

    def set_application(self, app):
        self._app = app

    @property
    def app(self):
        if self._app is None:
            raise ValueError(
                'Inversion of control is not initialized. '
                '(It needs to be initialized with an application service)')
        return self._app


ioc = InversionOfControl()
