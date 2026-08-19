from modules.integration.models import MetaLeadReceipt


def test_meta_receipt_field_names_allows_empty_list_contract():
    field = MetaLeadReceipt._meta.get_field("field_names")
    assert field.blank is True
    assert field.default() == []
