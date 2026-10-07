"""Builds the held-out claims dataset for a fictional insurer, Quillmoor Mutual.

Run once to write data/claims/ (then the files are read-only and pinned):

    uv run python -m eval.datasets.build_claims

The labels live here because they are defined together with the cases; this is
eval code, so it may hold them. Labelling rule: a criterion is covered only when
the cases listed for it, together, check every condition it states.
"""

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "claims"

HEADER = [
    "Case ID",
    "Name",
    "Setup",
    "Test steps",
    "Expected outcome",
    "Priority",
    "Labels",
    "Covers requirement",
    "Policy type",
    "Claim type",
    "Channel",
    "Customer tier",
    "Amount band",
]
SMALL, MID, LARGE, HUGE = (
    "Under 1,000",
    "1,000 to 5,000",
    "5,000 to 50,000",
    "Over 50,000",
)


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    narrative: str
    criteria: tuple[str, ...]


@dataclass(frozen=True)
class CaseDef:
    id: str
    name: str
    setup: str
    steps: str
    expected: str
    kind: str  # direct, paraphrase, multi, partial, boundary, same_topic, decoy, orphan
    covers: tuple[
        str, ...
    ] = ()  # criteria this case helps cover (all conditions, jointly)
    tag: str = ""
    ref: str = ""
    policy: str = "Auto"
    claim: str = "Collision"
    channel: str = "Web"
    tier: str = "Standard"
    amount: str = MID
    extra: dict[str, str] = field(default_factory=dict)


STORIES = [
    Story(
        "CL-01",
        "Report a new claim",
        "As a policyholder, I want to report a loss online or by phone so that my claim starts quickly.",
        (
            "A policyholder can report a new claim online by entering the policy number, the incident date and a description of the loss.",
            "The incident date cannot be in the future; the form shows an error and the claim is not submitted.",
            "After submission the policyholder sees a claim number in the format QM-YYYY-NNNNNN.",
            "A claim reported by phone is entered by a call-centre agent and records the channel as Phone.",
            "A confirmation email with the claim number is sent within 5 minutes of submission.",
        ),
    ),
    Story(
        "CL-02",
        "Validate the policy",
        "As a claims handler, I want claims checked against the policy so that only insured losses proceed.",
        (
            "A claim is accepted only if the policy was active on the incident date.",
            "A claim on a policy cancelled before the incident date is rejected with the reason 'Policy not in force'.",
            "A claim must name a vehicle or property listed on the policy; an unlisted vehicle sends the claim to manual review.",
            "A claim during the 14-day grace period after a missed premium is accepted but flagged 'Premium overdue'.",
            "A policy number that does not exist shows an error and no claim is created.",
        ),
    ),
    Story(
        "CL-03",
        "Check coverage by peril",
        "As an adjuster, I want the policy's covered perils applied so that only covered losses are paid.",
        (
            "Collision damage is covered only on auto policies that include collision coverage.",
            "Flood damage to a home is excluded unless the policy has the flood endorsement.",
            "Glass-only damage on auto policies is paid with no deductible.",
            "Vehicle theft requires a police report number before the claim can move to assessment.",
            "Wear and tear is never covered; the claim is denied with the reason 'Excluded peril'.",
        ),
    ),
    Story(
        "CL-04",
        "Apply the deductible",
        "As a policyholder, I want the deductible applied correctly so that I am paid what my policy says.",
        (
            "The deductible is subtracted from the assessed loss before payment.",
            "If the assessed loss is below the deductible, no payment is made and the policyholder is told why.",
            "Weather claims on home policies use the windstorm deductible of 2% of the dwelling limit instead of the standard deductible.",
            "When one incident damages both an insured car and an insured garage on bundled policies, only one deductible applies.",
            "The deductible is waived once liability of an at-fault third party is confirmed.",
        ),
    ),
    Story(
        "CL-05",
        "Respect limits and sublimits",
        "As the insurer, I want payouts capped by the policy so that we never pay more than was insured.",
        (
            "The payout never exceeds the policy limit for the covered item.",
            "Jewellery theft is capped at the 1,500 USD sublimit unless the item is scheduled on the policy.",
            "Rental car reimbursement is capped at 40 USD per day and at 30 days per claim.",
            "When a limit caps the payout, the settlement letter names the limit that was applied.",
            "Additional living expenses on home claims stop when the home is repaired or after 12 months, whichever comes first.",
        ),
    ),
    Story(
        "CL-06",
        "Approve payments by authority level",
        "As a claims manager, I want approval limits enforced so that large payments get the right sign-off.",
        (
            "An adjuster may approve payments up to and including 5,000 USD.",
            "Payments above 5,000 USD need supervisor approval before any money is released.",
            "Payments above 50,000 USD need approval from both a supervisor and a claims manager.",
            "A user cannot approve a payment on a claim they adjusted themselves.",
            "An approval request that is not decided within 2 business days is escalated to the next approver.",
        ),
    ),
    Story(
        "CL-07",
        "Handle late filing",
        "As an underwriter, I want late claims controlled so that delayed reports do not hide extra damage.",
        (
            "A claim filed more than 30 days after the incident is rejected unless the late-filing waiver is set.",
            "Only a supervisor can set the late-filing waiver, and a reason must be entered.",
            "Home water-damage claims filed more than 14 days after discovery are flagged for possible extra damage.",
            "The filing delay in days is shown on the claim summary.",
            "A rejected late claim can be reopened within 60 days if the waiver is granted later.",
        ),
    ),
    Story(
        "CL-08",
        "Collect required documents",
        "As an adjuster, I want the right documents before assessment so that I can assess the loss once.",
        (
            "Auto claims above 2,500 USD require a repair estimate before assessment.",
            "Home claims require at least three photos of the damage before assessment.",
            "Uploaded documents larger than 20 MB are refused with a message about the size limit.",
            "Only PDF, JPG and PNG files can be uploaded; other file types are refused.",
            "The policyholder is reminded by email when a required document is still missing after 7 days.",
        ),
    ),
    Story(
        "CL-09",
        "Flag possible fraud",
        "As the special investigations unit, I want suspicious claims flagged so that fraud is caught before payment.",
        (
            "A claim filed within 30 days of the policy start date is flagged 'Early claim'.",
            "Three or more claims on the same policy within 12 months raise a 'Frequency' flag.",
            "A claim with two or more fraud flags is referred to the special investigations unit and its payment is blocked.",
            "The investigator's referral decision is recorded with a reason and a timestamp.",
            "Fraud flags are never shown to the policyholder.",
        ),
    ),
    Story(
        "CL-10",
        "Assign the right adjuster",
        "As a team lead, I want claims routed automatically so that each claim gets a qualified adjuster quickly.",
        (
            "A new claim is assigned to an adjuster licensed in the state where the loss happened.",
            "An adjuster with 40 open claims receives no new assignments.",
            "Total-loss auto claims are assigned only to senior adjusters.",
            "When an adjuster goes on leave, their open claims are reassigned within 1 business day.",
            "The policyholder sees the assigned adjuster's name and phone number on the claim page.",
        ),
    ),
    Story(
        "CL-11",
        "Meet service levels",
        "As a policyholder, I want my claim handled on time so that I am not left waiting.",
        (
            "The first contact with the policyholder happens within 1 business day of the claim being reported.",
            "An assessment is completed within 10 business days of all required documents being received.",
            "A claim that breaches a service level appears on the supervisor's overdue list.",
            "Service-level clocks pause while the claim is waiting on the policyholder.",
            "Public holidays are not counted as business days.",
        ),
    ),
    Story(
        "CL-12",
        "Move claims through their statuses",
        "As a claims handler, I want a clear claim lifecycle so that everyone knows where a claim stands.",
        (
            "A claim moves through Reported, In review, Assessed, Approved, Paid and Closed in that order.",
            "A claim cannot be closed while a payment is pending.",
            "A denied claim moves to Closed and keeps its denial reason.",
            "Every status change records the user who made it and the time.",
            "A closed claim can be reopened only by a supervisor.",
        ),
    ),
    Story(
        "CL-13",
        "Pay the claim",
        "As a policyholder, I want to be paid the right way so that the money reaches me or my repairer.",
        (
            "Payments go to the bank account on the policy by default.",
            "When a vehicle has a lienholder, the payment is made out jointly to the policyholder and the lienholder.",
            "A payment can be split between the policyholder and a repair shop.",
            "A failed bank transfer is retried once and then sent as a cheque.",
            "The policyholder receives a payment advice showing the gross loss, the deductible and the net payment.",
        ),
    ),
    Story(
        "CL-14",
        "Settle a total loss",
        "As a policyholder whose car cannot be repaired, I want a fair settlement so that I can replace it.",
        (
            "A vehicle is a total loss when the repair estimate exceeds 75% of its market value.",
            "A total-loss settlement is the market value minus the deductible, and also minus the salvage value when the owner keeps the vehicle.",
            "The policyholder has 10 days to accept or dispute the total-loss offer.",
            "A disputed offer triggers an independent appraisal.",
            "Sales tax and registration fees are added to the total-loss settlement.",
        ),
    ),
    Story(
        "CL-15",
        "Cover rental and living expenses",
        "As a policyholder, I want temporary transport or housing paid so that I can carry on while repairs happen.",
        (
            "Rental cover starts on the day the vehicle is taken to the repair shop.",
            "Rental cover ends 3 days after the repair is completed or the total-loss settlement is paid.",
            "Additional living expenses are reimbursed only against receipts.",
            "The policyholder can see the remaining rental days on the claim page.",
            "Rental is not covered when the policy has no rental endorsement.",
        ),
    ),
    Story(
        "CL-16",
        "Recover costs through subrogation",
        "As the insurer, I want to recover what at-fault parties owe so that losses are not borne by us or the customer.",
        (
            "When a third party is at fault, the claim is flagged for subrogation.",
            "Money recovered from the third party first refunds the policyholder's deductible.",
            "Recovered amounts are shown on the claim's financial summary.",
            "Subrogation is closed when the recovery is received in full or written off by a manager.",
            "The policyholder is told when their deductible has been refunded.",
        ),
    ),
    Story(
        "CL-17",
        "Handle supplements and reopened claims",
        "As a repair shop, I want to report hidden damage so that the full repair is paid.",
        (
            "A repair shop can submit a supplement for damage found during the repair.",
            "A supplement above 1,000 USD needs a re-inspection before it can be approved.",
            "Supplements follow the same approval limits as the original payment, based on the combined total.",
            "A claim can be reopened within 12 months of closing for related damage.",
            "A reopened claim keeps its original claim number.",
        ),
    ),
    Story(
        "CL-18",
        "Notify the policyholder",
        "As a policyholder, I want timely updates so that I know what is happening with my claim.",
        (
            "The policyholder is emailed at every status change.",
            "Text messages are sent only to policyholders who opted in.",
            "Notifications are sent in the policyholder's preferred language, English or Spanish.",
            "No notifications are sent between 9 pm and 8 am local time; they are queued and sent at 8 am.",
            "A notification that bounces is logged and the adjuster is alerted.",
        ),
    ),
    Story(
        "CL-19",
        "Deny and appeal claims",
        "As a policyholder, I want clear denials and a fair appeal so that I can challenge a wrong decision.",
        (
            "A denial letter states the reason and the policy clause it relies on.",
            "Denials above 10,000 USD are reviewed by a claims manager before the letter is sent.",
            "The policyholder can appeal a denial within 60 days.",
            "An appeal is reviewed by someone other than the person who denied the claim.",
            "The appeal outcome is sent within 30 days of the appeal.",
        ),
    ),
    Story(
        "CL-20",
        "Audit access and permissions",
        "As the compliance officer, I want sensitive data protected and traced so that we meet our privacy duties.",
        (
            "Every view of a claim's medical or police documents is logged.",
            "Call-centre agents cannot see fraud flags or investigator notes.",
            "Adjusters can edit only the claims assigned to them.",
            "The audit log cannot be edited or deleted by any user, including administrators.",
            "Exporting claim data requires the manager role and is logged.",
        ),
    ),
]


def c(
    n: int, name: str, setup: str, steps: str, expected: str, kind: str, **kw: object
) -> CaseDef:
    return CaseDef(f"QT-{n:03d}", name, setup, steps, expected, kind, **kw)  # type: ignore[arg-type]


CASES = [
    # CL-01 report a new claim
    c(
        1,
        "Report a claim on the portal",
        "Signed-in policyholder with an active auto policy",
        "Open 'Report a claim'; enter the policy number, the incident date and a short description of the loss; submit",
        "Claim is created with the entered policy number, date and description",
        "direct",
        covers=("CL-01.AC1",),
        tag="fnol",
        ref="CL-01.AC1",
    ),
    c(
        2,
        "Reject an incident dated tomorrow",
        "Signed-in policyholder",
        "Enter tomorrow's date as the incident date; submit",
        "Message 'The date cannot be later than today'; nothing is filed",
        "paraphrase",
        covers=("CL-01.AC2",),
        tag="fnol",
    ),
    c(
        3,
        "Claim number format",
        "Signed-in policyholder",
        "Submit a valid claim",
        "Confirmation page shows a claim number matching QM-YYYY-NNNNNN",
        "direct",
        covers=("CL-01.AC3",),
        tag="fnol",
        ref="CL-01.AC3",
    ),
    c(
        4,
        "Agent files a claim from a call",
        "Call-centre agent signed in to ClaimDesk",
        "Enter the caller's policy number and loss details; save",
        "Claim is created and a claim number is read back to the caller",
        "decoy",
        tag="fnol",
        ref="CL-01.AC4",
        channel="Phone",
    ),
    c(
        5,
        "Confirmation email arrives quickly",
        "Policyholder with a verified email address",
        "Submit a claim; watch the inbox",
        "Email containing the claim number arrives within 5 minutes",
        "direct",
        covers=("CL-01.AC5",),
        tag="fnol",
    ),
    c(
        101,
        "Report a claim from a phone browser",
        "Policyholder on a mobile browser",
        "Fill in the policy number, when it happened and what was damaged; send",
        "Claim is created with all three details stored",
        "paraphrase",
        covers=("CL-01.AC1",),
    ),
    # CL-02 validate the policy
    c(
        7,
        "Claim on an active policy",
        "Auto policy in force from 1 March to 28 February",
        "File a claim for an incident on 10 June",
        "Claim is accepted for review",
        "multi",
        covers=("CL-02.AC1",),
        tag="policy",
        ref="CL-02.AC1",
    ),
    c(
        8,
        "Claim on a cancelled policy",
        "Auto policy cancelled on 2 May",
        "File a claim for an incident on 9 May",
        "Claim is rejected with the reason 'Policy not in force'",
        "multi",
        covers=("CL-02.AC1", "CL-02.AC2"),
        tag="policy",
    ),
    c(
        9,
        "Insured vehicle is prefilled",
        "Policy with one listed vehicle",
        "Start a claim and open the vehicle step",
        "The listed vehicle's make, model and plate are prefilled",
        "same_topic",
        tag="policy",
    ),
    c(
        10,
        "Claim inside the premium grace period",
        "Premium missed; incident on day 10 after the due date",
        "File the claim",
        "Claim is accepted and shows the flag 'Premium overdue'",
        "boundary",
        covers=("CL-02.AC4",),
        tag="policy",
    ),
    c(
        11,
        "Unknown policy reference",
        "Signed-in agent",
        "Enter the policy number QM-POL-0000000, which does not exist; submit",
        "Message 'Policy not found'; no claim number is issued",
        "paraphrase",
        covers=("CL-02.AC5",),
        ref="CL-02.AC5",
    ),
    # CL-03 coverage by peril
    c(
        12,
        "Collision claim with collision cover",
        "Auto policy that includes collision coverage",
        "File a collision claim",
        "Claim is accepted for assessment",
        "decoy",
        tag="coverage",
        ref="CL-03.AC1",
    ),
    c(
        13,
        "Flood without the endorsement",
        "Home policy without the flood endorsement",
        "File a claim for river flooding in the basement",
        "Claim is denied as an excluded peril",
        "multi",
        covers=("CL-03.AC2",),
        tag="coverage",
        policy="Home",
        claim="Water",
        amount=LARGE,
    ),
    c(
        14,
        "Flood with the endorsement",
        "Home policy with the flood endorsement",
        "File a claim for river flooding in the basement",
        "Claim is accepted for assessment",
        "multi",
        covers=("CL-03.AC2",),
        tag="coverage",
        policy="Home",
        claim="Water",
        amount=LARGE,
    ),
    c(
        15,
        "Windscreen replacement",
        "Auto policy with a 500 USD deductible",
        "Settle a glass-only claim assessed at 600 USD",
        "Payout is the full 600 USD with nothing withheld",
        "paraphrase",
        covers=("CL-03.AC3",),
        claim="Glass",
        amount=SMALL,
    ),
    c(
        16,
        "Theft needs a police report number",
        "Vehicle theft claim without a police report number",
        "Try to move the claim to assessment; then add the police report number and try again",
        "First attempt is blocked with a message asking for the number; second attempt succeeds",
        "direct",
        covers=("CL-03.AC4",),
        tag="coverage",
        ref="CL-03.AC4",
        claim="Theft",
        amount=LARGE,
    ),
    c(
        17,
        "Mechanical breakdown claim",
        "Auto policy",
        "File a claim for a failed gearbox",
        "Claim is routed to an adjuster for a coverage review",
        "same_topic",
        tag="coverage",
    ),
    c(
        117,
        "Stolen car without a crime reference",
        "Theft claim with no crime reference from the police",
        "Ask for assessment; enter the crime reference; ask again",
        "Assessment is refused until the crime reference is entered, then it starts",
        "paraphrase",
        covers=("CL-03.AC4",),
        claim="Theft",
        amount=LARGE,
    ),
    # CL-04 deductible
    c(
        18,
        "Deductible subtracted from the payout",
        "Auto policy with a 500 USD deductible",
        "Approve a claim assessed at 3,200 USD",
        "Payment of 2,700 USD",
        "direct",
        covers=("CL-04.AC1",),
        tag="deductible",
        ref="CL-04.AC1",
    ),
    c(
        19,
        "Loss smaller than the deductible",
        "Auto policy with a 500 USD deductible",
        "Assess the loss at 400 USD",
        "No payment; the policyholder is told the loss is below the deductible",
        "boundary",
        covers=("CL-04.AC2",),
        tag="deductible",
        amount=SMALL,
    ),
    c(
        20,
        "Storm claim on a home policy",
        "Home policy",
        "File a claim for roof damage after a storm, with photos",
        "Claim is accepted for assessment",
        "decoy",
        tag="deductible",
        ref="CL-04.AC3",
        policy="Home",
        claim="Weather",
        amount=LARGE,
    ),
    c(
        21,
        "One event damages car and garage",
        "Bundled auto and home policies, each with a deductible",
        "A tree falls on the parked car and the garage; file both claims",
        "One deductible is taken across the two claims",
        "paraphrase",
        covers=("CL-04.AC4",),
        tag="deductible",
        policy="Home",
        claim="Weather",
        amount=LARGE,
    ),
    c(
        102,
        "Net payout after excess",
        "Auto policy with a 250 USD excess",
        "Settle a loss of 1,250 USD",
        "Policyholder receives 1,000 USD",
        "paraphrase",
        covers=("CL-04.AC1",),
    ),
    c(
        113,
        "Third party admits fault",
        "Collision caused by another driver who admits fault",
        "Record the other driver's admission on the claim",
        "Claim is flagged for subrogation",
        "direct",
        covers=("CL-16.AC1",),
        tag="subrogation",
    ),
    # CL-05 limits
    c(
        22,
        "Payout capped at the policy limit",
        "Item insured up to 25,000 USD",
        "Assess a loss of 30,000 USD and settle",
        "Payout is 25,000 USD and the settlement letter names the 25,000 USD limit",
        "direct",
        covers=("CL-05.AC1", "CL-05.AC4"),
        tag="limits",
        ref="CL-05.AC1",
        amount=LARGE,
    ),
    c(
        23,
        "Ring theft above the sublimit",
        "Home policy; ring not scheduled",
        "File a theft claim for a 4,000 USD ring",
        "Payout is 1,500 USD",
        "partial",
        tag="limits",
        policy="Home",
        claim="Theft",
    ),
    c(
        24,
        "Rental above the daily cap",
        "Rental car at 55 USD a day",
        "Claim 10 days of rental",
        "400 USD is reimbursed (40 USD a day)",
        "multi",
        covers=("CL-05.AC3",),
        tag="limits",
        amount=SMALL,
    ),
    c(
        25,
        "Rental beyond 30 days",
        "Rental car at 35 USD a day",
        "Claim 35 days of rental",
        "30 days are reimbursed",
        "multi",
        covers=("CL-05.AC3",),
        tag="limits",
        amount=MID,
    ),
    c(
        26,
        "Living expenses stop after repairs",
        "Home claim with hotel costs",
        "Mark the repair as complete",
        "No further living expenses are accepted after the completion date",
        "partial",
        tag="limits",
        policy="Home",
        claim="Fire",
        amount=LARGE,
    ),
    # CL-06 approval authority
    c(
        27,
        "Adjuster approves exactly 5,000 USD",
        "Adjuster on an assigned claim",
        "Approve a payment of 5,000 USD",
        "Payment is approved without escalation",
        "boundary",
        covers=("CL-06.AC1",),
        tag="approval",
        ref="CL-06.AC1",
    ),
    c(
        28,
        "Adjuster approves 4,999 USD",
        "Adjuster on an assigned claim",
        "Approve a payment of 4,999 USD",
        "Payment is approved without escalation",
        "boundary",
        tag="approval",
    ),
    c(
        29,
        "Large payment goes to the supervisor queue",
        "Adjuster on an assigned claim",
        "Request a payment of 7,500 USD",
        "The request appears in the supervisor's approval queue",
        "decoy",
        tag="approval",
        ref="CL-06.AC2",
        amount=LARGE,
    ),
    c(
        30,
        "Very large payment needs two approvals",
        "Claim with a 60,000 USD payment request",
        "Supervisor approves; then the claims manager approves",
        "After the supervisor the payment is still pending; after the manager it is released",
        "direct",
        covers=("CL-06.AC3",),
        tag="approval",
        amount=HUGE,
    ),
    c(
        31,
        "Adjuster tries to approve own claim",
        "Adjuster who assessed the claim",
        "Open the payment and choose Approve",
        "Approve is disabled with the note 'You adjusted this claim'",
        "paraphrase",
        covers=("CL-06.AC4",),
        tag="approval",
    ),
    c(
        109,
        "Adjuster approves 3,200 USD",
        "Adjuster on an assigned claim",
        "Approve a payment of 3,200 USD",
        "Payment is approved directly",
        "direct",
        covers=("CL-06.AC1",),
    ),
    c(
        114,
        "Approval request waits in the queue",
        "Payment request pending for 3 business days",
        "Open the approval queue",
        "The request is listed as pending with its age in days",
        "same_topic",
        tag="approval",
    ),
    # CL-07 late filing
    c(
        32,
        "Claim filed 31 days late",
        "Incident 31 days ago; no waiver",
        "File the claim",
        "Claim is rejected as filed late",
        "multi",
        covers=("CL-07.AC1",),
        tag="late",
        ref="CL-07.AC1",
    ),
    c(
        33,
        "Late claim with a waiver",
        "Incident 45 days ago; late-filing waiver set",
        "File the claim",
        "Claim is accepted",
        "multi",
        covers=("CL-07.AC1",),
        tag="late",
    ),
    c(
        34,
        "Claim filed 29 days after the incident",
        "Incident 29 days ago",
        "File the claim",
        "Claim is accepted",
        "boundary",
        tag="late",
    ),
    c(
        35,
        "Supervisor sets the late-filing waiver",
        "Supervisor on a late claim",
        "Tick 'Late-filing waiver' and save",
        "The waiver is shown on the claim",
        "partial",
        tag="late",
    ),
    c(
        36,
        "Water damage reported long after discovery",
        "Leak discovered 20 days before the claim is filed",
        "File the water-damage claim",
        "Claim is flagged 'Possible extra damage'",
        "direct",
        covers=("CL-07.AC3",),
        tag="late",
        policy="Home",
        claim="Water",
    ),
    c(
        111,
        "Late claim shows a warning banner",
        "Claim filed 35 days after the incident",
        "Open the claim summary",
        "A 'Filed late' banner is shown",
        "same_topic",
        tag="late",
    ),
    # CL-08 documents
    c(
        37,
        "Repair estimate required above 2,500 USD",
        "Auto claim of 3,000 USD without an estimate",
        "Move the claim to assessment",
        "Blocked until a repair estimate is uploaded",
        "boundary",
        covers=("CL-08.AC1",),
        tag="documents",
        ref="CL-08.AC1",
    ),
    c(
        38,
        "No estimate needed at 2,000 USD",
        "Auto claim of 2,000 USD without an estimate",
        "Move the claim to assessment",
        "Assessment starts",
        "boundary",
        tag="documents",
    ),
    c(
        39,
        "Assessment waits for damage pictures",
        "Home claim with two pictures of the damage",
        "Start the assessment; add a third picture; start again",
        "First attempt is refused; with three pictures it starts",
        "paraphrase",
        covers=("CL-08.AC2",),
        policy="Home",
        claim="Fire",
        amount=LARGE,
    ),
    c(
        40,
        "Oversized upload refused",
        "Any open claim",
        "Upload a 25 MB PDF",
        "Upload is refused with 'Files must be 20 MB or smaller'",
        "direct",
        covers=("CL-08.AC3",),
        tag="documents",
    ),
    c(
        41,
        "Upload a PNG photo",
        "Any open claim",
        "Upload a PNG photo of the damage",
        "The photo is attached to the claim",
        "decoy",
        tag="documents",
        ref="CL-08.AC4",
    ),
    c(
        42,
        "Reminder for a missing estimate",
        "Repair estimate missing for 7 days",
        "Let the daily reminder job run",
        "Policyholder gets an email listing the missing estimate",
        "direct",
        covers=("CL-08.AC5",),
        tag="documents",
    ),
    # CL-09 fraud
    c(
        43,
        "Claim 20 days after the policy started",
        "Policy started 20 days ago",
        "File a claim",
        "Claim shows the flag 'Early claim'",
        "boundary",
        covers=("CL-09.AC1",),
        tag="fraud",
        ref="CL-09.AC1",
    ),
    c(
        44,
        "Second claim in a year",
        "Policy with one earlier claim this year",
        "File a second claim",
        "No 'Frequency' flag is raised",
        "boundary",
        tag="fraud",
    ),
    c(
        45,
        "Two flags send the claim to investigators",
        "Claim with 'Early claim' and 'Frequency' flags",
        "Run the fraud screen; try to release the payment",
        "Claim is referred to the special investigations unit and the payment cannot be released",
        "direct",
        covers=("CL-09.AC3",),
        tag="fraud",
    ),
    c(
        46,
        "Investigator closes a referral",
        "Claim referred to investigators",
        "Record the decision 'No fraud found' with a note",
        "History shows the decision, the note and the date and time",
        "paraphrase",
        covers=("CL-09.AC4",),
        tag="fraud",
    ),
    c(
        47,
        "Adjuster sees fraud flags",
        "Claim with an 'Early claim' flag",
        "Adjuster opens the claim",
        "The flag is visible in the adjuster's view",
        "decoy",
        tag="fraud",
        ref="CL-09.AC5",
    ),
    # CL-10 assignment
    c(
        48,
        "Assign by state licence",
        "Loss in Ohio",
        "Submit the claim",
        "Assigned adjuster holds an Ohio licence",
        "direct",
        covers=("CL-10.AC1",),
        tag="assignment",
        ref="CL-10.AC1",
    ),
    c(
        49,
        "Full workload is skipped",
        "Adjuster with 40 open claims",
        "Run assignment for a new claim",
        "That adjuster is not chosen",
        "boundary",
        covers=("CL-10.AC2",),
        tag="assignment",
    ),
    c(
        50,
        "Adjuster just under capacity",
        "Adjuster with 39 open claims",
        "Run assignment for a new claim",
        "That adjuster can be chosen",
        "boundary",
        tag="assignment",
    ),
    c(
        51,
        "Claims move when an adjuster is on leave",
        "Adjuster with 12 open claims marked on leave",
        "Wait for the next business day",
        "All 12 claims have a new adjuster",
        "direct",
        covers=("CL-10.AC4",),
        tag="assignment",
    ),
    c(
        52,
        "Adjuster contact on the claim page",
        "Assigned claim",
        "Policyholder opens the claim page",
        "Adjuster's name and phone number are shown",
        "direct",
        covers=("CL-10.AC5",),
    ),
    c(
        107,
        "Total-loss claim gets an adjuster",
        "Auto claim marked as a total loss",
        "Run assignment",
        "An adjuster is assigned",
        "partial",
        tag="assignment",
        amount=LARGE,
    ),
    # CL-11 service levels
    c(
        53,
        "First contact within one business day",
        "Claim reported Friday at 4 pm",
        "Check the first-contact task",
        "Task is due Monday at 4 pm and turns overdue if not done by then",
        "direct",
        covers=("CL-11.AC1",),
        tag="sla",
        ref="CL-11.AC1",
    ),
    c(
        54,
        "Assessment clock starts with complete documents",
        "Last required document uploaded today",
        "Open the service-level panel",
        "Assessment clock shows a start date of today",
        "partial",
        tag="sla",
    ),
    c(
        55,
        "Breached claim on the overdue list",
        "Claim past its assessment deadline",
        "Supervisor opens the overdue list",
        "The claim is listed",
        "direct",
        covers=("CL-11.AC3",),
        tag="sla",
    ),
    c(
        56,
        "Clock stops while waiting for the customer",
        "Claim in 'Waiting on policyholder' for 3 days",
        "Compare elapsed service-level time before and after",
        "Elapsed time did not grow during the wait",
        "paraphrase",
        covers=("CL-11.AC4",),
    ),
    c(
        115,
        "Weekends are not business days",
        "Claim reported on Friday",
        "Check the first-contact deadline",
        "Saturday and Sunday are skipped",
        "same_topic",
        tag="sla",
    ),
    # CL-12 statuses
    c(
        57,
        "Claim moves to In review",
        "Newly reported claim",
        "Adjuster opens the claim",
        "Status changes from Reported to In review",
        "decoy",
        tag="status",
        ref="CL-12.AC1",
    ),
    c(
        120,
        "Claim moves from Approved to Paid",
        "Approved claim",
        "Release the payment",
        "Status changes to Paid",
        "partial",
        tag="status",
    ),
    c(
        58,
        "Cannot close with a pending payment",
        "Claim with a payment awaiting release",
        "Try to close the claim",
        "Close is refused while the payment is pending",
        "direct",
        covers=("CL-12.AC2",),
        tag="status",
        ref="CL-12.AC2",
    ),
    c(
        59,
        "Denied claim closes with its reason",
        "Claim denied as 'Excluded peril'",
        "Open the closed claim",
        "Status is Closed and the denial reason is still shown",
        "direct",
        covers=("CL-12.AC3",),
        tag="status",
    ),
    c(
        60,
        "Status history shows who and when",
        "Claim with several status changes",
        "Open the history tab",
        "Each change lists the user and the time",
        "direct",
        covers=("CL-12.AC4",),
        tag="status",
    ),
    c(
        110,
        "History tab lists who changed the status",
        "Claim moved to Assessed by an adjuster",
        "Open the history tab",
        "Entry shows the adjuster's name and the date and time",
        "paraphrase",
        covers=("CL-12.AC4",),
    ),
    c(
        61,
        "Adjuster cannot reopen a closed claim",
        "Closed claim; adjuster signed in",
        "Choose Reopen",
        "Reopen is not available",
        "multi",
        covers=("CL-12.AC5",),
        tag="status",
    ),
    c(
        62,
        "Supervisor reopens a closed claim",
        "Closed claim; supervisor signed in",
        "Choose Reopen",
        "Claim is reopened",
        "multi",
        covers=("CL-12.AC5",),
        tag="status",
    ),
    # CL-13 payments
    c(
        63,
        "Payment goes to the bank account on file",
        "Policy with a bank account on file",
        "Release a payment",
        "Transfer is sent to that account",
        "direct",
        covers=("CL-13.AC1",),
        tag="payments",
        ref="CL-13.AC1",
    ),
    c(
        64,
        "Financed car payment",
        "Car financed by a bank that holds a lien",
        "Release the payment",
        "Payee shows both the policyholder and the finance company",
        "paraphrase",
        covers=("CL-13.AC2",),
        tag="payments",
        amount=LARGE,
    ),
    c(
        65,
        "Failed transfer is retried",
        "Bank rejects the first transfer",
        "Let the payment job run",
        "Transfer is attempted a second time",
        "partial",
        tag="payments",
    ),
    c(
        66,
        "Payment advice breakdown",
        "Approved claim",
        "Release the payment",
        "Advice shows gross loss, deductible and net payment",
        "direct",
        covers=("CL-13.AC5",),
        tag="payments",
    ),
    c(
        103,
        "Repair shop paid directly",
        "Policyholder chose a partner repair shop",
        "Release the payment",
        "Full amount is paid to the repair shop",
        "same_topic",
        tag="payments",
    ),
    # CL-14 total loss
    c(
        67,
        "Repair cost 80% of the car's value",
        "Car worth 10,000 USD; estimate 8,000 USD",
        "Run the total-loss check",
        "Car is declared a total loss",
        "boundary",
        covers=("CL-14.AC1",),
        tag="totalloss",
        ref="CL-14.AC1",
        amount=LARGE,
    ),
    c(
        68,
        "Repair cost 70% of the car's value",
        "Car worth 10,000 USD; estimate 7,000 USD",
        "Run the total-loss check",
        "Car is repaired, not a total loss",
        "boundary",
        tag="totalloss",
        amount=LARGE,
    ),
    c(
        69,
        "Total-loss settlement minus the deductible",
        "Car worth 12,000 USD; 500 USD deductible; owner gives up the car",
        "Calculate the settlement",
        "Settlement is 11,500 USD",
        "partial",
        tag="totalloss",
        amount=LARGE,
    ),
    c(
        70,
        "Ten days to answer the offer",
        "Total-loss offer made",
        "Accept on day 9 on one claim; on another claim open the offer on day 11",
        "Day 9 acceptance works; on day 11 accept and dispute are no longer offered",
        "direct",
        covers=("CL-14.AC3",),
        tag="totalloss",
        amount=LARGE,
    ),
    c(
        71,
        "Disputed offer goes to appraisal",
        "Total-loss offer made",
        "Dispute the offer",
        "An independent appraisal task is created",
        "direct",
        covers=("CL-14.AC4",),
        tag="totalloss",
        amount=LARGE,
    ),
    c(
        116,
        "Customer rejects the valuation",
        "Valuation sent to the customer",
        "Customer rejects it",
        "An outside appraiser is engaged to value the car",
        "paraphrase",
        covers=("CL-14.AC4",),
        amount=LARGE,
    ),
    c(
        108,
        "Total-loss settlement amount shown",
        "Car worth 9,000 USD",
        "Open the settlement screen",
        "Settlement of 9,000 USD is shown",
        "same_topic",
        tag="totalloss",
        amount=LARGE,
    ),
    # CL-15 rental and living expenses
    c(
        72,
        "Rental starts when the claim is reported",
        "Claim reported on 3 May",
        "Check the rental start date",
        "Rental is authorised from 3 May",
        "same_topic",
        tag="rental",
        amount=SMALL,
    ),
    c(
        73,
        "Rental ends after the repair",
        "Repair completed on 10 May",
        "Check the rental end date",
        "Rental ends on 13 May",
        "direct",
        covers=("CL-15.AC2",),
        tag="rental",
        ref="CL-15.AC2",
        amount=SMALL,
    ),
    c(
        74,
        "Hotel bill without proof",
        "Home claim; hotel bill entered without a receipt",
        "Submit the expense; then attach the receipt",
        "Expense is rejected until the receipt is attached",
        "paraphrase",
        covers=("CL-15.AC3",),
        policy="Home",
        claim="Fire",
        amount=MID,
    ),
    c(
        75,
        "Remaining rental days shown",
        "Rental with 12 days left",
        "Policyholder opens the claim page",
        "Page shows 'Rental days left: 12'",
        "direct",
        covers=("CL-15.AC4",),
        tag="rental",
        amount=SMALL,
    ),
    c(
        76,
        "No rental without the endorsement",
        "Auto policy without a rental endorsement",
        "Open the rental step",
        "Rental is not offered",
        "direct",
        covers=("CL-15.AC5",),
        tag="rental",
        amount=SMALL,
    ),
    # CL-16 subrogation
    c(
        77,
        "At-fault third party flags subrogation",
        "Police report names the other driver at fault",
        "Save the liability decision",
        "Claim is flagged for subrogation",
        "direct",
        covers=("CL-16.AC1",),
        tag="subrogation",
        ref="CL-16.AC1",
    ),
    c(
        78,
        "Recovered money is recorded",
        "Third party pays 2,000 USD",
        "Record the recovery",
        "2,000 USD recovery is saved on the claim",
        "same_topic",
        tag="subrogation",
    ),
    c(
        79,
        "Recovery on the financial summary",
        "Claim with a 1,200 USD recovery",
        "Open the financial summary",
        "Recovery of 1,200 USD is listed",
        "direct",
        covers=("CL-16.AC3",),
        tag="subrogation",
    ),
    c(
        104,
        "Manager views the subrogation file",
        "Open subrogation file",
        "Manager opens it",
        "The file and its notes are shown",
        "same_topic",
        tag="subrogation",
    ),
    # CL-17 supplements and reopening
    c(
        80,
        "Repair shop submits a supplement",
        "Repair shop with access to the claim",
        "Submit a supplement with photos of hidden damage",
        "Supplement is attached and pending review",
        "direct",
        covers=("CL-17.AC1",),
        tag="supplement",
        ref="CL-17.AC1",
    ),
    c(
        81,
        "Supplement of 1,200 USD needs re-inspection",
        "Supplement of 1,200 USD",
        "Try to approve it",
        "Approval is blocked until a re-inspection is recorded",
        "boundary",
        covers=("CL-17.AC2",),
        tag="supplement",
    ),
    c(
        82,
        "Supplement of 800 USD",
        "Supplement of 800 USD",
        "Approve it",
        "Approved without re-inspection",
        "boundary",
        tag="supplement",
        amount=SMALL,
    ),
    c(
        83,
        "Adjuster approves a small supplement",
        "Original payment 3,000 USD; supplement 1,500 USD",
        "Adjuster approves the supplement",
        "Supplement is approved",
        "boundary",
        tag="supplement",
    ),
    c(
        84,
        "Reopen for related damage",
        "Claim closed 11 months ago",
        "Reopen it for damage from the same accident",
        "Claim is reopened under its original claim number",
        "direct",
        covers=("CL-17.AC4", "CL-17.AC5"),
        tag="supplement",
    ),
    # CL-18 notifications
    c(
        85,
        "Email at each status change",
        "Claim moving from Reported to Paid",
        "Follow the claim through each status",
        "One email is sent for every change",
        "direct",
        covers=("CL-18.AC1",),
        tag="notifications",
        ref="CL-18.AC1",
    ),
    c(
        119,
        "Customer emailed on every step",
        "Claim moving through review and approval",
        "Approve and pay the claim",
        "Customer receives an email for each step",
        "paraphrase",
        covers=("CL-18.AC1",),
    ),
    c(
        86,
        "Opted-in policyholder gets texts",
        "Policyholder opted in to text messages",
        "Change the claim status",
        "A text message is sent",
        "multi",
        covers=("CL-18.AC2",),
        tag="notifications",
    ),
    c(
        87,
        "No texts without opt-in",
        "Policyholder did not opt in to text messages",
        "Change the claim status",
        "No text message is sent",
        "multi",
        covers=("CL-18.AC2",),
        tag="notifications",
    ),
    c(
        88,
        "Spanish-language updates",
        "Policyholder's preferred language is Spanish",
        "Change the claim status",
        "The email is in Spanish",
        "direct",
        covers=("CL-18.AC3",),
        tag="notifications",
    ),
    c(
        89,
        "Night-time message is held",
        "Status changes at 10 pm local time",
        "Check the outbox",
        "The message was not sent at 10 pm",
        "partial",
        tag="notifications",
    ),
    c(
        112,
        "Email to an invalid address",
        "Policyholder enters 'name@' as the email address",
        "Save the contact details",
        "Message 'Enter a valid email address'",
        "same_topic",
        tag="notifications",
    ),
    # CL-19 denials and appeals
    c(
        90,
        "Denial letter cites the clause",
        "Claim denied for wear and tear",
        "Open the denial letter",
        "Letter states the reason and the policy clause",
        "direct",
        covers=("CL-19.AC1",),
        tag="denial",
        ref="CL-19.AC1",
    ),
    c(
        91,
        "Denial of 9,000 USD",
        "Claim of 9,000 USD denied by an adjuster",
        "Send the denial letter",
        "Letter is sent without a manager review",
        "boundary",
        tag="denial",
        amount=LARGE,
    ),
    c(
        92,
        "Appeal deadline",
        "Claim denied 59 days ago, another denied 61 days ago",
        "Open each claim",
        "Appeal is possible on the first; the appeal option is gone on the second",
        "paraphrase",
        covers=("CL-19.AC3",),
        tag="denial",
    ),
    c(
        93,
        "Appeal goes to a different reviewer",
        "Claim denied by adjuster A",
        "Policyholder appeals",
        "Appeal is assigned to a reviewer other than adjuster A",
        "direct",
        covers=("CL-19.AC4",),
        tag="denial",
    ),
    c(
        105,
        "Appeal acknowledged by email",
        "Policyholder submits an appeal",
        "Check the inbox",
        "An acknowledgement email arrives",
        "same_topic",
        tag="denial",
    ),
    # CL-20 audit and permissions
    c(
        94,
        "Viewing a police report is logged",
        "Claim with a police report attached",
        "Adjuster opens the police report",
        "Audit log records the user and the time",
        "direct",
        covers=("CL-20.AC1",),
        tag="audit",
        ref="CL-20.AC1",
    ),
    c(
        95,
        "Call-centre view hides investigation data",
        "Claim with fraud flags and investigator notes",
        "Call-centre agent opens the claim",
        "Neither the flags nor the notes are shown",
        "paraphrase",
        covers=("CL-20.AC2",),
        tag="audit",
        channel="Phone",
    ),
    c(
        96,
        "Adjuster cannot edit a colleague's claim",
        "Claim assigned to another adjuster",
        "Open it and try to edit",
        "Claim is read-only",
        "direct",
        covers=("CL-20.AC3",),
        tag="audit",
    ),
    c(
        97,
        "Audit log is read-only for adjusters",
        "Adjuster signed in",
        "Open the audit log and try to change an entry",
        "Entries cannot be changed",
        "partial",
        tag="audit",
    ),
    c(
        106,
        "Manager exports a claim list",
        "Manager signed in",
        "Export open claims to CSV",
        "A CSV file is downloaded",
        "partial",
        tag="audit",
    ),
    # orphans: claim nothing and cover nothing
    c(
        98,
        "Change the portal colour theme",
        "Signed-in user",
        "Switch to the dark theme",
        "Pages use the dark theme",
        "orphan",
    ),
    c(
        99,
        "Download the mobile app",
        "Visitor on the home page",
        "Follow the app store link",
        "App store page opens",
        "orphan",
    ),
    c(
        100,
        "Update marketing email preferences",
        "Signed-in policyholder",
        "Unsubscribe from newsletters",
        "Newsletter preference is saved",
        "orphan",
    ),
    c(
        118,
        "Help centre search",
        "Visitor on the help centre",
        "Search for 'opening hours'",
        "Matching help articles are listed",
        "orphan",
    ),
    # extra cases that cover nothing more, to make the suite less tidy
    c(
        6,
        "Claim form keeps a draft",
        "Policyholder half-way through the claim form",
        "Close the browser and come back",
        "The draft is restored",
        "same_topic",
        tag="fnol",
    ),
]


def requirement_ids() -> list[str]:
    return [f"{s.id}.AC{n}" for s in STORIES for n in range(1, len(s.criteria) + 1)]


def labels() -> tuple[dict[str, list[str]], list[str]]:
    covered: dict[str, list[str]] = {}
    for case in sorted(CASES, key=lambda x: x.id):
        for ac in case.covers:
            covered.setdefault(ac, []).append(case.id)
    order = requirement_ids()
    covered = {ac: covered[ac] for ac in order if ac in covered}
    gaps = [ac for ac in order if ac not in covered]
    return covered, gaps


def check() -> None:
    """Fail loudly if the labels are inconsistent."""
    ids = [c.id for c in CASES]
    reqs = set(requirement_ids())
    assert len(ids) == len(set(ids)), "duplicate case IDs"
    _covered, gaps = labels()
    for case in CASES:
        assert set(case.covers) <= reqs, (case.id, case.covers)
        assert not case.ref or case.ref in reqs, (case.id, case.ref)
        if case.kind == "orphan":
            assert not (case.ref or case.tag or case.covers), case.id
        if case.kind == "decoy":
            assert case.ref in gaps and not case.covers, case.id
        if case.ref and case.kind != "decoy":
            assert case.ref in case.covers, (case.id, "ref must be truthful")
        if case.kind in {"partial", "same_topic"}:
            assert not case.covers, case.id
    assert len(reqs) == 100 and len(CASES) == 120, (len(reqs), len(CASES))


def spec_markdown() -> str:
    lines = [
        "# Quillmoor Mutual claims handling: user stories (fictional insurer, English)",
        "",
        "Synthetic spec for the Coverlens held-out claims domain. Quillmoor Mutual is",
        "fictional; the rules are invented and contain no data from any real insurer.",
        "",
    ]
    for story in STORIES:
        lines += [
            f"## {story.id} {story.title}",
            "",
            story.narrative,
            "",
            "Acceptance criteria:",
            "",
        ]
        for n, text in enumerate(story.criteria, start=1):
            lines.append(f"- **{story.id}.AC{n}** {text}")
        lines.append("")
    return "\n".join(lines)


def write_suite(path: Path) -> None:
    rng = random.Random(20261007)
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Claim tests"
    sheet.append(HEADER)
    for case in sorted(CASES, key=lambda x: x.id):
        sheet.append(
            [
                case.id,
                case.name,
                case.setup,
                case.steps,
                case.expected,
                rng.choice(["High", "Medium", "Medium", "Low"]),
                case.tag or None,
                case.ref or None,
                case.policy,
                case.claim,
                case.channel,
                case.tier if rng.random() > 0.3 else "Preferred",
                case.amount,
            ]
        )
    workbook.save(path)


def answer_key() -> dict[str, object]:
    covered, gaps = labels()
    return {
        "note": (
            "Answer key for the held-out claims domain. Built by an AI together "
            "with the cases; review disagreements before trusting the scores."
        ),
        "labelling_rule": (
            "A criterion is covered only when the listed cases, together, check "
            "every condition it states."
        ),
        "requirements": len(requirement_ids()),
        "cases": len(CASES),
        "covered": covered,
        "true_gaps": gaps,
        "decoys_claiming_gap_acs": [
            {"id": c.id, "claims": c.ref}
            for c in sorted(CASES, key=lambda x: x.id)
            if c.kind == "decoy"
        ],
        "orphan_cases": [
            c.id for c in sorted(CASES, key=lambda x: x.id) if c.kind == "orphan"
        ],
        "cases_with_blank_requirement_ref": sum(1 for c in CASES if not c.ref),
        "case_kinds": {c.id: c.kind for c in sorted(CASES, key=lambda x: x.id)},
    }


def build(out_dir: Path) -> None:
    check()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "user_stories.md").write_text(spec_markdown(), encoding="utf-8")
    write_suite(out_dir / "test_cases.xlsx")
    (out_dir / "answer_key.json").write_text(
        json.dumps(answer_key(), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DIR
    build(target)
    print(f"Wrote {target}")
