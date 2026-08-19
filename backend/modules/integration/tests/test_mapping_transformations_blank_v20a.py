from modules.integration.models import DataMappingProfile


def test_data_mapping_transformations_accept_empty_list():
    field = DataMappingProfile._meta.get_field("transformations")
    assert field.blank is True
    assert field.default is list
