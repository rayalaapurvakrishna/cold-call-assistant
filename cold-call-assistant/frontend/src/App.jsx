import React, { useEffect, useState } from 'react';
import {
  Phone, History, ChevronRight, Check, Clock, Sparkles, Save, X,
  Loader2, MessageSquareText, BarChart3, ArrowUpRight, FileText,
  ShieldCheck, RefreshCw, AlertCircle,
} from 'lucide-react';
import { stages } from './stages';
import { research } from './research';

const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const emptyForm = { prospect_name: '', company_name: '', role: '', phone_note: '' };
const outcomeOptions = [
  ['next_step_agreed', 'Next step agreed'],
  ['agreed_to_receive_report', 'Agreed to receive report'],
  ['interested', 'Interested, no fixed next step'],
  ['follow_up', 'Follow-up needed'],
  ['call_again', 'Call again / line issue'],
  ['not_interested', 'Not interested'],
  ['do_not_call', 'Do not call'],
  ['wrong_person', 'Wrong person'],
  ['moved_company', 'Moved company'],
  ['not_logged', 'Not logged / unclear'],
];

function App() {
  const [page, setPage] = useState('call');
  const [call, setCall] = useState(null);
  const [stage, setStage] = useState(1);
  const [furthestStage, setFurthestStage] = useState(1);
  const [drafts, setDrafts] = useState({});
  const [outcome, setOutcome] = useState('');
  const [history, setHistory] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(false);
  const [ai, setAi] = useState('');
  const [toast, setToast] = useState('');
  const [showEnd, setShowEnd] = useState(false);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [serviceHealth, setServiceHealth] = useState(null);

  const current = stages[stage - 1];
  const draft = drafts[stage] || { actions: [], words: '', note: '' };
  const pct = Math.round((stage / 8) * 100);

  const notify = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 2800);
  };

  async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try { const body = await response.json(); message = body.detail || message; } catch { /* use status */ }
      throw new Error(message);
    }
    return response.json();
  }

  async function loadHistory() {
    try {
      const data = await request('/calls');
      setHistory(data.calls || []);
    } catch (error) {
      notify('Could not load call history. Check the backend connection.');
    }
  }

  useEffect(() => {
    loadHistory();
    request('/health').then(setServiceHealth).catch(() => setServiceHealth({ status: 'offline', database: 'unavailable', ai: 'unavailable' }));
  }, []);

  function updateDraft(field, value) {
    setDrafts((previous) => ({
      ...previous,
      [stage]: { actions: [], words: '', note: '', ...(previous[stage] || {}), [field]: value },
    }));
  }

  async function startCall() {
    setLoading(true);
    try {
      const data = await request('/calls', { method: 'POST', body: JSON.stringify(form) });
      setCall(data.call);
      setStage(1);
      setFurthestStage(1);
      setDrafts({});
      setFurthestStage(1);
      setOutcome('');
      setAi('');
      setPage('call');
      notify('Call started. Keep the prospect’s words verbatim.');
    } catch (error) {
      notify(error.message || 'Backend unavailable. Check the API URL.');
    } finally { setLoading(false); }
  }

  async function saveStage(nextStage = null) {
    if (!call) return;
    setLoading(true);
    try {
      await request(`/calls/${call.id}/stage`, {
        method: 'POST',
        body: JSON.stringify({
          stage_number: stage,
          stage_reached: Math.max(furthestStage, nextStage || stage),
          actions: draft.actions,
          prospect_words: draft.words,
          caller_note: draft.note,
        }),
      });
      if (nextStage) { setStage(nextStage); setFurthestStage((previous) => Math.max(previous, nextStage)); }
      setAi('');
      notify('Stage saved');
    } catch (error) {
      notify(error.message || 'Could not save this stage. Your draft is still on screen.');
    } finally { setLoading(false); }
  }

  async function endCall() {
    if (!call || !outcome) return;
    setLoading(true);
    try {
      await request(`/calls/${call.id}/close`, {
        method: 'POST',
        body: JSON.stringify({
          outcome,
          final_note: draft.note,
          prospect_words: draft.words,
          actions: draft.actions,
          caller_note: draft.note,
          current_stage: stage,
          stage_reached: Math.max(furthestStage, stage),
        }),
      });
      setCall(null);
      setShowEnd(false);
      setDrafts({});
      setFurthestStage(1);
      setOutcome('');
      setPage('history');
      await loadHistory();
      notify('Call and final stage saved');
    } catch (error) {
      notify(error.message || 'Could not close call. Your notes are still on screen.');
    } finally { setLoading(false); }
  }

  async function askAI(kind) {
    if (!call) return;
    setLoading(true);
    setAi('');
    try {
      const data = await request(`/ai/${kind}`, {
        method: 'POST',
        body: JSON.stringify({
          stage_number: stage,
          prospect_words: draft.words,
          caller_note: draft.note,
          company_name: call.company_name || form.company_name,
          history: draft.actions,
        }),
      });
      setAi(data.result || 'No suggestion returned.');
    } catch (error) {
      setAi(error.message || 'AI could not respond. Check the Gemini key and backend logs.');
    } finally { setLoading(false); }
  }

  async function openDetail(item) {
    setDetailLoading(true);
    try {
      const data = await request(`/calls/${item.id}`);
      setDetail(data);
    } catch (error) { notify(error.message || 'Could not load call details.'); }
    finally { setDetailLoading(false); }
  }

  function goToStage(number) {
    setStage(number);
    setFurthestStage((previous) => Math.max(previous, number));
    setAi('');
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brandmark"><Phone size={18} /></div>
          <span>Call<span className="blue">Guide</span></span>
          <small>MERIDIAN GROWTH PARTNERS</small>
        </div>
        <nav>
          <button className={page === 'call' ? 'nav active' : 'nav'} onClick={() => setPage('call')}><Phone size={16} /> Live call</button>
          <button className={page === 'history' ? 'nav active' : 'nav'} onClick={() => { setPage('history'); loadHistory(); }}><History size={16} /> Past calls</button>
          <button className={page === 'research' ? 'nav active' : 'nav'} onClick={() => setPage('research')}><BarChart3 size={16} /> Research</button>
        </nav>
        <div className={`live-pill ${serviceHealth?.status === 'ok' ? 'online' : serviceHealth?.status === 'offline' ? 'offline' : ''}`}><i /> {serviceHealth?.status === 'ok' ? 'API ONLINE' : serviceHealth?.status === 'offline' ? 'API OFFLINE' : 'CONNECTING'}</div>
      </header>

      <main>
        {page === 'call' && !call && (
          <section className="welcome">
            <div className="eyebrow">MERIDIAN GROWTH PARTNERS · GROWTH CALLS</div>
            <h1>Make every call<br /><em>worth the conversation.</em></h1>
            <p className="intro">A calm, evidence-led guide for real conversations. Keep the structure in view and the prospect’s words at the centre.</p>
            <div className="research-strip">
              <div><b>{research.sampleSize}</b><span>calls reviewed</span></div>
              <div><b>1m 34s</b><span>median call length</span></div>
              <div><b>{research.underTwoMinutes}%</b><span>under two minutes</span></div>
              <button onClick={() => setPage('research')}>See research <ArrowUpRight size={14} /></button>
            </div>
            <div className="start-card">
              <div><div className="eyebrow">START A NEW CALL</div><h2>Who are you calling?</h2></div>
              <div className="formgrid">
                <label>Prospect name<input value={form.prospect_name} onChange={(e) => setForm({ ...form, prospect_name: e.target.value })} placeholder="e.g. Anjali Menon" /></label>
                <label>Company<input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="Company name" /></label>
                <label>Role / title<input value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} placeholder="e.g. Founder, Director" /></label>
                <label>Caller context<input value={form.phone_note} onChange={(e) => setForm({ ...form, phone_note: e.target.value })} placeholder="Optional context" /></label>
              </div>
              <button className="primary start" onClick={startCall} disabled={loading}>{loading ? <Loader2 className="spin" /> : <Phone size={17} />} Start call <ChevronRight size={17} /></button>
            </div>
            <div className="stage-preview"><div className="eyebrow">THE CALL, AT A GLANCE</div><div className="mini-stages">{stages.map((item) => <div key={item.id}><span>{String(item.id).padStart(2, '0')}</span><b>{item.name}</b></div>)}</div></div>
          </section>
        )}

        {page === 'call' && call && (
          <section className="workspace">
            <div className="call-head">
              <div><div className="eyebrow">LIVE CALL <span className="dotlive" /> IN PROGRESS</div><h1>{call.prospect_name || 'New prospect'}</h1><p>{call.company_name || 'Company not specified'} {call.role ? `· ${call.role}` : ''}</p></div>
              <button className="ghost" onClick={() => setShowEnd(true)}><X size={16} /> End call</button>
            </div>
            <div className="progress">
              <div className="progressline"><span style={{ width: `${pct}%` }} /></div>
              <div className="stepstrip">{stages.map((item) => <button key={item.id} className={`${stage === item.id ? 'chosen ' : ''}${stage > item.id ? 'done' : ''}`} onClick={() => goToStage(item.id)} title={item.name}><span>{stage > item.id ? <Check size={12} /> : item.id}</span></button>)}</div>
              <div className="progress-caption">STAGE {stage} OF 8 <span>{pct}% OF THE STRUCTURE</span></div>
            </div>
            <div className="workgrid">
              <article className="stagecard">
                <div className="stage-meta"><span>STAGE {String(stage).padStart(2, '0')}</span><span className="time"><Clock size={13} /> LIVE GUIDE</span></div>
                <div className="stage-title"><div className="number">{stage}</div><div><h2>{current.name}</h2><p>{current.purpose}</p></div></div>
                <div className="section-label">WHAT THE PROSPECT MAY SAY</div>
                <div className="saylist">{current.tends.map((item, index) => <div key={index}><MessageSquareText size={15} /><span>“{item}”</span></div>)}</div>
                {current.coach && <div className="stage-coach"><b>LISTEN FOR</b><span>{current.coach}</span></div>}
                <div className="section-label">WHAT HAPPENED AT THIS STAGE?</div>
                <div className="actiongrid">{current.actions.map((action) => <button key={action} onClick={() => updateDraft('actions', draft.actions.includes(action) ? draft.actions.filter((x) => x !== action) : [...draft.actions, action])} className={draft.actions.includes(action) ? 'action selected' : 'action'}>{draft.actions.includes(action) && <Check size={14} />} {action}</button>)}</div>
                <label className="textarea-label">PROSPECT’S WORDS <span>Capture what they actually said, not your interpretation.</span><textarea value={draft.words} onChange={(e) => updateDraft('words', e.target.value)} placeholder="Type the prospect’s exact words…" /></label>
                <label className="textarea-label">CALLER NOTE <span>Optional context for the next call.</span><textarea className="smallarea" value={draft.note} onChange={(e) => updateDraft('note', e.target.value)} placeholder="Short factual note…" /></label>
                <div className="airow">
                  <button className="ai-button" onClick={() => askAI('suggest-stage')} disabled={loading}><Sparkles size={15} /> AI stage coach</button>
                  <button className="ai-button" onClick={() => askAI('structure-notes')} disabled={loading}><FileText size={15} /> Structure notes</button>
                </div>
                {ai && <div className="airesult"><b><Sparkles size={14} /> AI assistant · verify before saving</b><p>{ai}</p></div>}
                <div className="stage-footer">
                  <button className="primary" disabled={loading} onClick={() => stage < 8 ? saveStage(stage + 1) : setShowEnd(true)}>{loading ? <Loader2 className="spin" /> : <Save size={15} />}{stage < 8 ? `Save & next: ${stages[stage].name}` : 'Finish this call'} <ChevronRight size={17} /></button>
                  <button className="ghost" onClick={() => setShowEnd(true)}>End call</button>
                </div>
              </article>
              <aside className="sidecard">
                <div className="eyebrow">CALL STRUCTURE</div><h3>Stay with the conversation.</h3><p>Most calls do not reach the end. Record what happened honestly; a short call is still useful data.</p>
                <div className="side-stages">{stages.map((item) => <button key={item.id} onClick={() => goToStage(item.id)} className={stage === item.id ? 'current' : stage > item.id ? 'passed' : ''}><span>{stage > item.id ? <Check size={13} /> : item.id}</span><b>{item.name}</b>{stage === item.id && <i>NOW</i>}</button>)}</div>
                <div className="tip"><b>FIELD NOTE</b><p>{stage === 5 ? 'This is the key evidence field. Preserve the prospect’s own language; do not turn it into a pitch.' : stage === 7 ? 'A document request, a callback and a scheduled meeting are different levels of commitment.' : 'You can jump to any stage. Draft notes are kept when you move between stages.'}</p></div>
              </aside>
            </div>
          </section>
        )}

        {page === 'history' && (
          <section className="history">
            <div className="eyebrow">CALL RECORDS</div><h1>Past calls</h1><p className="intro">Every saved conversation, with the stage it reached and what happened next.</p>
            <div className="history-toolbar"><span>{history.length} saved {history.length === 1 ? 'call' : 'calls'}</span><button className="ghost" onClick={loadHistory}><RefreshCw size={14} /> Refresh</button></div>
            {history.length === 0 ? <div className="empty"><History size={30} /><h3>No saved calls yet</h3><p>Completed calls will appear here.</p><button className="primary" onClick={() => setPage('call')}>Start your first call</button></div> : (
              <div className="historylist">{history.map((item) => <button className="historyrow" key={item.id} onClick={() => openDetail(item)}>
                <div className="hist-icon"><Phone size={17} /></div><div className="hist-main"><b>{item.prospect_name || 'Unknown prospect'}{item.company_name ? `, ${item.company_name}` : ''}</b><span>{item.final_note || item.outcome || 'Call saved'} · {item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span></div>
                <div className="hist-stage"><b>{stages[(item.stage_reached || 1) - 1]?.name || 'Opening'}</b><small>STAGE {item.stage_reached || 1}</small></div><span className="outcome">{(item.outcome || 'not logged').replaceAll('_', ' ')}</span><ChevronRight size={16} />
              </button>)}</div>
            )}
            {detailLoading && <div className="detail-loading"><Loader2 className="spin" /> Loading call details…</div>}
          </section>
        )}

        {page === 'research' && (
          <section className="research-page">
            <div className="eyebrow">PRODUCT DECISIONS · RESEARCH SAMPLE</div><h1>Built from real call patterns.</h1>
            <p className="intro">The supplied 100-call dataset was reviewed to shape the experience. These are aggregate observations only; individual transcript names and raw conversations are not shipped in this app.</p>
            <div className="research-stats"><div><b>100</b><span>fictionalised transcripts</span></div><div><b>1:34</b><span>median recording length</span></div><div><b>68%</b><span>under two minutes</span></div><div><b>10</b><span>distinct logged outcomes</span></div></div>
            <div className="research-grid">
              <article className="research-card"><div className="eyebrow">OUTCOME DISTRIBUTION</div><h2>How the calls were logged</h2><p>Counts are from the supplied sample, not from this app’s users.</p>
                <div className="bars">{research.outcomes.map((item) => <div className="barrow" key={item.key}><div><span>{item.label}</span><b>{item.count}</b></div><i><span style={{ width: `${item.count / research.sampleSize * 100}%` }} /></i></div>)}</div>
              </article>
              <article className="research-card"><div className="eyebrow">DESIGN DECISIONS</div><h2>What the evidence changed</h2><div className="decision-list">{research.decisions.map((item, index) => <div key={item.title}><span>{String(index + 1).padStart(2, '0')}</span><section><b>{item.title}</b><p>{item.body}</p></section></div>)}</div></article>
            </div>
            <div className="research-footnote"><ShieldCheck size={17} /><p><b>Responsible use:</b> The source dataset says its people and companies are fictionalised and the transcripts are for this task only. CallGuide uses aggregate counts and generalized patterns, not names or raw transcript text.</p></div>
          </section>
        )}
      </main>

      <footer><span>CALLGUIDE <b>·</b> BUILT FOR BETTER CONVERSATIONS</span><span>AI assists. The caller decides.</span></footer>

      {showEnd && <div className="modalback"><div className="modal"><button className="modalx" onClick={() => setShowEnd(false)}><X /></button><div className="eyebrow">FINISH THIS CALL</div><h2>How did the call end?</h2><p>Choose the closest honest outcome. A polite goodbye is not the same as interest.</p><div className="outcomes">{outcomeOptions.map(([value, label]) => <button key={value} className={outcome === value ? 'selected' : ''} onClick={() => setOutcome(value)}>{label}</button>)}</div><button className="primary full" onClick={endCall} disabled={loading || !outcome}>{loading ? <Loader2 className="spin" /> : <Save size={16} />} Save call</button></div></div>}

      {detail && <div className="modalback" onClick={() => setDetail(null)}><div className="modal detail-modal" onClick={(event) => event.stopPropagation()}><button className="modalx" onClick={() => setDetail(null)}><X /></button><div className="eyebrow">CALL REVIEW</div><h2>{detail.call.prospect_name || 'Unknown prospect'}</h2><p>{detail.call.company_name || 'Company not specified'} · {detail.call.outcome?.replaceAll('_', ' ')}</p><div className="detail-timeline">{(detail.stages || []).map((item) => <div key={item.stage_number}><span>{item.stage_number}</span><section><b>{stages[item.stage_number - 1]?.name}</b><small>{(item.actions || []).join(' · ')}</small>{item.prospect_words && <blockquote>“{item.prospect_words}”</blockquote>}{item.caller_note && <p>{item.caller_note}</p>}</section></div>)}</div></div></div>}
      {toast && <div className="toast"><AlertCircle size={15} /> {toast}</div>}
    </div>
  );
}

export default App;
