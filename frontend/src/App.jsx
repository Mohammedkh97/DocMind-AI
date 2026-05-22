import React, { useState, useEffect } from 'react';
import { ShieldCheck, ShieldAlert, Cpu, FileText, ArrowLeft, RefreshCw, Power } from 'lucide-react';
import UploadZone from './components/UploadZone';
import ComplianceDial from './components/ComplianceDial';
import DataViewer from './components/DataViewer';
import AuditCenter from './components/AuditCenter';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [status, setStatus] = useState('idle'); // idle | uploading | extracting | scoring | success | error
  const [errorMessage, setErrorMessage] = useState(null);
  
  // Data State
  const [file, setFile] = useState(null);
  const [extractionData, setExtractionData] = useState(null);
  const [complianceData, setComplianceData] = useState(null);
  
  // Connection Status
  const [backendConnected, setBackendConnected] = useState(null); // null (checking) | true | false

  // Check backend health on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/health`);
        if (res.ok) {
          setBackendConnected(true);
        } else {
          setBackendConnected(false);
        }
      } catch (err) {
        setBackendConnected(false);
      }
    };
    checkConnection();
  }, []);

  const handleFileSelected = async (selectedFile) => {
    setFile(selectedFile);
    setStatus('uploading');
    setErrorMessage(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      // Step 1: Upload and Extract (VLM + OCR)
      setStatus('extracting');
      const extractResponse = await fetch(`${API_BASE_URL}/extract`, {
        method: 'POST',
        body: formData,
      });

      if (!extractResponse.ok) {
        let errorData = {};
        try {
          errorData = await extractResponse.json();
        } catch {}
        throw new Error(errorData.detail?.message || `Extraction failed with status ${extractResponse.status}`);
      }

      const extracted = await extractResponse.json();
      setExtractionData(extracted);

      // Step 2: Scoring Compliance
      setStatus('scoring');
      const complianceResponse = await fetch(`${API_BASE_URL}/compliance-score`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(extracted),
      });

      if (!complianceResponse.ok) {
        let errorData = {};
        try {
          errorData = await complianceResponse.json();
        } catch {}
        throw new Error(errorData.detail?.message || `Compliance scoring failed with status ${complianceResponse.status}`);
      }

      const compliance = await complianceResponse.json();
      setComplianceData(compliance);
      setStatus('success');
    } catch (err) {
      console.error("Pipeline error:", err);
      setStatus('error');
      setErrorMessage(err.message || "An unexpected error occurred during processing.");
    }
  };

  const handleReset = () => {
    setStatus('idle');
    setFile(null);
    setExtractionData(null);
    setComplianceData(null);
    setErrorMessage(null);
  };

  return (
    <div className="container" style={{ display: 'flex', flexDirection: 'column', gap: '2rem', minHeight: '90vh' }}>
      {/* Top Header Navigation */}
      <header className="glass-panel" style={{ padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Cpu className="text-cyan animate-pulse-slow" style={{ color: 'var(--accent-cyan)' }} size={28} />
          <div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: '800', background: 'linear-gradient(135deg, #fff 30%, var(--accent-cyan))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              DocMind AI
            </h1>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Document Intelligence Hub
            </span>
          </div>
        </div>

        {/* Backend Connection Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
          <Power size={12} style={{ color: backendConnected === true ? 'var(--status-success)' : backendConnected === false ? 'var(--status-danger)' : 'var(--text-muted)' }} />
          <span style={{ color: 'var(--text-secondary)' }}>Backend:</span>
          {backendConnected === true && (
            <span className="badge badge-success" style={{ padding: '0.15rem 0.5rem', textTransform: 'none' }}>Connected</span>
          )}
          {backendConnected === false && (
            <span className="badge badge-danger" style={{ padding: '0.15rem 0.5rem', textTransform: 'none' }}>Disconnected</span>
          )}
          {backendConnected === null && (
            <span className="badge badge-info" style={{ padding: '0.15rem 0.5rem', textTransform: 'none' }}>Checking...</span>
          )}
        </div>
      </header>

      {/* Main View Area */}
      <main style={{ flex: '1', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        {status !== 'success' ? (
          <UploadZone 
            status={status} 
            errorMessage={errorMessage} 
            onFileSelected={handleFileSelected} 
            onReset={handleReset} 
          />
        ) : (
          /* Dashboard Layout */
          <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Top Back Action Bar */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <button 
                onClick={handleReset} 
                style={{ 
                  background: 'rgba(255,255,255,0.03)', 
                  border: '1px solid var(--border-muted)', 
                  color: 'var(--text-primary)', 
                  padding: '0.5rem 1.25rem', 
                  borderRadius: '9999px', 
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontWeight: '600',
                  fontSize: '0.85rem',
                  transition: 'all var(--transition-fast)'
                }}
                className="btn-back"
              >
                <ArrowLeft size={16} />
                <span>Upload Another Document</span>
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                <FileText size={16} style={{ color: 'var(--accent-cyan)' }} />
                <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{file?.name}</span>
                <span style={{ color: 'var(--text-muted)' }}>
                  ({(file?.size / (1024 * 1024)).toFixed(2)} MB)
                </span>
              </div>
            </div>

            {/* Grid Area: Score Card & Detailed Data */}
            <div className="grid-cols-2">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                <ComplianceDial complianceData={complianceData} />
                <AuditCenter complianceData={complianceData} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <DataViewer extractionData={extractionData} />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{ textAlign: 'center', padding: '1rem', borderTop: '1px solid var(--border-muted)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        DocMind AI &copy; 2026 • Hybrid Document Compliance Audit Engine
      </footer>
    </div>
  );
}

export default App;
