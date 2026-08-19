param([Parameter(Mandatory = $true)][string]$TargetProject)
$ErrorActionPreference = "Stop"
$backend = Join-Path ([System.IO.Path]::GetFullPath($TargetProject)) "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"
if (-not (Test-Path $python -PathType Leaf)) { $python = "python" }
Push-Location $backend
try {
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw "Django system check failed." }
    & $python manage.py shell -c "from modules.salesops.models import SalesPolicyVersion, DevelopmentInventory, SaleableUnit, BuyerAccount, UnitReservation, BookingAgreement, PaymentMilestone, CollectionReceipt, BrokerCommission, CustomerHandover; print({'policies': SalesPolicyVersion.objects.count(), 'developments': DevelopmentInventory.objects.count(), 'units': SaleableUnit.objects.count(), 'buyers': BuyerAccount.objects.count(), 'reservations': UnitReservation.objects.count(), 'bookings': BookingAgreement.objects.count(), 'milestones': PaymentMilestone.objects.count(), 'receipts': CollectionReceipt.objects.count(), 'commissions': BrokerCommission.objects.count(), 'handovers': CustomerHandover.objects.count()})"
    if ($LASTEXITCODE -ne 0) { throw "Could not inspect Phase 42 records." }
    Write-Host "[SUCCESS] Phase 42 development sales readiness verified." -ForegroundColor Green
} finally { Pop-Location }
