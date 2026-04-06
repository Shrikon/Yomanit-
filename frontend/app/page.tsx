'use client';
import React, { useState, useEffect } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'https://yomanit.onrender.com';
let BEZEQ_TEMPLATE_ID = '34967fa4-a92c-4876-bf73-f6cf05804519';

interface Municipality { id: string; name: string; code: string; }
interface UploadRow { row_num: number; phone: string; name: string; amount: number; date: string; invoice: string; account: string | null; has_index: boolean; description: string | null; }
interface UploadResult { filename: string; total_rows: number; matched: number; missing: number; rows: UploadRow[]; invoice_num: string; date_from: string; date_to: string; balance_ok: boolean; balance_diff: number; invoice_total: number; }
interface JournalEntry { id: string; reference_num: string; period: string; status: string; total_amount: number; created_at: string; }
interface IndexRow { id: string; key_value: string; account_code: string; connection_name: string; description: string; }

async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

const CATEGORIES = [
  { id: 'bezeq',       label: 'בזק',    icon: '📞', active: true },
  { id: 'electricity', label: 'חשמל',   icon: '⚡', active: true },
  { id: 'welfare',     label: 'רווחה',  icon: '🏥', active: true },
  { id: 'celcom',      label: 'סלקום',  icon: '📱', active: true },
  { id: 'leasing',     label: 'ליסינג', icon: '🚗', active: false },
  { id: 'other',       label: 'אחר',    icon: '📁', active: false },
];

let ELEC_TEMPLATE_ID = '5594291d-2a5f-4b6c-846a-bed1290388b1';

function CelcomDashboard({ muni, view, setView }: { muni: any, view: string, setView: (v: 'home' | 'intake' | 'indexes') => void }) {
  const [previewResult, setPreviewResult] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(false);
  const [approving, setApproving] = React.useState(false);
  const [error, setError] = React.useState('');
  const [lastFile, setLastFile] = React.useState<File|null>(null);
  const [celcomPeriod, setCelcomPeriod] = React.useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [indexes, setIndexes] = React.useState<any[]>([]);
  const [indexSearch, setIndexSearch] = React.useState('');
  const [editingId, setEditingId] = React.useState<string|null>(null);
  const [editVals, setEditVals] = React.useState<{phone_number:string;budget_section:string}>({phone_number:'',budget_section:''});

  const loadIndexes = async () => {
    if (!muni) return;
    setLoading(true);
    try {
      const data = await apiFetch(`/celcom/index?municipality_id=${muni.id}`);
      setIndexes(Array.isArray(data) ? data : []);
    } catch { setError('שגיאה בטעינת אינדקס'); }
    finally { setLoading(false); }
  };

  React.useEffect(() => {
    if (view === 'indexes') loadIndexes();
  }, [view, muni?.id]);

  const filteredIndexes = indexes.filter(idx =>
    !indexSearch ||
    idx.phone_number?.includes(indexSearch) ||
    idx.budget_section?.includes(indexSearch)
  );

  const saveIndexEdit = async (id: string) => {
    try {
      const fd = new FormData();
      fd.append('municipality_id', muni.id);
      fd.append('phone_number', editVals.phone_number);
      fd.append('budget_section', editVals.budget_section);
      await fetch(`${API}/celcom/index`, { method: 'POST', body: fd });
      setEditingId(null);
      loadIndexes();
    } catch { setError('שגיאה בשמירה'); }
  };

  const deleteIndex = async (id: string, phone: string) => {
    if (!confirm(`מחק מנוי ${phone}?`)) return;
    try {
      await apiFetch(`/celcom/index/${id}`, { method: 'DELETE' });
      setIndexes(p => p.filter(r => r.id !== id));
    } catch { setError('שגיאה במחיקה'); }
  };

  const handleApprove = async () => {
    if (!previewResult || !muni || !lastFile) return;
    setApproving(true); setError('');
    try {
      const fd = new FormData();
      fd.append('file', lastFile);
      fd.append('municipality_id', muni.id);
      fd.append('period', celcomPeriod);
      const res = await fetch(`${API}/celcom/approve`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) { console.error('[CELCOM APPROVE 500]', data); throw new Error(data.detail || 'שגיאה ביצירת פקודה'); }
      alert(`✅ פקודה נוצרה!\n${data.reference_num}\nסה"כ: ₪${data.total?.toLocaleString()}\n${data.lines_count} שורות | ${data.budget_lines} סעיפים`);
      setPreviewResult(null); setLastFile(null); setView('home');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'שגיאה');
    } finally { setApproving(false); }
  };

  if (view === 'home') return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="text-base font-semibold">סלקום – דשבורד</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {indexes.length} מנויים באינדקס</p>
        </div>
        <button onClick={() => setView('intake')} className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700 font-medium">
          📱 + קליטת חשבון
        </button>
      </div>
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-400 mb-1">מנויים באינדקס</div>
          <div className="text-2xl font-bold text-gray-900">{indexes.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-400 mb-1">מצב מודול</div>
          <div className="text-sm font-medium text-purple-700">פעיל</div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs text-gray-400 mb-1">פקודות מרוכזות</div>
          <div className="text-sm font-medium text-green-700">זמין ✓</div>
        </div>
      </div>
    </div>
  );

  if (view === 'intake') return (
    <div>
      <div className="flex justify-between mb-4 items-center">
        <h1 className="text-base font-semibold">קליטת חשבון סלקום</h1>
        {!previewResult && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">תקופה:</label>
            <input value={celcomPeriod} onChange={e => setCelcomPeriod(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-32 font-mono" />
          </div>
        )}
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">{error}</div>}
      {!previewResult ? (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${loading ? 'border-gray-200' : 'border-gray-300 hover:border-purple-400 hover:bg-purple-50'}`}>
            <div className="text-4xl mb-3">📱</div>
            <div className="text-sm font-medium text-gray-700">{loading ? 'מעבד...' : 'לחץ לבחירת קובץ סלקום (XLS)'}</div>
            <div className="text-xs text-gray-400 mt-1">קובץ CCR מסלקום</div>
            <input type="file" accept=".xlsx,.xls" className="hidden" disabled={loading}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file || !muni) return;
                setLoading(true); setError('');
                try {
                  const fd = new FormData();
                  fd.append('file', file);
                  fd.append('municipality_id', muni.id);
                  const res = await fetch(`${API}/celcom/preview`, { method: 'POST', body: fd });
                  const data = await res.json();
                  if (!res.ok) { console.error('[CELCOM 500]', data); throw new Error(data.detail || 'שגיאה בעיבוד הקובץ'); }
                  setPreviewResult(data);
                  setLastFile(file);
                } catch (err: unknown) {
                  setError(err instanceof Error ? err.message : 'שגיאה');
                } finally { setLoading(false); }
              }} />
          </label>
        </div>
      ) : (
        <div>
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 mb-4 text-sm">
            <div className="font-medium text-purple-800 mb-1">
              חשבונית {previewResult.invoice?.number} · {previewResult.invoice?.date} · סוג {previewResult.file_type}
            </div>
            <div className="flex gap-4 text-xs text-purple-700">
              <span>סה"כ לתשלום: <strong>₪{previewResult.invoice?.total?.toLocaleString()}</strong></span>
              <span>מע"מ: ₪{previewResult.invoice?.vat?.toLocaleString()}</span>
              {previewResult.invoice?.exempt > 0 && <span>פטור: ₪{previewResult.invoice?.exempt?.toLocaleString()}</span>}
              {previewResult.invoice?.equip > 0 && <span>ציוד: ₪{previewResult.invoice?.equip?.toLocaleString()}</span>}
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              ['מנויים', previewResult.summary?.total_subscribers],
              ['ממופים', previewResult.summary?.mapped_count],
              ['לא ממופים', previewResult.summary?.unmapped_count],
              ['הפרש', `₪${Math.abs(previewResult.summary?.diff || 0).toFixed(2)}`],
            ].map(([l,v]) => (
              <div key={l as string} className="bg-white rounded-xl border border-gray-200 p-3">
                <div className="text-xs text-gray-400 mb-1">{l}</div>
                <div className={`text-lg font-bold ${l==='לא ממופים' && Number(v) > 0 ? 'text-amber-600' : 'text-gray-900'}`}>{v}</div>
              </div>
            ))}
          </div>
          {previewResult.unmapped?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-xs text-amber-700">
              <div className="font-medium mb-1">⚠ {previewResult.unmapped.length} מנויים לא ממופים → סעיף 9999</div>
              <div className="flex flex-wrap gap-1">
                {previewResult.unmapped.slice(0,10).map((s:any) => (
                  <span key={s.phone} className="bg-amber-100 rounded px-1.5 py-0.5 font-mono">{s.phone}</span>
                ))}
                {previewResult.unmapped.length > 10 && <span>+{previewResult.unmapped.length - 10} נוספים</span>}
              </div>
            </div>
          )}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
            <div className="p-3 border-b border-gray-100 flex justify-between items-center">
              <span className="text-xs font-medium text-gray-600">פירוט מנויים</span>
              <span className="text-xs text-gray-400">{previewResult.subscribers?.length} שורות</span>
            </div>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50"><tr className="border-b border-gray-100">
                  {['מספר סלקום','שם','סכום','סעיף תקציבי','סטטוס'].map(h =>
                    <th key={h} className="text-right p-2.5 text-xs text-gray-500 font-medium">{h}</th>)}
                </tr></thead>
                <tbody>
                  {previewResult.subscribers?.map((s: any, i: number) => (
                    <tr key={`${s.phone}-${i}`} className={`border-b border-gray-50 hover:bg-gray-50 ${!s.mapped ? 'bg-amber-50' : ''}`}>
                      <td className="p-2.5 font-mono text-xs">{s.phone}</td>
                      <td className="p-2.5 text-xs text-gray-600 max-w-xs truncate">{s.name || '—'}</td>
                      <td className="p-2.5 text-xs font-medium">₪{s.amount?.toLocaleString()}</td>
                      <td className="p-2.5 font-mono text-xs">{s.budget}</td>
                      <td className="p-2.5">
                        {s.mapped
                          ? <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">✓ ממופה</span>
                          : <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700">לא ממופה</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="flex gap-3 items-center">
            <button onClick={() => { setPreviewResult(null); setLastFile(null); setError(''); }}
              className="border border-gray-200 rounded-lg px-4 py-2 text-sm">קובץ חדש</button>
            <div className="flex items-center gap-2 mr-auto">
              <label className="text-xs text-gray-500">תקופה:</label>
              <input value={celcomPeriod} onChange={e => setCelcomPeriod(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-28 font-mono" />
            </div>
            <button onClick={handleApprove} disabled={approving || !celcomPeriod}
              className="bg-purple-600 text-white rounded-lg px-6 py-2 text-sm hover:bg-purple-700 disabled:opacity-40 font-medium">
              {approving ? 'שומר...' : '✓ צור פקודת יומן'}
            </button>
          </div>
        </div>
      )}
    </div>
  );

  if (view === 'indexes') return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-base font-semibold">אינדקס סלקום</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {filteredIndexes.length} רשומות</p>
        </div>
        <input value={indexSearch} onChange={e => setIndexSearch(e.target.value)}
          placeholder="חיפוש לפי מספר / סעיף..." className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64" />
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">{error}</div>}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead><tr className="bg-gray-50 border-b border-gray-100">
            {['מספר סלקום','סעיף תקציבי','עדכון אחרון','פעולות'].map(h =>
              <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
          </tr></thead>
          <tbody>
            {loading && <tr><td colSpan={4} className="p-6 text-center text-sm text-gray-400">טוען...</td></tr>}
            {filteredIndexes.map(idx => (
              <tr key={idx.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs">
                  {editingId === idx.id
                    ? <input value={editVals.phone_number} onChange={e => setEditVals(v => ({...v, phone_number: e.target.value}))}
                        className="border border-blue-300 rounded px-2 py-1 text-xs w-28 font-mono" />
                    : idx.phone_number}
                </td>
                <td className="p-3 font-mono text-xs">
                  {editingId === idx.id
                    ? <input value={editVals.budget_section} onChange={e => setEditVals(v => ({...v, budget_section: e.target.value}))}
                        className="border border-blue-300 rounded px-2 py-1 text-xs w-28 font-mono" />
                    : idx.budget_section}
                </td>
                <td className="p-3 text-xs text-gray-400">{new Date(idx.updated_at).toLocaleDateString('he-IL')}</td>
                <td className="p-3">
                  {editingId === idx.id
                    ? <div className="flex gap-2">
                        <button onClick={() => saveIndexEdit(idx.id)} className="text-xs text-green-600 font-medium hover:underline">שמור</button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-gray-400 hover:underline">ביטול</button>
                      </div>
                    : <div className="flex gap-3">
                        <button onClick={() => { setEditingId(idx.id); setEditVals({phone_number: idx.phone_number, budget_section: idx.budget_section}); }}
                          className="text-xs text-blue-600 hover:underline">עריכה</button>
                        <button onClick={() => deleteIndex(idx.id, idx.phone_number)} className="text-xs text-red-500 hover:underline">מחק</button>
                      </div>}
                </td>
              </tr>
            ))}
            {!loading && filteredIndexes.length === 0 && (
              <tr><td colSpan={4} className="p-8 text-center text-sm text-gray-400">אין רשומות</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  return null;
}

function ElectricityDashboard({ muni, onNewIntake }: { muni: any, onNewIntake: () => void }) {
  const [entries, setEntries] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [vendorAccount, setVendorAccount] = React.useState('7000000000');
  const [editVendor, setEditVendor] = React.useState(false);
  const ELEC_TEMPLATE = '5594291d-2a5f-4b6c-846a-bed1290388b1';

  const loadData = () => {
    if (!muni) return;
    setLoading(true);
    Promise.all([
      apiFetch(`/journal-entries?municipality_id=${muni.id}&limit=50`),
      apiFetch(`/municipalities/${muni.id}/settings`).catch(() => null),
    ]).then(([entriesData, settings]) => {
      setEntries(Array.isArray(entriesData) ? entriesData : []);
      if (settings?.vendor_account) setVendorAccount(settings.vendor_account);
    }).catch(() => {}).finally(() => setLoading(false));
  };

  React.useEffect(() => { loadData(); }, [muni?.id]);

  const elecEntries = entries
    .filter((e: any) => e.template_key === 'electricity' || e.template_id === ELEC_TEMPLATE)
    .sort((a: any, b: any) => b.period.localeCompare(a.period));

  const deleteEntry = async (id: string, ref: string) => {
    if (!confirm(`מחק פקודה ${ref}?`)) return;
    await apiFetch(`/journal-entries/${id}`, { method: 'DELETE' });
    loadData();
  };

  const saveVendor = async () => {
    if (!muni) return;
    await apiFetch(`/municipalities/${muni.id}/settings`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_name: 'electricity', key: 'vendor_account', value: vendorAccount }),
    });
    setEditVendor(false);
  };

  const totalAll = elecEntries.reduce((s: number, e: any) => s + (e.total_amount || 0), 0);
  const lastEntry = elecEntries[0];
  const prevEntry = elecEntries[1];
  const lastTotal = lastEntry?.total_amount || 0;
  const prevTotal = prevEntry?.total_amount || 0;
  const monthDiff = prevTotal > 0 ? ((lastTotal - prevTotal) / prevTotal * 100) : null;
  const last12 = elecEntries.slice(0, 12);
  const avg12 = last12.length > 0 ? last12.reduce((s: number, e: any) => s + (e.total_amount || 0), 0) / last12.length : 0;

  return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="text-base font-semibold">חשמל – דשבורד</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {elecEntries.length} תקופות</p>
        </div>
        <button onClick={onNewIntake} className="bg-yellow-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-yellow-600 font-medium">⚡ + קליטת חשבון</button>
      </div>
      {loading ? <div className="p-12 text-center text-sm text-gray-400">טוען...</div> : (<>
      {elecEntries.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">חודש אחרון</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(lastTotal).toLocaleString()}</div>
            <div className="text-xs text-gray-500 mt-0.5">{lastEntry?.period}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">שינוי מהחודש הקודם</div>
            <div className={`text-lg font-bold ${monthDiff === null ? 'text-gray-400' : monthDiff > 0 ? 'text-red-600' : 'text-green-600'}`}>
              {monthDiff === null ? '—' : `${monthDiff > 0 ? '+' : ''}${monthDiff.toFixed(1)}%`}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">ממוצע 12 חודשים</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(avg12).toLocaleString()}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">סה"כ מצטבר</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(totalAll).toLocaleString()}</div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 bg-white rounded-xl border border-gray-200">
          <div className="p-3 border-b border-gray-100 flex justify-between items-center">
            <span className="text-xs font-medium text-gray-600">פקודות יומן</span>
            <span className="text-xs text-gray-400">{elecEntries.length} פקודות</span>
          </div>
          {elecEntries.length === 0
            ? <div className="p-8 text-center text-sm text-gray-400">אין פקודות עדיין</div>
            : <table className="w-full text-sm">
                <thead><tr className="border-b border-gray-100">
                  {['מספר','תקופה','סכום','סטטוס',''].map(h =>
                    <th key={h} className="text-right p-2.5 text-xs text-gray-400 font-medium">{h}</th>)}
                </tr></thead>
                <tbody>
                  {elecEntries.map((e: any) => (
                    <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="p-2.5 font-mono text-xs">{e.reference_num}</td>
                      <td className="p-2.5 text-xs">{e.period}</td>
                      <td className="p-2.5 text-xs font-medium">₪{Math.round(e.total_amount||0).toLocaleString()}</td>
                      <td className="p-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${e.status==='draft' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                          {e.status==='draft'?'טיוטה':'יוצא'}
                        </span>
                      </td>
                      <td className="p-2.5 flex gap-2">
                        <button onClick={() => window.open(`${API}/journal-entries/${e.id}/export`, '_blank')} className="text-xs text-blue-600 hover:underline">Excel</button>
                        {e.status === 'draft' && <button onClick={() => deleteEntry(e.id, e.reference_num)} className="text-xs text-red-400 hover:underline">מחק</button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="text-xs font-medium text-gray-600 mb-2">חשבון ספק חשמל</div>
          {editVendor ? (
            <div className="flex flex-col gap-2">
              <input value={vendorAccount} onChange={e => setVendorAccount(e.target.value)} className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono w-full" />
              <div className="flex gap-2">
                <button onClick={saveVendor} className="flex-1 text-xs bg-green-600 text-white px-2 py-1.5 rounded-lg">שמור</button>
                <button onClick={() => setEditVendor(false)} className="text-xs text-gray-400 px-2">ביטול</button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <code className="text-xs font-mono bg-gray-50 px-2 py-1 rounded">{vendorAccount}</code>
              <button onClick={() => setEditVendor(true)} className="text-xs text-blue-600 hover:underline">עדכן</button>
            </div>
          )}
        </div>
      </div>
      </>)}
    </div>
  );
}

function WelfareDashboard({ muni, onNewIntake, refreshKey }: { muni: any, onNewIntake: () => void, refreshKey?: number }) {
  const [entries, setEntries] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [templateId, setTemplateId] = React.useState<string|null>(null);

  const loadData = async () => {
    if (!muni) return;
    setLoading(true);
    try {
      // welfare template_id נשמר כ-constant — אין endpoint /templates
      const WELFARE_TEMPLATE_ID = '95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7';
      const url = `/journal-entries?municipality_id=${muni.id}&template_id=${WELFARE_TEMPLATE_ID}&limit=50`;
      const data = await apiFetch(url);
      const all = Array.isArray(data) ? data : [];
      const filtered = all.filter((e:any) =>
        String(e.template_id) === WELFARE_TEMPLATE_ID ||
        e.source_type === 'welfare' ||
        e.template_key === 'welfare' ||
        (e.reference_num && e.reference_num.startsWith('WLF'))
      );
      setEntries(filtered);
    } catch { setEntries([]); } finally { setLoading(false); }
  };

  React.useEffect(() => { loadData(); }, [muni?.id, refreshKey]);

  const welfareEntries = entries.sort((a: any, b: any) => b.period.localeCompare(a.period));
  const totalAll = welfareEntries.reduce((s: number, e: any) => s + (e.total_amount || 0), 0);
  const lastEntry = welfareEntries[0];

  const deleteEntry = async (id: string, ref: string) => {
    if (!confirm(`מחק פקודת רווחה ${ref}?`)) return;
    try { await apiFetch(`/journal-entries/${id}`, { method: 'DELETE' }); loadData(); }
    catch (err: unknown) { alert(err instanceof Error ? err.message : 'שגיאה'); }
  };

  const treasurerFileRef = React.useRef<HTMLInputElement>(null);

  const handleTreasurerReport = async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch(`${API}/upload/welfare/treasurer-report`, { method: 'POST', body: form });
      if (!res.ok) { const t = await res.text(); alert(t); return; }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      let filename = 'treasurer_report.pdf';
      const m = cd.match(/filename\*=UTF-8''(.+)/);
      if (m) filename = decodeURIComponent(m[1]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) { alert(err instanceof Error ? err.message : 'שגיאה בהפקת דוח'); }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="text-base font-semibold">רווחה – דשבורד</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {welfareEntries.length} תקופות</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => treasurerFileRef.current?.click()} className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700 font-medium">דוח לגזבר</button>
          <input ref={treasurerFileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) handleTreasurerReport(f); e.target.value = ''; }} />
          <button onClick={onNewIntake} className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 font-medium">+ קליטת דוח</button>
        </div>
      </div>
      {loading ? <div className="p-12 text-center text-sm text-gray-400">טוען...</div> : (<>
      {welfareEntries.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">תקופה אחרונה</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(lastEntry?.total_amount || 0).toLocaleString()}</div>
            <div className="text-xs text-gray-500 mt-0.5">{lastEntry?.period}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">סה"כ מצטבר</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(totalAll).toLocaleString()}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">מספר פקודות</div>
            <div className="text-lg font-bold text-gray-900">{welfareEntries.length}</div>
          </div>
        </div>
      )}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-3 border-b border-gray-100 flex justify-between items-center">
          <span className="text-xs font-medium text-gray-600">פקודות יומן</span>
          <span className="text-xs text-gray-400">{welfareEntries.length} פקודות</span>
        </div>
        {welfareEntries.length === 0
          ? <div className="p-8 text-center text-sm text-gray-400">אין פקודות עדיין</div>
          : <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100">
                {['מספר','תקופה','סכום','סטטוס',''].map(h =>
                  <th key={h} className="text-right p-2.5 text-xs text-gray-400 font-medium">{h}</th>)}
              </tr></thead>
              <tbody>
                {welfareEntries.map((e: any) => (
                  <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="p-2.5 font-mono text-xs">{e.reference_num}</td>
                    <td className="p-2.5 text-xs">{e.period}</td>
                    <td className="p-2.5 text-xs font-medium">₪{Math.round(e.total_amount||0).toLocaleString()}</td>
                    <td className="p-2.5">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${e.status==='draft' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                        {e.status==='draft' ? 'טיוטה' : 'יוצא'}
                      </span>
                    </td>
                    <td className="p-2.5 flex gap-2">
                      <button onClick={() => window.open(`${API}/journal-entries/${e.id}/export`, '_blank')} className="text-xs text-blue-600 hover:underline">Excel</button>
                      {e.status !== 'locked' && <button onClick={() => deleteEntry(e.id, e.reference_num)} className="text-xs text-red-400 hover:underline">מחק</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>}
      </div>
      </>)}
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState<'login'|'muni'|'module'|'main'|'settings'>('login');
  const [muni, setMuni] = useState<Municipality | null>(null);
  const [munis, setMunis] = useState<Municipality[]>([]);
  const [activeTab, setActiveTab] = useState('bezeq');
  const [bezeqView, setBezeqView] = useState<'home'|'intake'|'indexes'|'settings'>('home');
  const [elecView, setElecView] = useState<'home'|'intake'|'indexes'>('home');
  const [celcomView, setCelcomView] = useState<'home'|'intake'|'indexes'>('home');
  const [elecIndexSearch, setElecIndexSearch] = useState('');
  const [elecIndexes, setElecIndexes] = useState<any[]>([]);
  const [splitModal, setSplitModal] = useState<null|{open:boolean,contract:string,connectionName:string,splits:any[],saving:boolean,error:string}>(null);
  const [elecResult, setElecResult] = useState<any>(null);
  const [elecVendorAccount, setElecVendorAccount] = useState('7000000000');
  const [elecLoading, setElecLoading] = useState(false);
  const [welfareView, setWelfareView] = useState<'home'|'intake'|'indexes'>('home');
  const WELFARE_TEMPLATE_ID_IDX = '95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7';
  const [welfareIndexes, setWelfareIndexes] = useState<any[]>([]);
  const [welfareIndexSearch, setWelfareIndexSearch] = useState('');
  const [welfareIndexLoading, setWelfareIndexLoading] = useState(false);
  const [welfareNewRow, setWelfareNewRow] = useState({ key_value: '', debit: '', credit: '', name: '' });
  const [welfareAddError, setWelfareAddError] = useState('');
  const [welfareEditId, setWelfareEditId] = useState<string|null>(null);
  const [welfareEditVals, setWelfareEditVals] = useState({ debit: '', credit: '', name: '' });
  const [welfareResult, setWelfareResult] = useState<any>(null);
  const [welfareFileB64, setWelfareFileB64] = useState<string>('');
  const [welfareLoading, setWelfareLoading] = useState(false);
  const [welfareRefreshKey, setWelfareRefreshKey] = useState(0);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [indexMap, setIndexMap] = useState<Record<number, string>>({});
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [period, setPeriod] = useState('2026-02');
  const [indexes, setIndexes] = useState<IndexRow[]>([]);
  const [settings, setSettings] = useState<{vendor_account:string}>({vendor_account:'6000203000'});
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [treasurerEmail, setTreasurerEmail] = useState('');
  const [ministryAccount, setMinistryAccount] = useState('');
  const [treasurerSaved, setTreasurerSaved] = useState(false);
  const [indexSearch, setIndexSearch] = useState('');
  const [editingIndex, setEditingIndex] = useState<string|null>(null);
  const [editVals, setEditVals] = useState<{account_code:string;connection_name:string}>({account_code:'',connection_name:''});

  useEffect(() => {
    if (activeTab === 'electricity' && muni) {
      apiFetch(`/municipalities/${muni.id}/settings`)
        .then((s:any) => { if (s?.vendor_account) setElecVendorAccount(s.vendor_account); })
        .catch(() => {});
    }
  }, [activeTab, muni?.id]);

  useEffect(() => {
    if (screen === 'muni') {
      setLoading(true);
      Promise.all([
        apiFetch('/municipalities').then(setMunis),
        apiFetch('/templates').then((tmpls: any[]) => {
          const elec = tmpls.find((t: any) => t.name === 'electricity');
          const bezeq = tmpls.find((t: any) => t.name === 'bezeq');
          if (elec) ELEC_TEMPLATE_ID = elec.id;
          if (bezeq) BEZEQ_TEMPLATE_ID = bezeq.id;
        }).catch(() => {}),
      ]).catch(() => setError('שגיאה')).finally(() => setLoading(false));
    }
  }, [screen]);

  useEffect(() => {
    if (screen === 'main' && muni && activeTab === 'bezeq' && bezeqView === 'home') {
      apiFetch(`/journal-entries?municipality_id=${muni.id}`).then(setEntries).catch(() => {});
    }
  }, [screen, muni, activeTab, bezeqView]);

  async function createElectricityJournal() {
    if (!muni || !elecResult) return;
    setElecLoading(true); setError('');
    try {
      const heMonths: Record<string, string> = {'ינואר':'01','פברואר':'02','מרץ':'03','אפריל':'04','מאי':'05','יוני':'06','יולי':'07','אוגוסט':'08','ספטמבר':'09','אוקטובר':'10','נובמבר':'11','דצמבר':'12'};
      const rawPeriod = elecResult.period || '';
      const pparts = rawPeriod.trim().split(' ');
      const periodStr = pparts.length === 2 && heMonths[pparts[0]] ? `${pparts[1]}-${heMonths[pparts[0]]}` : rawPeriod.slice(0, 7) || '2025-09';
      const lines = elecResult.rows.filter((r: any) => r.status === 'ok').map((r: any) => ({ account: r.account, amount: r.amount, description: r.description, key_value: r.contract }));
      const res = await apiFetch('/upload/electricity/approve', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ municipality_id: muni.id, template_id: elecResult.template_id || ELEC_TEMPLATE_ID, period: periodStr, source_file: elecResult.filename || 'buller.csv', date_from: elecResult.date_from, date_to: elecResult.date_to, invoice_total: elecResult.sum_details, lines }),
      });
      alert(`פקודה נוצרה! ${res.reference_num}`);
      setElecResult(null); setElecView('home');
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setElecLoading(false); }
  }

  async function loadSettings() {
    if (!muni) return;
    try { const data = await apiFetch(`/municipalities/${muni.id}/settings`); if (data?.vendor_account) setSettings({vendor_account: data.vendor_account}); } catch { }
  }

  async function loadMuniSettings() {
    if (!muni) return;
    try {
      const data = await apiFetch(`/municipalities/${muni.id}/settings`);
      setTreasurerEmail(data?.treasurer_email || '');
      setMinistryAccount(data?.ministry_account || '');
    } catch { }
  }

  async function saveMuniSettings() {
    if (!muni) return;
    setLoading(true);
    try {
      await apiFetch(`/municipalities/${muni.id}/settings`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({template_name: 'general', key: 'treasurer_email', value: treasurerEmail}) });
      if (ministryAccount) {
        await apiFetch(`/municipalities/${muni.id}/settings`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({template_name: 'welfare', key: 'ministry_account', value: ministryAccount}) });
      }
      setTreasurerSaved(true); setTimeout(() => setTreasurerSaved(false), 3000);
    } catch { setError('שגיאה בשמירה'); } finally { setLoading(false); }
  }

  async function saveSettings() {
    if (!muni) return;
    setLoading(true);
    try {
      await apiFetch(`/municipalities/${muni.id}/settings`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({template_name: 'bezeq', key: 'vendor_account', value: settings.vendor_account}) });
      setSettingsSaved(true); setTimeout(() => setSettingsSaved(false), 3000);
    } catch { setError('שגיאה בשמירה'); } finally { setLoading(false); }
  }

  async function loadIndexes() {
    if (!muni) return;
    setLoading(true);
    try {
      const data = await apiFetch(`/indexes?municipality_id=${muni.id}&limit=300${indexSearch ? '&search='+encodeURIComponent(indexSearch) : ''}`);
      setIndexes(data);
    } catch { setError('שגיאה'); } finally { setLoading(false); }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !muni) return;
    setLoading(true); setError('');
    try {
      const check = await apiFetch(`/journal-entries/check-period?municipality_id=${muni.id}&template_id=${BEZEQ_TEMPLATE_ID}&period=${period}`);
      if (check.exists) { setLoading(false); setError(`קיימת פקודה לתקופה ${period} (${check.reference_num}). יש למחוק אותה קודם.`); return; }
      const fd = new FormData();
      fd.append('file', file); fd.append('municipality_id', muni.id); fd.append('template', 'bezeq');
      const res = await fetch(`${API}/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'שגיאה');
      setUploadResult(data); setStep(2);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function handleSaveIndexesAndContinue() {
    if (!muni || !uploadResult) return;
    setLoading(true); setError('');
    try {
      const missing = uploadResult.rows.filter(r => !r.has_index);
      for (const row of missing) {
        const acct = indexMap[row.row_num] || '';
        await apiFetch('/indexes', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ municipality_id: muni.id, template_id: BEZEQ_TEMPLATE_ID, key_value: row.phone, account_code: acct || 'PENDING', description: row.name !== 'nan' ? row.name : row.phone }) });
      }
      setStep(3);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function handleCreateJournal() {
    if (!muni || !uploadResult || loading) return;
    setLoading(true); setError('');
    try {
      const lines = uploadResult.rows.map(r => ({ account: r.account || indexMap[r.row_num] || '9999', description: r.description || r.name, debit: r.amount, credit: 0, reference: r.invoice, key_value: r.phone }));
      const extraLines = (uploadResult as any).extra_lines || [];
      for (const el of extraLines) {
        const keyVal = (el.phone && el.phone.trim()) ? el.phone.trim() : '00000000000';
        if (!el.amount) continue;
        lines.push({ account: el.account || '9999', description: el.description, debit: el.amount, credit: 0, reference: '', key_value: keyVal });
      }
      const total = lines.reduce((s, l) => s + l.debit, 0);
      lines.push({ account: '6000203000', description: 'ספק בזק', debit: 0, credit: total, reference: '', key_value: '' });
      const res = await apiFetch('/journal-entries', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ municipality_id: muni.id, template_id: BEZEQ_TEMPLATE_ID, period, source_file: uploadResult.filename, notes: JSON.stringify({ invoice_num: uploadResult.invoice_num||'', date_from: uploadResult.date_from||'', date_to: uploadResult.date_to||'' }), lines }) });
      alert('פקודה נוצרה! ' + res.reference_num);
      setUploadResult(null); setStep(1); setBezeqView('home');
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function saveIndexEdit(id: string) {
    try { await apiFetch(`/indexes/${id}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify(editVals) }); setEditingIndex(null); loadIndexes(); }
    catch { setError('שגיאה'); }
  }

  async function deleteJournalEntry(id: string, refNum: string) {
    if (!confirm(`מחק פקודה ${refNum}?`)) return;
    try { await apiFetch(`/journal-entries/${id}`, { method: 'DELETE' }); setEntries(prev => prev.filter(e => e.id !== id)); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
  }

  async function deleteIndex(id: string, phone: string) {
    if (!confirm(`מחק ${phone}?`)) return;
    try { await apiFetch(`/indexes/${id}`, { method: 'DELETE' }); loadIndexes(); }
    catch { setError('שגיאה'); }
  }

  const sidebarItems: Record<string, {label:string; view:string; icon:string}[]> = {
    bezeq: [
      { label: 'דשבורד', view: 'home', icon: '📊' },
      { label: 'קליטת חשבון', view: 'intake', icon: '📂' },
      { label: 'אינדקסים', view: 'indexes', icon: '📋' },
      { label: 'הגדרות', view: 'settings', icon: '⚙️' },
    ],
    electricity: [
      { label: 'דשבורד', view: 'home', icon: '📊' },
      { label: 'קליטת חשבון', view: 'intake', icon: '📂' },
      { label: 'אינדקסים', view: 'indexes', icon: '📋' },
    ],
    welfare: [
      { label: 'דשבורד', view: 'home', icon: '📊' },
      { label: 'קליטת דוח', view: 'intake', icon: '📂' },
      { label: 'עדכון אינדקס', view: 'indexes', icon: '📋' }, // welfare-index
    ],
    celcom: [
      { label: 'דשבורד', view: 'home', icon: '📊' },
      { label: 'קליטת חשבון', view: 'intake', icon: '📂' },
      { label: 'אינדקס', view: 'indexes', icon: '📋' },
    ],
    leasing: [{ label: 'בקרוב', view: 'home', icon: '🚗' }],
    other:   [{ label: 'בקרוב', view: 'home', icon: '📁' }],
  };

  function switchTab(tabId: string) {
    setActiveTab(tabId); setBezeqView('home'); setError('');
    if (tabId === 'celcom') setCelcomView('home');
  }

  if (screen === 'login') return (
    <div dir="rtl" className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-xl border border-gray-200 p-8 w-full max-w-sm shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">י</div>
          <div><div className="font-semibold text-gray-900">יומנית</div><div className="text-xs text-gray-500">מערכת ניהול פקודות יומן</div></div>
        </div>
        <div className="space-y-3">
          <input type="email" defaultValue="admin@muni.gov.il" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"/>
          <input type="password" defaultValue="••••••••" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"/>
          <button onClick={() => setScreen('muni')} className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700">כניסה</button>
        </div>
      </div>
    </div>
  );

  if (screen === 'muni') return (
    <div dir="rtl" className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-lg font-semibold mb-1">בחירת רשות</h1>
      <p className="text-sm text-gray-500 mb-6">בחר את הרשות לעבודה</p>
      {loading && <p className="text-sm text-gray-400 mb-4">טוען...</p>}
      <div className="grid grid-cols-3 gap-3 max-w-2xl">
        {munis.map(m => (
          <button key={m.id} onClick={() => { setMuni(m); setScreen('module'); }}
            className="bg-white border border-gray-200 rounded-xl p-4 text-right hover:border-blue-400 transition-colors">
            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-600 font-semibold text-sm mb-2">{m.code.slice(0,2)}</div>
            <div className="font-medium text-sm text-gray-900">{m.name}</div>
            <div className="text-xs text-green-600">פעיל</div>
          </button>
        ))}
      </div>
    </div>
  );

  if (screen === 'module') return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6" dir="rtl">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">י</span>
          </div>
          <div>
            <div className="font-semibold text-gray-900">יומנית</div>
            <div className="text-xs text-gray-500">{muni?.name}</div>
          </div>
        </div>
        <h1 className="text-lg font-semibold mb-1 text-gray-900">בחירת מודול</h1>
        <p className="text-sm text-gray-500 mb-6">איזה מודול תרצה לפתוח?</p>
        <div className="grid grid-cols-2 gap-4">
          {[
            { id: 'electricity', label: 'חשמל',  icon: '⚡', desc: 'קליטת חשבונות חשמל',  color: 'bg-yellow-50 border-yellow-200 hover:border-yellow-400' },
            { id: 'bezeq',      label: 'בזק',    icon: '📞', desc: 'קליטת חשבונות בזק',   color: 'bg-blue-50 border-blue-200 hover:border-blue-400' },
            { id: 'welfare',    label: 'רווחה',  icon: '🤝', desc: 'קליטת דוח תמר',       color: 'bg-green-50 border-green-200 hover:border-green-400' },
            { id: 'celcom',     label: 'סלקום',  icon: '📱', desc: 'קליטת חשבונות סלקום', color: 'bg-purple-50 border-purple-200 hover:border-purple-400' },
          ].map(mod => (
            <button key={mod.id} onClick={() => { setActiveTab(mod.id); setScreen('main'); }}
              className={`border-2 rounded-xl p-5 text-right transition-colors ${mod.color} cursor-pointer`}>
              <div className="text-3xl mb-2">{mod.icon}</div>
              <div className="font-semibold text-gray-900 mb-0.5">{mod.label}</div>
              <div className="text-xs text-gray-500">{mod.desc}</div>
            </button>
          ))}
        </div>
        <div className="mt-6 flex items-center justify-between">
          <button onClick={() => setScreen('muni')} className="text-xs text-gray-400 hover:text-gray-600">← החלפת רשות</button>
          <button onClick={() => { setScreen('settings'); loadMuniSettings(); }} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">⚙️ הגדרות</button>
        </div>
      </div>
    </div>
  );

  if (screen === 'settings') return (
    <div dir="rtl" className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-xl border border-gray-200 p-8 w-full max-w-md shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-9 h-9 bg-gray-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-lg">⚙️</span>
          </div>
          <div>
            <div className="font-semibold text-gray-900">הגדרות רשות</div>
            <div className="text-xs text-gray-500">{muni?.name}</div>
          </div>
        </div>
        {treasurerSaved && <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg p-3 mb-4">נשמר בהצלחה</div>}
        {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">{error}</div>}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">מייל גזבר</label>
            <input type="email" value={treasurerEmail} onChange={e => setTreasurerEmail(e.target.value)} placeholder="treasurer@example.com" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            <p className="text-xs text-gray-400 mt-1">כתובת לשליחת דוחות גזבר אוטומטיים</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">חו"ז משרד הרווחה</label>
            <input value={ministryAccount} onChange={e => setMinistryAccount(e.target.value)} placeholder="7000034000" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono" />
            <p className="text-xs text-gray-400 mt-1">חשבון חו"ז לשורת איזון בפקודת רווחה</p>
          </div>
          <button onClick={saveMuniSettings} disabled={loading} className="bg-blue-600 text-white rounded-lg px-6 py-2 text-sm font-medium disabled:opacity-50 hover:bg-blue-700">{loading ? 'שומר...' : 'שמור'}</button>
        </div>
        <button onClick={() => { setScreen('module'); setError(''); }} className="mt-6 text-xs text-gray-400 hover:text-gray-600">← חזרה</button>
      </div>
    </div>
  );

  if (screen === 'main') return (
    <div dir="rtl" className="min-h-screen bg-gray-50 flex flex-col">
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-xs">י</div>
          <span className="font-semibold text-sm text-gray-900">יומנית</span>
          <span className="text-gray-300">|</span>
          <span className="text-sm text-gray-600">{muni?.name}</span>
        </div>
        <button onClick={() => setScreen('module')} className="text-xs text-gray-400 hover:text-gray-600">החלפת מודול</button>
      </div>

      <div className="bg-white border-b border-gray-200 px-4 flex gap-1">
        {CATEGORIES.map(cat => (
          <button key={cat.id} onClick={() => switchTab(cat.id)}
            className={`flex items-center gap-1.5 px-4 py-3 text-sm border-b-2 transition-colors ${activeTab === cat.id ? 'border-blue-600 text-blue-700 font-medium' : 'border-transparent text-gray-500 hover:text-gray-700'} ${!cat.active && activeTab !== cat.id ? 'opacity-50' : ''}`}>
            <span>{cat.icon}</span><span>{cat.label}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-44 bg-white border-l border-gray-200 flex flex-col py-2">
          {(sidebarItems[activeTab] || []).map(item => (
            <button key={item.view}
              onClick={() => {
                if (activeTab === 'celcom') { setCelcomView(item.view as any); setError(''); }
                if (activeTab === 'electricity') {
                  setElecView(item.view as any); setError('');
                  if (item.view === 'intake') setElecResult(null);
                  if (item.view === 'indexes' && muni) {
                    setElecIndexes([]);
                    apiFetch(`/indexes?municipality_id=${muni.id}&template_id=${ELEC_TEMPLATE_ID}&limit=500`)
                      .then((d:any) => setElecIndexes(Array.isArray(d) ? d : [])).catch(() => {});
                  }
                }
                if (activeTab === 'welfare') { setWelfareView(item.view as any); if (item.view === 'intake') { setWelfareResult(null); setError(''); } if (item.view === 'indexes' && muni) { setWelfareIndexSearch(''); apiFetch(`/indexes?municipality_id=${muni.id}&template_id=95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7&limit=500`).then(d => setWelfareIndexes(Array.isArray(d)?d:[])); } }
                if (activeTab === 'bezeq') {
                  setBezeqView(item.view as any);
                  if (item.view === 'indexes') { setIndexSearch(''); loadIndexes(); }
                  if (item.view === 'intake') { setStep(1); setUploadResult(null); }
                  if (item.view === 'settings') loadSettings();
                  setError('');
                }
              }}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm text-right transition-colors border-r-2 ${
                ((activeTab === 'bezeq' && bezeqView === item.view) || (activeTab === 'electricity' && elecView === item.view) || (activeTab === 'welfare' && welfareView === item.view) || (activeTab === 'celcom' && celcomView === item.view))
                  ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium' : 'border-transparent text-gray-600 hover:bg-gray-50'}`}>
              <span className="text-base">{item.icon}</span><span>{item.label}</span>
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-auto p-6">
          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">{error}</div>}

          {activeTab === 'celcom' && <CelcomDashboard muni={muni} view={celcomView} setView={setCelcomView} />}

          {activeTab === 'electricity' && elecView === 'home' && (
            <ElectricityDashboard muni={muni} onNewIntake={() => { setElecView('intake'); setElecResult(null); setError(''); }} />
          )}

          {activeTab === 'electricity' && elecView === 'intake' && (
            <div>
              <h1 className="text-base font-semibold mb-4">קליטת חשבון חשמל</h1>
              {!elecResult ? (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${elecLoading ? 'border-gray-200' : 'border-gray-300 hover:border-yellow-400 hover:bg-yellow-50'}`}>
                    <div className="text-4xl mb-3">⚡</div>
                    <div className="text-sm font-medium text-gray-700">{elecLoading ? 'מעלה...' : 'לחץ לבחירת קובץ BULLER (CSV)'}</div>
                    <input type="file" accept=".csv" className="hidden" disabled={elecLoading}
                      onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file || !muni) return;
                        setElecLoading(true); setError('');
                        try {
                          const fd = new FormData(); fd.append('file', file); fd.append('municipality_id', muni.id);
                          const res = await fetch(`${API}/upload/electricity`, { method: 'POST', body: fd });
                          const data = await res.json();
                          if (!res.ok) throw new Error(data.detail || 'שגיאה');
                          setElecResult(data);
                        } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
                        finally { setElecLoading(false); }
                      }} />
                  </label>
                </div>
              ) : (
                <div>
                  <div className={`rounded-lg p-3 mb-4 text-sm ${elecResult.balance_ok && elecResult.missing === 0 ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-amber-50 border border-amber-200 text-amber-700'}`}>
                    <div className="font-medium mb-1">{elecResult.customer_name} · {elecResult.period}</div>
                    <div className="flex gap-4 text-xs">
                      <span>שורות: {elecResult.total_rows}</span>
                      <span>תואמות: {elecResult.matched}</span>
                      {elecResult.missing > 0 && <span className="text-red-600 font-medium">חסרות: {elecResult.missing}</span>}
                      <span>סה"כ: ₪{elecResult.sum_details?.toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50 border-b border-gray-100">
                        {['מספר חוזה','תיאור','קוד חשבון','סכום','סטטוס'].map(h => <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>
                        {elecResult.rows.map((row: any) => (
                          <tr key={`${row.row_num}-${row.contract}`} className={`border-b border-gray-50 ${row.status === 'missing_index' ? 'bg-red-50' : 'hover:bg-gray-50'}`}>
                            <td className="p-3 font-mono text-xs">{row.contract}</td>
                            <td className="p-3 text-xs text-gray-600 max-w-xs truncate">{row.description}</td>
                            <td className="p-3"><code className="text-xs">{row.account || '—'}</code></td>
                            <td className="p-3 text-xs font-medium">₪{row.amount?.toLocaleString()}</td>
                            <td className="p-3">
                              {row.status === 'ok'
                                ? <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">✓ תקין</span>
                                : <span className="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700">חסר אינדקס</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={() => { setElecResult(null); setError(''); }} className="border border-gray-200 rounded-lg px-4 py-2 text-sm">קובץ חדש</button>
                    <button disabled={!elecResult.can_approve || elecLoading} onClick={createElectricityJournal} className="bg-green-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-40">
                      {elecLoading ? 'שומר...' : elecResult.can_approve ? 'צור פקודת יומן ✓' : `לא ניתן לאשר (${elecResult.missing} חסרים)`}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'electricity' && elecView === 'indexes' && (() => {
            const grouped: Record<string, any[]> = {};
            elecIndexes.filter((idx: any) => !elecIndexSearch || idx.key_value?.includes(elecIndexSearch) || idx.account_code?.includes(elecIndexSearch) || (idx.connection_name||'').includes(elecIndexSearch))
              .forEach((idx: any) => { if (!grouped[idx.key_value]) grouped[idx.key_value] = []; grouped[idx.key_value].push(idx); });
            const contracts = Object.keys(grouped).sort();

            const openSplitModal = (contract: string) => {
              const rows = grouped[contract];
              setSplitModal({ open: true, contract, connectionName: rows[0]?.connection_name || '', splits: rows.map((r:any) => ({ account_code: r.account_code, percent: parseFloat(r.description||'100') })), saving: false, error: '' });
            };

            const saveSplit = async () => {
              if (!splitModal || !muni) return;
              const total = splitModal.splits.reduce((s:number, r:any) => s + (parseFloat(r.percent)||0), 0);
              if (Math.abs(total - 100) > 0.01) { setSplitModal(p => p ? {...p, error: `סכום האחוזים = ${total.toFixed(2)}%, חייב להיות 100%`} : p); return; }
              setSplitModal(p => p ? {...p, saving: true, error: ''} : p);
              try {
                await apiFetch('/indexes/split', { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ municipality_id: muni.id, template_id: ELEC_TEMPLATE_ID, key_value: splitModal.contract, connection_name: splitModal.connectionName, splits: splitModal.splits.map((s:any) => ({ account_code: s.account_code.trim(), percent: parseFloat(s.percent) })) }) });
                const fresh = await apiFetch(`/indexes?municipality_id=${muni.id}&template_id=${ELEC_TEMPLATE_ID}&limit=500`);
                setElecIndexes(Array.isArray(fresh) ? fresh : []);
                setSplitModal(null);
              } catch(e:any) { setSplitModal(p => p ? {...p, saving: false, error: e.message || 'שגיאה'} : p); }
            };

            return (
              <div>
                {splitModal?.open && (
                  <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={e => { if(e.target===e.currentTarget) setSplitModal(null); }}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 mx-4" dir="rtl">
                      <div className="flex justify-between items-center mb-4">
                        <h2 className="font-semibold text-base">פיצול חוזה {splitModal.contract}</h2>
                        <button onClick={() => setSplitModal(null)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
                      </div>
                      <div className="mb-4">
                        <label className="text-xs text-gray-500 block mb-1">שם חיבור</label>
                        <input value={splitModal.connectionName} onChange={e => setSplitModal(p => p ? {...p, connectionName: e.target.value} : p)} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full" />
                      </div>
                      {splitModal.splits.map((s:any, i:number) => (
                        <div key={i} className="grid grid-cols-12 gap-2 mb-2 items-center">
                          <input value={s.account_code} dir="ltr" onChange={e => setSplitModal(p => { if(!p) return p; const sp=[...p.splits]; sp[i]={...sp[i],account_code:e.target.value}; return {...p,splits:sp}; })} className="col-span-7 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono" />
                          <input value={s.percent} type="number" onChange={e => setSplitModal(p => { if(!p) return p; const sp=[...p.splits]; sp[i]={...sp[i],percent:e.target.value}; return {...p,splits:sp}; })} className="col-span-3 border border-gray-200 rounded-lg px-3 py-2 text-sm text-center" />
                          <button onClick={() => setSplitModal(p => { if(!p) return p; return {...p,splits:p.splits.filter((_:any,j:number)=>j!==i)}; })} className="col-span-2 text-red-400 text-lg text-center" disabled={splitModal.splits.length<=1}>✕</button>
                        </div>
                      ))}
                      <button onClick={() => setSplitModal(p => p ? {...p, splits:[...p.splits,{account_code:'',percent:''}]} : p)} className="text-sm text-blue-600 hover:underline mb-4">+ הוסף פיצול</button>
                      {splitModal.error && <div className="text-red-500 text-sm mb-3">{splitModal.error}</div>}
                      <div className="flex gap-2 justify-end">
                        <button onClick={() => setSplitModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg">ביטול</button>
                        <button onClick={saveSplit} disabled={splitModal.saving} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg disabled:opacity-50">{splitModal.saving ? 'שומר...' : 'שמור'}</button>
                      </div>
                    </div>
                  </div>
                )}
                <div className="flex justify-between items-center mb-4">
                  <div><h1 className="text-base font-semibold">אינדקסי חשמל</h1><p className="text-xs text-gray-500">{muni?.name} · {contracts.length} חוזים</p></div>
                  <input value={elecIndexSearch} onChange={e => setElecIndexSearch(e.target.value)} placeholder="חיפוש..." className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64" />
                </div>
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead><tr className="bg-gray-50 border-b border-gray-100">
                      {['מספר חוזה','שם חיבור','קוד חשבון','%','פיצול',''].map(h => <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {contracts.map(contract => {
                        const rows = grouped[contract];
                        const totalPct = rows.reduce((s:number,r:any) => s + parseFloat(r.description||'100'), 0);
                        const isInvalid = Math.abs(totalPct - 100) > 0.01;
                        const isSplit = rows.length > 1;
                        return rows.map((idx: any, ri: number) => (
                          <tr key={idx.id} className={`border-b border-gray-50 hover:bg-gray-50 ${isInvalid ? 'bg-red-50' : ''}`}>
                            {ri === 0 && <td className="p-3 font-mono text-xs align-top" rowSpan={rows.length}>{contract}{isSplit && <div className="text-blue-500 text-xs">מפוצל ל-{rows.length}</div>}</td>}
                            <td className="p-3 text-xs text-gray-500">{idx.connection_name || '—'}</td>
                            <td className="p-3 font-mono text-xs">{idx.account_code}</td>
                            <td className="p-3 text-xs text-center">{parseFloat(idx.description||'100').toFixed(0)}%</td>
                            {ri === 0 && <td className="p-3 align-top" rowSpan={rows.length}><button onClick={() => openSplitModal(contract)} className="text-xs text-blue-600 border border-blue-200 rounded-lg px-2 py-1 hover:bg-blue-50">✂ ערוך</button></td>}
                            <td className="p-3 text-xs text-red-400 cursor-pointer hover:text-red-600" onClick={async () => { if (!confirm('מחק?')) return; await apiFetch(`/indexes/${idx.id}`, { method: 'DELETE' }); setElecIndexes(p => p.filter((r:any) => r.id !== idx.id)); }}>מחק</td>
                          </tr>
                        ));
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}

          {activeTab === 'welfare' && welfareView === 'home' && (
            <WelfareDashboard muni={muni} onNewIntake={() => { setWelfareView('intake'); setWelfareResult(null); }} refreshKey={welfareRefreshKey} />
          )}

          {activeTab === 'welfare' && welfareView === 'intake' && (
            <div>
              <h1 className="text-base font-semibold mb-4">קליטת דוח רווחה</h1>
              {!welfareResult ? (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${welfareLoading ? 'border-gray-200' : 'border-gray-300 hover:border-green-400 hover:bg-green-50'}`}>
                    <div className="text-4xl mb-3">🤝</div>
                    <div className="text-sm font-medium text-gray-700">{welfareLoading ? 'מעלה...' : 'לחץ לבחירת קובץ דוח רווחה (Excel)'}</div>
                    <input type="file" accept=".xlsx,.xls" className="hidden" disabled={welfareLoading}
                      onChange={async (e) => {
                        const file = e.target.files?.[0]; if (!file || !muni) return;
                        setWelfareLoading(true); setError('');
                        try {
                          const fd = new FormData(); fd.append('file', file); fd.append('municipality_id', muni.id);
                          // Store file as base64 for treasurer report
                          const buf = await file.arrayBuffer();
                          setWelfareFileB64(btoa(String.fromCharCode(...new Uint8Array(buf))));
                          const res = await fetch(`${API}/upload/welfare`, { method: 'POST', body: fd });
                          const data = await res.json();
                          if (!res.ok) throw new Error(data.detail || 'שגיאה');
                          setWelfareResult(data);
                        } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
                        finally { setWelfareLoading(false); }
                      }} />
                  </label>
                </div>
              ) : (
                <div>
                  <div className={`rounded-lg p-3 mb-4 text-sm ${welfareResult.can_approve ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-amber-50 border border-amber-200 text-amber-700'}`}>
                    <div className="font-medium mb-1">{welfareResult.municipality} · {welfareResult.period}</div>
                    <div className="flex gap-4 text-xs">
                      <span>שורות: {welfareResult.total_rows}</span><span>תואמות: {welfareResult.matched}</span>
                      <span>חובה: ₪{welfareResult.total_debit?.toLocaleString()}</span>
                    </div>
                  </div>
                  {welfareResult.missing_index?.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                      <div className="font-semibold text-amber-700 text-sm mb-2">
                        ⚠️ {welfareResult.missing_index.length} סעיפים חסרים באינדקס — יירשמו ללא קוד חשבון
                      </div>
                      <div className="text-xs text-amber-600 mb-3">הפקודה תיקלט. ניתן להשלים את הקודים בעדכון אינדקס ולהפיק מחדש:</div>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-amber-600 border-b border-amber-200">
                            <th className="text-right pb-1">סמל סעיף</th>
                            <th className="text-right pb-1">שם סעיף</th>
                            <th className="text-right pb-1">סכום T</th>
                            <th className="text-right pb-1">סכום K</th>
                          </tr>
                        </thead>
                        <tbody>
                          {welfareResult.missing_index.map((r: any) => (
                            <tr key={r.semel} className="border-b border-amber-100">
                              <td className="py-1 font-mono text-amber-700">{r.semel}</td>
                              <td className="py-1 text-amber-600">{r.name}</td>
                              <td className="py-1 text-amber-600">₪{(parseFloat(r.govt_amount || 0)).toLocaleString()}</td>
                              <td className="py-1 text-amber-600">₪{(parseFloat(r.source_amount || 0)).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="flex gap-3 flex-wrap">
                    <button onClick={() => { setWelfareResult(null); setError(''); }} className="border border-gray-200 rounded-lg px-4 py-2 text-sm">קובץ חדש</button>
                    {welfareResult.missing_index?.length > 0 && muni && (
                      <button
                        onClick={async () => {
                          if (!muni || !welfareResult) return;
                          try {
                            const res = await fetch(`${API}/upload/welfare/missing-report`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ municipality_id: muni.id, period: `${welfareResult.month}/${welfareResult.year || 2026}`, missing: welfareResult.missing_index })
                            });
                            if (!res.ok) throw new Error(await res.text());
                            const blob = await res.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a'); a.href = url;
                            a.download = `missing_welfare_${welfareResult.month}_${welfareResult.year || 2026}.xlsx`;
                            a.click(); URL.revokeObjectURL(url);
                          } catch(e: any) { alert(e.message); }
                        }}
                        className="border border-amber-300 text-amber-700 rounded-lg px-4 py-2 text-sm hover:bg-amber-50">
                        ⬇ דוח סעיפים חסרים ({welfareResult.missing_index.length})
                      </button>
                    )}
                    <button disabled={welfareLoading}
                      onClick={async () => {
                        if (!muni || !welfareResult) return;
                        setWelfareLoading(true); setError('');
                        try {
                          const lines = welfareResult.rows.filter((r:any) => r.amount > 0).map((r:any) => ({ semel: r.semel, account: r.account, amount: r.amount, side: r.side, description: r.description }));
                          const res = await apiFetch('/upload/welfare/approve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ municipality_id: muni.id, period: `${welfareResult.year || new Date().getFullYear()}-${String(welfareResult.month).padStart(2,'0')}`, month: welfareResult.month, year: welfareResult.year || new Date().getFullYear(), source_file: welfareResult.filename, source_file_b64: welfareFileB64 || undefined, lines }) });
                          alert(`פקודה נוצרה! ${res.reference_num}`);
                          // Auto-generate & download treasurer PDF
                          if (welfareFileB64) {
                            try {
                              const byteChars = atob(welfareFileB64);
                              const byteArr = new Uint8Array(byteChars.length);
                              for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
                              const blob = new Blob([byteArr], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                              const fd = new FormData(); fd.append('file', blob, 'welfare.xlsx');
                              const pdfRes = await fetch(`${API}/upload/welfare/treasurer-report`, { method: 'POST', body: fd });
                              if (pdfRes.ok) {
                                const pdfBlob = await pdfRes.blob();
                                const url = URL.createObjectURL(pdfBlob);
                                const a = document.createElement('a'); a.href = url;
                                a.download = `דוח_גזבר_${muni.name}_${welfareResult.month}_${welfareResult.year || new Date().getFullYear()}.pdf`;
                                a.click(); URL.revokeObjectURL(url);
                              }
                            } catch (e) { console.warn('Treasurer PDF download failed:', e); }
                          }
                          setWelfareResult(null); setWelfareFileB64(''); setWelfareRefreshKey(k => k + 1); setWelfareView('home');
                        } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
                        finally { setWelfareLoading(false); }
                      }}
                      className="bg-green-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-40">
                      {welfareLoading ? 'שומר...' : 'צור פקודת יומן ✓'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'welfare' && welfareView === 'indexes' && (
            <div>
              <div className="flex justify-between items-center mb-4">
                <div><h1 className="text-base font-semibold">אינדקס רווחה</h1><p className="text-xs text-gray-500">{muni?.name} · {welfareIndexes.filter(i=>!welfareIndexSearch||i.key_value?.includes(welfareIndexSearch)||i.account_code?.includes(welfareIndexSearch)||(i.connection_name||'').includes(welfareIndexSearch)).length} רשומות</p></div>
                <input value={welfareIndexSearch} onChange={e=>setWelfareIndexSearch(e.target.value)} placeholder="חיפוש סמל / חשבון..." className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-56" />
              </div>
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                <table className="w-full text-sm">
                  <thead><tr className="bg-gray-50 border-b border-gray-100">
                    {['סמל סעיף','שם','חשבון חובה','חשבון זכות',''].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {welfareIndexes.filter(i=>!welfareIndexSearch||i.key_value?.includes(welfareIndexSearch)||(i.connection_name||'').includes(welfareIndexSearch)||i.account_code?.includes(welfareIndexSearch)).filter((idx:any,i:number,arr:any[])=>arr.findIndex((x:any)=>x.key_value===idx.key_value)===i).map((idx:any)=>(
                      <tr key={idx.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="p-3 font-mono text-xs">{idx.key_value}</td>
                        <td className="p-3 text-xs text-gray-500">{idx.connection_name||'—'}</td>
                        {welfareEditId===idx.id ? (
                          <><td className="p-2"><input value={welfareEditVals.name} onChange={e=>setWelfareEditVals(p=>({...p,name:e.target.value}))} className="border rounded px-2 py-1 text-xs w-full" placeholder="שם סעיף"/></td>
                          <td className="p-2"><input value={welfareEditVals.debit} onChange={e=>setWelfareEditVals(p=>({...p,debit:e.target.value}))} className="border rounded px-2 py-1 text-xs font-mono w-32" placeholder="חשבון חובה"/></td>
                          <td className="p-2"><input value={welfareEditVals.credit} onChange={e=>setWelfareEditVals(p=>({...p,credit:e.target.value}))} className="border rounded px-2 py-1 text-xs font-mono w-32" placeholder="חשבון זכות"/></td>
                          <td className="p-2 flex gap-1"><button onClick={async()=>{try{if(welfareEditVals.debit)await apiFetch(`/indexes/${idx.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_code:welfareEditVals.debit,description:'debit',connection_name:welfareEditVals.name})});if(welfareEditVals.credit){const cr=welfareIndexes.find(x=>x.key_value===idx.key_value&&x.description==='credit');if(cr)await apiFetch(`/indexes/${cr.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({account_code:welfareEditVals.credit,connection_name:welfareEditVals.name})});}setWelfareEditId(null);if(muni)apiFetch(`/indexes?municipality_id=${muni.id}&template_id=95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7&limit=500`).then(d=>setWelfareIndexes(Array.isArray(d)?d:[]));} catch(e:any){setWelfareAddError(e.message);}}} className="text-xs bg-blue-600 text-white rounded px-2 py-1">שמור</button><button onClick={()=>setWelfareEditId(null)} className="text-xs border rounded px-2 py-1">ביטול</button></td></>
                        ) : (
                          <><td className="p-3 font-mono text-xs">{idx.description==='debit'?idx.account_code:welfareIndexes.find(x=>x.key_value===idx.key_value&&x.description==='debit')?.account_code||'—'}</td>
                          <td className="p-3 font-mono text-xs">{idx.description==='credit'?idx.account_code:welfareIndexes.find(x=>x.key_value===idx.key_value&&x.description==='credit')?.account_code||'—'}</td>
                          <td className="p-3 flex gap-2"><button onClick={()=>{const db=welfareIndexes.find(x=>x.key_value===idx.key_value&&x.description==='debit');const cr=welfareIndexes.find(x=>x.key_value===idx.key_value&&x.description==='credit');setWelfareEditId(idx.id);setWelfareEditVals({debit:db?.account_code||'',credit:cr?.account_code||'',name:idx.connection_name||''});}} className="text-xs text-blue-600 hover:underline">ערוך</button><button onClick={async()=>{if(!confirm('מחק?'))return;const same=welfareIndexes.filter(x=>x.key_value===idx.key_value);await Promise.all(same.map(x=>apiFetch(`/indexes/${x.id}`,{method:'DELETE'})));setWelfareIndexes(p=>p.filter(x=>x.key_value!==idx.key_value));}} className="text-xs text-red-400 hover:text-red-600">מחק</button></td></>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <h2 className="text-sm font-semibold mb-3">+ הוספת סעיף חדש</h2>
                {welfareAddError && <div className="text-red-500 text-xs mb-2">{welfareAddError}</div>}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div><label className="text-xs text-gray-500 block mb-1">סמל סעיף</label><input value={welfareNewRow.key_value} onChange={e=>setWelfareNewRow(p=>({...p,key_value:e.target.value}))} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full font-mono" placeholder="למשל: 039734"/></div>
                  <div><label className="text-xs text-gray-500 block mb-1">שם סעיף</label><input value={welfareNewRow.name} onChange={e=>setWelfareNewRow(p=>({...p,name:e.target.value}))} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full" placeholder="שם לתצוגה"/></div>
                  <div><label className="text-xs text-gray-500 block mb-1">חשבון חובה</label><input value={welfareNewRow.debit} onChange={e=>setWelfareNewRow(p=>({...p,debit:e.target.value}))} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full font-mono" placeholder="184XXXXXXX"/></div>
                  <div><label className="text-xs text-gray-500 block mb-1">חשבון זכות</label><input value={welfareNewRow.credit} onChange={e=>setWelfareNewRow(p=>({...p,credit:e.target.value}))} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full font-mono" placeholder="134XXXXXXX"/></div>
                </div>
                <button onClick={async()=>{
                  setWelfareAddError('');
                  if(!welfareNewRow.key_value||!welfareNewRow.credit){setWelfareAddError('סמל וחשבון זכות הם שדות חובה');return;}
                  try{
                    if(!muni) return;
                    if(welfareNewRow.debit) await apiFetch('/indexes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({municipality_id:muni.id,template_id:'95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7',key_value:welfareNewRow.key_value.trim(),account_code:welfareNewRow.debit.trim(),description:'debit',connection_name:welfareNewRow.name.trim()})});
                    await apiFetch('/indexes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({municipality_id:muni.id,template_id:'95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7',key_value:welfareNewRow.key_value.trim(),account_code:welfareNewRow.credit.trim(),description:'credit',connection_name:welfareNewRow.name.trim()})});
                    setWelfareNewRow({key_value:'',debit:'',credit:'',name:''});
                    const fresh=await apiFetch(`/indexes?municipality_id=${muni.id}&template_id=95b37d2d-c9ea-4ef1-9164-ab5ac642b0c7&limit=500`);
                    setWelfareIndexes(Array.isArray(fresh)?fresh:[]);
                  }catch(e:any){setWelfareAddError(e.message||'שגיאה');}
                }} className="bg-green-600 text-white rounded-lg px-5 py-2 text-sm hover:bg-green-700">הוסף סעיף</button>
              </div>
            </div>
          )}


          {activeTab !== 'bezeq' && activeTab !== 'electricity' && activeTab !== 'welfare' && activeTab !== 'celcom' && (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="text-5xl mb-4">{CATEGORIES.find(c=>c.id===activeTab)?.icon}</div>
              <h2 className="text-lg font-semibold text-gray-700 mb-2">{CATEGORIES.find(c=>c.id===activeTab)?.label} – בקרוב</h2>
              <p className="text-sm text-gray-400">מודול זה יתווסף בגרסה הבאה</p>
            </div>
          )}

          {activeTab === 'bezeq' && bezeqView === 'home' && (
            <div>
              <div className="flex justify-between items-center mb-5">
                <div><h1 className="text-base font-semibold text-gray-900">בזק – דשבורד</h1><p className="text-xs text-gray-500">{muni?.name}</p></div>
                <button onClick={() => { setStep(1); setUploadResult(null); setBezeqView('intake'); }} className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">+ קליטת חשבון</button>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                {[['פקודות', entries.filter((e:any)=>e.template_key==='bezeq').length],['טיוטות', entries.filter((e:any)=>e.template_key==='bezeq'&&e.status==='draft').length],
                  ['סה"כ', '₪'+entries.filter((e:any)=>e.template_key==='bezeq').reduce((s:number,e:any)=>s+(e.total_amount||0),0).toLocaleString()]].map(([l,v])=>(
                  <div key={l as string} className="bg-gray-100 rounded-lg p-4">
                    <div className="text-xs text-gray-500 mb-1">{l}</div>
                    <div className="text-2xl font-semibold text-gray-900">{v}</div>
                  </div>
                ))}
              </div>
              <div className="bg-white rounded-xl border border-gray-200">
                <div className="p-4 border-b border-gray-100 text-sm font-medium">פקודות אחרונות</div>
                {entries.length === 0 ? <div className="p-8 text-center text-sm text-gray-400">אין פקודות עדיין</div>
                  : <table className="w-full text-sm"><thead><tr className="border-b border-gray-100">
                      {['מספר','תקופה','סכום','סטטוס',''].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                    </tr></thead><tbody>
                    {entries.filter((e:any)=>e.template_key==='bezeq'||(!e.template_key&&e.template_name!=='חשמל')).map(e=>(
                      <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="p-3 font-mono text-xs">{e.reference_num}</td>
                        <td className="p-3 text-xs">{e.period}</td>
                        <td className="p-3 font-medium text-xs">₪{(e.total_amount||0).toLocaleString()}</td>
                        <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs ${e.status==='draft'?'bg-blue-100 text-blue-700':'bg-green-100 text-green-700'}`}>{e.status==='draft'?'טיוטה':'מאושר'}</span></td>
                        <td className="p-3 flex gap-3">
                          <button onClick={()=>window.open(`${API}/journal-entries/${e.id}/export`,'_blank')} className="text-xs text-blue-600 hover:underline">Excel</button>
                          {e.status !== 'approved' && <button onClick={()=>deleteJournalEntry(e.id, e.reference_num)} className="text-xs text-red-500 hover:underline">מחק</button>}
                        </td>
                      </tr>
                    ))}
                  </tbody></table>}
              </div>
            </div>
          )}

          {activeTab === 'bezeq' && bezeqView === 'intake' && (
            <div>
              <div className="flex justify-between mb-4"><h1 className="text-base font-semibold">קליטת חשבון בזק</h1><span className="text-xs text-gray-400">שלב {step}/3</span></div>
              <div className="flex items-center gap-2 mb-6">
                {['העלאה','אינדקסים','פקודה'].map((s,i)=>(
                  <div key={i} className="flex items-center gap-2">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${step>i+1?'bg-green-500 text-white':step===i+1?'bg-blue-600 text-white':'bg-gray-200 text-gray-500'}`}>{step>i+1?'✓':i+1}</div>
                    <span className={`text-xs ${step===i+1?'font-medium text-gray-900':'text-gray-400'}`}>{s}</span>
                    {i<2&&<div className="w-8 h-px bg-gray-200"/>}
                  </div>
                ))}
              </div>
              {step===1 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <div className="mb-4">
                    <label className="text-xs text-gray-500 block mb-1">תקופה (YYYY-MM)</label>
                    <input value={period} onChange={e=>setPeriod(e.target.value)} className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-40"/>
                  </div>
                  <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${loading?'border-gray-200':'border-gray-300 hover:border-blue-400 hover:bg-blue-50'}`}>
                    <div className="text-4xl mb-3">📂</div>
                    <div className="text-sm font-medium text-gray-700">{loading?'מעלה...':'לחץ לבחירת קובץ בזק'}</div>
                    <input type="file" accept=".csv,.xlsx,.xls" onChange={handleFileUpload} className="hidden" disabled={loading}/>
                  </label>
                </div>
              )}
              {step===2 && uploadResult && (
                <div>
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4 text-sm text-green-700">נטענו {uploadResult.total_rows} שורות · {uploadResult.matched} תואמות · {uploadResult.missing} חסרות</div>
                  {uploadResult.missing > 0 && <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4 text-sm text-amber-700">מספרים חסרים ייפתחו באינדקס וימתינו לשיוך סעיף תקציבי</div>}
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50 border-b border-gray-100">
                        {['מספר מנוי','שם','סכום','קוד חשבון','סטטוס'].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>{uploadResult.rows.map(row=>(
                        <tr key={row.row_num} className={`border-b border-gray-50 ${!row.has_index?'bg-amber-50':''}`}>
                          <td className="p-3 font-mono text-xs">{row.phone}</td>
                          <td className="p-3 text-xs text-gray-600">{row.description || row.name}</td>
                          <td className="p-3 text-xs font-medium">₪{row.amount.toLocaleString()}</td>
                          <td className="p-3">{row.has_index?<code className="text-xs">{row.account}</code>:<input placeholder="סעיף (אופציונלי)" className="border border-amber-300 rounded px-2 py-1 text-xs w-28" onChange={e=>setIndexMap(m=>({...m,[row.row_num]:e.target.value}))}/>}</td>
                          <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs ${row.has_index?'bg-green-100 text-green-700':'bg-amber-100 text-amber-700'}`}>{row.has_index?'קיים':'חדש'}</span></td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={()=>setStep(1)} className="border border-gray-200 rounded-lg px-4 py-2 text-sm">חזרה</button>
                    <button onClick={handleSaveIndexesAndContinue} disabled={loading} className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm disabled:opacity-50">{loading?'שומר...':'שמור והמשך ←'}</button>
                  </div>
                </div>
              )}
              {step===3 && uploadResult && (
                <div>
                  <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
                    <div className="grid grid-cols-3 gap-3">
                      {[['רשות',muni?.name],['תקופה',period],['שורות',uploadResult.total_rows]].map(([l,v])=>(
                        <div key={l as string} className="bg-gray-50 rounded-lg p-3"><div className="text-xs text-gray-500 mb-1">{l}</div><div className="text-sm font-medium text-gray-900">{v}</div></div>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-3">
                    <button onClick={()=>setStep(2)} className="border border-gray-200 rounded-lg px-4 py-2 text-sm">חזרה</button>
                    <button onClick={handleCreateJournal} disabled={loading} className="bg-green-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-50">{loading?'שומר...':'שמור פקודה ✓'}</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'bezeq' && bezeqView === 'settings' && (
            <div className="max-w-lg">
              <h1 className="text-base font-semibold mb-1">הגדרות בזק</h1>
              <p className="text-xs text-gray-500 mb-6">{muni?.name}</p>
              {settingsSaved && <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg p-3 mb-4">✓ נשמר</div>}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <label className="block text-sm font-medium text-gray-700 mb-1">חשבון ספק בזק</label>
                <input value={settings.vendor_account} onChange={e => setSettings(s => ({...s, vendor_account: e.target.value}))} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono mb-4" />
                <button onClick={saveSettings} disabled={loading} className="bg-blue-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-50">{loading ? 'שומר...' : 'שמור'}</button>
              </div>
            </div>
          )}

          {activeTab === 'bezeq' && bezeqView === 'indexes' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div><h1 className="text-base font-semibold">אינדקסי בזק</h1><p className="text-xs text-gray-500">{muni?.name} · {indexes.length} רשומות</p></div>
              </div>
              <div className="flex gap-3 mb-4">
                <input value={indexSearch} onChange={e=>setIndexSearch(e.target.value)} placeholder="חיפוש לפי טלפון, חשבון..." className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm" onKeyDown={e=>e.key==='Enter'&&loadIndexes()}/>
                <button onClick={loadIndexes} className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm">חפש</button>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="w-full text-sm">
                  <thead><tr className="bg-gray-50 border-b border-gray-100">
                    {['מספר טלפון','קוד חשבון','שם חיבור','פעולות'].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                  </tr></thead>
                  <tbody>
                    {loading && <tr><td colSpan={4} className="p-6 text-center text-sm text-gray-400">טוען...</td></tr>}
                    {indexes.map(idx=>(
                      <tr key={idx.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="p-3 font-mono text-xs">{idx.key_value}</td>
                        <td className="p-3">{editingIndex===idx.id?<input value={editVals.account_code} onChange={e=>setEditVals(v=>({...v,account_code:e.target.value}))} className="border border-blue-300 rounded px-2 py-1 text-xs w-28"/>:<code className="text-xs">{idx.account_code}</code>}</td>
                        <td className="p-3 text-xs">{editingIndex===idx.id?<input value={editVals.connection_name} onChange={e=>setEditVals(v=>({...v,connection_name:e.target.value}))} className="border border-blue-300 rounded px-2 py-1 text-xs w-48"/>:<span>{idx.connection_name||'—'}</span>}</td>
                        <td className="p-3">
                          {editingIndex===idx.id
                            ?<div className="flex gap-2"><button onClick={()=>saveIndexEdit(idx.id)} className="text-xs text-green-600 font-medium hover:underline">שמור</button><button onClick={()=>setEditingIndex(null)} className="text-xs text-gray-400 hover:underline">ביטול</button></div>
                            :<div className="flex gap-3"><button onClick={()=>{setEditingIndex(idx.id);setEditVals({account_code:idx.account_code,connection_name:idx.connection_name||''});}} className="text-xs text-blue-600 hover:underline">עריכה</button><button onClick={()=>deleteIndex(idx.id,idx.key_value)} className="text-xs text-red-500 hover:underline">מחק</button></div>}
                        </td>
                      </tr>
                    ))}
                    {!loading&&indexes.length===0&&<tr><td colSpan={4} className="p-8 text-center text-sm text-gray-400">לחץ חפש</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return null;
}
