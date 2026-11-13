export const stages = [
  {
    "id": 1,
    "name": "Opening",
    "purpose": "Reach the right person and say who you are. The prospect decides in the first few seconds whether this call is worth a minute.",
    "tends": [
      "Who is calling, and from which company?",
      "I am in a meeting, driving, or on another call.",
      "This number belongs to someone who left the company.",
      "You have reached the wrong person or department."
    ],
    "actions": [
      "Confirmed the right person",
      "Asked who is calling / from where",
      "Unavailable right now",
      "Wrong person / outdated contact"
    ],
    "next": "Purpose",
    "coach": "Do not mistake a receptionist, assistant or outdated contact for the decision-maker. Confirm who you have reached."
  },
  {
    "id": 2,
    "name": "Purpose",
    "purpose": "Explain in one or two sentences why you called, in words the prospect can repeat to a colleague.",
    "tends": [
      "What is this regarding?",
      "What does your company actually do?",
      "Where did you get my number?",
      "Is this a report, consulting service, or sales call?"
    ],
    "actions": [
      "Asked what we do",
      "Asked where we got the number",
      "Asked how the service works",
      "Understood the reason"
    ],
    "next": "Permission",
    "coach": "If they ask who you are or where you got the number, answer plainly before repeating the pitch."
  },
  {
    "id": 3,
    "name": "Permission",
    "purpose": "Find out whether they are willing to talk now. A clear yes, a clear no, or a time to call back are all useful outcomes.",
    "tends": [
      "Call me after this meeting / later today.",
      "I am travelling or driving; keep it brief.",
      "Send the company profile or report first.",
      "Yes, go ahead — but they may still be distracted."
    ],
    "actions": [
      "Agreed to talk now",
      "Asked for a callback at a time",
      "Asked for information first",
      "Unavailable / no permission"
    ],
    "next": "Their business",
    "coach": "A callback request is a useful outcome. Record the time they gave; do not keep pitching while they are unavailable."
  },
  {
    "id": 4,
    "name": "Their business",
    "purpose": "Ask about their company and their work before saying anything more about yours.",
    "tends": [
      "I handle a different function or department.",
      "The head office / corporate team makes this decision.",
      "I am not the right person; speak to this colleague.",
      "That person left the company or this number is outdated."
    ],
    "actions": [
      "Explained their business / role",
      "Pointed to the right department",
      "Referred us to a decision-maker",
      "Wrong contact / moved company"
    ],
    "next": "Their need, in their words",
    "coach": "Let them describe the business. Avoid correcting them or switching to your pitch too early."
  },
  {
    "id": 5,
    "name": "Their need, in their words",
    "purpose": "Hear what they are trying to do or struggling with, in their own words. Capture the exact words rather than a sales interpretation.",
    "tends": [
      "Our priority is revenue, profitability, or expansion.",
      "We need skilled manpower / new products / better capacity.",
      "Sustainability or operational improvement matters to us.",
      "We are doing fine, or I cannot share internal plans."
    ],
    "actions": [
      "Shared a specific goal / challenge",
      "Said there is no current need",
      "Withheld confidential information",
      "Asked how we could help"
    ],
    "next": "Objection",
    "coach": "Capture the actual phrase. Do not translate a vague answer into a need they did not state."
  },
  {
    "id": 6,
    "name": "Objection",
    "purpose": "Understand the reason for a no. A reason you understand can be answered now or later; a reason you talked over cannot.",
    "tends": [
      "We already have an internal team or consultant.",
      "Our global contracts / head office handle this.",
      "I cannot share company data with an outside party.",
      "I am not the decision-maker or this is not relevant."
    ],
    "actions": [
      "Existing provider / internal team",
      "Wrong decision-maker / department",
      "Confidentiality / data concern",
      "Declined / no current need"
    ],
    "next": "Next step",
    "coach": "Separate an existing provider, a wrong contact, lack of need and lack of budget. They call for different responses."
  },
  {
    "id": 7,
    "name": "Next step",
    "purpose": "Agree one concrete thing: a document, a call at a named time, or a meeting. Name the channel or time.",
    "tends": [
      "Send your company profile, sample, or report by email.",
      "WhatsApp it to me; I will review and respond.",
      "Call next week / at a specific time.",
      "Speak to this colleague or arrange a working session."
    ],
    "actions": [
      "Report / profile by email or WhatsApp",
      "Callback at a named time",
      "Meeting / working session agreed",
      "Referral to the right person"
    ],
    "next": "Close",
    "coach": "Name the deliverable, channel and time. A yes to receiving information is not the same as a meeting."
  },
  {
    "id": 8,
    "name": "Close",
    "purpose": "End clearly and record what happened: the outcome, the next step, and the prospect's exact words from stage 5.",
    "tends": [
      "A polite goodbye after a refusal — still a no.",
      "They agree to review information but no meeting is set.",
      "A specific callback or meeting time is confirmed.",
      "The contact is wrong, has moved, or asks not to be called."
    ],
    "actions": [
      "Concrete next step agreed",
      "Information sent / follow-up needed",
      "Not interested / no need",
      "Do not call / wrong contact"
    ],
    "coach": "Close politely and record the outcome accurately. A warm goodbye does not reverse a no."
  }
];
