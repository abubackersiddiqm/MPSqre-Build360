from django.test import override_settings

from modules.accessops.api.views import invitation_link_material_allowed


@override_settings(BUILD360_ENVIRONMENT="development")
def test_development_may_expose_inline_invitation_material():
    assert invitation_link_material_allowed() is True


@override_settings(BUILD360_ENVIRONMENT="demo")
def test_demo_may_expose_inline_invitation_material():
    assert invitation_link_material_allowed() is True


@override_settings(BUILD360_ENVIRONMENT="testing")
def test_testing_never_exposes_invitation_material():
    assert invitation_link_material_allowed() is False


@override_settings(BUILD360_ENVIRONMENT="production")
def test_production_never_exposes_invitation_material():
    assert invitation_link_material_allowed() is False
