# CRM production gates

Run the technical tenant gate:

```bat
call ops\crm\Verify-CRM-Production-Readiness.bat "D:\MPSqre\MPSqre_Build360" COMPANY_CODE
```

Create pre-deployment backup evidence:

```bat
call ops\crm\Create-CRM-PreDeploy-Backup.bat "D:\MPSqre\MPSqre_Build360"
```

Then complete `CRM-UAT-CHECKLIST.md`. Automated validation does not constitute production approval by itself.
