'use client';
import React, { useState, useEffect } from 'react';

const API = 'http://localhost:8000';
const BEZEQ_TEMPLATE_ID = '34967fa4-a92c-4876-bf73-f6cf05804519';

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
  { id: 'electricity', label: 'חשמל',   icon: '⚡', active: false },
  { id: 'welfare',     label: 'רווחה',  icon: '🏥', active: false },
  { id: 'leasing',     label: 'ליסינג', icon: '🚗', active: false },
  { id: 'other',       label: 'אחר',    icon: '📁', active: false },
];

const ELEC_TEMPLATE_ID = '5594291d-2a5f-4b6c-846a-bed1290388b1';

function ElectricityDashboard({ muni, onNewIntake }: { muni: any, onNewIntake: () => void }) {
  const [entries, setEntries] = React.useState<any[]>([]);
  const [lines, setLines] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [vendorAccount, setVendorAccount] = React.useState('7000000000');
  const [editVendor, setEditVendor] = React.useState(false);
  const [selectedPeriod, setSelectedPeriod] = React.useState<string|null>(null);

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

  // KPIs
  const totalAll   = elecEntries.reduce((s: number, e: any) => s + (e.total_amount || 0), 0);
  const lastEntry  = elecEntries[0];
  const prevEntry  = elecEntries[1];
  const lastTotal  = lastEntry?.total_amount || 0;
  const prevTotal  = prevEntry?.total_amount || 0;
  const monthDiff  = prevTotal > 0 ? ((lastTotal - prevTotal) / prevTotal * 100) : null;

  // ממוצע 12 חודשים אחרונים
  const last12     = elecEntries.slice(0, 12);
  const avg12      = last12.length > 0 ? last12.reduce((s: number, e: any) => s + (e.total_amount || 0), 0) / last12.length : 0;



  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="text-base font-semibold">חשמל – דשבורד</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {elecEntries.length} תקופות</p>
        </div>
        <button onClick={onNewIntake} className="bg-yellow-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-yellow-600 font-medium">
          ⚡ + קליטת חשבון
        </button>
      </div>

      {loading ? <div className="p-12 text-center text-sm text-gray-400">טוען...</div> : (<>

      {/* KPI Cards */}
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
            <div className="text-xs text-gray-500 mt-0.5">מול {prevEntry?.period || '—'}</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">ממוצע 12 חודשים</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(avg12).toLocaleString()}</div>
            <div className="text-xs text-gray-500 mt-0.5">{last12.length} חודשים</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">סה"כ מצטבר</div>
            <div className="text-lg font-bold text-gray-900">₪{Math.round(totalAll).toLocaleString()}</div>
            <div className="text-xs text-gray-500 mt-0.5">כל התקופות</div>
          </div>
        </div>
      )}

      {/* גרף עמודות – השוואת חודשים */}
      {elecEntries.length > 1 && (() => {
        const chartData = elecEntries.slice(0, 12).reverse();
        const maxVal = Math.max(...chartData.map((e: any) => e.total_amount || 0));
        return (
          <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5">
            <div className="text-xs font-medium text-gray-600 mb-3">השוואת חודשים</div>
            <div className="flex items-end gap-2 h-28">
              {chartData.map((e: any) => {
                const h = maxVal > 0 ? ((e.total_amount || 0) / maxVal * 100) : 0;
                const isLast = e.id === lastEntry?.id;
                return (
                  <div key={e.id} className="flex flex-col items-center flex-1 gap-1">
                    <div className="text-xs text-gray-500" style={{fontSize:'9px'}}>₪{Math.round((e.total_amount||0)/1000)}K</div>
                    <div className={`w-full rounded-t-sm transition-all ${isLast ? 'bg-yellow-400' : 'bg-blue-200'}`}
                      style={{height: `${Math.max(h, 4)}%`}} title={`${e.period}: ₪${(e.total_amount||0).toLocaleString()}`}></div>
                    <div className="text-gray-400 text-center" style={{fontSize:'8px'}}>{e.period?.slice(5)}/{e.period?.slice(2,4)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* הגדרות + פקודות */}
      <div className="grid grid-cols-3 gap-4">
        {/* טבלת פקודות */}
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
                        <span className={`px-2 py-0.5 rounded-full text-xs ${
                          e.status==='draft' ? 'bg-blue-100 text-blue-700' :
                          e.status==='exported' ? 'bg-green-100 text-green-700' :
                          'bg-gray-100 text-gray-600'}`}>
                          {e.status==='draft'?'טיוטה':e.status==='exported'?'יוצא':e.status}
                        </span>
                      </td>
                      <td className="p-2.5 flex gap-2">
                        <button onClick={() => window.open(`http://localhost:8000/journal-entries/${e.id}/export`, '_blank')}
                          className="text-xs text-blue-600 hover:underline">Excel</button>
                        {e.status === 'draft' &&
                          <button onClick={() => deleteEntry(e.id, e.reference_num)}
                            className="text-xs text-red-400 hover:underline">מחק</button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>}
        </div>

        {/* פאנל ימני */}
        <div className="flex flex-col gap-3">
          {/* חשבון ספק */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs font-medium text-gray-600 mb-2">חשבון ספק חשמל</div>
            {editVendor ? (
              <div className="flex flex-col gap-2">
                <input value={vendorAccount} onChange={e => setVendorAccount(e.target.value)}
                  className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono w-full" />
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

          {/* סטטיסטיקה מהירה */}
          {elecEntries.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <div className="text-xs font-medium text-gray-600 mb-2">סטטוס פקודות</div>
              {[
                { label: 'טיוטא', status: 'draft', color: 'bg-blue-100 text-blue-700' },
                { label: 'יוצא', status: 'exported', color: 'bg-green-100 text-green-700' },
              ].map(({ label, status, color }) => {
                const count = elecEntries.filter((e: any) => e.status === status).length;
                return count > 0 ? (
                  <div key={status} className="flex justify-between items-center mb-1">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${color}`}>{label}</span>
                    <span className="text-xs font-medium text-gray-700">{count}</span>
                  </div>
                ) : null;
              })}
            </div>
          )}
        </div>
      </div>

      </>)}
    </div>
  );
}


function WelfareDashboard({ muni, onNewIntake }: { muni: any, onNewIntake: () => void }) {
  const [entries, setEntries] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);

  const loadData = () => {
    if (!muni) return;
    setLoading(true);
    apiFetch(`/journal-entries?municipality_id=${muni.id}&limit=50`)
      .then((data: any) => setEntries(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  React.useEffect(() => { loadData(); }, [muni?.id]);

  const welfareEntries = entries
    .filter((e: any) => e.template_key === 'welfare' || e.template_name === 'רווחה')
    .sort((a: any, b: any) => b.period.localeCompare(a.period));

  const totalAll  = welfareEntries.reduce((s: number, e: any) => s + (e.total_amount || 0), 0);
  const lastEntry = welfareEntries[0];

  return (
    <div>
      <div className="flex justify-between items-center mb-5">
        <div>
          <h1 className="text-base font-semibold">רווחה – דשבורד</h1>
          <p className="text-xs text-gray-500">{muni?.name} · {welfareEntries.length} תקופות</p>
        </div>
        <button onClick={onNewIntake} className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 font-medium">
          🤝 + קליטת דוח
        </button>
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
            <div className="text-xs text-gray-500 mt-0.5">כל התקופות</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-400 mb-1">מספר פקודות</div>
            <div className="text-lg font-bold text-gray-900">{welfareEntries.length}</div>
            <div className="text-xs text-gray-500 mt-0.5">סה"כ</div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-3 border-b border-gray-100 flex justify-between items-center">
          <span className="text-xs font-medium text-gray-600">פקודות יומן</span>
          <span className="text-xs text-gray-400">{welfareEntries.length} פקודות</span>
        </div>
        {welfareEntries.length === 0
          ? <div className="p-8 text-center text-sm text-gray-400">אין פקודות עדיין – לחץ "קליטת דוח"</div>
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
                        {e.status==='draft' ? 'טיוטה' : e.status==='exported' ? 'יוצא' : e.status}
                      </span>
                    </td>
                    <td className="p-2.5">
                      <button onClick={() => window.open(`http://localhost:8000/journal-entries/${e.id}/export`, '_blank')}
                        className="text-xs text-blue-600 hover:underline">Excel</button>
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
  const [screen, setScreen] = useState<'login'|'muni'|'module'|'main'>('login');
  const [muni, setMuni] = useState<Municipality | null>(null);
  const [munis, setMunis] = useState<Municipality[]>([]);
  const [activeTab, setActiveTab] = useState('bezeq');
  const [bezeqView, setBezeqView] = useState<'home'|'intake'|'indexes'>('home');
  const [elecView, setElecView] = useState<'home'|'intake'|'indexes'>('home');
  const [elecIndexSearch, setElecIndexSearch] = useState('');
  const [elecIndexes, setElecIndexes] = useState<any[]>([]);
  const [elecIndexEdit, setElecIndexEdit] = useState<Record<string,string>>({});
  const [splitModal, setSplitModal] = useState<null|{open:boolean,contract:string,connectionName:string,splits:any[],saving:boolean,error:string}>(null);
  const [elecResult, setElecResult] = useState<any>(null);
  const [elecVendorAccount, setElecVendorAccount] = useState('7000000000');

  useEffect(() => {
    if (activeTab === 'electricity' && muni) {
      apiFetch(`/municipalities/${muni.id}/settings`)
        .then((s:any) => { if (s?.vendor_account) setElecVendorAccount(s.vendor_account); })
        .catch(() => {});
    }
  }, [activeTab, muni?.id]);
  const [elecLoading, setElecLoading] = useState(false);

  // ── Welfare state ──
  const [welfareView, setWelfareView] = useState<'home'|'intake'>('home');
  const [welfareResult, setWelfareResult] = useState<any>(null);
  const [welfareLoading, setWelfareLoading] = useState(false);

  // Bezeq state
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [indexMap, setIndexMap] = useState<Record<number, string>>({});
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [period, setPeriod] = useState('2026-02');

  // Indexes state
  const [indexes, setIndexes] = useState<IndexRow[]>([]);
  const [settings, setSettings] = useState<{vendor_account:string}>({vendor_account:'6000203000'});
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [indexSearch, setIndexSearch] = useState('');
  const [editingIndex, setEditingIndex] = useState<string|null>(null);
  const [editVals, setEditVals] = useState<{account_code:string;connection_name:string}>({account_code:'',connection_name:''});

  useEffect(() => {
    if (screen === 'muni') {
      setLoading(true);
      apiFetch('/municipalities').then(setMunis).catch(() => setError('שגיאה')).finally(() => setLoading(false));
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
      const heMonths: Record<string, string> = {
        'ינואר':'01','פברואר':'02','מרץ':'03','אפריל':'04',
        'מאי':'05','יוני':'06','יולי':'07','אוגוסט':'08',
        'ספטמבר':'09','אוקטובר':'10','נובמבר':'11','דצמבר':'12'
      };
      const rawPeriod = elecResult.period || '';
      const pparts = rawPeriod.trim().split(' ');
      const period = pparts.length === 2 && heMonths[pparts[0]]
        ? `${pparts[1]}-${heMonths[pparts[0]]}`
        : rawPeriod.slice(0, 7) || '2025-09';

      const lines = elecResult.rows
        .filter((r: any) => r.status === 'ok')
        .map((r: any) => ({
          account:     r.account,
          amount:      r.amount,
          description: r.description,
          key_value:   r.contract,
        }));

      const res = await apiFetch('/upload/electricity/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          municipality_id: muni.id,
          template_id:     elecResult.template_id || '5594291d-2a5f-4b6c-846a-bed1290388b1',
          period,
          source_file:     elecResult.filename || 'buller.csv',
          date_from:       elecResult.date_from,
          date_to:         elecResult.date_to,
          invoice_total:   elecResult.sum_details,
          lines,
        }),
      });
      alert(`פקודה נוצרה! ${res.reference_num}\nסה"כ: ₪${res.total?.toLocaleString()}\n${res.lines_count} שורות`);
      setElecResult(null);
      setElecView('home');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'שגיאה ביצירת פקודה');
    } finally { setElecLoading(false); }
  }
  async function loadSettings() {
    if (!muni) return;
    try {
      const data = await apiFetch(`/municipalities/${muni.id}/settings`);
      if (data?.vendor_account) setSettings({vendor_account: data.vendor_account});
    } catch { }
  }

  async function saveSettings() {
    if (!muni) return;
    setLoading(true);
    try {
      await apiFetch(`/municipalities/${muni.id}/settings`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({template_name: 'bezeq', key: 'vendor_account', value: settings.vendor_account}),
      });
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 3000);
    } catch { setError('שגיאה בשמירה'); }
    finally { setLoading(false); }
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
      // בדיקת כפילות תקופה
      const check = await apiFetch(`/journal-entries/check-period?municipality_id=${muni.id}&template_id=${BEZEQ_TEMPLATE_ID}&period=${period}`);
      if (check.exists) {
        setLoading(false);
        setError(`קיימת פקודה לתקופה ${period} (${check.reference_num}). יש למחוק אותה קודם.`);
        return;
      }
      const fd = new FormData();
      fd.append('file', file); fd.append('municipality_id', muni.id); fd.append('template', 'bezeq');
      const res = await fetch(`${API}/upload`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) {
        const msg = typeof data.detail === 'string' ? data.detail : 'שגיאה בעיבוד הקובץ';
        throw new Error(msg);
      }
      setUploadResult(data); setStep(2);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function handleSaveIndexesAndContinue() {
    if (!muni || !uploadResult) return;
    setLoading(true); setError('');
    try {
      const missing = uploadResult.rows.filter(r => !r.has_index && indexMap[r.row_num]);
      for (const row of missing) {
        await apiFetch('/indexes', { method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ municipality_id: muni.id, template_id: BEZEQ_TEMPLATE_ID,
            key_value: row.phone, account_code: indexMap[row.row_num], description: row.name !== 'nan' ? row.name : row.phone }) });
      }
      setStep(3);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function handleCreateJournal() {
    if (!muni || !uploadResult) return;
    if (loading) return;  // מנע לחיצה כפולה
    setLoading(true); setError('');
    try {
      const lines = uploadResult.rows.map(r => ({
        account: r.account || indexMap[r.row_num] || '9999',
        description: r.description || r.name, debit: r.amount, credit: 0,
        reference: r.invoice, key_value: r.phone,
      }));
      // הוסף extra_lines – חשבוניות קודמות, חיובים למשלם וכו
      const extraLines = (uploadResult as any).extra_lines || [];
      for (const el of extraLines) {
        const keyVal = (el.phone && el.phone.trim()) ? el.phone.trim() : '00000000000';
        const amt = el.amount || 0;
        if (amt === 0) continue;
        lines.push({
          account: el.account || '9999',
          description: el.description,
          debit: amt,  // שלילי = הוצאה שלילית (זיכוי)
          credit: 0,
          reference: '',
          key_value: keyVal
        });
      }
      const total = lines.reduce((s, l) => s + l.debit, 0);
      lines.push({ account: '6000203000', description: 'ספק בזק', debit: 0, credit: total, reference: '', key_value: '' });
      const res = await apiFetch('/journal-entries', { method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ municipality_id: muni.id, template_id: BEZEQ_TEMPLATE_ID, period,
          source_file: uploadResult.filename,
          notes: JSON.stringify({ invoice_num: uploadResult.invoice_num||'', date_from: uploadResult.date_from||'', date_to: uploadResult.date_to||'' }),
          lines }) });
      alert('פקודה נוצרה! ' + res.reference_num);
      setUploadResult(null); setStep(1); setBezeqView('home');
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה'); }
    finally { setLoading(false); }
  }

  async function saveIndexEdit(id: string) {
    try {
      await apiFetch(`/indexes/${id}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify(editVals) });
      setEditingIndex(null); loadIndexes();
    } catch { setError('שגיאה'); }
  }

  async function deleteJournalEntry(id: string, refNum: string) {
    if (!confirm(`מחק פקודה ${refNum}?`)) return;
    try {
      await apiFetch(`/journal-entries/${id}`, { method: 'DELETE' });
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (err: unknown) { setError(err instanceof Error ? err.message : 'שגיאה במחיקה'); }
  }

  async function deleteIndex(id: string, phone: string) {
    if (!confirm(`מחק ${phone}?`)) return;
    try { await apiFetch(`/indexes/${id}`, { method: 'DELETE' }); loadIndexes(); }
    catch { setError('שגיאה'); }
  }

  // ─── Sidebar nav items per tab ───
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
    welfare:     [
      { label: 'דשבורד', view: 'home', icon: '📊' },
      { label: 'קליטת דוח', view: 'intake', icon: '📂' },
    ],
    leasing:     [{ label: 'בקרוב', view: 'home', icon: '🚗' }],
    other:       [{ label: 'בקרוב', view: 'home', icon: '📁' }],
  };

  function switchTab(tabId: string) {
    setActiveTab(tabId); setBezeqView('home'); setError('');
  }

  // ─── SCREENS ───

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
            { id: 'electricity', label: 'חשמל', icon: '⚡', desc: 'קליטת חשבונות חשמל', color: 'bg-yellow-50 border-yellow-200 hover:border-yellow-400' },
            { id: 'bezeq', label: 'בזק', icon: '📞', desc: 'קליטת חשבונות בזק', color: 'bg-blue-50 border-blue-200 hover:border-blue-400' },
            { id: 'welfare', label: 'רווחה', icon: '🤝', desc: 'קליטת דוח תמר', color: 'bg-green-50 border-green-200 hover:border-green-400', disabled: false },
            { id: 'other', label: 'אחר', icon: '📁', desc: 'בקרוב', color: 'bg-gray-50 border-gray-200', disabled: true },
          ].map(mod => (
            <button key={mod.id}
              disabled={mod.disabled}
              onClick={() => { setActiveTab(mod.id); setScreen('main'); }}
              className={`border-2 rounded-xl p-5 text-right transition-colors ${mod.color} ${mod.disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}>
              <div className="text-3xl mb-2">{mod.icon}</div>
              <div className="font-semibold text-gray-900 mb-0.5">{mod.label}</div>
              <div className="text-xs text-gray-500">{mod.desc}</div>
            </button>
          ))}
        </div>
        <button onClick={() => setScreen('muni')} className="mt-6 text-xs text-gray-400 hover:text-gray-600">← החלפת רשות</button>
      </div>
    </div>
  );

  if (screen === 'main') return (
    <div dir="rtl" className="min-h-screen bg-gray-50 flex flex-col">

      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-xs">י</div>
          <span className="font-semibold text-sm text-gray-900">יומנית</span>
          <span className="text-gray-300">|</span>
          <span className="text-sm text-gray-600">{muni?.name}</span>
        </div>
        <button onClick={() => setScreen('module')} className="text-xs text-gray-400 hover:text-gray-600">החלפת מודול</button>
      </div>

      {/* Category tabs */}
      <div className="bg-white border-b border-gray-200 px-4 flex gap-1">
        {CATEGORIES.map(cat => (
          <button key={cat.id} onClick={() => switchTab(cat.id)}
            className={`flex items-center gap-1.5 px-4 py-3 text-sm border-b-2 transition-colors ${
              activeTab === cat.id
                ? 'border-blue-600 text-blue-700 font-medium'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            } ${!cat.active && activeTab !== cat.id ? 'opacity-50' : ''}`}>
            <span>{cat.icon}</span>
            <span>{cat.label}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">

        {/* Sidebar */}
        <div className="w-44 bg-white border-l border-gray-200 flex flex-col py-2">
          {(sidebarItems[activeTab] || []).map(item => (
            <button key={item.view}
              onClick={() => {
                if (activeTab === 'electricity') {
                  setElecView(item.view as 'home'|'intake'|'indexes');
                  setError('');
                  if (muni) {
                    apiFetch(`/municipalities/${muni.id}/settings`)
                      .then((s:any) => { if (s?.vendor_account) setElecVendorAccount(s.vendor_account); })
                      .catch(() => {});
                  }
                  if (item.view === 'intake') { setElecResult(null); }
                  if (item.view === 'indexes') {
                    if (!muni) return;
                    setElecIndexes([]);
                    apiFetch(`/indexes?municipality_id=${muni.id}&template_id=5594291d-2a5f-4b6c-846a-bed1290388b1&limit=500`)
                      .then((d:any) => setElecIndexes(Array.isArray(d) ? d : []))
                      .catch(() => {});
                  }
                }
                if (activeTab === 'welfare') {
                  setWelfareView(item.view as 'home'|'intake');
                  if (item.view === 'intake') { setWelfareResult(null); }
                  setError('');
                }
                if (activeTab === 'bezeq') {
                  setBezeqView(item.view as 'home'|'intake'|'indexes');
                  if (item.view === 'indexes') { setIndexSearch(''); loadIndexes(); }
                  if (item.view === 'intake') { setStep(1); setUploadResult(null); }
                  if (item.view === 'settings') { loadSettings(); }
                  setError('');
                }
              }}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm text-right transition-colors border-r-2 ${
                ((activeTab === 'bezeq' && bezeqView === item.view) ||
                 (activeTab === 'electricity' && elecView === item.view) ||
                 (activeTab === 'welfare' && welfareView === item.view))
                  ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
                  : 'border-transparent text-gray-600 hover:bg-gray-50'
              }`}>
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-auto p-6">
          {error && <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg p-3 mb-4">{error}</div>}

          {/* ══ ELECTRICITY ══ */}
          {activeTab === 'electricity' && elecView === 'home' && (
            <ElectricityDashboard muni={muni} onNewIntake={() => { setElecView('intake'); setElecResult(null); setError(''); }} />
          )}

          {activeTab === 'electricity' && elecView === 'intake' && (
            <div>
              <div className="flex justify-between mb-4">
                <h1 className="text-base font-semibold">קליטת חשבון חשמל</h1>
              </div>
              {!elecResult ? (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${elecLoading ? 'border-gray-200' : 'border-gray-300 hover:border-yellow-400 hover:bg-yellow-50'}`}>
                    <div className="text-4xl mb-3">⚡</div>
                    <div className="text-sm font-medium text-gray-700">{elecLoading ? 'מעלה...' : 'לחץ לבחירת קובץ BULLER (CSV)'}</div>
                    <input type="file" accept=".csv" className="hidden" disabled={elecLoading}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file || !muni) return;
                        setElecLoading(true); setError('');
                        try {
                          const fd = new FormData();
                          fd.append('file', file);
                          fd.append('municipality_id', muni.id);
                          const res = await fetch(`${API}/upload/electricity`, { method: 'POST', body: fd });
                          const data = await res.json();
                          if (!res.ok) throw new Error(data.detail || 'שגיאה');
                          setElecResult(data);
                        } catch (err: unknown) {
                          setError(err instanceof Error ? err.message : 'שגיאה');
                        } finally { setElecLoading(false); }
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
                      {!elecResult.balance_ok && <span className="text-red-600">⚠ לא מאוזן הפרש ₪{elecResult.balance_diff}</span>}
                    </div>
                  </div>
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50 border-b border-gray-100">
                        {['מספר חוזה','תיאור','קוד חשבון','סכום','סטטוס'].map(h =>
                          <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>
                        {elecResult.rows.map((row: any) => (
                          <tr key={`row-${row.row_num}-${row.contract}-${row.account}`} className={`border-b border-gray-50 ${row.status === 'missing_index' ? 'bg-red-50' : 'hover:bg-gray-50'}`}>
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
                  {/* Preview מפוצל */}
                  {elecResult.contracts && elecResult.contracts.length > 0 && (
                    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                      <div className="bg-gray-50 border-b border-gray-100 px-4 py-2 flex justify-between items-center">
                        <span className="text-xs font-medium text-gray-600">תצוגת פקודה מפוצלת</span>
                        <span className="text-xs text-gray-400">{elecResult.contracts.filter((c:any)=>c.status==='ok').length} חוזים תקינים</span>
                      </div>
                      <table className="w-full text-sm">
                        <thead><tr className="border-b border-gray-100">
                          {['חוזה','קוד חשבון','%','סכום','סטטוס'].map(h =>
                            <th key={h} className="text-right p-2 text-xs text-gray-400 font-medium">{h}</th>)}
                        </tr></thead>
                        <tbody>
                          {elecResult.contracts.map((c: any, ci: number) =>
                            c.status === 'ok' ? (
                              c.lines.map((line: any, li: number) => (
                                <tr key={`prev-${ci}-${li}-${line.account}`} className="border-b border-gray-50 hover:bg-gray-50">
                                  {li === 0 && (
                                    <td className="p-2 font-mono text-xs align-top" rowSpan={c.lines.length}>
                                      {c.contract}
                                      {c.lines.length > 1 && <div className="text-blue-500 text-xs">מפוצל ל-{c.lines.length}</div>}
                                    </td>
                                  )}
                                  <td className="p-2 font-mono text-xs">{line.account}</td>
                                  <td className="p-2 text-xs text-center text-blue-600">{line.percent ? `${line.percent}%` : '100%'}</td>
                                  <td className="p-2 text-xs font-medium">₪{line.amount?.toLocaleString()}</td>
                                  {li === 0 && (
                                    <td className="p-2 align-top" rowSpan={c.lines.length}>
                                      <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">✓</span>
                                    </td>
                                  )}
                                </tr>
                              ))
                            ) : (
                              <tr key={`missing-${ci}`} className="border-b border-gray-50 bg-red-50">
                                <td className="p-2 font-mono text-xs">{c.contract}</td>
                                <td className="p-2 text-xs text-gray-400" colSpan={3}>{c.error}</td>
                                <td className="p-2"><span className="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-600">חסר</span></td>
                              </tr>
                            )
                          )}
                        </tbody>
                      </table>
                      {/* שורת זכות */}
                      <div className="border-t border-gray-200 px-4 py-2 flex justify-between items-center bg-gray-50">
                        <span className="text-xs text-gray-500">זכות ספק חשמל ({elecVendorAccount})</span>
                        <span className="text-xs font-bold text-gray-700">₪{elecResult.sum_details?.toLocaleString()}</span>
                      </div>
                    </div>
                  )}

                  <div className="flex gap-3">
                    <button onClick={() => { setElecResult(null); setError(''); }}
                      className="border border-gray-200 rounded-lg px-4 py-2 text-sm">קובץ חדש</button>
                    <button
                      disabled={!elecResult.can_approve || elecLoading}
                      onClick={createElectricityJournal}
                      className="bg-green-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed">
                      {elecLoading ? 'שומר...' : elecResult.can_approve ? 'צור פקודת יומן ✓' : `לא ניתן לאשר (${elecResult.missing} חסרים)`}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══ ELECTRICITY INDEXES ══ */}
          {activeTab === 'electricity' && elecView === 'indexes' && (() => {
            // Group by contract
            const grouped: Record<string, any[]> = {};
            elecIndexes
              .filter((idx: any) => !elecIndexSearch ||
                idx.key_value?.includes(elecIndexSearch) ||
                idx.account_code?.includes(elecIndexSearch) ||
                (idx.connection_name||'').includes(elecIndexSearch))
              .forEach((idx: any) => {
                if (!grouped[idx.key_value]) grouped[idx.key_value] = [];
                grouped[idx.key_value].push(idx);
              });

            const contracts = Object.keys(grouped).sort();
            const invalidContracts = contracts.filter(c => {
              const total = grouped[c].reduce((s:number,r:any) => s + parseFloat(r.description||'100'), 0);
              return Math.abs(total - 100) > 0.01;
            });

            // Split modal state
            const openSplitModal = (contract: string) => {
              const rows = grouped[contract];
              setSplitModal({
                open: true,
                contract,
                connectionName: rows[0]?.connection_name || '',
                splits: rows.map((r:any) => ({ account_code: r.account_code, percent: parseFloat(r.description||'100') })),
                saving: false,
                error: '',
              });
            };

            const saveSplit = async () => {
              if (!splitModal || !muni) return;
              // ולידציה בצד לקוח
              const total = splitModal.splits.reduce((s:number, r:any) => s + (parseFloat(r.percent)||0), 0);
              if (Math.abs(total - 100) > 0.01) {
                setSplitModal(p => p ? {...p, error: `סכום האחוזים = ${total.toFixed(2)}%, חייב להיות 100%`} : p);
                return;
              }
              for (const s of splitModal.splits) {
                if (!s.account_code.trim()) {
                  setSplitModal(p => p ? {...p, error: 'קוד חשבון ריק'} : p);
                  return;
                }
                if ((parseFloat(s.percent)||0) <= 0) {
                  setSplitModal(p => p ? {...p, error: 'אחוז חייב להיות גדול מ-0'} : p);
                  return;
                }
              }
              const accounts = splitModal.splits.map((s:any) => s.account_code.trim());
              if (new Set(accounts).size !== accounts.length) {
                setSplitModal(p => p ? {...p, error: 'קוד חשבון כפול'} : p);
                return;
              }
              setSplitModal(p => p ? {...p, saving: true, error: ''} : p);
              try {
                await apiFetch('/indexes/split', {
                  method: 'PUT',
                  headers: {'Content-Type':'application/json'},
                  body: JSON.stringify({
                    municipality_id: muni.id,
                    template_id: '5594291d-2a5f-4b6c-846a-bed1290388b1',
                    key_value: splitModal.contract,
                    connection_name: splitModal.connectionName,
                    splits: splitModal.splits.map((s:any) => ({
                      account_code: s.account_code.trim(),
                      percent: parseFloat(s.percent)
                    }))
                  })
                });
                // רענן אינדקסים
                const fresh = await apiFetch(`/indexes?municipality_id=${muni.id}&template_id=5594291d-2a5f-4b6c-846a-bed1290388b1&limit=500`);
                setElecIndexes(Array.isArray(fresh) ? fresh : []);
                setSplitModal(null);
              } catch(e:any) {
                setSplitModal(p => p ? {...p, saving: false, error: e.message || 'שגיאה בשמירה'} : p);
              }
            };

            return (
              <div>
                {/* Split Modal */}
                {splitModal?.open && (
                  <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={e => { if(e.target===e.currentTarget) setSplitModal(null); }}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 mx-4" dir="rtl">
                      <div className="flex justify-between items-center mb-4">
                        <h2 className="font-semibold text-base">פיצול חוזה {splitModal.contract}</h2>
                        <button onClick={() => setSplitModal(null)} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
                      </div>

                      {/* שם חיבור */}
                      <div className="mb-4">
                        <label className="text-xs text-gray-500 block mb-1">שם חיבור (לפקודה)</label>
                        <input value={splitModal.connectionName}
                          onChange={e => setSplitModal(p => p ? {...p, connectionName: e.target.value} : p)}
                          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full"
                          placeholder="שם החיבור..." />
                      </div>

                      {/* שורות פיצול */}
                      <div className="mb-2">
                        <div className="grid grid-cols-12 gap-2 text-xs text-gray-400 mb-1 px-1">
                          <span className="col-span-7">קוד חשבון</span>
                          <span className="col-span-3">%</span>
                          <span className="col-span-2"></span>
                        </div>
                        {splitModal.splits.map((s:any, i:number) => (
                          <div key={i} className="grid grid-cols-12 gap-2 mb-2 items-center">
                            <input value={s.account_code} dir="ltr"
                              onChange={e => setSplitModal(p => { if(!p) return p; const sp=[...p.splits]; sp[i]={...sp[i],account_code:e.target.value}; return {...p,splits:sp}; })}
                              className="col-span-7 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                              placeholder="קוד חשבון" />
                            <input value={s.percent} type="number" min="0.01" max="100" step="0.01"
                              onChange={e => setSplitModal(p => { if(!p) return p; const sp=[...p.splits]; sp[i]={...sp[i],percent:e.target.value}; return {...p,splits:sp}; })}
                              className="col-span-3 border border-gray-200 rounded-lg px-3 py-2 text-sm text-center" />
                            <button onClick={() => setSplitModal(p => { if(!p) return p; const sp=p.splits.filter((_:any,j:number)=>j!==i); return {...p,splits:sp}; })}
                              className="col-span-2 text-red-400 hover:text-red-600 text-center text-lg" disabled={splitModal.splits.length<=1}>✕</button>
                          </div>
                        ))}
                      </div>

                      {/* סה"כ אחוזים */}
                      {(() => {
                        const total = splitModal.splits.reduce((s:number,r:any) => s+(parseFloat(r.percent)||0), 0);
                        const ok = Math.abs(total-100) <= 0.01;
                        return (
                          <div className={`text-sm font-medium mb-3 px-1 ${ok ? 'text-green-600' : 'text-red-500'}`}>
                            סה"כ: {total.toFixed(2)}% {ok ? '✓' : `(חסר ${(100-total).toFixed(2)}%)`}
                          </div>
                        );
                      })()}

                      <button onClick={() => setSplitModal(p => p ? {...p, splits:[...p.splits,{account_code:'',percent:''}]} : p)}
                        className="text-sm text-blue-600 hover:underline mb-4">+ הוסף פיצול</button>

                      {splitModal.error && <div className="text-red-500 text-sm mb-3 bg-red-50 rounded-lg p-2">{splitModal.error}</div>}

                      <div className="flex gap-2 justify-end">
                        <button onClick={() => setSplitModal(null)} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">ביטול</button>
                        <button onClick={saveSplit} disabled={splitModal.saving}
                          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                          {splitModal.saving ? 'שומר...' : 'שמור פיצול'}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex justify-between items-center mb-4">
                  <div>
                    <h1 className="text-base font-semibold">אינדקסי חשמל</h1>
                    <p className="text-xs text-gray-500">{muni?.name} · {contracts.length} חוזים · {elecIndexes.length} רשומות
                      {invalidContracts.length > 0 && <span className="text-red-500 mr-2"> ⚠ {invalidContracts.length} חוזים לא מסתכמים ל-100%</span>}
                    </p>
                  </div>
                  <input value={elecIndexSearch} onChange={e => setElecIndexSearch(e.target.value)}
                    placeholder="חיפוש לפי חוזה, חשבון, שם..." className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64" />
                </div>

                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead><tr className="bg-gray-50 border-b border-gray-100">
                      {['מספר חוזה','שם חיבור','קוד חשבון','%','פיצול',''].map(h =>
                        <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                    </tr></thead>
                    <tbody>
                      {contracts.map(contract => {
                        const rows = grouped[contract];
                        const totalPct = rows.reduce((s:number,r:any) => s + parseFloat(r.description||'100'), 0);
                        const isInvalid = Math.abs(totalPct - 100) > 0.01;
                        const isSplit = rows.length > 1;
                        return rows.map((idx: any, ri: number) => (
                          <tr key={idx.id} className={`border-b border-gray-50 hover:bg-gray-50 ${isInvalid ? 'bg-red-50' : ''}`}>
                            {ri === 0 && (
                              <td className="p-3 font-mono text-xs align-top" rowSpan={rows.length}>
                                {contract}
                                {isInvalid && <div className="text-red-500 text-xs mt-0.5">⚠ {totalPct.toFixed(0)}%</div>}
                                {isSplit && <div className="text-blue-500 text-xs mt-0.5">מפוצל ל-{rows.length}</div>}
                              </td>
                            )}
                            <td className="p-3 text-xs text-gray-500 max-w-xs truncate">{idx.connection_name || '—'}</td>
                            <td className="p-3 font-mono text-xs">{idx.account_code}</td>
                            <td className="p-3 text-xs font-medium text-center">
                              <span className={isInvalid ? 'text-red-500' : isSplit ? 'text-blue-600' : 'text-gray-700'}>
                                {parseFloat(idx.description||'100').toFixed(idx.description?.includes('.') ? 2 : 0)}%
                              </span>
                            </td>
                            {ri === 0 && (
                              <td className="p-3 align-top" rowSpan={rows.length}>
                                <button onClick={() => openSplitModal(contract)}
                                  className="text-xs text-blue-600 border border-blue-200 rounded-lg px-2 py-1 hover:bg-blue-50 whitespace-nowrap">
                                  ✂ ערוך פיצול
                                </button>
                              </td>
                            )}
                            <td className="p-3 text-xs text-red-400 cursor-pointer hover:text-red-600 align-top"
                              onClick={async () => {
                                if (!confirm('מחק שורה זו?')) return;
                                await apiFetch(`/indexes/${idx.id}`, { method: 'DELETE' });
                                setElecIndexes(p => p.filter((r:any) => r.id !== idx.id));
                              }}>מחק</td>
                          </tr>
                        ));
                      })}
                      {contracts.length === 0 && (
                        <tr><td colSpan={6} className="p-8 text-center text-sm text-gray-400">אין אינדקסים</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}

          {/* ── WELFARE ── */}
          {activeTab === 'welfare' && welfareView === 'home' && (
            <WelfareDashboard muni={muni} onNewIntake={() => { setWelfareView('intake'); setWelfareResult(null); }} />
          )}

          {activeTab === 'welfare' && welfareView === 'intake' && (
            <div>
              <div className="flex justify-between mb-4">
                <h1 className="text-base font-semibold">קליטת דוח רווחה</h1>
              </div>
              {!welfareResult ? (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <label className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center cursor-pointer ${welfareLoading ? 'border-gray-200' : 'border-gray-300 hover:border-green-400 hover:bg-green-50'}`}>
                    <div className="text-4xl mb-3">🤝</div>
                    <div className="text-sm font-medium text-gray-700">{welfareLoading ? 'מעלה...' : 'לחץ לבחירת קובץ דוח התחשבנות רווחה (Excel)'}</div>
                    <div className="text-xs text-gray-400 mt-1">קובץ Tamar_revaha.xlsx או דומה</div>
                    <input type="file" accept=".xlsx,.xls" className="hidden" disabled={welfareLoading}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file || !muni) return;
                        setWelfareLoading(true); setError('');
                        try {
                          const fd = new FormData();
                          fd.append('file', file);
                          fd.append('municipality_id', muni.id);
                          const res = await fetch(`${API}/upload/welfare`, { method: 'POST', body: fd });
                          const data = await res.json();
                          if (!res.ok) throw new Error(data.detail || 'שגיאה');
                          setWelfareResult(data);
                        } catch (err: unknown) {
                          setError(err instanceof Error ? err.message : 'שגיאה');
                        } finally { setWelfareLoading(false); }
                      }} />
                  </label>
                </div>
              ) : (
                <div>
                  <div className={`rounded-lg p-3 mb-4 text-sm ${welfareResult.can_approve ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-amber-50 border border-amber-200 text-amber-700'}`}>
                    <div className="font-medium mb-1">{welfareResult.municipality} · {welfareResult.period}</div>
                    <div className="flex gap-4 text-xs">
                      <span>שורות: {welfareResult.total_rows}</span>
                      <span>תואמות: {welfareResult.matched}</span>
                      {welfareResult.missing > 0 && <span className="text-red-600 font-medium">חסרות: {welfareResult.missing}</span>}
                      <span>חובה: ₪{welfareResult.total_debit?.toLocaleString()}</span>
                      <span>זכות: ₪{welfareResult.total_credit?.toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50 border-b border-gray-100">
                        {['סעיף','שם','צד','קוד חשבון','סכום','סטטוס'].map(h =>
                          <th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>
                        {welfareResult.rows.filter((r:any) => r.amount > 0 || r.status === 'missing_index').map((row: any, ri: number) => (
                          <tr key={`${row.semel}-${ri}`} className={`border-b border-gray-50 ${row.status === 'missing_index' ? 'bg-red-50' : 'hover:bg-gray-50'}`}>
                            <td className="p-3 font-mono text-xs">{row.semel}</td>
                            <td className="p-3 text-xs text-gray-600 max-w-xs truncate">{row.name}</td>
                            <td className="p-3">
                              <span className={`px-2 py-0.5 rounded-full text-xs ${row.side === 'debit' ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'}`}>
                                {row.side === 'debit' ? 'חובה' : 'זכות'}
                              </span>
                            </td>
                            <td className="p-3 font-mono text-xs">{row.account || '—'}</td>
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
                    <button onClick={() => { setWelfareResult(null); setError(''); }}
                      className="border border-gray-200 rounded-lg px-4 py-2 text-sm">קובץ חדש</button>
                    <button
                      disabled={!welfareResult.can_approve || welfareLoading}
                      onClick={async () => {
                        if (!muni || !welfareResult) return;
                        setWelfareLoading(true); setError('');
                        try {
                          const lines = welfareResult.rows
                            .filter((r:any) => r.status === 'ok' && r.amount > 0)
                            .map((r:any) => ({
                              semel:       r.semel,
                              account:     r.account,
                              amount:      r.amount,
                              side:        r.side,
                              description: r.description,
                            }));
                          const res = await apiFetch('/upload/welfare/approve', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              municipality_id: muni.id,
                              period:          String(welfareResult.year || new Date().getFullYear()),
                              month:           welfareResult.month,
                              year:            welfareResult.year || new Date().getFullYear(),
                              source_file:     welfareResult.filename,
                              lines,
                            }),
                          });
                          const diff = res.ministry_diff ? ` | חו"ז: ₪${Math.abs(res.ministry_diff).toLocaleString()}` : '';
                          alert(`פקודה נוצרה! ${res.reference_num}${diff}`);
                          setWelfareResult(null);
                          setWelfareView('home');
                        } catch (err: unknown) {
                          setError(err instanceof Error ? err.message : 'שגיאה');
                        } finally { setWelfareLoading(false); }
                      }}
                      className="bg-green-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed">
                      {welfareLoading ? 'שומר...' : welfareResult.can_approve ? 'צור פקודת יומן ✓' : `לא ניתן לאשר (${welfareResult.missing} חסרים)`}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── COMING SOON ── */}
          {activeTab !== 'bezeq' && activeTab !== 'electricity' && activeTab !== 'welfare' && (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <div className="text-5xl mb-4">{CATEGORIES.find(c=>c.id===activeTab)?.icon}</div>
              <h2 className="text-lg font-semibold text-gray-700 mb-2">
                {CATEGORIES.find(c=>c.id===activeTab)?.label} – בקרוב
              </h2>
              <p className="text-sm text-gray-400">מודול זה יתווסף בגרסה הבאה</p>
            </div>
          )}

          {/* ══ BEZEQ HOME ══ */}
          {activeTab === 'bezeq' && bezeqView === 'home' && (
            <div>
              <div className="flex justify-between items-center mb-5">
                <div>
                  <h1 className="text-base font-semibold text-gray-900">בזק – דשבורד</h1>
                  <p className="text-xs text-gray-500">{muni?.name}</p>
                </div>
                <button onClick={() => { setStep(1); setUploadResult(null); setBezeqView('intake'); }}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">+ קליטת חשבון</button>
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
                {entries.length === 0
                  ? <div className="p-8 text-center text-sm text-gray-400">אין פקודות עדיין</div>
                  : <table className="w-full text-sm"><thead><tr className="border-b border-gray-100">
                      {['מספר','תקופה','סכום','סטטוס',''].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                    </tr></thead><tbody>
                    {entries.filter((e:any)=>e.template_key==='bezeq'||(!e.template_key&&e.template_name!=='חשמל')).map(e=>(
                      <tr key={e.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="p-3 font-mono text-xs">{e.reference_num}</td>
                        <td className="p-3 text-xs">{e.period}</td>
                        <td className="p-3 font-medium text-xs">₪{(e.total_amount||0).toLocaleString()}</td>
                        <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs ${e.status==='draft'?'bg-blue-100 text-blue-700':'bg-green-100 text-green-700'}`}>{e.status==='draft'?'טיוטה':'אושר'}</span></td>
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

          {/* ══ BEZEQ INTAKE ══ */}
          {activeTab === 'bezeq' && bezeqView === 'intake' && (
            <div>
              <div className="flex justify-between mb-4">
                <h1 className="text-base font-semibold">קליטת חשבון בזק</h1>
                <span className="text-xs text-gray-400">שלב {step}/3</span>
              </div>
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
                    <div className="text-xs text-gray-400 mt-1">CSV או Excel</div>
                    <input type="file" accept=".csv,.xlsx,.xls" onChange={handleFileUpload} className="hidden" disabled={loading}/>
                  </label>
                </div>
              )}

              {step===2 && uploadResult && (
                <div>
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4 text-sm text-green-700">
                    נטענו {uploadResult.total_rows} שורות · {uploadResult.matched} תואמות · {uploadResult.missing} חסרות
                    {uploadResult.invoice_total > 0 && <span className="mr-3">· חשבונית: ₪{uploadResult.invoice_total.toLocaleString()} {uploadResult.balance_ok ? '✓' : `⚠ הפרש ₪${uploadResult.balance_diff}`}</span>}
                  </div>
                  <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-4">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-gray-50 border-b border-gray-100">
                        {['מספר מנוי','שם חיבור','סכום','קוד חשבון','סטטוס'].map(h=><th key={h} className="text-right p-3 text-xs text-gray-500 font-medium">{h}</th>)}
                      </tr></thead>
                      <tbody>{uploadResult.rows.map(row=>(
                        <tr key={row.row_num} className={`border-b border-gray-50 ${!row.has_index?'bg-amber-50':''}`}>
                          <td className="p-3 font-mono text-xs">{row.phone}</td>
                          <td className="p-3 text-xs text-gray-600">{row.description || (row.name && row.name!=='nan' ? row.name : '—')}</td>
                          <td className="p-3 text-xs font-medium">₪{row.amount.toLocaleString()}</td>
                          <td className="p-3">{row.has_index?<code className="text-xs">{row.account}</code>:<input placeholder="קוד..." className="border border-amber-300 rounded px-2 py-1 text-xs w-24" onChange={e=>setIndexMap(m=>({...m,[row.row_num]:e.target.value}))}/>}</td>
                          <td className="p-3"><span className={`px-2 py-0.5 rounded-full text-xs ${row.has_index?'bg-green-100 text-green-700':'bg-amber-100 text-amber-700'}`}>{row.has_index?'קיים':'חסר'}</span></td>
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
                      {[['רשות',muni?.name],['סוג','בזק'],['תקופה',period],
                        ['שורות',uploadResult.total_rows],['סה"כ','₪'+uploadResult.rows.reduce((s,r)=>s+r.amount,0).toLocaleString()],
                        ['חשבונית',uploadResult.invoice_num||'—']].map(([l,v])=>(
                        <div key={l as string} className="bg-gray-50 rounded-lg p-3">
                          <div className="text-xs text-gray-500 mb-1">{l}</div>
                          <div className="text-sm font-medium text-gray-900">{v}</div>
                        </div>
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

          {/* ══ BEZEQ SETTINGS ══ */}
          {activeTab === 'bezeq' && bezeqView === 'settings' && (
            <div className="max-w-lg">
              <h1 className="text-base font-semibold mb-1">הגדרות בזק</h1>
              <p className="text-xs text-gray-500 mb-6">{muni?.name}</p>
              {settingsSaved && <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg p-3 mb-4">✓ נשמר בהצלחה</div>}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="mb-5">
                  <label className="block text-sm font-medium text-gray-700 mb-1">חשבון ספק בזק (זכות)</label>
                  <p className="text-xs text-gray-500 mb-2">מספר החשבון שיירשם בשורת הזכות בכל פקודת יומן</p>
                  <input
                    value={settings.vendor_account}
                    onChange={e => setSettings(s => ({...s, vendor_account: e.target.value}))}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
                    placeholder="6000203000"
                  />
                </div>
                <button onClick={saveSettings} disabled={loading}
                  className="bg-blue-600 text-white rounded-lg px-6 py-2 text-sm disabled:opacity-50">
                  {loading ? 'שומר...' : 'שמור הגדרות'}
                </button>
              </div>
            </div>
          )}

          {/* ══ BEZEQ INDEXES ══ */}
          {activeTab === 'bezeq' && bezeqView === 'indexes' && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h1 className="text-base font-semibold">אינדקסי בזק</h1>
                  <p className="text-xs text-gray-500">{muni?.name} · {indexes.length} רשומות</p>
                </div>
              </div>
              <div className="flex gap-3 mb-4">
                <input value={indexSearch} onChange={e=>setIndexSearch(e.target.value)}
                  placeholder="חיפוש לפי טלפון, חשבון או שם חיבור..."
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
                  onKeyDown={e=>e.key==='Enter'&&loadIndexes()}/>
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
                        <td className="p-3">{editingIndex===idx.id
                          ?<input value={editVals.account_code} onChange={e=>setEditVals(v=>({...v,account_code:e.target.value}))} className="border border-blue-300 rounded px-2 py-1 text-xs w-28"/>
                          :<code className="text-xs">{idx.account_code}</code>}</td>
                        <td className="p-3 text-xs">{editingIndex===idx.id
                          ?<input value={editVals.connection_name} onChange={e=>setEditVals(v=>({...v,connection_name:e.target.value}))} className="border border-blue-300 rounded px-2 py-1 text-xs w-48"/>
                          :<span className={idx.connection_name?'text-gray-700':'text-gray-400'}>{idx.connection_name||'—'}</span>}</td>
                        <td className="p-3">
                          {editingIndex===idx.id
                            ?<div className="flex gap-2">
                              <button onClick={()=>saveIndexEdit(idx.id)} className="text-xs text-green-600 font-medium hover:underline">שמור</button>
                              <button onClick={()=>setEditingIndex(null)} className="text-xs text-gray-400 hover:underline">ביטול</button>
                            </div>
                            :<div className="flex gap-3">
                              <button onClick={()=>{setEditingIndex(idx.id);setEditVals({account_code:idx.account_code,connection_name:idx.connection_name||''});}} className="text-xs text-blue-600 hover:underline">עריכה</button>
                              <button onClick={()=>deleteIndex(idx.id,idx.key_value)} className="text-xs text-red-500 hover:underline">מחק</button>
                            </div>}
                        </td>
                      </tr>
                    ))}
                    {!loading&&indexes.length===0&&<tr><td colSpan={4} className="p-8 text-center text-sm text-gray-400">לחץ חפש לטעינת אינדקסים</td></tr>}
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
