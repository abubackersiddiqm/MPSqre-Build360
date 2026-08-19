from django.db import migrations

PERMISSIONS=[
("vendor.stage.read","Read configurable supply stages"),("vendor.stage.manage","Manage configurable supply stages"),("vendor.dashboard.read","Read vendor dashboard"),("vendor.vendor.read","Read vendors"),("vendor.vendor.manage","Create and update vendors"),("vendor.qualification.read","Read vendor qualifications"),("vendor.qualification.decide","Decide vendor qualifications"),
("procurement.dashboard.read","Read procurement dashboard"),("procurement.request.read","Read purchase requests"),("procurement.request.manage","Create purchase requests"),("procurement.request.transition","Transition purchase requests"),("procurement.rfq.read","Read RFQs"),("procurement.rfq.manage","Create and issue RFQs"),("procurement.quote.read","Read vendor quotes"),("procurement.quote.manage","Capture vendor quotes"),("procurement.award.decide","Award vendor quotes"),("procurement.po.read","Read purchase orders"),("procurement.po.manage","Manage purchase orders"),("procurement.receipt.read","Read goods receipts"),("procurement.receipt.manage","Create goods receipts"),("procurement.receipt.post","Post goods receipts"),
("inventory.dashboard.read","Read inventory dashboard"),("inventory.item.read","Read inventory items"),("inventory.item.manage","Manage inventory items"),("inventory.warehouse.read","Read warehouses"),("inventory.warehouse.manage","Manage warehouses"),("inventory.stock.read","Read stock balances"),("inventory.ledger.read","Read stock ledger"),("inventory.movement.post","Post stock movements")]

def create_permissions(apps,schema_editor):
    permission=apps.get_model("identity","Permission")
    for code,description in PERMISSIONS: permission.objects.get_or_create(code=code,defaults={"description":description,"data_class":"supply"})

def delete_permissions(apps,schema_editor):
    apps.get_model("identity","Permission").objects.filter(code__in=[code for code,_ in PERMISSIONS]).delete()

class Migration(migrations.Migration):
    dependencies=[("identity","0005_phase5_delivery_permissions")]
    operations=[migrations.RunPython(create_permissions,delete_permissions)]
