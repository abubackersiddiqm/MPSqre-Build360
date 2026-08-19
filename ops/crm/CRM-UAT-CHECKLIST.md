# Build360 Universal CRM — Production UAT Checklist

Do not mark CRM production-approved from automated tests alone. Complete this checklist with one real test company and one restricted test user.

## 1. Tenant and SaaS boundary
- [ ] CRM Core enabled company can open CRM.
- [ ] CRM Core disabled company receives 403 from direct CRM API access.
- [ ] CRM Automation tab appears only when `crm.automation` is enabled and user has `crm.automation.read`.
- [ ] Construction project conversion is absent/blocked when `module.delivery` is disabled.

## 2. Permission boundary
- [ ] Normal Company User does not see CRM Setup, even if operational CRM configuration data is readable for rendering.
- [ ] Company Admin with `access.user.manage` + `crm.configuration.read` sees CRM Setup.
- [ ] CRM Setup changes require both `access.user.manage` and `crm.configuration.manage`; direct API mutation by a non-admin is rejected.
- [ ] User without `crm.contact_center.use` cannot open Contact Center timeline.
- [ ] User with Contact Center permission but without `crm.contact.reveal` still sees masked phone/email only.
- [ ] Automation read-only user can see rules/history but cannot create, edit, activate or pause rules.

## 3. Protected contact security
- [ ] Contact list shows masked phone/email.
- [ ] Call reveal returns phone only; email is not returned.
- [ ] Email reveal returns email only; phone is not returned.
- [ ] Unsupported reveal reasons are rejected.
- [ ] Reveal response has `Cache-Control: no-store`.
- [ ] Repeated reveal traffic is throttled according to `CRM_CONTACT_REVEAL_THROTTLE_RATE`.
- [ ] Audit evidence records who revealed the contact and why.

## 4. Universal CRM business flow
- [ ] Create contact.
- [ ] Create lead and required custom fields are enforced.
- [ ] Move lead through allowed stages only.
- [ ] Convert qualified lead without duplicating the contact.
- [ ] Create opportunity and move through allowed stages.
- [ ] Create call / WhatsApp / email / meeting activity and capture outcome.
- [ ] Follow-up appears in activity history.

## 5. Automation
- [ ] Create `Lead created -> Create task` rule.
- [ ] Matching lead creates exactly one task.
- [ ] Re-processing same event does not create a duplicate task.
- [ ] Failed automation records FAILED evidence without rolling back the lead.
- [ ] `No answer -> follow-up` rule creates the expected follow-up.

## 6. White label and account UX
- [ ] White-label company admin sees tenant branding configuration when entitled.
- [ ] Normal company user does not see SaaS/platform controls.
- [ ] Single-company user enters company directly after sign-in.
- [ ] Multi-company user sees company selection only when needed.
- [ ] Super Admin and tenant user remain logged in simultaneously in the same browser profile.

## 7. Production UX
- [ ] People and Companies screens contain only user-facing business language; no implementation notes such as card-wall/layout explanations are visible.
- [ ] Normal users are told to contact their company administrator when pipeline setup is incomplete; they are not directed to hidden admin screens.
- [ ] Company Admin can open CRM Setup and save a controlled configuration change.

## 8. Release evidence
- [ ] Backend targeted validation passed.
- [ ] Frontend targeted validation passed.
- [ ] Frontend production build passed.
- [ ] Full regression passed or approved exceptions are documented.
- [ ] Pre-deployment backup created and SHA evidence saved.
- [ ] Restore procedure is known/tested for the target environment.
- [ ] UAT owner, date and production approval are recorded outside this checklist.

## 9. AI Sales Copilot
- [ ] Relationship 360 shows `AI Copilot` only when an active lead exists, the tenant AI entitlement is enabled and the user has governed CRM AI read permission.
- [ ] `AI Prep` opens the same person's AI workspace without leaving Relationship 360.
- [ ] English is the default language.
- [ ] Tanglish uses Roman Tamil only (example: `call pannunga`, `follow-up pannunga`); Tamil script is not shown by this mode.
- [ ] Next-call playbook includes objective, opening line, talking points, questions and closing line.
- [ ] WhatsApp and email drafts can be copied but are never sent automatically by AI.
- [ ] AI attention signals are grounded only in recorded CRM outcomes/follow-ups; no unrecorded customer intent is invented.
- [ ] Contact-level call/WhatsApp/email history for the same person makes the cached lead AI insight stale and requires refresh.
- [ ] Evidence citations are visible and protected phone/email values never appear in AI output or citations.
- [ ] After recording a new call outcome, AI insight reports new CRM history and can be refreshed from the latest evidence.
