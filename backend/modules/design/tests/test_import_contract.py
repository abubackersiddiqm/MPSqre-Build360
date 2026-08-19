from modules.design.api import views as design_views
from modules.projects.application.services import available_transitions


def test_design_api_uses_project_owned_available_transitions() -> None:
    assert design_views.available_transitions is available_transitions
