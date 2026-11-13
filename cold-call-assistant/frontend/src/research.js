// Aggregated, non-identifying observations from the supplied 100-call research sample.
// The raw transcripts and names are intentionally not shipped in the public application.
export const research = {
  sampleSize: 100,
  medianSeconds: 93.5,
  underTwoMinutes: 68,
  outcomes: [
    { key: 'not_interested', label: 'Not interested', count: 14 },
    { key: 'agreed_to_receive_report', label: 'Agreed to receive report', count: 14 },
    { key: 'follow_up', label: 'Follow-up', count: 14 },
    { key: 'not_logged', label: 'Not logged', count: 13 },
    { key: 'next_step_agreed', label: 'Next step agreed', count: 11 },
    { key: 'do_not_call', label: 'Do not call', count: 10 },
    { key: 'wrong_person', label: 'Wrong person', count: 8 },
    { key: 'interested', label: 'Interested', count: 7 },
    { key: 'moved_company', label: 'Moved company', count: 5 },
    { key: 'call_again', label: 'Call again', count: 4 },
  ],
  decisions: [
    { title: 'A short call is normal', body: '68 of the 100 recordings are under two minutes. The guide keeps the stage, quick taps and note field visible without forcing a long form.' },
    { title: 'A report request is not a meeting', body: 'The dataset separates report acceptance, interest, follow-up and a concrete next step. CallGuide preserves those as different outcomes.' },
    { title: 'Wrong person is a valid result', body: 'The caller can record a referral, a moved contact or a wrong person instead of pushing the conversation through the sales stages.' },
    { title: 'The prospect’s wording matters', body: 'Stage 5 has a dedicated verbatim field. AI summaries preserve quotes and original-language phrases instead of inventing needs or silently translating them.' },
    { title: 'The calls are multilingual', body: 'The sample includes English, Hindi/Hinglish, Marathi and a request for Kannada. The note field accepts Unicode, and the AI is instructed to preserve the prospect’s original wording.' },
    { title: 'A clear no must stay a no', body: 'The close flow includes “Do not call”, and the AI guidance explicitly prohibits suggesting another pitch after a clear refusal.' },
  ],
};
