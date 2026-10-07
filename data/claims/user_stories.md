# Quillmoor Mutual claims handling: user stories (fictional insurer, English)

Synthetic spec for the Coverlens held-out claims domain. Quillmoor Mutual is
fictional; the rules are invented and contain no data from any real insurer.

## CL-01 Report a new claim

As a policyholder, I want to report a loss online or by phone so that my claim starts quickly.

Acceptance criteria:

- **CL-01.AC1** A policyholder can report a new claim online by entering the policy number, the incident date and a description of the loss.
- **CL-01.AC2** The incident date cannot be in the future; the form shows an error and the claim is not submitted.
- **CL-01.AC3** After submission the policyholder sees a claim number in the format QM-YYYY-NNNNNN.
- **CL-01.AC4** A claim reported by phone is entered by a call-centre agent and records the channel as Phone.
- **CL-01.AC5** A confirmation email with the claim number is sent within 5 minutes of submission.

## CL-02 Validate the policy

As a claims handler, I want claims checked against the policy so that only insured losses proceed.

Acceptance criteria:

- **CL-02.AC1** A claim is accepted only if the policy was active on the incident date.
- **CL-02.AC2** A claim on a policy cancelled before the incident date is rejected with the reason 'Policy not in force'.
- **CL-02.AC3** A claim must name a vehicle or property listed on the policy; an unlisted vehicle sends the claim to manual review.
- **CL-02.AC4** A claim during the 14-day grace period after a missed premium is accepted but flagged 'Premium overdue'.
- **CL-02.AC5** A policy number that does not exist shows an error and no claim is created.

## CL-03 Check coverage by peril

As an adjuster, I want the policy's covered perils applied so that only covered losses are paid.

Acceptance criteria:

- **CL-03.AC1** Collision damage is covered only on auto policies that include collision coverage.
- **CL-03.AC2** Flood damage to a home is excluded unless the policy has the flood endorsement.
- **CL-03.AC3** Glass-only damage on auto policies is paid with no deductible.
- **CL-03.AC4** Vehicle theft requires a police report number before the claim can move to assessment.
- **CL-03.AC5** Wear and tear is never covered; the claim is denied with the reason 'Excluded peril'.

## CL-04 Apply the deductible

As a policyholder, I want the deductible applied correctly so that I am paid what my policy says.

Acceptance criteria:

- **CL-04.AC1** The deductible is subtracted from the assessed loss before payment.
- **CL-04.AC2** If the assessed loss is below the deductible, no payment is made and the policyholder is told why.
- **CL-04.AC3** Weather claims on home policies use the windstorm deductible of 2% of the dwelling limit instead of the standard deductible.
- **CL-04.AC4** When one incident damages both an insured car and an insured garage on bundled policies, only one deductible applies.
- **CL-04.AC5** The deductible is waived once liability of an at-fault third party is confirmed.

## CL-05 Respect limits and sublimits

As the insurer, I want payouts capped by the policy so that we never pay more than was insured.

Acceptance criteria:

- **CL-05.AC1** The payout never exceeds the policy limit for the covered item.
- **CL-05.AC2** Jewellery theft is capped at the 1,500 USD sublimit unless the item is scheduled on the policy.
- **CL-05.AC3** Rental car reimbursement is capped at 40 USD per day and at 30 days per claim.
- **CL-05.AC4** When a limit caps the payout, the settlement letter names the limit that was applied.
- **CL-05.AC5** Additional living expenses on home claims stop when the home is repaired or after 12 months, whichever comes first.

## CL-06 Approve payments by authority level

As a claims manager, I want approval limits enforced so that large payments get the right sign-off.

Acceptance criteria:

- **CL-06.AC1** An adjuster may approve payments up to and including 5,000 USD.
- **CL-06.AC2** Payments above 5,000 USD need supervisor approval before any money is released.
- **CL-06.AC3** Payments above 50,000 USD need approval from both a supervisor and a claims manager.
- **CL-06.AC4** A user cannot approve a payment on a claim they adjusted themselves.
- **CL-06.AC5** An approval request that is not decided within 2 business days is escalated to the next approver.

## CL-07 Handle late filing

As an underwriter, I want late claims controlled so that delayed reports do not hide extra damage.

Acceptance criteria:

- **CL-07.AC1** A claim filed more than 30 days after the incident is rejected unless the late-filing waiver is set.
- **CL-07.AC2** Only a supervisor can set the late-filing waiver, and a reason must be entered.
- **CL-07.AC3** Home water-damage claims filed more than 14 days after discovery are flagged for possible extra damage.
- **CL-07.AC4** The filing delay in days is shown on the claim summary.
- **CL-07.AC5** A rejected late claim can be reopened within 60 days if the waiver is granted later.

## CL-08 Collect required documents

As an adjuster, I want the right documents before assessment so that I can assess the loss once.

Acceptance criteria:

- **CL-08.AC1** Auto claims above 2,500 USD require a repair estimate before assessment.
- **CL-08.AC2** Home claims require at least three photos of the damage before assessment.
- **CL-08.AC3** Uploaded documents larger than 20 MB are refused with a message about the size limit.
- **CL-08.AC4** Only PDF, JPG and PNG files can be uploaded; other file types are refused.
- **CL-08.AC5** The policyholder is reminded by email when a required document is still missing after 7 days.

## CL-09 Flag possible fraud

As the special investigations unit, I want suspicious claims flagged so that fraud is caught before payment.

Acceptance criteria:

- **CL-09.AC1** A claim filed within 30 days of the policy start date is flagged 'Early claim'.
- **CL-09.AC2** Three or more claims on the same policy within 12 months raise a 'Frequency' flag.
- **CL-09.AC3** A claim with two or more fraud flags is referred to the special investigations unit and its payment is blocked.
- **CL-09.AC4** The investigator's referral decision is recorded with a reason and a timestamp.
- **CL-09.AC5** Fraud flags are never shown to the policyholder.

## CL-10 Assign the right adjuster

As a team lead, I want claims routed automatically so that each claim gets a qualified adjuster quickly.

Acceptance criteria:

- **CL-10.AC1** A new claim is assigned to an adjuster licensed in the state where the loss happened.
- **CL-10.AC2** An adjuster with 40 open claims receives no new assignments.
- **CL-10.AC3** Total-loss auto claims are assigned only to senior adjusters.
- **CL-10.AC4** When an adjuster goes on leave, their open claims are reassigned within 1 business day.
- **CL-10.AC5** The policyholder sees the assigned adjuster's name and phone number on the claim page.

## CL-11 Meet service levels

As a policyholder, I want my claim handled on time so that I am not left waiting.

Acceptance criteria:

- **CL-11.AC1** The first contact with the policyholder happens within 1 business day of the claim being reported.
- **CL-11.AC2** An assessment is completed within 10 business days of all required documents being received.
- **CL-11.AC3** A claim that breaches a service level appears on the supervisor's overdue list.
- **CL-11.AC4** Service-level clocks pause while the claim is waiting on the policyholder.
- **CL-11.AC5** Public holidays are not counted as business days.

## CL-12 Move claims through their statuses

As a claims handler, I want a clear claim lifecycle so that everyone knows where a claim stands.

Acceptance criteria:

- **CL-12.AC1** A claim moves through Reported, In review, Assessed, Approved, Paid and Closed in that order.
- **CL-12.AC2** A claim cannot be closed while a payment is pending.
- **CL-12.AC3** A denied claim moves to Closed and keeps its denial reason.
- **CL-12.AC4** Every status change records the user who made it and the time.
- **CL-12.AC5** A closed claim can be reopened only by a supervisor.

## CL-13 Pay the claim

As a policyholder, I want to be paid the right way so that the money reaches me or my repairer.

Acceptance criteria:

- **CL-13.AC1** Payments go to the bank account on the policy by default.
- **CL-13.AC2** When a vehicle has a lienholder, the payment is made out jointly to the policyholder and the lienholder.
- **CL-13.AC3** A payment can be split between the policyholder and a repair shop.
- **CL-13.AC4** A failed bank transfer is retried once and then sent as a cheque.
- **CL-13.AC5** The policyholder receives a payment advice showing the gross loss, the deductible and the net payment.

## CL-14 Settle a total loss

As a policyholder whose car cannot be repaired, I want a fair settlement so that I can replace it.

Acceptance criteria:

- **CL-14.AC1** A vehicle is a total loss when the repair estimate exceeds 75% of its market value.
- **CL-14.AC2** A total-loss settlement is the market value minus the deductible, and also minus the salvage value when the owner keeps the vehicle.
- **CL-14.AC3** The policyholder has 10 days to accept or dispute the total-loss offer.
- **CL-14.AC4** A disputed offer triggers an independent appraisal.
- **CL-14.AC5** Sales tax and registration fees are added to the total-loss settlement.

## CL-15 Cover rental and living expenses

As a policyholder, I want temporary transport or housing paid so that I can carry on while repairs happen.

Acceptance criteria:

- **CL-15.AC1** Rental cover starts on the day the vehicle is taken to the repair shop.
- **CL-15.AC2** Rental cover ends 3 days after the repair is completed or the total-loss settlement is paid.
- **CL-15.AC3** Additional living expenses are reimbursed only against receipts.
- **CL-15.AC4** The policyholder can see the remaining rental days on the claim page.
- **CL-15.AC5** Rental is not covered when the policy has no rental endorsement.

## CL-16 Recover costs through subrogation

As the insurer, I want to recover what at-fault parties owe so that losses are not borne by us or the customer.

Acceptance criteria:

- **CL-16.AC1** When a third party is at fault, the claim is flagged for subrogation.
- **CL-16.AC2** Money recovered from the third party first refunds the policyholder's deductible.
- **CL-16.AC3** Recovered amounts are shown on the claim's financial summary.
- **CL-16.AC4** Subrogation is closed when the recovery is received in full or written off by a manager.
- **CL-16.AC5** The policyholder is told when their deductible has been refunded.

## CL-17 Handle supplements and reopened claims

As a repair shop, I want to report hidden damage so that the full repair is paid.

Acceptance criteria:

- **CL-17.AC1** A repair shop can submit a supplement for damage found during the repair.
- **CL-17.AC2** A supplement above 1,000 USD needs a re-inspection before it can be approved.
- **CL-17.AC3** Supplements follow the same approval limits as the original payment, based on the combined total.
- **CL-17.AC4** A claim can be reopened within 12 months of closing for related damage.
- **CL-17.AC5** A reopened claim keeps its original claim number.

## CL-18 Notify the policyholder

As a policyholder, I want timely updates so that I know what is happening with my claim.

Acceptance criteria:

- **CL-18.AC1** The policyholder is emailed at every status change.
- **CL-18.AC2** Text messages are sent only to policyholders who opted in.
- **CL-18.AC3** Notifications are sent in the policyholder's preferred language, English or Spanish.
- **CL-18.AC4** No notifications are sent between 9 pm and 8 am local time; they are queued and sent at 8 am.
- **CL-18.AC5** A notification that bounces is logged and the adjuster is alerted.

## CL-19 Deny and appeal claims

As a policyholder, I want clear denials and a fair appeal so that I can challenge a wrong decision.

Acceptance criteria:

- **CL-19.AC1** A denial letter states the reason and the policy clause it relies on.
- **CL-19.AC2** Denials above 10,000 USD are reviewed by a claims manager before the letter is sent.
- **CL-19.AC3** The policyholder can appeal a denial within 60 days.
- **CL-19.AC4** An appeal is reviewed by someone other than the person who denied the claim.
- **CL-19.AC5** The appeal outcome is sent within 30 days of the appeal.

## CL-20 Audit access and permissions

As the compliance officer, I want sensitive data protected and traced so that we meet our privacy duties.

Acceptance criteria:

- **CL-20.AC1** Every view of a claim's medical or police documents is logged.
- **CL-20.AC2** Call-centre agents cannot see fraud flags or investigator notes.
- **CL-20.AC3** Adjusters can edit only the claims assigned to them.
- **CL-20.AC4** The audit log cannot be edited or deleted by any user, including administrators.
- **CL-20.AC5** Exporting claim data requires the manager role and is logged.
