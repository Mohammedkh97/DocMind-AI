import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader2, AlertTriangle, CheckCircle, Circle } from 'lucide-react';
import './UploadZone.css';

export default function UploadZone({ status, errorMessage, onFileSelected, onReset }) {
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === "application/pdf" || file.name.endsWith(".pdf")) {
        onFileSelected(file);
      }
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelected(e.target.files[0]);
    }
  };

  const onButtonClick = (e) => {
    e.stopPropagation();
    fileInputRef.current.click();
  };

  // Stepper helper
  const getStepStatus = (stepName) => {
    if (status === 'error') return 'pending';
    
    const steps = ['uploading', 'extracting', 'scoring', 'success'];
    const currentIdx = steps.indexOf(status);
    const targetIdx = steps.indexOf(stepName);

    if (currentIdx > targetIdx) return 'completed';
    if (currentIdx === targetIdx) return 'active';
    return 'pending';
  };

  const renderStepIcon = (stepStatus) => {
    switch (stepStatus) {
      case 'completed':
        return <CheckCircle className="step-icon text-success" size={18} style={{ color: 'var(--status-success)' }} />;
      case 'active':
        return <Loader2 className="step-icon animate-spin" size={18} style={{ color: 'var(--accent-cyan)' }} />;
      case 'pending':
      default:
        return <Circle className="step-icon text-muted" size={18} style={{ color: 'var(--text-muted)' }} />;
    }
  };

  const isProcessing = ['uploading', 'extracting', 'scoring'].includes(status);

  if (isProcessing) {
    return (
      <div className="glass-panel loading-box animate-fade-in" style={{ padding: '3rem 2rem' }}>
        <div className="pulse-spinner">
          <Loader2 size={36} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        </div>
        <h3 className="upload-title" style={{ marginBottom: '1.5rem' }}>Analyzing Document</h3>
        <div className="step-list">
          <div className={`step-item ${getStepStatus('uploading')}`}>
            {renderStepIcon(getStepStatus('uploading'))}
            <span>Uploading PDF shipping documents</span>
          </div>
          <div className={`step-item ${getStepStatus('extracting')}`}>
            {renderStepIcon(getStepStatus('extracting'))}
            <span>Running VLM extraction (Gemini 2.5 Flash)</span>
          </div>
          <div className={`step-item ${getStepStatus('scoring')}`}>
            {renderStepIcon(getStepStatus('scoring'))}
            <span>Evaluating deterministic compliance rules</span>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="glass-panel error-box animate-fade-in" style={{ margin: '4rem auto' }}>
        <div className="error-title">
          <AlertTriangle size={24} />
          <span>Extraction Failed</span>
        </div>
        <p className="error-desc">{errorMessage || 'An unknown error occurred while processing your document.'}</p>
        <button className="retry-btn" onClick={onReset}>
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div 
      className={`glass-panel upload-container animate-fade-in ${dragActive ? 'drag-active' : ''}`}
      onDragEnter={handleDrag}
      onDragOver={handleDrag}
      onDragLeave={handleDrag}
      onDrop={handleDrop}
      onClick={onButtonClick}
    >
      <input 
        ref={fileInputRef}
        type="file" 
        className="file-input" 
        accept=".pdf"
        onChange={handleFileInput}
      />
      <div className="icon-wrapper">
        <UploadCloud size={64} strokeWidth={1.5} />
      </div>
      <h3 className="upload-title">Upload Shipping Documents</h3>
      <p className="upload-subtitle">Drag & drop your logistics PDF (Invoice & Packing List) here, or click to browse</p>
      <button type="button" className="select-btn">
        Select PDF File
      </button>
      <div style={{ marginTop: '2rem', display: 'flex', gap: '1.5rem', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <FileText size={14} />
          <span>Commercial Invoice</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <FileText size={14} />
          <span>Packing List</span>
        </div>
      </div>
    </div>
  );
}
