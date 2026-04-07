import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { generateReport } from '../../api/client';
import { useAppStore } from '../../store/appStore';
import './ReportView.css';

export default function ReportView() {
  const { sessionId } = useAppStore();
  const [tripName, setTripName] = useState('Trip Report');
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'preview' | 'raw'>('preview');

  async function handleGenerate() {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await generateReport(sessionId, tripName, ['markdown', 'pdf']);
      setMarkdown(result.markdown);
      setPdfBase64(result.pdf_base64);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Report generation failed');
    } finally {
      setLoading(false);
    }
  }

  function downloadPdf() {
    if (!pdfBase64) return;
    const bytes = atob(pdfBase64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([arr], { type: 'application/pdf' }));
    const a = document.createElement('a');
    a.href = url; a.download = `${tripName}.pdf`; a.click();
    URL.revokeObjectURL(url);
  }

  function downloadMd() {
    if (!markdown) return;
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown' }));
    const a = document.createElement('a');
    a.href = url; a.download = `${tripName}.md`; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="report-view">
      <div className="report-toolbar">
        <div className="report-name-row">
          <span className="field-label">TRIP NAME</span>
          <input
            type="text"
            value={tripName}
            onChange={e => setTripName(e.target.value)}
            placeholder="e.g. Greece 2024"
          />
        </div>

        <button className="btn btn-fill" onClick={handleGenerate} disabled={loading}>
          {loading ? <span className="spinner spinner-white" /> : '↓'}
          {loading ? 'Generating…' : 'Generate Report'}
        </button>

        {markdown && (
          <div className="report-downloads">
            <button className="btn btn-sm" onClick={downloadMd}>↓ .md</button>
            <button className="btn btn-sm btn-fill" onClick={downloadPdf}>↓ .pdf</button>
          </div>
        )}

        {markdown && (
          <div className="report-view-toggle">
            <button className={`btn btn-sm ${view === 'preview' ? 'btn-fill' : ''}`} onClick={() => setView('preview')}>Preview</button>
            <button className={`btn btn-sm ${view === 'raw' ? 'btn-fill' : ''}`} onClick={() => setView('raw')}>Raw</button>
          </div>
        )}
      </div>

      {error && <div className="report-error">{error}</div>}

      {markdown && (
        <div className="report-content">
          {view === 'preview' ? (
            <div className="md-preview">
              <ReactMarkdown>{markdown}</ReactMarkdown>
            </div>
          ) : (
            <pre className="md-raw">{markdown}</pre>
          )}
        </div>
      )}

      {!markdown && !loading && (
        <div className="report-empty">
          <p>Enter a trip name and click <strong>Generate Report</strong>.</p>
        </div>
      )}
    </div>
  );
}
