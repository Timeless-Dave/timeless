import { useState } from 'react';
import Folder from '@/components/Folder';
import Masonry from '@/components/Masonry';
import { approvalFields } from '@/lib/approvals';
import { api } from '@/lib/api';
import { mailChipTone, mailTypeLabel, relTime, stateLabel, when } from '@/lib/summary';

const OPP_KINDS = ['internship', 'hackathon', 'conference', 'other'];
const OPP_STATES = [
  'seen',
  'applied',
  'shortlisted',
  'interview',
  'waiting',
  'offer',
  'rejected',
  'skipped',
  'ignored',
];

export function EventsSection({ meetings, onRefresh, showToast, searchHide }) {
  const join = async id => {
    await api(`/api/meetings/${id}/join`, { method: 'POST', body: '{}' });
    showToast('Opening meeting…', 'mint');
    await onRefresh({ force: true });
  };

  const patch = async (id, body) => {
    await api(`/api/meetings/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
    await onRefresh({ force: true });
  };

  return (
    <section className={`card panel${searchHide ? ' search-hide' : ''}`} id="panel-events">
      <div className="card-head">
        <h2>Events</h2>
      </div>
      <div className="scroll">
        {meetings?.length ? (
          <table className="grid-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Title</th>
                <th>Type</th>
                <th>Join</th>
              </tr>
            </thead>
            <tbody>
              {meetings.map(m => (
                <tr key={m.id}>
                  <td>
                    {when(m.start_at)}
                    <br />
                    <span className="chip cyan">{relTime(m.start_at)}</span>
                  </td>
                  <td>{m.title}</td>
                  <td>
                    <select
                      value={m.modality || 'virtual'}
                      onChange={e => patch(m.id, { modality: e.target.value })}
                    >
                      <option value="virtual">Virtual</option>
                      <option value="physical">In person</option>
                    </select>
                  </td>
                  <td>
                    {m.join_url ? (
                      <button type="button" className="ghost" onClick={() => join(m.id)}>
                        Join
                      </button>
                    ) : null}
                    <input
                      placeholder="paste link"
                      defaultValue={m.join_url || ''}
                      onBlur={e => {
                        if (e.target.value !== (m.join_url || '')) patch(m.id, { join_url: e.target.value });
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-note">No events stored.</p>
        )}
      </div>
    </section>
  );
}

export function ProgramsSection({
  opportunities,
  googleState,
  onRefresh,
  showToast,
  searchHide,
  topPrograms,
  reduce,
}) {
  const [form, setForm] = useState({
    company: '',
    role: '',
    kind: 'internship',
    url: '',
    deadline_at: '',
  });
  const [busy, setBusy] = useState(false);

  const patchOpp = async (id, body) => {
    await api(`/api/opportunities/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
    await onRefresh({ force: true });
  };

  const setState = async (id, state) => {
    await api(`/api/opportunities/${id}/state`, {
      method: 'POST',
      body: JSON.stringify({ state }),
    });
    await onRefresh({ force: true });
  };

  const addOpp = async e => {
    e.preventDefault();
    setBusy(true);
    try {
      await api('/api/opportunities', { method: 'POST', body: JSON.stringify(form) });
      setForm({ company: '', role: '', kind: 'internship', url: '', deadline_at: '' });
      showToast('Posting added.', 'mint');
      await onRefresh({ force: true });
    } catch (err) {
      showToast(err.message);
    } finally {
      setBusy(false);
    }
  };

  const exportCsv = () => {
    const rows = opportunities || [];
    if (!rows.length) {
      showToast('Nothing to export yet.');
      return;
    }
    const columns = ['company', 'role', 'kind', 'state', 'deadline_at', 'url', 'source', 'updated_at'];
    const csvCell = v => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const csv = [columns, ...rows.map(row => columns.map(key => row[key]))]
      .map(row => row.map(csvCell).join(','))
      .join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    link.download = 'timeless-programs.csv';
    link.click();
    URL.revokeObjectURL(link.href);
    showToast('CSV ready for Google Sheets.', 'mint');
  };

  const syncGoogle = async () => {
    setBusy(true);
    try {
      const out = await api('/api/integrations/google/sync', { method: 'POST' });
      showToast(`${out.rows} programs synced.`, 'mint');
      await onRefresh({ force: true });
    } catch (err) {
      showToast(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={`card panel${searchHide ? ' search-hide' : ''}`} id="panel-programs">
      <div className="card-head">
        <h2>Programs</h2>
        <div className="row">
          <button type="button" className="ghost" onClick={exportCsv}>
            Export CSV
          </button>
          {googleState?.connected ? (
            <button type="button" className="ghost" disabled={busy} onClick={syncGoogle}>
              Sync Sheets
            </button>
          ) : googleState?.configured ? (
            <button
              type="button"
              className="ghost"
              disabled={busy}
              onClick={async () => {
                const out = await api('/api/integrations/google/connect', { method: 'POST' });
                location.href = out.authorization_url;
              }}
            >
              Connect Google
            </button>
          ) : null}
          {googleState?.spreadsheet_url ? (
            <a className="ghost" href={googleState.spreadsheet_url} target="_blank" rel="noopener">
              View sheet
            </a>
          ) : null}
        </div>
      </div>
      {topPrograms.length ? (
        <div className="folder-programs">
          <Folder
            size={1.15}
            color="#d08726"
            items={topPrograms.map(o => (
              <span key={o.id}>{o.role || o.company}</span>
            ))}
          />
          <p className="folder-programs__caption">
            Top {topPrograms.length} open — click the folder to preview
          </p>
        </div>
      ) : null}
      <div className="scroll">
        {opportunities?.length ? (
          <table className="grid-table tracker-table">
            <thead>
              <tr>
                <th>Company</th>
                <th>Role</th>
                <th>Kind</th>
                <th>Status</th>
                <th>Deadline</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map(o => (
                <tr key={o.id}>
                  <td data-label="Company">
                    <input
                      defaultValue={o.company || ''}
                      onBlur={e => {
                        if (e.target.value !== (o.company || '')) patchOpp(o.id, { company: e.target.value });
                      }}
                    />
                  </td>
                  <td data-label="Role">
                    <input
                      defaultValue={o.role || ''}
                      onBlur={e => {
                        if (e.target.value !== (o.role || '')) patchOpp(o.id, { role: e.target.value });
                      }}
                    />
                  </td>
                  <td data-label="Kind">
                    <select
                      defaultValue={o.kind || 'internship'}
                      onChange={e => patchOpp(o.id, { kind: e.target.value })}
                    >
                      {OPP_KINDS.map(k => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td data-label="Status">
                    <select value={o.state || 'seen'} onChange={e => setState(o.id, e.target.value)}>
                      {OPP_STATES.map(s => (
                        <option key={s} value={s}>
                          {stateLabel(s)}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td data-label="Deadline">
                    <input
                      type="date"
                      defaultValue={(o.deadline_at || '').slice(0, 10)}
                      onBlur={e => {
                        if (e.target.value !== (o.deadline_at || '').slice(0, 10))
                          patchOpp(o.id, { deadline_at: e.target.value });
                      }}
                    />
                  </td>
                  <td data-label="URL">
                    <input
                      type="url"
                      defaultValue={o.url || ''}
                      onBlur={e => {
                        if (e.target.value !== (o.url || '')) patchOpp(o.id, { url: e.target.value });
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-note">No postings yet.</p>
        )}
      </div>
      <form className="tracker-add row" onSubmit={addOpp}>
        <input
          placeholder="Company"
          value={form.company}
          onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
        />
        <input
          placeholder="Role"
          required
          value={form.role}
          onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
        />
        <select value={form.kind} onChange={e => setForm(f => ({ ...f, kind: e.target.value }))}>
          {OPP_KINDS.map(k => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <input
          type="url"
          placeholder="URL"
          required
          value={form.url}
          onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
        />
        <input
          type="date"
          value={form.deadline_at}
          onChange={e => setForm(f => ({ ...f, deadline_at: e.target.value }))}
        />
        <button type="submit" disabled={busy}>
          Add
        </button>
      </form>
    </section>
  );
}

export function MailSection({ mail, mailMasonryItems, reduce, searchHide }) {
  return (
    <section className={`card panel${searchHide ? ' search-hide' : ''}`} id="panel-mail">
      <div className="card-head">
        <h2>Mail</h2>
      </div>
      <div className="masonry-slot">
        {mailMasonryItems.length ? (
          <Masonry items={mailMasonryItems} blurToFocus={!reduce} />
        ) : (
          <p className="empty-note">No actionable mail cards.</p>
        )}
      </div>
      {mail?.length ? (
        <table className="grid-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Subject</th>
            </tr>
          </thead>
          <tbody>
            {mail.map(m => {
              const label = mailTypeLabel(m);
              return (
                <tr key={m.id}>
                  <td>
                    <span className={`chip ${mailChipTone(label)}`}>{label}</span>
                  </td>
                  <td>{m.subject}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export function RitualsSection({ rituals, onRefresh, showToast, searchHide }) {
  return (
    <section className={`card panel${searchHide ? ' search-hide' : ''}`} id="panel-rituals">
      <div className="card-head">
        <h2>Rituals</h2>
      </div>
      {rituals?.length ? (
        <div className="approval-list">
          {rituals.map(r => (
            <article key={r.id} className="approval-item">
              <div className="approval-head">
                <strong className="approval-title">{r.name}</strong>
                {r.launch_url ? (
                  <a className="approval-kind" href={r.launch_url} target="_blank" rel="noopener">
                    Open link
                  </a>
                ) : null}
              </div>
              <div className="approval-actions">
                <button
                  type="button"
                  onClick={async () => {
                    const res = await api(`/api/rituals/${r.id}/done`, { method: 'POST' });
                    showToast(res.praise || 'Ritual marked done.', 'mint');
                    await onRefresh({ force: true });
                  }}
                >
                  Done
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-note">No rituals pinned.</p>
      )}
    </section>
  );
}

export function ApprovalsSection({ approvals, onRefresh, showToast, searchHide }) {
  const act = async (id, action) => {
    await api(`/api/approvals/${id}/${action}`, { method: 'POST' });
    showToast('Approval updated.');
    await onRefresh({ force: true });
  };

  return (
    <section className={`card panel${searchHide ? ' search-hide' : ''}`} id="panel-approvals">
      <div className="card-head">
        <h2>Approvals</h2>
      </div>
      {approvals?.length ? (
        <div className="approval-list">
          {approvals.map(a => {
            const f = approvalFields(a.kind, a.payload);
            return (
              <article key={a.id} className="approval-item">
                <div className="approval-head">
                  <strong className="approval-title">{f.title}</strong>
                  <span className="approval-kind">{a.kind.replace(/_/g, ' ')}</span>
                </div>
                <div className="approval-body">
                  {f.lines.length ? (
                    f.lines.map((l, i) => (
                      <div key={i} className="approval-field">
                        <span className="approval-label">{l.label}</span>
                        <span className="approval-value">
                          {l.value.length > 220 ? l.value.slice(0, 217) + '…' : l.value}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="approval-empty">No details.</p>
                  )}
                </div>
                {f.hint ? <p className="approval-hint">{f.hint}</p> : null}
                <div className="approval-actions">
                  <button type="button" onClick={() => act(a.id, 'accept')}>
                    Accept
                  </button>
                  <button type="button" className="ghost" onClick={() => act(a.id, 'keep')}>
                    Keep seen
                  </button>
                  <button type="button" className="ghost" onClick={() => act(a.id, 'reject')}>
                    Ignore
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="empty-note">None pending.</p>
      )}
    </section>
  );
}
